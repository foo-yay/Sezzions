"""
Database Reset Service

Provides database reset operations with optional data preservation.
Supports full reset or selective reset keeping reference/setup data.
"""

import sqlite3
from typing import List, Optional

from services.tools.dtos import ResetResult


class ResetService:
    """
    Service for resetting database to initial state.
    
    Supports:
    - Full reset: Delete all data from all tables
    - Keep setup data: Preserve reference tables (users, sites, cards, etc.)
    """
    
    # Tables considered "setup/reference" data
    SETUP_TABLES = [
        'users',
        'sites',
        'cards',
        'redemption_methods',
        'game_types',
        'games'
    ]
    
    # Tables containing transactional data
    TRANSACTION_TABLES = [
        'purchases',
        'redemptions',
        'game_sessions',
        'daily_sessions',
        'expenses',
        'realized_transactions'
    ]
    
    def __init__(self, db_connection):
        """
        Initialize reset service.
        
        Args:
            db_connection: Active database connection
        """
        self.db = db_connection
    
    def reset_database(
        self,
        keep_setup_data: bool = False,
        keep_audit_log: bool = False,
        tables_to_reset: Optional[List[str]] = None
    ) -> ResetResult:
        """
        Reset database to initial state.
        
        Args:
            keep_setup_data: If True, preserve reference/setup tables (default False)
            keep_audit_log: If True, preserve audit_log table (default False)
            tables_to_reset: Specific tables to reset (overrides keep_setup_data)
        
        Returns:
            ResetResult with success status and count of records deleted
        
        Example:
            >>> service = ResetService(db)
            >>> 
            >>> # Full reset - delete everything
            >>> result = service.reset_database()
            >>> 
            >>> # Keep setup data, reset only transactions
            >>> result = service.reset_database(keep_setup_data=True)
            >>> 
            >>> # Reset only specific tables
            >>> result = service.reset_database(tables_to_reset=['purchases', 'game_sessions'])
        """
        try:
            cursor = self._get_cursor()
            
            # Determine which tables to reset
            if tables_to_reset:
                # User specified exact tables
                tables = tables_to_reset
            elif keep_setup_data:
                # Reset only transaction tables
                tables = self._get_transaction_tables()
            else:
                # Reset all tables except audit log (if requested)
                tables = self._get_all_resettable_tables(keep_audit_log)
            
            # Disable foreign key constraints temporarily
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            total_deleted = 0
            tables_affected = []
            errors = []
            
            # Delete data from each table
            for table_name in tables:
                try:
                    # Count records before deletion
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count_before = cursor.fetchone()[0]
                    
                    if count_before > 0:
                        # Delete all records
                        cursor.execute(f"DELETE FROM {table_name}")
                        
                        # Reset autoincrement counter
                        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")
                        
                        total_deleted += count_before
                        tables_affected.append(table_name)
                        
                except Exception as e:
                    errors.append(f"{table_name}: {str(e)}")
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Commit changes
            self._commit()
            
            # Log audit trail
            action_type = 'RESET_PARTIAL' if keep_setup_data else 'RESET_FULL'
            table_summary = ', '.join([f"{t}" for t in tables_affected[:5]])
            if len(tables_affected) > 5:
                table_summary += f", +{len(tables_affected)-5} more"
            
            self.db.log_audit(
                action=action_type,
                table_name='database',
                details=f"Reset {len(tables_affected)} table(s): {table_summary}. Total records: {total_deleted}"
            )
            
            if errors:
                return ResetResult(
                    success=False,
                    error=f"Some tables failed to reset: {'; '.join(errors)}"
                )
            
            return ResetResult(
                success=True,
                records_deleted=total_deleted,
                tables_cleared=tables_affected
            )
            
        except Exception as e:
            # Rollback on error
            self._rollback()
            return ResetResult(
                success=False,
                error=f"Reset failed: {str(e)}"
            )
    
    def reset_transaction_data_only(self) -> ResetResult:
        """
        Convenience method: Reset only transaction data, keep setup data.
        
        Equivalent to reset_database(keep_setup_data=True)
        
        Returns:
            ResetResult with success status
        
        Example:
            >>> service = ResetService(db)
            >>> result = service.reset_transaction_data_only()
            >>> print(f"Deleted {result.records_deleted} transaction records")
        """
        return self.reset_database(keep_setup_data=True, keep_audit_log=True)
    
    def reset_table(self, table_name: str) -> ResetResult:
        """
        Reset a single table.
        
        Args:
            table_name: Name of table to reset
        
        Returns:
            ResetResult with success status
        
        Example:
            >>> service = ResetService(db)
            >>> result = service.reset_table('purchases')
            >>> if result.success:
            ...     print(f"Deleted {result.records_deleted} purchases")
        """
        return self.reset_database(tables_to_reset=[table_name])
    
    def get_table_counts(self) -> dict[str, int]:
        """
        Get record counts for all tables.
        
        Useful for displaying current state before reset.
        
        Returns:
            Dictionary mapping table names to record counts
        
        Example:
            >>> service = ResetService(db)
            >>> counts = service.get_table_counts()
            >>> for table, count in counts.items():
            ...     print(f"{table}: {count} records")
        """
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        counts = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            except Exception:
                counts[table] = 0
        
        return counts
    
    def preview_reset(
        self,
        keep_setup_data: bool = False,
        keep_audit_log: bool = False
    ) -> dict:
        """
        Preview what would be deleted by a reset operation.
        
        Args:
            keep_setup_data: Whether to keep setup data
            keep_audit_log: Whether to keep audit log
        
        Returns:
            Dictionary with tables_to_reset and total_records_to_delete
        
        Example:
            >>> service = ResetService(db)
            >>> preview = service.preview_reset(keep_setup_data=True)
            >>> print(f"Will delete {preview['total_records']} records from:")
            >>> for table in preview['tables']:
            ...     print(f"  - {table}: {preview['record_counts'][table]}")
        """
        # Determine tables to reset
        if keep_setup_data:
            tables = self._get_transaction_tables()
        else:
            tables = self._get_all_resettable_tables(keep_audit_log)
        
        # Get counts for each table
        counts = self.get_table_counts()
        tables_with_counts = {t: counts.get(t, 0) for t in tables}
        total_records = sum(tables_with_counts.values())
        
        return {
            'tables': tables,
            'record_counts': tables_with_counts,
            'total_records': total_records
        }
    
    def _get_transaction_tables(self) -> List[str]:
        """Get list of transaction tables."""
        all_tables = self._get_all_tables()
        return [t for t in all_tables if t in self.TRANSACTION_TABLES]
    
    def _get_all_resettable_tables(self, keep_audit_log: bool) -> List[str]:
        """Get all tables except audit log (optionally)."""
        all_tables = self._get_all_tables()
        
        # Exclude audit log if requested
        if keep_audit_log and 'audit_log' in all_tables:
            all_tables.remove('audit_log')
        
        return all_tables
    
    def _get_all_tables(self) -> List[str]:
        """Get list of all user tables (excludes sqlite internal tables)."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        return [row[0] for row in cursor.fetchall()]
    
    def _get_cursor(self):
        """Get database cursor."""
        if hasattr(self.db, 'cursor'):
            return self.db.cursor()
        else:
            return self.db
    
    def _commit(self):
        """Commit current transaction."""
        if hasattr(self.db, 'commit'):
            self.db.commit()
    
    def _rollback(self):
        """Rollback current transaction."""
        if hasattr(self.db, 'rollback'):
            self.db.rollback()
