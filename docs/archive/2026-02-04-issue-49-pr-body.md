## Problem

When editing a purchase, the system computes an "expected balance" to validate the user-entered starting balance. Previously, this used a "1 second before purchase" time cutoff to avoid including the edited purchase in its own expected balance calculation.

**Edge case:** When two purchases share the exact same timestamp (hour:minute:second), the 1-second cutoff was ambiguous and could incorrectly include or exclude purchases, leading to false positives or false negatives in the balance check.

Closes #49

## Solution

Replaced the time-epsilon approach with an explicit `exclude_purchase_id` parameter that threads through the balance computation call chain:

1. **Service layer** (`GameSessionService.compute_expected_balances()`):
   - Added `exclude_purchase_id: Optional[int] = None` parameter
   - Skip purchase by ID check: `if exclude_purchase_id is not None and p.id == exclude_purchase_id: continue`

2. **Facade layer** (`AppFacade.compute_expected_balances()`):
   - Added `exclude_purchase_id` parameter with documentation
   - Pass through to service layer

3. **UI layer** (`PurchasesTab._update_balance_check()`):
   - Pass `exclude_purchase_id = self.purchase.id if self.purchase else None` when computing expected balance
   - Changed to pass actual purchase date/time instead of "1 second before" cutoff
   - **Removed** obsolete `_balance_check_cutoff()` helper function

## Behavior

At a given timestamp, all purchases/redemptions at that timestamp are included in the expected balance calculation **EXCEPT** the one being edited. This ensures stable, deterministic balance checks even when multiple purchases share the same timestamp.

## Test Coverage

Added comprehensive regression test suite in `tests/integration/test_issue_49_purchase_exclusion.py`:

1. **Same-timestamp scenario (primary fix)**: Two purchases at 10:30:00, editing either one correctly excludes only that purchase
2. **Different-timestamp scenario**: Verifies editing a purchase doesn't affect balance checks for other purchases at different times
3. **No exclusion scenario**: Verifies that when `exclude_purchase_id=None`, all purchases are included (existing behavior preserved)

All 622 tests pass, including the 4 new regression tests.

## Documentation

- Updated `docs/status/CHANGELOG.md` with entry `2026-02-04-02`
- Updated `docs/PROJECT_SPEC.md` section 4.2 (new section on "Expected Balance Checks") documenting the ID-based exclusion pattern

## Files Changed

- `services/game_session_service.py` (3 lines: parameter + skip logic)
- `app_facade.py` (2 lines: parameter + pass-through)
- `ui/tabs/purchases_tab.py` (removed 18 lines: `_balance_check_cutoff()` function; changed 2 lines: balance check call)
- `tests/integration/test_issue_49_purchase_exclusion.py` (new file, 157 lines)
- `docs/PROJECT_SPEC.md` (+17 lines: new section 4.2)
- `docs/status/CHANGELOG.md` (+19 lines: changelog entry)

## Review Notes

This is a surgical fix that replaces a time-based approximation with explicit ID-based exclusion. The change is minimal, well-tested, and documented. The core accounting logic remains unchanged—only the exclusion mechanism for balance checks is improved.
