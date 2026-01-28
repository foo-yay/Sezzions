"""
Database Restore Service

Provides database restore operations with multiple merge modes.
Supports full replacement, selective table restore, and merge strategies.
"""

import sqlite3
import shutil
from pathlib import Path
from typing import Optional, List

from services.tools.dtos import RestoreResult
from services.tools.enums import RestoreMode


class RestoreService:
    """
    Service for restoring database from backups.
    
    Supports multiple restore modes:
    - REPLACE: Full database replacement
    - MERGE_ALL: Merge all tables (skip duplicates)
    - MERGE_SELECTED: Merge specific tables only
    """
    
    def __init__(self, db_connection):
        """
        Initialize restore service.
        
        Args:
            db_connection: Active database connection
        """
        self.db = db_connection
    
    def restore_database(
        self,
        backup_path: str,
        mode: RestoreMode = RestoreMode.REPLACE,
        tables: Optional[List[str]] = None
    ) -> RestoreResult:
        """
        Restore database from backup file.
        
        Args:
            backup_path: Path to backup file
            mode: Restore mode (REPLACE, MERGE_ALL, MERGE_SELECTED)
            tables: List of tables to restore (for MERGE_SELECTED mode)
        
        Returns:
            RestoreResult with success status and affected tables
        
        Example:
            >>> service = RestoreService(db)
            >>> # Full replacement
            >>> result = service.restore_database('backup.db', RestoreMode.REPLACE)
            >>> 
            >>> # Merge only purchases and sessions
            >>> result = service.restore_database(
            ...     'backup.db',
            ...     RestoreMode.MERGE_SELECTED,
            ...     tables=['purchases', 'game_sessions']
            ... )
        """
        backup_path_obj = Path(backup_path)
        
        if not backup_path_obj.exists():
            return RestoreResult(
                success=False,
                error=f"Backup file not found: {backup_path}"
            )
        
        try:
            # Verify backup integrity first
            if not self._verify_backup_integrity(backup_path):
                return RestoreResult(
                    success=False,
                    error="Backup file is corrupted or invalid"
                )
            
            # Execute restore based on mode
            if mode == RestoreMode.REPLACE:
                return self._restore_full_replace(backup_path)
            elif mode == RestoreMode.MERGE_ALL:
                return self._restore_merge_all(backup_path)
            elif mode == RestoreMode.MERGE_SELECTED:
                if not tables:
                    return RestoreResult(
                        success=False,
                        error="MERGE_SELECTED mode requires tables list"
                    )
                return self._restore_merge_selective(backup_path, tables)
            else:
                return RestoreResult(
                    success=False,
                    error=f"Unknown restore mode: {mode}"
                )
                
        except Exception as e:
            return RestoreResult(
                success=False,
                error=f"Restore failed: {str(e)}"
            )
    
    def _restore_full_replace(self, backup_path: str) -> RestoreResult:
        """
        Full database replacement.
        
        Drops all tables and recreates from backup.
        THIS IS DESTRUCTIVE - all current data is lost.
        """
        try:
            # Connect to backup database
            backup_conn = sqlite3.connect(backup_path)
            backup_conn.row_factory = sqlite3.Row
            
            # Get list of current tables
            current_tables = self._get_table_list()
            
            # Disable foreign keys
            db = self._get_cursor()
            db.execute_no_commit("PRAGMA foreign_keys = OFF")
            
            # Drop all current tables
            for table in current_tables:
                try:
                    db.execute_no_commit(f"DROP TABLE IF EXISTS {table}")
                except Exception as e:
                    # Continue dropping other tables
                    pass
            
            # Get schema from backup
            backup_cursor = backup_conn.cursor()
            backup_cursor.execute("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
                ORDER BY name
            """)
            schemas = [row[0] for row in backup_cursor.fetchall()]
            
            # Recreate tables from backup schema
            for schema in schemas:
                db.execute_no_commit(schema)
            
            # Get list of tables from backup
            backup_cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in backup_cursor.fetchall()]
            
            # Copy data from backup to current database
            total_restored = 0
            for table_name in tables:
                # Get columns
                backup_cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in backup_cursor.fetchall()]
                
                if not columns:
                    continue
                
                # Fetch all records
                backup_cursor.execute(f"SELECT * FROM {table_name}")
                records = backup_cursor.fetchall()
                
                if records:
                    placeholders = ','.join(['?' for _ in columns])
                    column_names = ','.join(columns)
                    insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
                    
                    params_list = [tuple([record[col] for col in columns]) for record in records]
                    db.executemany_no_commit(insert_sql, params_list)
                    total_restored += len(records)
            
            # Re-enable foreign keys
            db.execute_no_commit("PRAGMA foreign_keys = ON")
            
            # Commit all changes
            self._commit()
            
            backup_conn.close()
            
            # Log audit trail
            self.db.log_audit(
                action='RESTORE_REPLACE',
                table_name='database',
                details=f"Full database replacement from {backup_path} ({total_restored} records)"
            )
            
            return RestoreResult(
                success=True,
                records_restored=total_restored,
                tables_affected=tables
            )
            
        except Exception as e:
            return RestoreResult(
                success=False,
                error=f"Full replace failed: {str(e)}"
            )
    
    def _restore_merge_all(self, backup_path: str) -> RestoreResult:
        """
        Merge all tables from backup into current database.
        
        Skips duplicate records (based on primary key).
        Useful for combining data from multiple sources.
        """
        try:
            # Attach backup database
            backup_conn = sqlite3.connect(backup_path)
            backup_conn.row_factory = sqlite3.Row
            
            # Get list of tables from backup
            cursor = backup_conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            total_restored = 0
            tables_affected = []
            
            # Merge each table
            for table_name in tables:
                count = self._merge_table(backup_conn, table_name)
                if count > 0:
                    total_restored += count
                    tables_affected.append(table_name)
            
            backup_conn.close()
            
            return RestoreResult(
                success=True,
                records_restored=total_restored,
                tables_affected=tables_affected
            )
            
        except Exception as e:
            return RestoreResult(
                success=False,
                error=f"Merge all failed: {str(e)}"
            )
    
    def _restore_merge_selective(
        self,
        backup_path: str,
        tables: List[str]
    ) -> RestoreResult:
        """
        Merge specific tables from backup into current database.
        
        Allows fine-grained control over what data to restore.
        """
        try:
            # Attach backup database
            backup_conn = sqlite3.connect(backup_path)
            backup_conn.row_factory = sqlite3.Row
            
            total_restored = 0
            tables_affected = []
            errors = []
            
            # Merge each specified table
            for table_name in tables:
                try:
                    count = self._merge_table(backup_conn, table_name)
                    if count > 0:
                        total_restored += count
                        tables_affected.append(table_name)
                except Exception as e:
                    errors.append(f"{table_name}: {str(e)}")
            
            backup_conn.close()
            
            if errors:
                return RestoreResult(
                    success=False,
                    error=f"Some tables failed to restore: {'; '.join(errors)}"
                )
            
            return RestoreResult(
                success=True,
                records_restored=total_restored,
                tables_affected=tables_affected
            )
            
        except Exception as e:
            return RestoreResult(
                success=False,
                error=f"Selective merge failed: {str(e)}"
            )
    
    def _merge_table(self, backup_conn: sqlite3.Connection, table_name: str) -> int:
        """
        Merge single table from backup into current database.
        
        Uses INSERT OR IGNORE to skip duplicates based on primary key.
        
        Returns:
            Number of records inserted
        """
        # Get all columns for this table
        cursor = backup_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        if not columns:
            return 0
        
        # Fetch all records from backup
        cursor.execute(f"SELECT * FROM {table_name}")
        records = cursor.fetchall()
        
        if not records:
            return 0
        
        # Prepare INSERT OR IGNORE statement
        placeholders = ','.join(['?' for _ in columns])
        column_names = ','.join(columns)
        insert_sql = f"""
            INSERT OR IGNORE INTO {table_name} ({column_names})
            VALUES ({placeholders})
        """
        
        # Insert records into current database
        db = self._get_cursor()
        
        # Get count before merge
        before_count = db.fetch_one(f"SELECT COUNT(*) as count FROM {table_name}")['count']
        
        # Batch insert all records
        params_list = []
        for record in records:
            values = tuple([record[col] for col in columns])
            params_list.append(values)
        
        if params_list:
            db.executemany_no_commit(insert_sql, params_list)
        
        # Get count after merge
        after_count = db.fetch_one(f"SELECT COUNT(*) as count FROM {table_name}")['count']
        inserted_count = after_count - before_count
        
        self._commit()
        
        # Log audit trail for non-zero merges
        if inserted_count > 0:
            self.db.log_audit(
                action='RESTORE_MERGE',
                table_name=table_name,
                details=f"Merged {inserted_count} record(s) from backup"
            )
        
        return inserted_count
    
    def _verify_backup_integrity(self, backup_path: str) -> bool:
        """
        Verify backup file is a valid SQLite database.
        
        Returns:
            True if backup is valid, False otherwise
        """
        try:
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            return result and result[0] == 'ok'
        except Exception:
            return False
    
    def _get_table_list(self) -> List[str]:
        """Get list of tables in current database."""
        db = self._get_cursor()
        tables_result = db.fetch_all("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        return [row['name'] for row in tables_result]
    
    def _get_database_path(self) -> Optional[str]:
        """Get path to current database file."""
        try:
            db = self._get_cursor()
            result = db.fetch_one("PRAGMA database_list")
            if result and 'file' in result:
                return result['file']  # Database file path
            return None
        except Exception:
            return None
    
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
    
    def _close_connection(self):
        """Close database connection."""
        if hasattr(self.db, 'close'):
            self.db.close()
        elif hasattr(self.db, 'conn'):
            self.db.conn.close()
    
    def _reopen_connection(self):
        """
        Reopen database connection.
        
        Note: This is a placeholder. In production, the application
        should handle reconnection at a higher level.
        """
        # This should be handled by the application layer
        pass
