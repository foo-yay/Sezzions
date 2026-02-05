## Summary

Implements Issue #66: Purchase dialogs now use delta-based extra SC warnings and display the basis period purchase chain.

## Changes

### 1. Delta-Based Balance Warnings

**Problem:** Purchase dialogs showed the same "extra SC" warning repeatedly for each purchase in a basis period, even when the extra was persistent (not new). This created warning fatigue.

**Solution:** 
- Compare current purchase's `total_extra` against the previous purchase in the same basis period
- Only warn if:
  1. `total_extra < 0` (negative always warns - indicates tracked loss or missing SC)
  2. `delta_extra > 0` (positive increase - indicates new untracked wins/freebies)
- Warning dialog shows both `total_extra` and `delta` when a previous purchase exists

**Basis Period:** Bounded by FULL redemptions (`more_remaining=0`). Period start = instant after most recent FULL redemption.

### 2. Basis Period Purchases Display

**New UI Feature:**
- Purchase View dialog's Related tab now includes a "Basis Period Purchases" section
- Shows all purchases in the current basis period with:
  - Date/time
  - Purchase amount
  - SC received
  - Post-purchase SC balance
  - Current purchase indicator (✓)

### 3. Facade Helper Methods

Added to `AppFacade`:
- `get_basis_period_start_for_purchase()`: finds most recent FULL redemption datetime before a purchase
- `get_basis_period_purchases()`: returns purchases in the same basis period, ordered by (date, time, id)
- `compute_purchase_total_extra()`: computes total_extra given entered balance values (not currently used, available for future)

### 4. Documentation Updates

- **CHANGELOG.md**: Added entry 2026-02-05-04 documenting the feature
- **PROJECT_SPEC.md**: Added "Delta-based warnings" section under Expected Balance Checks

## Testing

- ✅ All 645 existing tests pass
- ⚠️ No new scenario-based tests added yet (follow-up required per Agent Quality Bar)

## Files Changed

- `app_facade.py`: Added 3 new helper methods for basis period logic
- `ui/tabs/purchases_tab.py`: 
  - Updated `_add_purchase()` balance check with delta logic
  - Updated `_edit_purchase()` balance check with delta logic
  - Added basis period purchases section to `_create_related_tab()`
- `docs/status/CHANGELOG.md`: Added changelog entry
- `docs/PROJECT_SPEC.md`: Added delta-based warnings documentation

## Follow-up Work (Pitfalls / Not in Scope)

1. **Scenario-based tests needed:** Add tests for:
   - Happy path: delta warning suppressed when extra is persistent
   - Edge case: first purchase in period (no previous purchase)
   - Edge case: negative total_extra always warns
   - Edge case: positive delta increase triggers warning
   - Invariant: basis period boundaries defined correctly by FULL redemptions

2. **Performance consideration:** Current implementation fetches and processes all purchases/redemptions for basis period calculation. For users with many purchases, this could be optimized with SQL queries instead of in-memory filtering.

3. **UX refinement:** Warning dialog could be enhanced to show a mini-table of recent purchases in the period directly in the warning, rather than requiring users to open the View dialog.

## Related Issues

Closes #66
