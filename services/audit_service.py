"""
Audit Service - Centralized audit logging for CRUD operations

Provides structured audit trail with JSON snapshots and operation grouping.
Supports atomic logging (within transactions) and undo/redo tracking.

Reference: Issue #92 - Audit Log + Undo/Redo + Soft Delete
Reference: Issue #97 - Two-tier audit retention + meaningful audit summaries
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from repositories.database import DatabaseManager


class AuditService:
    """Service for recording audit trail of CRUD operations"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    @staticmethod
    def build_summary(
        table_name: str,
        action: str,
        record_id: int,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Build a compact summary JSON for long-term audit retention.
        
        Summaries capture essential business context (amounts, users, sites, timestamps)
        without the full snapshot payload. This allows long-term audit retention
        even when detailed old_data/new_data snapshots are pruned.
        
        Args:
            table_name: Table name (purchases, redemptions, game_sessions, etc.)
            action: CRUD action (CREATE, UPDATE, DELETE)
            record_id: Record ID
            old_data: Old record data (for UPDATE/DELETE)
            new_data: New record data (for CREATE/UPDATE)
        
        Returns:
            JSON string summary, or None if table is not supported/data is invalid
        """
        # Defensive: handle None/empty data gracefully
        if new_data is None and old_data is None:
            return None
        
        # Choose the data payload to extract from
        data = new_data if new_data else old_data
        if not data or not isinstance(data, dict):
            return None
        
        try:
            summary = {
                "entity": None,
                "entity_id": record_id,
                "crud": action,
                "timestamp": datetime.now().isoformat(),
                "fields": {}
            }
            
            # Entity-specific summary rules
            if table_name == "purchases":
                summary["entity"] = "purchase"
                summary["fields"]["amount"] = data.get("amount")
                summary["fields"]["user_id"] = data.get("user_id")
                summary["fields"]["site_id"] = data.get("site_id")
                # Starting SC is a useful derived field
                if "starting_sc_balance" in data:
                    summary["fields"]["starting_sc"] = data.get("starting_sc_balance")
            
            elif table_name == "redemptions":
                summary["entity"] = "redemption"
                summary["fields"]["amount"] = data.get("amount")
                summary["fields"]["user_id"] = data.get("user_id")
                summary["fields"]["site_id"] = data.get("site_id")
            
            elif table_name == "game_sessions":
                summary["entity"] = "game_session"
                # Determine if this is a start or end event
                if action == "CREATE" or (action == "UPDATE" and new_data and old_data and old_data.get("status") == "Active"):
                    # Session start summary
                    if "session_date" in data and "session_time" in data:
                        summary["fields"]["start_datetime"] = f"{data['session_date']} {data['session_time']}"
                    summary["fields"]["start_sc"] = data.get("starting_balance")
                    summary["fields"]["start_redeemable"] = data.get("starting_redeemable")
                    summary["fields"]["user_id"] = data.get("user_id")
                    summary["fields"]["site_id"] = data.get("site_id")
                
                # Check for session end (status changed to Ended, or end_date is present)
                if action == "UPDATE" and new_data:
                    if new_data.get("end_date") or new_data.get("status") == "Ended":
                        # Session end summary
                        if "end_date" in new_data and "end_time" in new_data:
                            summary["fields"]["end_datetime"] = f"{new_data['end_date']} {new_data['end_time']}"
                        summary["fields"]["end_sc"] = new_data.get("ending_balance")
                        summary["fields"]["end_redeemable"] = new_data.get("ending_redeemable")
                        summary["fields"]["user_id"] = new_data.get("user_id")
                        summary["fields"]["site_id"] = new_data.get("site_id")
            
            else:
                # Unsupported table - no summary generated
                return None
            
            # Only return summary if we actually captured meaningful fields
            if summary["entity"] and summary["fields"]:
                return json.dumps(summary, default=str)
            else:
                return None
        
        except Exception:
            # Never crash on summary generation - return None and let audit proceed
            return None
    
    def log_create(
        self,
        table_name: str,
        record_id: int,
        new_data: Dict[str, Any],
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> None:
        """
        Log a CREATE operation.
        
        Args:
            table_name: Table where record was created
            record_id: ID of the created record
            new_data: Dictionary of the new record's data
            user_name: Optional username (defaults to 'system')
            group_id: Optional UUID grouping related operations
            auto_commit: If False, caller must commit transaction
        """
        summary = self.build_summary(table_name, "CREATE", record_id, None, new_data)
        self.db.log_audit(
            action="CREATE",
            table_name=table_name,
            record_id=record_id,
            details=f"Created {table_name} record",
            user_name=user_name,
            old_data=None,
            new_data=json.dumps(new_data, default=str),
            group_id=group_id,
            summary_data=summary,
            auto_commit=auto_commit
        )
    
    def log_update(
        self,
        table_name: str,
        record_id: int,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> None:
        """
        Log an UPDATE operation.
        
        Args:
            table_name: Table where record was updated
            record_id: ID of the updated record
            old_data: Dictionary of the record's data before update
            new_data: Dictionary of the record's data after update
            user_name: Optional username (defaults to 'system')
            group_id: Optional UUID grouping related operations
            auto_commit: If False, caller must commit transaction
        """
        summary = self.build_summary(table_name, "UPDATE", record_id, old_data, new_data)
        self.db.log_audit(
            action="UPDATE",
            table_name=table_name,
            record_id=record_id,
            details=f"Updated {table_name} record",
            user_name=user_name,
            old_data=json.dumps(old_data, default=str),
            new_data=json.dumps(new_data, default=str),
            group_id=group_id,
            summary_data=summary,
            auto_commit=auto_commit
        )
    
    def log_delete(
        self,
        table_name: str,
        record_id: int,
        old_data: Dict[str, Any],
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> None:
        """
        Log a DELETE (soft delete) operation.
        
        Args:
            table_name: Table where record was deleted
            record_id: ID of the deleted record
            old_data: Dictionary of the record's data before deletion
            user_name: Optional username (defaults to 'system')
            group_id: Optional UUID grouping related operations
            auto_commit: If False, caller must commit transaction
        """
        summary = self.build_summary(table_name, "DELETE", record_id, old_data, None)
        self.db.log_audit(
            action="DELETE",
            table_name=table_name,
            record_id=record_id,
            details=f"Soft-deleted {table_name} record",
            user_name=user_name,
            old_data=json.dumps(old_data, default=str),
            new_data=None,
            group_id=group_id,
            summary_data=summary,
            auto_commit=auto_commit
        )
    
    def log_restore(
        self,
        table_name: str,
        record_id: int,
        restored_data: Dict[str, Any],
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> None:
        """
        Log a RESTORE operation (undo soft delete).
        
        Args:
            table_name: Table where record was restored
            record_id: ID of the restored record
            restored_data: Dictionary of the record's data after restoration
            user_name: Optional username (defaults to 'system')
            group_id: Optional UUID grouping related operations
            auto_commit: If False, caller must commit transaction
        """
        self.db.log_audit(
            action="RESTORE",
            table_name=table_name,
            record_id=record_id,
            details=f"Restored soft-deleted {table_name} record",
            user_name=user_name,
            old_data=None,
            new_data=json.dumps(restored_data, default=str),
            group_id=group_id,
            auto_commit=auto_commit
        )
    
    def log_undo(
        self,
        description: str,
        affected_records: List[Dict[str, Any]],
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> None:
        """
        Log an UNDO operation.
        
        Args:
            description: Human-readable description of what was undone
            affected_records: List of dicts with 'table_name', 'record_id', 'old_data', 'new_data'
            user_name: Optional username (defaults to 'system')
            group_id: Optional UUID grouping related operations
            auto_commit: If False, caller must commit transaction
        """
        self.db.log_audit(
            action="UNDO",
            table_name="__system__",
            record_id=None,
            details=description,
            user_name=user_name,
            old_data=None,
            new_data=json.dumps(affected_records, default=str),
            group_id=group_id,
            auto_commit=auto_commit
        )
    
    def log_redo(
        self,
        description: str,
        affected_records: List[Dict[str, Any]],
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> None:
        """
        Log a REDO operation.
        
        Args:
            description: Human-readable description of what was redone
            affected_records: List of dicts with 'table_name', 'record_id', 'old_data', 'new_data'
            user_name: Optional username (defaults to 'system')
            group_id: Optional UUID grouping related operations
            auto_commit: If False, caller must commit transaction
        """
        self.db.log_audit(
            action="REDO",
            table_name="__system__",
            record_id=None,
            details=description,
            user_name=user_name,
            old_data=None,
            new_data=json.dumps(affected_records, default=str),
            group_id=group_id,
            auto_commit=auto_commit
        )
    
    def generate_group_id(self) -> str:
        """Generate a UUID for grouping related audit operations"""
        return str(uuid.uuid4())
    
    def get_audit_log(
        self,
        table_name: Optional[str] = None,
        action: Optional[str] = None,
        record_id: Optional[int] = None,
        group_id: Optional[str] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query audit log with optional filters.
        
        Args:
            table_name: Filter by table name
            action: Filter by action type (CREATE, UPDATE, DELETE, UNDO, REDO, etc.)
            record_id: Filter by record ID
            group_id: Filter by group ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of records to return
        
        Returns:
            List of audit log entries as dictionaries
        """
        from datetime import date
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if table_name:
            query += " AND table_name = ?"
            params.append(table_name)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        if record_id is not None:
            query += " AND record_id = ?"
            params.append(record_id)
        
        if group_id:
            query += " AND group_id = ?"
            params.append(group_id)
        
        if start_date:
            if isinstance(start_date, date):
                query += " AND DATE(timestamp) >= ?"
                params.append(start_date.isoformat())
        
        if end_date:
            if isinstance(end_date, date):
                query += " AND DATE(timestamp) <= ?"
                params.append(end_date.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = self.db.fetch_all(query, tuple(params))
        
        # Convert rows to dicts
        result = []
        for row in rows:
            entry = dict(row)
            # Parse JSON fields
            if entry.get('old_data'):
                try:
                    entry['old_data'] = json.loads(entry['old_data'])
                except (json.JSONDecodeError, TypeError):
                    pass
            if entry.get('new_data'):
                try:
                    entry['new_data'] = json.loads(entry['new_data'])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(entry)
        
        return result
    
    def get_max_audit_log_rows(self) -> int:
        """
        Get the max audit log rows setting.
        
        Returns:
            Maximum number of audit rows to retain (0 means unlimited)
        """
        result = self.db.fetch_one(
            "SELECT value FROM settings WHERE key = ?",
            ("max_audit_log_rows",)
        )
        if result and result.get("value"):
            try:
                return int(result["value"])
            except (ValueError, TypeError):
                return 10000  # Default fallback
        return 10000  # Default
    
    def set_max_audit_log_rows(self, max_rows: int) -> None:
        """
        Set the max audit log rows setting.
        
        Args:
            max_rows: Maximum number of audit rows to retain (0 means unlimited)
        """
        # Upsert the setting
        existing = self.db.fetch_one(
            "SELECT value FROM settings WHERE key = ?",
            ("max_audit_log_rows",)
        )
        if existing:
            self.db.execute(
                "UPDATE settings SET value = ? WHERE key = ?",
                (str(max_rows), "max_audit_log_rows")
            )
        else:
            self.db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                ("max_audit_log_rows", str(max_rows))
            )
    
    def prune_audit_log(self) -> int:
        """
        Prune audit log to respect max_audit_log_rows setting.
        
        Deletes the oldest audit rows to stay within the configured limit.
        Pruning is atomic: if any error occurs, all changes are rolled back.
        
        Returns:
            Number of rows pruned
        """
        max_rows = self.get_max_audit_log_rows()
        
        # If max_rows is 0, retention is unlimited - don't prune
        if max_rows <= 0:
            return 0
        
        # Count current rows
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM audit_log")
        current_count = result["count"] if result else 0
        
        if current_count <= max_rows:
            # Nothing to prune
            return 0
        
        # Calculate how many rows to delete
        to_delete = current_count - max_rows
        
        # Delete oldest rows atomically
        try:
            # Use execute_no_commit for atomic transaction
            cursor = self.db._connection.cursor()
            cursor.execute(
                """DELETE FROM audit_log 
                   WHERE id IN (
                       SELECT id FROM audit_log 
                       ORDER BY id ASC 
                       LIMIT ?
                   )""",
                (to_delete,)
            )
            self.db._connection.commit()
            return to_delete
        except Exception as e:
            # Rollback on any error
            self.db._connection.rollback()
            raise e
    
    def export_audit_log_csv(
        self,
        output_path: str,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None
    ) -> int:
        """
        Export audit log to CSV file.
        
        Args:
            output_path: File path for output CSV
            start_date: Optional start date filter (inclusive)
            end_date: Optional end date filter (inclusive)
        
        Returns:
            Number of rows exported
        """
        import csv
        from datetime import date
        
        # Build query with optional date filtering
        query = """
            SELECT id, action, table_name, record_id, details, user_name, 
                   timestamp, old_data, new_data, group_id, summary_data
            FROM audit_log
            WHERE 1=1
        """
        params = []
        
        if start_date:
            # Filter by timestamp (audit_log.timestamp is a TEXT field in ISO format)
            if isinstance(start_date, date):
                query += " AND DATE(timestamp) >= ?"
                params.append(start_date.isoformat())
        
        if end_date:
            if isinstance(end_date, date):
                query += " AND DATE(timestamp) <= ?"
                params.append(end_date.isoformat())
        
        query += " ORDER BY id ASC"
        
        # Fetch rows
        rows = self.db.fetch_all(query, tuple(params))
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'id', 'action', 'table_name', 'record_id', 'details', 'user_name',
                'timestamp', 'old_data', 'new_data', 'group_id', 'summary_data'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in rows:
                # Convert dict to plain dict (in case it's a sqlite3.Row)
                row_dict = dict(row)
                writer.writerow(row_dict)
        
        return len(rows)
