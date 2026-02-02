# Bug: Startup Crash on Corrupted Data + Partial Database Writes

## Problem

Two related critical issues:

1. **Startup crash before maintenance mode activates**: When corrupted data exists in the database (e.g., purchases with `remaining_amount > amount`), the app crashes during tab creation/data loading before the maintenance mode integrity check can present the user with recovery options.

2. **Partial database writes**: Database operations (purchase/redemption create/update/delete) could fail mid-operation after some writes completed, leaving the database in a corrupted state. Example: a purchase gets created but the subsequent FIFO rebuild fails, leaving inconsistent `remaining_amount` values.

### Evidence
Production database contained 3 corrupted purchases:
- Purchase 175: amount=$7.99, remaining_amount=$10.00
- Purchase 176: amount=$82.48, remaining_amount=$100.00  
- Purchase 177: amount=$82.48, remaining_amount=$100.00

These violated the model constraint `remaining_amount <= amount` and caused startup crash with:
```
ValueError: Remaining amount cannot exceed purchase amount
```

## Root Causes

1. **Startup timing**: `_check_data_integrity()` runs at line 33 in `MainWindow.__init__`, but `_create_tabs()` at line 109 loads all data and crashes before integrity violations can be handled gracefully.

2. **No transaction wrapping**: `AppFacade` methods like `create_purchase`, `update_purchase`, `delete_purchase`, and `create_redemption` performed multiple database operations without transaction boundaries, allowing partial writes on failure.

## Proposal

### Fix 1: Graceful Startup Error Handling
Wrap `_create_tabs()` in try/except in `MainWindow.__init__` to catch data loading errors (ValueError, etc.) and force maintenance mode entry:

```python
try:
    self._create_tabs()
except (ValueError, Exception) as e:
    print(f"[STARTUP] Data error detected during tab creation: {e}")
    self.maintenance_mode = True
    self.setWindowTitle("Sezzions - MAINTENANCE MODE")
    self._create_tabs()  # Re-create in maintenance mode
```

This ensures corrupted data triggers maintenance mode instead of crashing.

### Fix 2: Atomic Transaction Wrapping
Wrap all multi-step database operations in `AppFacade` with `self.db.transaction()` context manager:

- `create_purchase`: wrap purchase creation + FIFO rebuild + session recalc + link rebuild
- `update_purchase`: wrap purchase update + conditional rebuilds
- `delete_purchase`: wrap purchase deletion + rebuilds
- `create_redemption`: wrap redemption creation + FIFO rebuild + session recalc + link rebuild

This guarantees operations either fully succeed or fully roll back—no partial writes.

### Additional Fix: Remove Orphaned Code
`EndSessionDialog.collect_data()` references `self.tax_rate_edit` which doesn't exist in the dialog's `__init__`. This is leftover code from template copying. Remove the tax withholding block from `collect_data`.

## Scope

**Files to modify:**
- `ui/main_window.py`: wrap tab creation in try/except
- `ui/tabs/game_sessions_tab.py`: remove orphaned tax_rate_edit reference
- `app_facade.py`: add transaction wrapping to 4 methods
- `docs/status/CHANGELOG.md`: add entry
- `docs/PROJECT_SPEC.md`: document transaction guarantees

**Out of scope:**
- Fixing existing corrupted data (user must run recalculate in maintenance mode)
- Adding transactions to all other operations (focus on primary data entry operations)

## Acceptance Criteria

1. App with corrupted purchase data starts successfully in maintenance mode instead of crashing
2. User sees warning banner and restricted access to Setup tab only
3. All purchase/redemption create/update/delete operations use transactions
4. Operations fail atomically (no partial writes on error)
5. EndSessionDialog no longer references missing tax_rate_edit field

## Test Plan

### Manual Testing
1. Create corrupted purchase: `UPDATE purchases SET remaining_amount = amount + 10 WHERE id = X`
2. Launch app—should enter maintenance mode, not crash
3. Verify warning banner and Setup-only access
4. Use Tools > Full Recalculation to fix corruption
5. Restart app—should launch normally

### Integration Testing
- Add test: create purchase, force exception mid-transaction, verify rollback (no partial data)
- Add test: corrupted data triggers maintenance mode on startup

## Notes

- This is an urgent production bug fix completed interactively
- Corrupted data discovered during user testing of "End Session" feature
- Transaction wrapping prevents recurrence but doesn't auto-fix existing corruption
- User must manually recalculate or restore from backup to repair existing corruption
