"""
Audit Service - Centralized audit logging for CRUD operations

Provides structured audit trail with JSON snapshots and operation grouping.
Supports atomic logging (within transactions) and undo/redo tracking.

Reference: Issue #92 - Audit Log + Undo/Redo + Soft Delete
"""
import json
import uuid
from typing import Optional, Dict, Any, List
from repositories.database import DatabaseManager


class AuditService:
    """Service for recording audit trail of CRUD operations"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
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
        self.db.log_audit(
            action="CREATE",
            table_name=table_name,
            record_id=record_id,
            details=f"Created {table_name} record",
            user_name=user_name,
            old_data=None,
            new_data=json.dumps(new_data, default=str),
            group_id=group_id,
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
        self.db.log_audit(
            action="UPDATE",
            table_name=table_name,
            record_id=record_id,
            details=f"Updated {table_name} record",
            user_name=user_name,
            old_data=json.dumps(old_data, default=str),
            new_data=json.dumps(new_data, default=str),
            group_id=group_id,
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
        self.db.log_audit(
            action="DELETE",
            table_name=table_name,
            record_id=record_id,
            details=f"Soft-deleted {table_name} record",
            user_name=user_name,
            old_data=json.dumps(old_data, default=str),
            new_data=None,
            group_id=group_id,
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
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query audit log with optional filters.
        
        Args:
            table_name: Filter by table name
            action: Filter by action type (CREATE, UPDATE, DELETE, UNDO, REDO, etc.)
            record_id: Filter by record ID
            group_id: Filter by group ID
            limit: Maximum number of records to return
        
        Returns:
            List of audit log entries as dictionaries
        """
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
