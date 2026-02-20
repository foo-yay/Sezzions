"""
Undo/Redo Service - In-order undo/redo with persistent stacks

Provides Excel-like undo/redo functionality backed by persistent storage.
Uses audit log snapshots to reconstruct operation state and rollback atomically.

Reference: Issue #92 - Audit Log + Undo/Redo + Soft Delete
"""
import json
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import date, datetime
from repositories.database import DatabaseManager
from services.audit_service import AuditService
from models.purchase import Purchase
from models.redemption import Redemption
from models.game_session import GameSession


class UndoOperation:
    """Represents a single undoable operation"""
    def __init__(self, group_id: str, description: str, timestamp: str):
        self.group_id = group_id
        self.description = description
        self.timestamp = timestamp


class UndoRedoService:
    """Service for in-order undo/redo with persistent stacks"""
    
    # Model mapping for reconstruction from JSON
    MODEL_MAP = {
        'purchases': Purchase,
        'redemptions': Redemption,
        'game_sessions': GameSession
    }
    
    # Default maximum undo operations (Issue #95)
    DEFAULT_MAX_UNDO_OPERATIONS = 100
    
    def __init__(self, db: DatabaseManager, audit_service: AuditService, post_operation_callback=None, repositories=None):
        self.db = db
        self.audit_service = audit_service
        self.post_operation_callback = post_operation_callback  # Called after undo/redo to trigger recalculations
        self.repositories = repositories or {}  # Map of table_name -> repository instance
        self._undo_stack = []  # List of UndoOperation
        self._redo_stack = []  # List of UndoOperation
        self._max_undo_operations = self.DEFAULT_MAX_UNDO_OPERATIONS  # Issue #95
        self._load_stacks()
        self._load_max_undo_setting()
    
    def _load_stacks(self) -> None:
        """Load undo/redo stacks from persistent settings"""
        # Fetch undo stack from settings
        undo_json = self.db.fetch_one("SELECT value FROM settings WHERE key = ?", ("undo_stack",))
        if undo_json and undo_json['value']:
            try:
                undo_data = json.loads(undo_json['value'])
                self._undo_stack = [
                    UndoOperation(op['group_id'], op['description'], op['timestamp'])
                    for op in undo_data
                ]
            except (json.JSONDecodeError, KeyError) as e:
                self._undo_stack = []
        
        # Fetch redo stack from settings
        redo_json = self.db.fetch_one("SELECT value FROM settings WHERE key = ?", ("redo_stack",))
        if redo_json and redo_json['value']:
            try:
                redo_data = json.loads(redo_json['value'])
                self._redo_stack = [
                    UndoOperation(op['group_id'], op['description'], op['timestamp'])
                    for op in redo_data
                ]
            except (json.JSONDecodeError, KeyError) as e:
                self._redo_stack = []
    
    def _load_max_undo_setting(self) -> None:
        """Load max_undo_operations setting from database (Issue #95)"""
        result = self.db.fetch_one("SELECT value FROM settings WHERE key = ?", ("max_undo_operations",))
        if result and result['value']:
            try:
                self._max_undo_operations = int(result['value'])
            except (ValueError, TypeError):
                self._max_undo_operations = self.DEFAULT_MAX_UNDO_OPERATIONS
        else:
            self._max_undo_operations = self.DEFAULT_MAX_UNDO_OPERATIONS

    def _is_in_transaction(self) -> bool:
        """Return True when the underlying sqlite connection already has an open transaction."""
        connection = getattr(self.db, "_connection", None)
        if connection is None:
            return False
        return bool(getattr(connection, "in_transaction", False))
    
    def _save_stacks(self, *, auto_commit: bool = True) -> None:
        """Persist undo/redo stacks to settings table"""
        undo_data = [
            {"group_id": op.group_id, "description": op.description, "timestamp": op.timestamp}
            for op in self._undo_stack
        ]
        redo_data = [
            {"group_id": op.group_id, "description": op.description, "timestamp": op.timestamp}
            for op in self._redo_stack
        ]
        
        # Upsert undo_stack
        if auto_commit:
            self.db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("undo_stack", json.dumps(undo_data))
            )
        else:
            self.db.execute_no_commit(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("undo_stack", json.dumps(undo_data))
            )
        
        # Upsert redo_stack
        if auto_commit:
            self.db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("redo_stack", json.dumps(redo_data))
            )
        else:
            self.db.execute_no_commit(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("redo_stack", json.dumps(redo_data))
            )
    
    def can_undo(self) -> bool:
        """Check if undo is available"""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available"""
        return len(self._redo_stack) > 0
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of the next undo operation"""
        if self.can_undo():
            return self._undo_stack[-1].description
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of the next redo operation"""
        if self.can_redo():
            return self._redo_stack[-1].description
        return None
    
    def push_operation(self, group_id: str, description: str, timestamp: str) -> None:
        """
        Push a new operation onto the undo stack.
        
        This is called after a successful CRUD operation to make it undoable.
        Clears the redo stack (Excel-like behavior).
        
        Args:
            group_id: UUID of the operation group (from audit log)
            description: Human-readable description
            timestamp: ISO timestamp of the operation
        """
        self._undo_stack.append(UndoOperation(group_id, description, timestamp))
        self._redo_stack.clear()  # Invalidate redo after new operation
        
        # Auto-prune if exceeds max (Issue #95)
        if self._max_undo_operations > 0 and len(self._undo_stack) > self._max_undo_operations:
            self._prune_to_limit(self._max_undo_operations)

        self._save_stacks(auto_commit=not self._is_in_transaction())
    
    def get_max_undo_operations(self) -> int:
        """Get the current max undo operations limit (Issue #95)"""
        return self._max_undo_operations
    
    def set_max_undo_operations(self, max_operations: int) -> None:
        """
        Set the maximum number of undo operations to retain (Issue #95).
        
        This will prune older operations immediately if the new limit is lower.
        Pruning removes JSON snapshots from audit_log but preserves metadata.
        
        Args:
            max_operations: Maximum operations (0 = disable undo/redo)
        """
        if max_operations < 0:
            raise ValueError("max_undo_operations must be >= 0")
        
        self._max_undo_operations = max_operations
        
        # Persist setting
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("max_undo_operations", str(max_operations))
        )
        
        # Prune immediately if needed
        self._prune_to_limit(max_operations)
    
    def _prune_to_limit(self, max_operations: int) -> None:
        """
        Prune undo/redo stacks and audit snapshots to the specified limit (Issue #95).
        
        This operation is atomic (uses a transaction).
        
        Args:
            max_operations: Maximum operations to retain
        """
        if max_operations == 0:
            # Prune everything
            pruned_group_ids = [op.group_id for op in self._undo_stack] + [op.group_id for op in self._redo_stack]
            self._undo_stack.clear()
            self._redo_stack.clear()
        else:
            # Prune old operations beyond the limit
            pruned_group_ids = []
            
            # Prune undo stack
            if len(self._undo_stack) > max_operations:
                pruned = self._undo_stack[:-max_operations]
                pruned_group_ids.extend([op.group_id for op in pruned])
                self._undo_stack = self._undo_stack[-max_operations:]
            
            # Prune redo stack (keep only if total within limit)
            total_operations = len(self._undo_stack) + len(self._redo_stack)
            if total_operations > max_operations:
                redo_allowed = max_operations - len(self._undo_stack)
                if redo_allowed < len(self._redo_stack):
                    pruned = self._redo_stack[redo_allowed:]
                    pruned_group_ids.extend([op.group_id for op in pruned])
                    self._redo_stack = self._redo_stack[:redo_allowed]
        
        in_transaction = self._is_in_transaction()

        # Prune audit snapshots in a transaction (or the caller's existing transaction)
        if pruned_group_ids:
            try:
                if in_transaction:
                    for group_id in pruned_group_ids:
                        self.db.execute_no_commit(
                            "UPDATE audit_log SET old_data = NULL, new_data = NULL WHERE group_id = ?",
                            (group_id,)
                        )
                    self._save_stacks(auto_commit=False)
                else:
                    with self.db.transaction():
                        for group_id in pruned_group_ids:
                            self.db.execute_no_commit(
                                "UPDATE audit_log SET old_data = NULL, new_data = NULL WHERE group_id = ?",
                                (group_id,)
                            )
                        self._save_stacks(auto_commit=False)
            except Exception as e:
                # Transaction rolled back; reload stacks to restore consistency
                self._load_stacks()
                raise RuntimeError(f"Failed to prune undo history: {e}")
        else:
            # No pruning needed, just save stacks
            self._save_stacks(auto_commit=not in_transaction)
    
    def undo(self) -> Optional[str]:
        """
        Undo the last operation by reversing changes from audit log.
        
        Returns:
            Description of the undone operation, or None if nothing to undo
        """
        if not self.can_undo():
            return None
        
        operation = self._undo_stack.pop()
        
        # Fetch all audit entries for this group_id
        audit_entries = self.audit_service.get_audit_log(group_id=operation.group_id, limit=1000)
        
        if not audit_entries:
            # No audit data found; push back to stack
            self._undo_stack.append(operation)
            self._save_stacks()
            return None
        
        try:
            # Begin transaction
            with self.db.transaction():
                # Reverse operations in LIFO order (last change first)
                for entry in audit_entries:
                    self._reverse_audit_entry(entry)
                
                # Log the undo operation
                affected_records = [
                    {
                        "table_name": e['table_name'],
                        "record_id": e['record_id'],
                        "old_data": e.get('old_data'),
                        "new_data": e.get('new_data')
                    }
                    for e in audit_entries
                ]
                
                undo_group_id = self.audit_service.generate_group_id()
                self.audit_service.log_undo(
                    description=f"Undid: {operation.description}",
                    affected_records=affected_records,
                    group_id=undo_group_id,
                    auto_commit=False  # Within transaction
                )
            
            # Move to redo stack
            self._redo_stack.append(operation)
            self._save_stacks()
            
            # Trigger post-operation callback for recalculations (after transaction commits)
            if self.post_operation_callback:
                try:
                    self.post_operation_callback(operation='undo', audit_entries=audit_entries)
                except Exception as e:
                    # Don't fail undo if recalculation fails; log and continue
                    print(f"Warning: Post-undo recalculation failed: {e}")
            
            return operation.description
        
        except Exception as e:
            # Rollback happened; restore stack state
            self._undo_stack.append(operation)
            self._save_stacks()
            raise RuntimeError(f"Undo failed: {e}")
    
    def redo(self) -> Optional[str]:
        """
        Redo the last undone operation by replaying changes from audit log.
        
        Returns:
            Description of the redone operation, or None if nothing to redo
        """
        if not self.can_redo():
            return None
        
        operation = self._redo_stack.pop()
        
        # Fetch all audit entries for this group_id
        audit_entries = self.audit_service.get_audit_log(group_id=operation.group_id, limit=1000)
        
        if not audit_entries:
            # No audit data found; push back to stack
            self._redo_stack.append(operation)
            self._save_stacks()
            return None
        
        try:
            # Begin transaction
            with self.db.transaction():
                # Replay operations in FIFO order (first change first)
                for entry in reversed(audit_entries):
                    self._replay_audit_entry(entry)
                
                # Log the redo operation
                affected_records = [
                    {
                        "table_name": e['table_name'],
                        "record_id": e['record_id'],
                        "old_data": e.get('old_data'),
                        "new_data": e.get('new_data')
                    }
                    for e in audit_entries
                ]
                
                redo_group_id = self.audit_service.generate_group_id()
                self.audit_service.log_redo(
                    description=f"Redid: {operation.description}",
                    affected_records=affected_records,
                    group_id=redo_group_id,
                    auto_commit=False  # Within transaction
                )
            
            # Move back to undo stack
            self._undo_stack.append(operation)
            self._save_stacks()
            
            # Trigger post-operation callback for recalculations (after transaction commits)
            if self.post_operation_callback:
                try:
                    self.post_operation_callback(operation='redo', audit_entries=audit_entries)
                except Exception as e:
                    # Don't fail redo if recalculation fails; log and continue
                    print(f"Warning: Post-redo recalculation failed: {e}")
            
            return operation.description
        
        except Exception as e:
            # Rollback happened; restore stack state
            self._redo_stack.append(operation)
            self._save_stacks()
            raise RuntimeError(f"Redo failed: {e}")
    
    def _reverse_audit_entry(self, entry: Dict[str, Any]) -> None:
        """        Reverse a single audit log entry.
        
        For CREATE: soft-delete the record
        For UPDATE: restore old_data
        For DELETE: restore the record (clear deleted_at)
        """
        action = entry['action']
        table_name = entry['table_name']
        record_id = entry['record_id']
        repo = self.repositories.get(table_name)
        
        if action == "CREATE":
            # Reverse create: soft-delete the record
            if repo and hasattr(repo, 'delete'):
                repo.delete(record_id)
            else:
                # Fallback to raw SQL if no repository available
                self.db.execute(
                    f"UPDATE {table_name} SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (record_id,)
                )
        
        elif action == "UPDATE":
            # Reverse update: restore old_data
            if entry.get('old_data'):
                self._apply_update(table_name, record_id, entry['old_data'], repo)
        
        elif action == "DELETE":
            # Reverse delete: restore full record state from old_data, then clear deleted_at
            if entry.get('old_data'):
                # Parse old_data if it's a JSON string
                import json
                old_data = entry['old_data']
                if isinstance(old_data, str):
                    old_data = json.loads(old_data)
                
                # First restore the old field values (deleted record still exists with old data)
                self._apply_update(table_name, record_id, old_data, repo)
            
            # Then clear deleted_at to make record visible again
            if repo and hasattr(repo, 'restore'):
                repo.restore(record_id)
            else:
                # Fallback to raw SQL if no repository available
                self.db.execute(
                    f"UPDATE {table_name} SET deleted_at = NULL WHERE id = ?",
                    (record_id,)
                )
    
    def _replay_audit_entry(self, entry: Dict[str, Any]) -> None:
        """
        Replay a single audit log entry (for redo).
        
        For CREATE: clear deleted_at (un-soft-delete)
        For UPDATE: restore new_data
        For DELETE: re-apply soft delete
        """
        action = entry['action']
        table_name = entry['table_name']
        record_id = entry['record_id']
        repo = self.repositories.get(table_name)
        
        if action == "CREATE":
            # Replay create: clear deleted_at
            if repo and hasattr(repo, 'restore'):
                repo.restore(record_id)
            else:
                # Fallback to raw SQL if no repository available
                self.db.execute(
                    f"UPDATE {table_name} SET deleted_at = NULL WHERE id = ?",
                    (record_id,)
                )
        
        elif action == "UPDATE":
            # Replay update: restore new_data
            if entry.get('new_data'):
                self._apply_update(table_name, record_id, entry['new_data'], repo)
        
        elif action == "DELETE":
            # Replay delete: re-soft-delete
            if repo and hasattr(repo, 'delete'):
                repo.delete(record_id)
            else:
                # Fallback to raw SQL if no repository available
                self.db.execute(
                    f"UPDATE {table_name} SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (record_id,)
                )
    
    def _apply_update(self, table_name: str, record_id: int, data: Dict[str, Any], repo=None) -> None:
        """
        Apply an UPDATE by reconstructing the full model object.
        
        This ensures all model validation, type coercion, and business logic is applied.
        Falls back to raw SQL only for tables without model definitions.
        """
        model_data = self._prepare_model_data(data.copy())
        model_class = self.MODEL_MAP.get(table_name)
        if table_name == 'account_adjustments':
            model_class = None
        
        if model_class and repo and hasattr(repo, 'update'):
            # Reconstruct full model from snapshot
            # Remove metadata fields that aren't in the model
            # (deleted_at is in DB but not in model classes)
            model_data.pop('deleted_at', None)
            
            # For game sessions, exclude calculated/derived fields that will be recomputed
            # by the post-operation recalculation callback (Issue #97 undo/redo fix)
            if table_name == 'game_sessions':
                calculated_fields = {
                    'delta_total', 'delta_redeem', 'session_basis',
                    'basis_consumed', 'net_taxable_pl', 'expected_start_total',
                    'expected_start_redeemable', 'discoverable_sc'
                }
                for field in calculated_fields:
                    model_data.pop(field, None)
            
            # Model's __post_init__ will validate and coerce types
            model = model_class(**model_data)
            
            # Use repository update (gets validation, type safety, consistency)
            repo.update(model)
        else:
            # Fallback to raw SQL for tables without models (e.g., lookup tables)
            skip_fields = {'id', 'created_at', 'updated_at', 'deleted_at'}
            if table_name == 'account_adjustments':
                # For adjustment undo/redo we must restore deleted_at from snapshot,
                # otherwise soft-delete state can drift from audited state.
                skip_fields.remove('deleted_at')
            fields = {k: v for k, v in model_data.items() if k not in skip_fields}
            
            if not fields:
                return
            
            set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
            values = list(fields.values())
            values.append(record_id)
            
            query = f"UPDATE {table_name} SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            self.db.execute(query, tuple(values))
    
    def _prepare_model_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare JSON snapshot data for model reconstruction.
        
        Handles type coercion for:
        - Decimal fields (stored as strings in JSON)
        - Date fields (stored as ISO strings)
        - Datetime fields (stored as ISO strings)
        """
        result = {}
        
        for key, value in data.items():
            if value is None:
                result[key] = value
            elif key == 'type':
                if isinstance(value, str) and value.startswith('AdjustmentType.'):
                    result[key] = value.split('.', 1)[1]
                else:
                    result[key] = value
            # Date fields: purchase_date, redemption_date, session_date, end_date, receipt_date
            elif key.endswith('_date') or key == 'session_date':
                if isinstance(value, str):
                    result[key] = datetime.strptime(value, '%Y-%m-%d').date()
                else:
                    result[key] = value
            # Datetime fields: created_at, updated_at, deleted_at
            elif key.endswith('_at'):
                if isinstance(value, str) and value:
                    result[key] = datetime.fromisoformat(value)
                else:
                    result[key] = value
            # Decimal fields: amount, fees, cost_basis, balances, etc.
            elif key in {'amount', 'sc_received', 'starting_sc_balance', 'cashback_earned', 
                        'remaining_amount', 'fees', 'cost_basis', 'taxable_profit',
                        'starting_balance', 'ending_balance', 'starting_redeemable', 'ending_redeemable',
                        'purchases_during', 'redemptions_during', 'wager_amount',
                        'expected_start_total', 'expected_start_redeemable', 'discoverable_sc',
                        'delta_total', 'delta_redeem', 'session_basis', 'basis_consumed',
                        'net_taxable_pl', 'profit_loss',
                        'taxable_earnings', 'ending_basis'}:
                if isinstance(value, (str, int, float)):
                    result[key] = Decimal(str(value))
                else:
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def clear_stacks(self) -> None:
        """Clear both undo and redo stacks (for testing or reset)"""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._save_stacks()
