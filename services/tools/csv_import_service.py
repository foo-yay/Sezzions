"""CSV Import Service - orchestrates the complete import workflow."""

import csv
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import date
from decimal import Decimal

from .dtos import (
    ImportPreview, ImportResult, ValidationError, ValidationSeverity, ValidationContext
)
from .enums import FieldType
from .schemas import EntitySchema, CSVFieldDef, get_schema
from .csv_utils import parse_date, parse_time, parse_decimal, parse_boolean
from .fk_resolver import ForeignKeyResolver
from .validators.purchase_validator import PurchaseValidator
from .validators.redemption_validator import RedemptionValidator
from .validators.game_session_validator import GameSessionValidator
from repositories.database import DatabaseManager
from repositories.bulk_tools_repository import BulkToolsRepository


class CSVImportService:
    """Service for importing CSV files into the database."""
    
    def __init__(self, db):
        self.db = db
        self.fk_resolver = ForeignKeyResolver(db)
        # BulkToolsRepository requires specific DB manager, create manually for imports
        self._use_bulk_repo = hasattr(db, 'executemany_no_commit')
        if self._use_bulk_repo:
            self.bulk_repo = BulkToolsRepository(db)
        
        # Validator registry
        self.validators = {
            'purchases': PurchaseValidator(),
            'redemptions': RedemptionValidator(),
            'game_sessions': GameSessionValidator(),
        }
    
    def preview_import(
        self,
        csv_path: str,
        entity_type: str,
        strict_mode: bool = True
    ) -> ImportPreview:
        """Preview CSV import without committing to database.
        
        Args:
            csv_path: Path to CSV file
            entity_type: Type of entity being imported (e.g., 'purchases')
            strict_mode: Whether to enforce strict validation
        
        Returns:
            ImportPreview with analysis of what would be imported
        """
        schema = get_schema(entity_type)
        if not schema:
            return ImportPreview(
                invalid_rows=[ValidationError(
                    row_number=0,
                    field='entity_type',
                    value=entity_type,
                    message=f"Unknown entity type: {entity_type}",
                    severity=ValidationSeverity.ERROR
                )]
            )
        
        # Clear and reload FK caches (to pick up any recently imported data)
        self.fk_resolver._cache.clear()
        self.fk_resolver.load_cache_for_schema(schema)
        
        # Parse CSV
        records, parse_errors = self._parse_csv(csv_path, schema)
        
        if parse_errors:
            return ImportPreview(
                to_add=[],
                to_update=[],
                exact_duplicates=[],
                conflicts=[],
                invalid_rows=parse_errors,
                csv_duplicates=[]
            )
        
        # Load existing records for duplicate detection
        existing_records = self._load_existing_records(schema)
        
        # Categorize records
        to_add: List[Dict[str, Any]] = []
        to_update: List[Dict[str, Any]] = []
        exact_duplicates: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        invalid_rows: List[ValidationError] = []
        csv_duplicates: List[ValidationError] = []
        
        # Validate and categorize
        validator = self.validators.get(entity_type)
        validation_context = ValidationContext(
            row_number=0,
            entity_type=entity_type,
            existing_data=self.fk_resolver.get_cache(),
            strict_mode=strict_mode
        )
        
        # Batch validation first (detect CSV duplicates)
        if validator:
            batch_errors = validator.validate_batch(records)
            csv_duplicates.extend(batch_errors)
        
        # Track unique keys within CSV
        seen_keys: Set[tuple] = set()
        
        for idx, record in enumerate(records):
            row_num = idx + 2  # +1 for 0-index, +1 for header row
            validation_context.row_number = row_num
            
            # Field-level and record-level validation
            if validator:
                errors = validator.validate_record(record, validation_context)
                if errors:
                    invalid_rows.extend(errors)
                    continue
            
            # Check for duplicates within CSV
            unique_key = self._make_unique_key(record, schema)
            if unique_key in seen_keys:
                # Already flagged by batch validator
                continue
            seen_keys.add(unique_key)
            
            # Check against existing DB records
            existing_match = self._find_existing_match(record, existing_records, schema)
            
            if existing_match:
                if self._is_exact_match(record, existing_match):
                    exact_duplicates.append(record)
                else:
                    # Conflict - same unique key but different data
                    conflict_record = record.copy()
                    conflict_record['_existing_id'] = existing_match['id']
                    conflicts.append(conflict_record)
            else:
                to_add.append(record)
        
        return ImportPreview(
            to_add=to_add,
            to_update=to_update,
            exact_duplicates=exact_duplicates,
            conflicts=conflicts,
            invalid_rows=invalid_rows,
            csv_duplicates=csv_duplicates
        )
    
    def execute_import(
        self,
        csv_path: str,
        entity_type: str,
        skip_conflicts: bool = False,
        overwrite_conflicts: bool = False
    ) -> ImportResult:
        """Execute CSV import atomically.
        
        Args:
            csv_path: Path to CSV file
            entity_type: Type of entity being imported
            skip_conflicts: Skip records that conflict with existing data
            overwrite_conflicts: Overwrite existing records on conflict
        
        Returns:
            ImportResult with outcome
        """
        # Get preview first
        preview = self.preview_import(csv_path, entity_type)
        
        # Block if errors exist
        if preview.has_errors:
            return ImportResult(
                success=False,
                records_added=0,
                records_updated=0,
                records_skipped=0,
                errors=[
                    str(error)
                    for error in [*preview.invalid_rows, *preview.csv_duplicates]
                    if error.severity == ValidationSeverity.ERROR
                ],
                warnings=[
                    str(error)
                    for error in [*preview.invalid_rows, *preview.csv_duplicates]
                    if error.severity == ValidationSeverity.WARNING
                ]
            )
        
        schema = get_schema(entity_type)
        records_to_insert = preview.to_add.copy()
        records_to_update = []
        records_skipped = len(preview.exact_duplicates)
        
        # Handle conflicts based on flags
        if preview.conflicts:
            if skip_conflicts:
                records_skipped += len(preview.conflicts)
            elif overwrite_conflicts:
                # Convert conflicts to updates
                for conflict in preview.conflicts:
                    existing_id = conflict.pop('_existing_id')
                    conflict['id'] = existing_id
                    records_to_update.append(conflict)
            else:
                # Conflicts exist but no resolution specified
                return ImportResult(
                    success=False,
                    records_added=0,
                    records_updated=0,
                    records_skipped=0,
                    errors=[str(ValidationError(
                        row_number=0,
                        field='conflicts',
                        value=len(preview.conflicts),
                        message=f"Found {len(preview.conflicts)} conflicts. Specify skip_conflicts or overwrite_conflicts.",
                        severity=ValidationSeverity.ERROR
                    ))]
                )
        
        # Sort transaction tables chronologically
        if entity_type in ['purchases', 'redemptions', 'game_sessions']:
            records_to_insert = self._sort_chronologically(records_to_insert, schema)
            records_to_update = self._sort_chronologically(records_to_update, schema)
        
        # Convert Decimals to floats for SQLite compatibility
        def convert_decimals(record: Dict[str, Any]) -> Dict[str, Any]:
            return {k: float(v) if isinstance(v, Decimal) else v for k, v in record.items()}
        
        records_to_insert = [convert_decimals(rec) for rec in records_to_insert]
        records_to_update = [convert_decimals(rec) for rec in records_to_update]
        
        # Execute atomic import
        try:
            if self._use_bulk_repo:
                # Use BulkToolsRepository for production
                added = 0
                updated = 0
                
                # Insert new records
                if records_to_insert:
                    insert_result = self.bulk_repo.bulk_import_records(
                        schema.table_name,
                        records_to_insert,
                        update_on_conflict=False
                    )
                    if not insert_result.success:
                        raise Exception(insert_result.error)
                    added = insert_result.records_inserted
                
                # Update existing records
                if records_to_update:
                    update_result = self.bulk_repo.bulk_import_records(
                        schema.table_name,
                        records_to_update,
                        update_on_conflict=True,
                        unique_columns=('id',)
                    )
                    if not update_result.success:
                        raise Exception(update_result.error)
                    updated = update_result.records_updated
            else:
                # Fallback for tests/simple DB wrappers
                added, updated = self._simple_import(
                    schema.table_name,
                    schema,
                    records_to_insert,
                    records_to_update
                )
            
            # Track affected user_ids and site_ids for recalculation prompts
            affected_user_ids = set()
            affected_site_ids = set()
            
            all_records = records_to_insert + records_to_update
            for record in all_records:
                if 'user_id' in record and record['user_id']:
                    affected_user_ids.add(record['user_id'])
                if 'site_id' in record and record['site_id']:
                    affected_site_ids.add(record['site_id'])
            
            return ImportResult(
                success=True,
                records_added=added,
                records_updated=updated,
                records_skipped=records_skipped,
                warnings=[str(error) for error in preview.invalid_rows if error.severity == ValidationSeverity.WARNING],
                entity_type=entity_type,
                affected_user_ids=sorted(affected_user_ids),
                affected_site_ids=sorted(affected_site_ids)
            )
        except Exception as e:
            return ImportResult(
                success=False,
                records_added=0,
                records_updated=0,
                records_skipped=0,
                errors=[str(ValidationError(
                    row_number=0,
                    field='database',
                    value=str(e),
                    message=f"Database error during import: {str(e)}",
                    severity=ValidationSeverity.ERROR
                ))]
            )
    
    def _parse_csv(
        self,
        csv_path: str,
        schema: EntitySchema
    ) -> tuple[List[Dict[str, Any]], List[ValidationError]]:
        """Parse CSV file into records according to schema.
        
        Returns:
            (records, errors)
        """
        records = []
        errors = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Validate headers
                csv_headers = set(reader.fieldnames or [])
                schema_headers = {field.csv_header for field in schema.fields}
                required_headers = {field.csv_header for field in schema.fields if field.required}
                
                missing_required = required_headers - csv_headers
                if missing_required:
                    errors.append(ValidationError(
                        row_number=0,
                        field='headers',
                        value=', '.join(missing_required),
                        message=f"Missing required columns: {', '.join(missing_required)}",
                        severity=ValidationSeverity.ERROR
                    ))
                    return [], errors
                
                # Parse each row
                for idx, row in enumerate(reader):
                    row_num = idx + 2  # +1 for 0-index, +1 for header
                    parsed_record, row_errors = self._parse_row(row, schema, row_num)
                    
                    if row_errors:
                        errors.extend(row_errors)
                    else:
                        records.append(parsed_record)
        
        except FileNotFoundError:
            errors.append(ValidationError(
                row_number=0,
                field='file',
                value=csv_path,
                message=f"File not found: {csv_path}",
                severity=ValidationSeverity.ERROR
            ))
        except Exception as e:
            errors.append(ValidationError(
                row_number=0,
                field='parse',
                value=str(e),
                message=f"Error parsing CSV: {str(e)}",
                severity=ValidationSeverity.ERROR
            ))
        
        return records, errors
    
    def _parse_row(
        self,
        row: Dict[str, str],
        schema: EntitySchema,
        row_num: int
    ) -> tuple[Dict[str, Any], List[ValidationError]]:
        """Parse a single CSV row into a record."""
        record = {}
        errors = []
        
        for field in schema.fields:
            csv_value = row.get(field.csv_header, '')
            
            # Apply default if empty
            if csv_value == '' and field.default_value is not None:
                csv_value = field.default_value
            
            # For optional empty fields, set to None instead of skipping
            # This ensures all records have the same keys for bulk import
            if csv_value == '' and not field.required:
                record[field.db_column] = None
                continue
            
            # Parse by type
            parsed_value = self._parse_field_value(csv_value, field)
            
            # Foreign key resolution
            if field.foreign_key and parsed_value is not None:
                # Build scope for user-scoped FK tables (redemption_methods, cards)
                scope = None
                if field.foreign_key.table in ('redemption_methods', 'cards'):
                    # Scope by user_id if it's already been resolved in this row
                    if 'user_id' in record and record['user_id'] is not None:
                        scope = {'user_id': record['user_id']}
                
                fk_result = self.fk_resolver.resolve_fk(parsed_value, field.foreign_key.table, scope=scope)
                if fk_result.success:
                    record[field.db_column] = fk_result.resolved_id
                else:
                    errors.append(ValidationError(
                        row_number=row_num,
                        field=field.csv_header,
                        value=parsed_value,
                        message=fk_result.error or "FK resolution failed",
                        severity=ValidationSeverity.ERROR
                    ))
            else:
                record[field.db_column] = parsed_value
        
        # Post-processing: Set calculated fields based on entity type
        if schema.table_name == 'purchases':
            # Initialize remaining_amount to sc_received (full amount available until consumed)
            if 'sc_received' in record:
                record['remaining_amount'] = record['sc_received']
            elif 'amount' in record:
                # Fallback: if sc_received not set, use amount
                record['remaining_amount'] = record['amount']
            else:
                record['remaining_amount'] = '0.00'
        
        elif schema.table_name == 'game_sessions':
            # Auto-set status to Closed if end_date is provided
            if 'end_date' in record and record['end_date'] is not None:
                record['status'] = 'Closed'
            elif 'status' not in record or record['status'] is None:
                record['status'] = 'Active'
        
        return record, errors
    
    def _parse_field_value(self, value: str, field: CSVFieldDef) -> Any:
        """Parse field value according to field type."""
        if value == '':
            return None
        
        if field.field_type == FieldType.TEXT:
            return str(value).strip()
        elif field.field_type == FieldType.INTEGER:
            try:
                return int(value)
            except ValueError:
                return None
        elif field.field_type == FieldType.DECIMAL:
            return parse_decimal(value)
        elif field.field_type == FieldType.DATE:
            return parse_date(value)
        elif field.field_type == FieldType.TIME:
            return parse_time(value)
        elif field.field_type == FieldType.BOOLEAN:
            return parse_boolean(value)
        elif field.field_type == FieldType.FOREIGN_KEY:
            # Return raw value for FK resolution
            return str(value).strip()
        
        return value
    
    def _load_existing_records(self, schema: EntitySchema) -> List[Dict[str, Any]]:
        """Load existing records from database for duplicate detection."""
        try:
            query = f"SELECT * FROM {schema.table_name}"
            rows = self.db.fetch_all(query)
            return [dict(row) for row in rows]
        except Exception:
            return []
    
    def _find_existing_match(
        self,
        record: Dict[str, Any],
        existing_records: List[Dict[str, Any]],
        schema: EntitySchema
    ) -> Optional[Dict[str, Any]]:
        """Find existing record that matches unique columns."""
        if not schema.unique_columns:
            return None
        
        for existing in existing_records:
            if self._matches_unique_key(record, existing, schema.unique_columns):
                return existing
        
        return None
    
    def _matches_unique_key(
        self,
        record: Dict[str, Any],
        existing: Dict[str, Any],
        unique_columns: List[str]
    ) -> bool:
        """Check if record matches existing on unique columns."""
        for col in unique_columns:
            rec_val = record.get(col)
            exist_val = existing.get(col)
            
            # Handle type differences (Decimal vs float, date vs string)
            if isinstance(rec_val, Decimal) and isinstance(exist_val, (int, float)):
                rec_val = float(rec_val)
            elif isinstance(exist_val, Decimal) and isinstance(rec_val, (int, float)):
                exist_val = float(exist_val)
            
            # Convert dates to strings for comparison
            if hasattr(rec_val, 'isoformat'):
                rec_val = rec_val.isoformat() if isinstance(rec_val, date) else str(rec_val)
            if hasattr(exist_val, 'isoformat'):
                exist_val = exist_val.isoformat() if isinstance(exist_val, date) else str(exist_val)
            
            if rec_val != exist_val:
                return False
        return True
    
    def _is_exact_match(
        self,
        record: Dict[str, Any],
        existing: Dict[str, Any]
    ) -> bool:
        """Check if record exactly matches existing (all non-ID fields)."""
        for key, value in record.items():
            if key == 'id':
                continue
            
            exist_val = existing.get(key)
            
            # Treat None and 0 as equivalent for numeric fields (handles defaults)
            if isinstance(value, Decimal) and value == 0 and exist_val is None:
                continue
            if isinstance(exist_val, (int, float)) and exist_val == 0 and value is None:
                continue
            
            # Handle type differences
            if isinstance(value, Decimal) and isinstance(exist_val, (int, float)):
                value = float(value)
            elif isinstance(exist_val, Decimal) and isinstance(value, (int, float)):
                exist_val = float(exist_val)
            
            # Convert dates to strings
            if hasattr(value, 'isoformat'):
                value = value.isoformat() if isinstance(value, date) else str(value)
            if hasattr(exist_val, 'isoformat'):
                exist_val = exist_val.isoformat() if isinstance(exist_val, date) else str(exist_val)
            
            if exist_val != value:
                return False
        return True
    
    def _make_unique_key(self, record: Dict[str, Any], schema: EntitySchema) -> tuple:
        """Create tuple of unique column values for deduplication."""
        if not schema.unique_columns:
            return tuple()
        
        return tuple(record.get(col) for col in schema.unique_columns)
    
    def _sort_chronologically(
        self,
        records: List[Dict[str, Any]],
        schema: EntitySchema
    ) -> List[Dict[str, Any]]:
        """Sort transaction records chronologically (date, then time)."""
        date_col = None
        time_col = None
        
        # Find date and time columns
        for field in schema.fields:
            if field.field_type == FieldType.DATE and 'date' in field.db_column:
                date_col = field.db_column
            if field.field_type == FieldType.TIME and 'time' in field.db_column:
                time_col = field.db_column
        
        if not date_col:
            return records
        
        def sort_key(rec: Dict[str, Any]) -> tuple:
            rec_date = rec.get(date_col) or date.min
            rec_time = rec.get(time_col) or '00:00:00'
            return (rec_date, rec_time)
        
        return sorted(records, key=sort_key)
    
    def _simple_import(
        self,
        table_name: str,
        schema: EntitySchema,
        records_to_insert: List[Dict[str, Any]],
        records_to_update: List[Dict[str, Any]]
    ) -> tuple[int, int]:
        """Simple import for tests/basic DB wrappers (not transaction-safe)."""
        added = 0
        updated = 0
        
        # Convert Decimals to floats for SQLite
        def convert_decimals(record: Dict[str, Any]) -> Dict[str, Any]:
            converted = {}
            for k, v in record.items():
                if isinstance(v, Decimal):
                    converted[k] = float(v)
                else:
                    converted[k] = v
            return converted
        
        # Build column list from first record (if any)
        if records_to_insert:
            columns = list(records_to_insert[0].keys())
            placeholders = ', '.join(['?' for _ in columns])
            col_names = ', '.join(columns)
            
            insert_query = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
            
            for record in records_to_insert:
                converted = convert_decimals(record)
                values = tuple(converted.get(col) for col in columns)
                self.db.execute(insert_query, values)
                added += 1
        
        # Updates
        if records_to_update:
            for record in records_to_update:
                record_id = record.pop('id')
                converted = convert_decimals(record)
                set_clauses = ', '.join([f"{col} = ?" for col in converted.keys()])
                update_query = f"UPDATE {table_name} SET {set_clauses} WHERE id = ?"
                
                values = tuple(converted.values()) + (record_id,)
                self.db.execute(update_query, values)
                updated += 1
        
        self.db.commit()
        return added, updated

