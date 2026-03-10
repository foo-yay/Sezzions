## Summary
Scoped FIFO rebuild (`rebuild_fifo_for_pair_from`) still uses legacy handling for `Balance Closed` close-marker redemptions (`amount=0`, parsable `Net Loss` note): it writes realized loss but does not consume basis or write `redemption_allocations`.

## Impact / scope
Impact:
- Unrealized basis can be overstated after close markers when updates go through scoped rebuild flows.
- Unrealized P/L can be materially incorrect (double-hit effect: realized loss booked while basis remains open).
- Inconsistency between full rebuild and scoped rebuild semantics.

Scope:
- `services/recalculation_service.py` scoped rebuild path (`rebuild_fifo_for_pair_from`).
- Regression coverage for scoped path close-marker handling.
- Documentation updates clarifying invariant parity between full and scoped rebuild.

## Steps to reproduce
1. Use a user/site pair with purchases and close-marker redemptions.
2. Trigger operations that call scoped rebuild (`AppFacade._rebuild_or_mark_stale` normal mode path).
3. Ensure close marker redemptions exist with:
   - `amount=0`
   - parsable notes: `Balance Closed - Net Loss: $X.XX`
4. Inspect DB:
   - `realized_transactions` includes close-marker net loss rows
   - `redemption_allocations` has no corresponding rows for those close markers
   - pre-close purchases still retain positive `remaining_amount`.

## Expected behavior
Scoped rebuild should match full rebuild semantics:
- consume FIFO basis for close markers (timestamp-bounded, capped by available basis),
- write `redemption_allocations`,
- update `purchases.remaining_amount`,
- keep realized row synchronized to consumed basis.

## Actual behavior
Scoped rebuild writes realized close-loss rows only and skips basis consumption/allocation for close markers.

## Logs / traceback
Observed on Sheesh (site_id=37, user_id=1):
- close markers: redemptions 238 and 243
- realized rows exist for both close markers
- no allocation rows for 238/243
- purchases 794/844/886/954 each retained 74.99 remaining basis (sum 299.96), causing Unrealized to display -209.77 from checkpoint 90.19.

## Severity
High (data incorrect / accounting display materially wrong)

## Environment
- macOS
- SQLite local DB (`sezzions.db`)

## Acceptance
- [x] I’ve checked `docs/PROJECT_SPEC.md` and this is unexpected.
- [x] This bug involves data correctness (should add/adjust a scenario-based test).

---

## Proposed fix scope
1. Add regression tests for scoped rebuild close-marker semantics:
   - Happy path: close marker consumes basis + writes allocations in scoped mode.
   - Edge case: close-loss note exceeds available basis (cap allocation).
   - Edge case: no parsable Net Loss note keeps existing non-close-loss behavior.
   - Invariant: full and scoped rebuild paths produce equivalent close-marker basis outcomes.
2. Patch `rebuild_fifo_for_pair_from` close-marker branch to mirror full rebuild logic.
3. Re-run targeted recalculation tests and full `pytest`.
4. Update `docs/PROJECT_SPEC.md` and `docs/status/CHANGELOG.md` with reproducible details.
