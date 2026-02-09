# Audit Log + Undo/Redo + Soft Delete (Issue #92)

## Summary

Implements comprehensive audit logging, undo/redo functionality, and soft delete pattern for purchases, redemptions, and game sessions.

## Implementation Details

### Schema Changes (Tasks 1-2)
- **audit_log expansion**: Added `old_data` (JSON TEXT), `new_data` (JSON TEXT), `group_id` (TEXT UUID) columns + `idx_audit_group` index
- **Soft delete columns**: Added `deleted_at` (TIMESTAMP NULL) + `idx_*_deleted` indexes to `purchases`, `redemptions`, `game_sessions`
- **Migration pattern**: Idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS` guarded by `PRAGMA table_info()`

### Services Layer (Tasks 3-4)
- **AuditService**: Structured logging with JSON snapshots, operation grouping via `group_id`, `auto_commit` flag
  - Methods: `log_create/update/delete/restore/undo/redo`, `get_audit_log(filters)`, `generate_group_id()`
- **UndoRedoService**: Persistent stacks (stored in settings table), atomic rollback, Excel-like behavior
  - `undo()`: Reverses audit entries in LIFO order
  - `redo()`: Replays audit entries in FIFO order
  - New operations clear redo stack

### Repository Layer (Task 2)
- **Soft delete pattern**: All `delete()` methods → `UPDATE SET deleted_at = CURRENT_TIMESTAMP`
- **restore()**: Clears `deleted_at` to NULL
- **Query filters**: All `get_*()` queries filter `WHERE deleted_at IS NULL`
- **FIFO integrity**: `get_available_for_fifo()` excludes soft-deleted purchases

### UI Layer (Tasks 5-7)
- **Menu actions**: "Edit → Undo (Ctrl+Z)", "Edit → Redo (Ctrl+Shift+Z)", "Tools → View Audit Log…"
- **Dynamic action text**: Updates with operation descriptions (e.g., "Undo CREATE purchase #123")
- **Tools tab section**: Collapsible "📋 Audit Log" with helper text
- **Audit Log Viewer Dialog**: Full browser with filters (table/action/limit), split view, color-coded actions

### Testing (Tasks 8-9)
- **Unit tests**: 15 tests (soft delete behavior, restore, FIFO exclusion, JSON snapshots, group_id, filters, auto_commit)
- **Headless UI smoke tests**: 8 tests (menu actions, handlers, MainWindow instantiation)
- **All tests pass**: 787/787 (764 existing + 23 new)

### Documentation (Task 10)
- Updated `docs/DATABASE_DESIGN.md`: audit_log schema, soft delete behavior for purchases/redemptions/game_sessions
- Updated `docs/status/CHANGELOG.md`: Full Issue #92 entry with all commits

## Files Changed

**Schema/Repositories:**
- `repositories/database.py`
- `repositories/purchase_repository.py`
- `repositories/redemption_repository.py`
- `repositories/game_session_repository.py`

**Services:**
- `services/audit_service.py` (NEW)
- `services/undo_redo_service.py` (NEW)

**UI:**
- `ui/main_window.py`
- `ui/tabs/tools_tab.py`
- `ui/audit_log_viewer_dialog.py` (NEW)

**Tests:**
- `tests/unit/test_soft_delete.py` (NEW)
- `tests/unit/test_audit_service.py` (NEW)
- `tests/ui/test_issue_92_ui_smoke.py` (NEW)

**Documentation:**
- `docs/DATABASE_DESIGN.md`
- `docs/status/CHANGELOG.md`

## Commits

1. `59b2502`: Schema layer (deleted_at + indexes)
2. `5b50b1f`: Repository soft delete + restore methods
3. `2d36227`: Audit schema expansion
4. `658b5a6`: AuditService implementation
5. `8062abb`: UndoRedoService implementation
6. `2dbcf1e`: UI menu actions
7. `0971198`: Tools tab section
8. `1723415`: Audit Log Viewer dialog
9. `1fde0ff`: Comprehensive tests
10. `40cf5a0`: Headless UI smoke tests
11. `83cd7e4`: Documentation updates

## Testing

```bash
pytest -q
# Result: 787 passed, 305 warnings in 41.13s
```

All existing tests pass. New tests cover:
- Soft delete exclusion from queries
- Restore functionality
- FIFO correctness with soft-deleted purchases
- Audit log JSON snapshot storage/retrieval
- Operation grouping via group_id
- Audit log filters
- Menu action wiring
- MainWindow instantiation

## Acceptance Criteria

- [x] Soft delete pattern implemented for purchases, redemptions, game_sessions
- [x] Audit log captures full JSON snapshots (old_data, new_data)
- [x] Undo/Redo functionality with persistent stacks
- [x] UI menu actions (Ctrl+Z, Ctrl+Shift+Z)
- [x] Audit Log Viewer dialog with filters
- [x] Tools tab section for quick access
- [x] Comprehensive test coverage (unit + UI smoke tests)
- [x] Documentation updated

## Notes

- Follows agent workflow: Red → Green → Review (tests written first)
- All queries automatically exclude soft-deleted records
- Undo/redo stacks persist across app restarts (stored in settings table)
- Audit log supports operation grouping for multi-table transactions
- FIFO integrity maintained (soft-deleted purchases excluded from basis calculations)

Closes #92
