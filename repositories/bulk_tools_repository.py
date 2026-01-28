"""
Bulk operations repository for Tools features.

This repository provides transaction-safe bulk write operations for:
- CSV imports (bulk insert/update)
- Database reset (bulk delete)
- Database merge/restore (selective bulk insert)

CRITICAL: All operations use DatabaseManager.transaction() + execute_no_commit/executemany_no_commit
to ensure atomicity. Never call execute() inside a transaction context.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from repositories.database import DatabaseManager


@dataclass
class BulkImportResult:
    """Result of a bulk import operation"""
    success: bool
    records_inserted: int
    records_updated: int
    error: Optional[str] = None


@dataclass
class BulkResetResult:
    """Result of a bulk reset operation"""
    success: bool
    tables_cleared: List[str]
    records_deleted: int
    error: Optional[str] = None


@dataclass
class BulkMergeResult:
    """Result of a bulk merge operation"""
    success: bool
    records_merged: int
    tables_affected: List[str]
    error: Optional[str] = None


class BulkToolsRepository:
    """Repository for atomic bulk operations in Tools workflows.
    
    All methods operate inside DatabaseManager.transaction() and use
    execute_no_commit/executemany_no_commit to ensure true atomicity.
    """
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def bulk_import_records(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        update_on_conflict: bool = False,
        unique_columns: Optional[Tuple[str, ...]] = None
    ) -> BulkImportResult:
        """Import records into a table atomically.
        
        Args:
            table_name: Target table name
            records: List of record dicts (column -> value)
            update_on_conflict: If True, update existing records; if False, skip duplicates
            unique_columns: Columns that define uniqueness for conflict detection
        
        Returns:
            BulkImportResult with counts and status
        
        Raises:
            Exception: Any error during import triggers rollback via transaction context
        """
        if not records:
            return BulkImportResult(success=True, records_inserted=0, records_updated=0)
        
        inserted = 0
        updated = 0
        
        try:
            with self.db.transaction():
                # Get all column names from first record
                columns = list(records[0].keys())
                placeholders = ', '.join(['?'] * len(columns))
                col_names = ', '.join(columns)
                
                if update_on_conflict and unique_columns:
                    # INSERT OR REPLACE strategy
                    for record in records:
                        # Check if exists
                        where_clauses = [f"{col} = ?" for col in unique_columns]
                        where_sql = " AND ".join(where_clauses)
                        where_params = tuple(record[col] for col in unique_columns)
                        
                        existing = self.db.fetch_one(
                            f"SELECT id FROM {table_name} WHERE {where_sql}",
                            where_params
                        )
                        
                        values = tuple(record[col] for col in columns)
                        
                        if existing:
                            # Update existing record
                            set_clauses = [f"{col} = ?" for col in columns if col != 'id']
                            set_sql = ", ".join(set_clauses)
                            update_values = tuple(record[col] for col in columns if col != 'id')
                            update_params = update_values + (existing['id'],)
                            
                            self.db.execute_no_commit(
                                f"UPDATE {table_name} SET {set_sql} WHERE id = ?",
                                update_params
                            )
                            updated += 1
                        else:
                            # Insert new record
                            self.db.execute_no_commit(
                                f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                                values
                            )
                            inserted += 1
                else:
                    # Simple bulk insert (will fail on duplicates if unique constraints exist)
                    insert_sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
                    params_seq = [tuple(record[col] for col in columns) for record in records]
                    self.db.executemany_no_commit(insert_sql, params_seq)
                    inserted = len(records)
            
            return BulkImportResult(
                success=True,
                records_inserted=inserted,
                records_updated=updated
            )
        
        except Exception as e:
            return BulkImportResult(
                success=False,
                records_inserted=0,
                records_updated=0,
                error=str(e)
            )
    
    def bulk_delete_tables(
        self,
        table_names: List[str],
        keep_setup_data: bool = False
    ) -> BulkResetResult:
        """Delete all records from specified tables atomically.
        
        Args:
            table_names: List of table names to clear
            keep_setup_data: If True, only clear transactional tables
        
        Returns:
            BulkResetResult with status and counts
        """
        if keep_setup_data:
            # Only clear transactional tables
            transactional_tables = [
                'purchases', 'redemptions', 'game_sessions',
                'daily_sessions', 'expenses', 'audit_log',
                'realized_transactions', 'redemption_allocations',
                'game_session_event_links'
            ]
            table_names = [t for t in table_names if t in transactional_tables]
        
        deleted_count = 0
        cleared_tables = []
        
        try:
            with self.db.transaction():
                for table_name in table_names:
                    # Count before delete
                    count_result = self.db.fetch_one(
                        f"SELECT COUNT(*) as c FROM {table_name}",
                        ()
                    )
                    count = count_result['c'] if count_result else 0
                    
                    # Delete all records
                    self.db.execute_no_commit(f"DELETE FROM {table_name}", ())
                    
                    deleted_count += count
                    cleared_tables.append(table_name)
            
            return BulkResetResult(
                success=True,
                tables_cleared=cleared_tables,
                records_deleted=deleted_count
            )
        
        except Exception as e:
            return BulkResetResult(
                success=False,
                tables_cleared=[],
                records_deleted=0,
                error=str(e)
            )
    
    def bulk_merge_from_backup(
        self,
        backup_db_path: str,
        table_names: List[str],
        skip_duplicates: bool = True,
        site_id_filter: Optional[int] = None,
        user_id_filter: Optional[int] = None
    ) -> BulkMergeResult:
        """Merge records from a backup database atomically.
        
        Args:
            backup_db_path: Path to backup SQLite database
            table_names: Tables to merge
            skip_duplicates: If True, skip records that already exist
            site_id_filter: If provided, only merge records for this site
            user_id_filter: If provided, only merge records for this user
        
        Returns:
            BulkMergeResult with status and counts
        """
        import sqlite3
        
        merged_count = 0
        affected_tables = []
        
        try:
            # Open backup database
            backup_conn = sqlite3.connect(backup_db_path)
            backup_conn.row_factory = sqlite3.Row
            backup_cursor = backup_conn.cursor()
            
            with self.db.transaction():
                for table_name in table_names:
                    # Get column names from current DB
                    cols_result = self.db.fetch_all(f"PRAGMA table_info({table_name})", ())
                    if not cols_result:
                        continue
                    
                    columns = [col['name'] for col in cols_result if col['name'] != 'id']
                    
                    # Build SELECT query for backup DB with optional filters
                    select_sql = f"SELECT {', '.join(columns)} FROM {table_name}"
                    where_clauses = []
                    
                    if site_id_filter is not None and 'site_id' in columns:
                        where_clauses.append(f"site_id = {site_id_filter}")
                    if user_id_filter is not None and 'user_id' in columns:
                        where_clauses.append(f"user_id = {user_id_filter}")
                    
                    if where_clauses:
                        select_sql += " WHERE " + " AND ".join(where_clauses)
                    
                    # Fetch records from backup
                    backup_cursor.execute(select_sql)
                    backup_records = backup_cursor.fetchall()
                    
                    if not backup_records:
                        continue
                    
                    # Insert records (skip duplicates if requested)
                    col_names = ', '.join(columns)
                    placeholders = ', '.join(['?'] * len(columns))
                    
                    for backup_row in backup_records:
                        values = tuple(backup_row[col] for col in columns)
                        
                        if skip_duplicates:
                            # Simple duplicate check: try insert, ignore if fails
                            try:
                                self.db.execute_no_commit(
                                    f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                                    values
                                )
                                merged_count += 1
                            except sqlite3.IntegrityError:
                                # Duplicate or constraint violation, skip
                                continue
                        else:
                            # Insert or fail
                            self.db.execute_no_commit(
                                f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                                values
                            )
                            merged_count += 1
                    
                    affected_tables.append(table_name)
            
            backup_conn.close()
            
            return BulkMergeResult(
                success=True,
                records_merged=merged_count,
                tables_affected=affected_tables
            )
        
        except Exception as e:
            if 'backup_conn' in locals():
                backup_conn.close()
            
            return BulkMergeResult(
                success=False,
                records_merged=0,
                tables_affected=[],
                error=str(e)
            )
