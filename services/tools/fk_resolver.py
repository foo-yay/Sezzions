"""Foreign key resolution service for CSV imports."""

from typing import Dict, List, Any, Optional, Tuple
import unicodedata
from .schemas import EntitySchema, CSVFieldDef
from repositories.database import DatabaseManager


def normalize_name(name: str) -> str:
    """Normalize a name for case-insensitive, punctuation-insensitive comparison.
    
    Strategy: Remove all punctuation and normalize to lowercase ASCII.
    This handles all quote variations by simply removing them.
    """
    # Unicode NFKD normalization (compatibility decomposition)
    normalized = unicodedata.normalize('NFKD', name)
    
    # Encode to ASCII, ignoring non-ASCII chars
    normalized = normalized.encode('ascii', 'ignore').decode('ascii')
    
    # Remove all punctuation and special characters, keep only alphanumeric and spaces
    import re
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    
    # Lowercase
    normalized = normalized.lower()
    
    return normalized


class FKResolutionResult:
    """Result of foreign key resolution."""
    
    def __init__(self):
        self.resolved_id: Optional[int] = None
        self.error: Optional[str] = None
        self.ambiguous_matches: List[Dict[str, Any]] = []
    
    @property
    def success(self) -> bool:
        """Whether resolution was successful."""
        return self.resolved_id is not None and self.error is None


class ForeignKeyResolver:
    """Resolves foreign key names to IDs for CSV imports.
    
    Builds lookup caches for all FK tables referenced in a schema,
    then resolves CSV values (names) to database IDs.
    """
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def clear(self) -> None:
        """Clear all cached FK lookups. Useful for tests or when database changes."""
        self._cache.clear()
    
    def load_cache_for_schema(self, schema: EntitySchema) -> None:
        """Load FK lookup caches for all foreign keys in schema.
        
        Args:
            schema: Entity schema to scan for foreign keys
        """
        for field in schema.fields:
            if field.foreign_key:
                self._load_fk_table(field.foreign_key.table)
    
    def _load_fk_table(self, table_name: str) -> None:
        """Load foreign key lookup data for a table.
        
        Creates two lookups:
        - {table}_by_id: {id: name}
        - {table}_by_name: {name: [list of matching records]}
        """
        # Query all records from FK table
        query = f"SELECT * FROM {table_name}"
        
        try:
            rows = self.db.fetch_all(query)
        except Exception as e:
            # Table might not exist yet
            rows = []
        
        # Build ID lookup
        by_id = {}
        by_name = {}
        
        for row in rows:
            record_id = row['id']
            # Try common name columns
            if 'name' in row.keys():
                name = row['name']
            elif 'title' in row.keys():
                name = row['title']
            else:
                name = str(record_id)
            
            by_id[record_id] = name
            
            # Normalize name for lookup (handles quotes, case, whitespace)
            normalized_name = normalize_name(name)
            
            # For name lookup, store list of matching records (for ambiguity detection)
            # Use normalized name as key
            if normalized_name not in by_name:
                by_name[normalized_name] = []
            by_name[normalized_name].append(row)
        
        self._cache[f"{table_name}_by_id"] = by_id
        self._cache[f"{table_name}_by_name"] = by_name
    
    def resolve_fk(
        self,
        value: Any,
        fk_table: str,
        allow_create: bool = False,
        scope: Optional[Dict[str, Any]] = None
    ) -> FKResolutionResult:
        """Resolve a foreign key value (name or ID) to database ID.
        
        Args:
            value: FK value from CSV (name or ID)
            fk_table: Target FK table name
            allow_create: Whether to allow creation of new FK records (future)
            scope: Optional scope filters (e.g., {"user_id": 5} to filter by user)
        
        Returns:
            FKResolutionResult with resolved ID or error
        """
        result = FKResolutionResult()
        
        if value is None or value == '':
            # Empty FK (valid if optional)
            return result
        
        # Ensure cache is loaded
        self._load_fk_table(fk_table)
        
        by_id = self._cache.get(f"{fk_table}_by_id", {})
        by_name = self._cache.get(f"{fk_table}_by_name", {})
        
        # Try to resolve as ID first (if numeric)
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            fk_id = int(value)
            if fk_id in by_id:
                result.resolved_id = fk_id
                return result
            else:
                result.error = f"ID {fk_id} not found in {fk_table}"
                return result
        
        # Resolve by name
        name_str = str(value).strip()
        
        # Normalize the lookup name (handles quotes, case, whitespace)
        normalized_lookup = normalize_name(name_str)
        
        # Direct lookup with normalized name (cache keys are already normalized)
        if normalized_lookup in by_name:
            matches = by_name[normalized_lookup]
        else:
            available = list(by_name.keys()) if by_name else []
            result.error = f"'{name_str}' not found in {fk_table}. Available normalized keys: {', '.join(available[:5])}" if available else f"'{name_str}' not found in {fk_table} (table appears empty)"
            return result
        
        # Apply scope filters if provided (e.g., filter by user_id)
        if scope:
            filtered_matches = []
            for match in matches:
                # Check all scope criteria
                match_passes = True
                for scope_key, scope_value in scope.items():
                    # Note: sqlite3.Row requires .keys() for 'in' check
                    if scope_key not in match.keys() or match[scope_key] != scope_value:
                        match_passes = False
                        break
                if match_passes:
                    filtered_matches.append(match)
            matches = filtered_matches
        
        if len(matches) == 0:
            # Not found (possibly after scope filtering)
            if scope:
                scope_desc = ', '.join(f"{k}={v}" for k, v in scope.items())
                result.error = f"'{name_str}' not found in {fk_table} for {scope_desc}"
            else:
                result.error = f"'{name_str}' not found in {fk_table}"
            return result
        elif len(matches) == 1:
            # Unique match - success
            result.resolved_id = matches[0]['id']
            return result
        elif len(matches) > 1:
            # Ambiguous - multiple records with same name (even after scope filtering)
            if scope:
                scope_desc = ', '.join(f"{k}={v}" for k, v in scope.items())
                result.error = f"'{name_str}' is ambiguous in {fk_table} for {scope_desc} (found {len(matches)} matches)"
            else:
                result.error = f"'{name_str}' is ambiguous in {fk_table} (found {len(matches)} matches)"
            result.ambiguous_matches = matches
            return result
        
        result.error = f"'{name_str}' not found in {fk_table}"
        return result
    
    def get_cache(self) -> Dict[str, Any]:
        """Get the complete FK cache for validation context."""
        return self._cache.copy()
    
    def get_name_for_id(self, fk_table: str, fk_id: int) -> Optional[str]:
        """Get name for a given FK ID (for export).
        
        Args:
            fk_table: FK table name
            fk_id: Foreign key ID
        
        Returns:
            Name string or None if not found
        """
        self._load_fk_table(fk_table)
        by_id = self._cache.get(f"{fk_table}_by_id", {})
        return by_id.get(fk_id)
