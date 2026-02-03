# Bug: Editing a purchase shows incorrect SC balance check (self-inclusion / double-count)

## Problem
When editing an existing purchase, the Purchase dialog’s balance check computes the expected pre-purchase SC using the purchase’s exact timestamp. Because expected-balance logic includes purchases with `purchase_dt <= cutoff`, the purchase being edited is included in the expected total.

This makes the edit-flow warning inconsistent with the add-flow warning and produces a smaller discrepancy than expected.

## Repro (real DB example)
Pair: user_id=1, site_id=34 (Zula)

Purchases:
- 2026-01-22 12:06:00: `sc_received=15`, `starting_sc_balance=36.75`
- 2026-02-02 17:50:00: `sc_received=10`, `starting_sc_balance=55.75`

No sessions, no redemptions.

1. Open the 2026-02-02 purchase and click Edit.
2. Observe Balance Check message.

### Expected
Balance check should compare against the expected pre-purchase balance **just before** the purchase.
- Expected pre-purchase: 15.00 (only the earlier purchase)
- Observed pre-purchase: 55.75 - 10.00 = 45.75
- Delta: 30.75 higher than expected
- Expected post-purchase (for display): 25.00

### Actual
Edit flow computes expected pre-purchase including the purchase being edited.
- Expected pre-purchase: 25.00 (includes the edited purchase’s +10)
- Observed pre-purchase: 45.75
- Delta: 20.75 higher than expected
- Expected post-purchase (for display): 35.00 (matches what was observed)

## Suspected root cause
- `services/game_session_service.py::compute_expected_balances()` includes purchases with `p_dt <= cutoff`.
- `ui/tabs/purchases_tab.py`:
  - Add flow computes expected using “purchase time - 1 second” (pre-purchase).
  - Edit flow (and the dialog’s live `_update_balance_check`) uses the raw purchase timestamp, so it self-includes.

## Proposal
- Standardize purchase balance-check cutoff to “just before purchase” in:
  - PurchasesTab edit flow
  - PurchaseDialog live balance check
- Keep existing expected-balance engine unchanged; only adjust the UI cutoff inputs.
- Use a date+time-safe cutoff (handle midnight rollover).

## Acceptance criteria
- Editing a purchase produces the same balance-check result as adding a purchase with identical values.
- Regression test covers the Zula-style scenario: edit dialog shows `30.75 higher` and expected-post-purchase `25.00` (not `35.00`).
- No behavior change for session start balance checks.

## Test matrix
- Happy path: two purchases, edit the second → expected pre excludes the second.
- Edge case 1: purchase at 00:00:00 → cutoff rolls to previous day 23:59:59.
- Edge case 2: empty time field (defaults to now) → balance check still stable.
- Failure injection: invalid time string in UI → balance check degrades to neutral ("—") without raising.
