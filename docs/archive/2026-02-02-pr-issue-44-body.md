## Summary
Fix for Issue #44: The Unrealized tab now reflects purchases and redemptions that occur after the most recent completed session, providing a "mostly accurate" current view of each open position.

## Problem
Before this fix, once a site/user had any completed sessions, the **Current SC / Current Value / Unrealized P/L** columns would remain "stuck" at the last session's ending balances, even after new purchases or redemptions. Only the **Basis** column updated, making the P/L calculations appear stale and confusing.

## Root Cause
`UnrealizedPositionRepository.get_all_positions()` pulled `current_sc` directly from the most recent session's `ending_redeemable` / `ending_balance` and ignored all subsequent transactions (purchases/redemptions after that session).

## Solution
Modified the repository to estimate current balances by:
1. Taking the last session's ending balances as a baseline
2. Adding purchases that occurred after the session
3. Subtracting redemptions that occurred after the session

**Formula:**
- `estimated_redeemable_sc = last_session_ending_redeemable + purchases_since - redemptions_since`
- `current_value = estimated_redeemable_sc * sc_rate`
- `unrealized_pl = current_value - remaining_basis`

This provides a "mostly accurate" real-time view (freebies/bonuses aren't tracked in real-time, but known transactions are incorporated).

## Changes Made
- **repositories/unrealized_position_repository.py**: Updated `get_all_positions()` to incorporate transactions after last session
- **ui/tabs/unrealized_tab.py**: Updated column headers for clarity:
  - "Purchase Basis" → "Remaining Basis"
  - "Current SC" → "Current Redeemable SC"
  - "Unrealized P/L" → "Est. Unrealized P/L"
- **tests/integration/test_issue_44_unrealized_live_balances.py**: Added 6 comprehensive integration tests
- **docs/status/CHANGELOG.md**: Added entry 2026-02-02-05
- **docs/PROJECT_SPEC.md**: Updated Cashflow P/L section with Issue #44 note

## Testing
Added 6 new integration tests covering:
- Purchase after session updates current SC
- Redemption after session updates current SC
- Multiple transactions after session
- No sessions (purchases only)
- Last activity tracking from most recent transaction
- Basis calculation invariants

**All 597 tests passing** (591 original + 6 new)

## Acceptance Criteria Met
✅ After adding a purchase for a site/user with existing session history, the Unrealized tab updates Current SC estimates (not just basis)
✅ After completing a session, the Unrealized tab reflects new session ending balances
✅ Estimated Unrealized P/L uses redeemable balance: `(estimated_redeemable_sc * sc_rate) - remaining_basis`
✅ Existing behavior around notes and close-balance filtering remains unchanged

## Pitfalls / Follow-ups
- The estimate won't incorporate bonuses/freebies; documented as "Estimated" in column headers
- If perfect "current" balances are needed long-term, may require derived running-balance table or explicit balance events
