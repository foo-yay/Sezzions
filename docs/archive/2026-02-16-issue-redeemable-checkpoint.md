## Problem

When a user makes a purchase after a session that has established a redeemable balance, the Unrealized tab incorrectly resets the redeemable_sc to 0.

**Example:**
1. User ends session with total_sc=150, redeemable_sc=100
2. User makes purchase with starting_sc_balance=150
3. Unrealized tab shows: total_sc=200 (correct), redeemable_sc=0 (WRONG - should be 100)

**Root Cause:**
Purchase checkpoints currently only store `starting_sc_balance` (total SC) but not redeemable SC. When the purchase becomes the most recent checkpoint, the unrealized position calculation uses redeemable_sc=0 from the purchase instead of carrying forward the value from the previous session.

## Proposed Solution

Add `starting_redeemable_balance` field to purchases table and auto-populate it at purchase creation time using the existing `compute_expected_balances` logic.

**Benefits:**
- Simple, clean implementation
- Follows existing pattern of `starting_sc_balance`
- Leverages existing `compute_expected_balances` method
- Automatically handles redemptions between checkpoints
- No runtime lookups required

## Scope

### Schema Changes
- Add `starting_redeemable_balance DECIMAL(10,2) DEFAULT 0.00` to `purchases` table

### Code Changes
1. **Database migration** (`repositories/database.py`):
   - Add column to purchases table migration

2. **Auto-populate on create** (`services/purchase_service.py`):
   - Call `compute_expected_balances` to get redeemable at purchase time
   - Store in `starting_redeemable_balance`

3. **Update expected balances logic** (`services/game_session_service.py`):
   - When applying purchases, also update `expected_redeemable` from stored snapshot

4. **Update checkpoint query** (`repositories/unrealized_position_repository.py`):
   - Use `starting_redeemable_balance` instead of hardcoded 0

5. **Data backfill**:
   - One-time migration to populate existing purchases with redeemable values

### Testing
- Test: Purchase after session preserves redeemable balance
- Test: Redemption between purchases correctly reduces redeemable
- Test: Multiple purchases back-to-back reference correct checkpoints
- Test: First purchase ever has redeemable=0

## Acceptance Criteria

- [ ] Schema migration adds `starting_redeemable_balance` column
- [ ] Creating purchase auto-populates redeemable from `compute_expected_balances`
- [ ] Unrealized positions use stored redeemable instead of 0
- [ ] Existing purchases backfilled with correct redeemable values
- [ ] All existing tests pass (892 tests)
- [ ] New integration tests verify fix
- [ ] Changelog updated
- [ ] PROJECT_SPEC.md updated

## Test Plan

1. Start session, end with redeemable balance
2. Make purchase with starting_sc_balance
3. Verify Unrealized tab shows correct redeemable (not 0)
4. Make redemption, then another purchase
5. Verify second purchase has correct redeemable (minus redemption)
