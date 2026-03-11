## Summary
Adjust auto-calculate Ending Redeemable SC to fully redeem ending balance when normalized wager covers ending SC.

## Problem
Current auto-calc can understate redeemable in sessions where site balance is fully played through (e.g. wager exceeds ending SC after playthrough normalization), because gains after unlock are not promoted to redeemable.

## Requested Behavior
- In End Session and Edit Closed Session auto-calc logic:
  - If `(wager / playthrough_requirement) >= ending_total_sc`, set `ending_redeemable_sc = ending_total_sc`.
  - Keep hard cap behavior (`ending_redeemable_sc <= ending_total_sc`).
  - Preserve existing conservative logic for non-qualifying scenarios.

## Acceptance Criteria
- Spindoo-like scenario with start 201.70, start redeemable 0.00, wager 211.20, end 204.78 should auto-calc to 204.78.
- Existing loss/unlock/wager-required scenarios remain passing.
- Tests added for End Session and Edit Closed Session.

## Test Plan
- `pytest -q tests/ui/test_end_session_auto_redeemable.py`
