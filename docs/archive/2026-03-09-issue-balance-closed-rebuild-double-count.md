## Summary
Recalculation rebuild can double-count basis after a `Balance Closed` closeout: a realized loss row is recreated from notes, but FIFO allocations and `purchases.remaining_amount` consumption are skipped for that closeout event.

## Impact / scope
Impact:
- Accounting correctness risk (realized and unrealized can both reflect the same pre-close basis).
- Reopened unrealized positions can include stale pre-close purchase basis.
- Related FIFO attribution for closeout events becomes incomplete.

Scope:
- `services/recalculation_service.py` FIFO rebuild path for close markers (`amount=0`, `notes` containing `Net Loss:`).
- Regression tests for rebuild semantics on closeout rows.
- Documentation updates for closeout + rebuild invariants.

## Steps to reproduce
1. Create purchases for a site/user totaling basis (e.g., 3 purchases of 74.99).
2. Create normal redemptions that consume earlier purchases.
3. Create close marker redemption with:
   - `amount=0`
   - `more_remaining=0`
   - `notes='Balance Closed - Net Loss: $149.98 (...)'`
4. Run FIFO rebuild (`RecalculationService._rebuild_fifo_for_pair` / Tools recalculation).
5. Inspect DB:
   - `realized_transactions` has close-loss row (`cost_basis=149.98`, `net_pl=-149.98`)
   - but `redemption_allocations` has no rows for close marker redemption
   - and pre-close purchases still show positive `remaining_amount`.

## Expected behavior
- Close marker rebuild should produce results equivalent to full closeout semantics:
  - realize the parsed net loss,
  - consume matching pre-close basis via FIFO allocations,
  - update `purchases.remaining_amount` so pre-close lots are not re-opened later,
  - preserve chronological constraints (no allocation from future purchases).

## Actual behavior
- Rebuild writes realized close-loss row but does not write allocations or consume remaining basis for that close marker.
- Old basis then reappears in unrealized after new activity, effectively double-dipping loss/basis across realized + unrealized views.

## Logs / traceback
Observed in production DB during investigation:
- close marker redemption present (`amount=0`, `more_remaining=0`, notes include `Net Loss: $149.98`)
- realized row present for close marker (`cost_basis=149.98`, `payout=0`, `net_pl=-149.98`)
- no `redemption_allocations` rows for that close marker
- pre-close purchases still have positive `remaining_amount`.

## Severity
Critical (data loss / accounting incorrect)

## Environment
- macOS
- Sezzions desktop app
- SQLite local DB (`sezzions.db`)

## Acceptance
- [x] I’ve checked `docs/PROJECT_SPEC.md` and this is unexpected.
- [x] This bug involves data correctness (should add/adjust a scenario-based test).

---

## Proposed Fix Scope (full)
1. Add failing regression tests first (unit + integration-style where appropriate):
   - Happy path: close marker loss consumes basis and writes allocations.
   - Edge case A: parsed close-loss exceeds available pre-close basis (cap allocation to available basis; keep deterministic behavior).
   - Edge case B: no parsable `Net Loss` text keeps existing zero-allocation semantics.
   - Failure injection: malformed timestamp ordering / future purchase boundary should not allocate future lots.
   - Invariants:
     - Only target site/user purchases are changed.
     - Allocations sum equals consumed basis.
     - Consumed basis is not later re-counted as unrealized for pre-close lots.
2. Implement minimal fix in `services/recalculation_service.py` close-marker branch to run bounded FIFO consumption and allocation writes.
3. Re-run targeted and full `pytest`.
4. Update `docs/PROJECT_SPEC.md` with rebuild closeout invariants.
5. Add changelog entry in `docs/status/CHANGELOG.md`.
