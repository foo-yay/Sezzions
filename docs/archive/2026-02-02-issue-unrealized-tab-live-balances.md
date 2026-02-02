# Issue: Unrealized tab values not reflecting recent purchases (and clarify semantics)

## Problem
Values on the **Unrealized** tab do not appear to incorporate *recent purchases* into the **Current SC / Current Value / Unrealized P/L** columns once a site/user has any completed sessions.

In practice:
- **Basis** updates (because it sums remaining purchase basis).
- **Current SC / Value / P/L** can remain “stuck” at the last ended session balance, even after new purchases.

This makes the Unrealized tab feel inaccurate/out-of-date for day-to-day use.

## Current Behavior (Observed)
The Unrealized tab’s calculations come from `UnrealizedPositionRepository.get_all_positions()`.

Current logic:
- `purchase_basis` = `SUM(purchases.remaining_amount)` for site/user.
- If there is at least one completed session (`ending_balance IS NOT NULL`), then:
  - `current_sc` = most recent session `ending_redeemable` or `ending_balance`.
  - Purchases after that session do **not** affect `current_sc`.
- Else (no sessions exist), `current_sc` = `SUM(purchases.sc_received)`.
- `current_value` = `current_sc * sc_rate`.
- `unrealized_pl` = `current_value - purchase_basis`.

Net effect: purchases after the last session update basis but not the other columns.

## Desired Semantics
The Unrealized tab should be a **mostly accurate reflection of current state** for each site with remaining (unconsumed) basis.

It will not be perfect (we don’t track freebies/bonuses in real time), but it should be close.

Recommended display/meaning:
- **Remaining Basis**: sum of remaining purchase basis (what would be consumed if redeemed/closed now).
- **Current Total SC (Estimated)**: total balance as of the most recent event (last purchase or last session, whichever is newer), using known transactions.
- **Current Redeemable SC (Estimated)**: last known redeemable balance updated by known transactions.
- **Current Value ($)**: `redeemable_sc * sc_rate` (keep to support non-1:1 edge cases).
- **Estimated Unrealized P/L ($)**: value minus remaining basis.

Formula:
- `estimated_unrealized_pl = (estimated_redeemable_sc * sc_rate) - remaining_basis`

## Why this is likely a bug (or at least a UI/logic mismatch)
The column labels (“Current …”) strongly imply *as-of-now*, but the computation is effectively *as-of-last-session* once any sessions exist.

Users expect purchases to change the Unrealized position immediately.

## Acceptance Criteria
1. After adding a purchase for a site/user with an existing session history, the Unrealized tab updates the **Current Total SC** and **Current Redeemable SC** estimates (not just basis).
2. After completing a session, the Unrealized tab reflects the new session ending balances.
3. **Estimated Unrealized P/L** uses **redeemable** balance (not total) and matches:
   - `(estimated_redeemable_sc * sc_rate) - remaining_basis`
4. Existing behavior around notes and close-balance filtering remains unchanged.

## Implementation Notes (non-binding)
One plausible approach:
- Determine a baseline checkpoint from the latest ended session (date/time).
- Apply known transactions after that checkpoint:
  - `purchases.sc_received` since checkpoint
  - `redemptions.amount` since checkpoint
- Estimate:
  - `estimated_total_sc = last_session_ending_balance + purchases_since - redemptions_since`
  - `estimated_redeemable_sc = last_session_ending_redeemable + purchases_since - redemptions_since`

Edge cases to define:
- Purchases exist but no sessions yet.
- Redemptions exist after last session.
- `ending_redeemable` is NULL (fallback to `ending_balance`).
- Purchases/redemptions with missing times.

## Test Plan
Add scenario-based tests around `UnrealizedPositionRepository.get_all_positions()` (or via facade/UI smoke if preferred):
- Happy path: session exists, then purchase -> “Current Total SC” and “Redeemable SC” increase.
- Edge case 1: purchase only (no sessions) -> values based on purchases.
- Edge case 2: session exists, then redemption -> values decrease.
- Invariant: remaining basis continues to equal sum of `remaining_amount`.

## Pitfalls / Follow-ups
- The estimate won’t incorporate bonuses/freebies; document as “Estimated”.
- If we want perfect “current” balances long-term, we may need a derived running-balance table or explicit balance events.
