## Problem
Purchase dialogs can repeatedly show the same "extra SC" balance mismatch message across multiple purchases in the same basis period. The message is technically correct (extra is still present), but it reads like a new discrepancy each time and becomes confusing/noisy.

Also, when a mismatch occurs, the user cannot easily see the purchase chain that forms the active basis stack, which would help explain why balances differ.

## Goals
- Reduce repeated "extra SC" warnings without hiding real problems.
- Preserve the existing purchase balance-check confirmation UI where possible (dialogs are already busy).
- Add a compact way to view the prior purchases that belong to the current basis period (for reconciliation/debugging).
- Ensure edits/recalculations/deletions automatically cascade (computed on-the-fly; avoid persisted baseline state).

## Proposed Change
### A) Purchase dialogs: Related tab shows "Basis Period Purchases"
In Add/View/Edit Purchase dialogs, display the previous purchases that belong to the same **basis period** (for the selected user+site) as-of the purchase timestamp.

Definitions (v1; avoid time-travel FIFO simulation):
- **Basis period**: a contiguous time slice of activity for a user+site, beginning immediately after the most recent "closure" event and continuing until the next closure event.
- **Closure event (basis boundary / reset):** a FULL redemption (`more_remaining = 0`) or explicit close-marker semantics (consistent with current dormant/close behavior). If both exist, the most recent one before the purchase timestamp wins.
- **Basis period start** for a given purchase timestamp: the instant just after the most recent closure event strictly before the purchase; if none exists, period start is the beginning of time for that user+site.

Important: this definition intentionally does *not* depend on whether FIFO basis was fully consumed at some point (because “fully consumed as-of time” can require a historical allocation replay). We can add a follow-up issue later if we want “basis hits zero” to also define a boundary.

UX sketch (compact):
- A small table/list of purchases in the period (date/time, amount, SC received, post-purchase balance; consumed/remaining if available).
- Optional action button: View selected purchase (space-permitting).

Basis-period purchase scoping (v1):
- Show purchases for the same user+site with purchase datetime in `(basis_period_start_dt, current_purchase_dt]`, ordered by `(purchase_date, COALESCE(purchase_time,'00:00:00'), id)`.

### B) Purchase dialogs: switch "extra SC" warnings to a running-delta system
Keep the current purchase mismatch confirmation dialog, but change *when* it triggers for the "extra" case.

At purchase timestamp $P$:
- `actual_pre = entered_post - sc_received`
- `expected_pre = compute_expected_balances(...)` (expected total)
- `total_extra(P) = actual_pre - expected_pre`

Precision / tolerance:
- Use `Decimal` math end-to-end.
- SC is treated as a 2-decimal currency-like value (0.00 format).
- Compare using a canonical quantization for SC balances: `quantize(Decimal('0.01'))`.
- Tolerance is effectively zero after quantization: treat any non-zero quantized mismatch as a mismatch.

Rules:
1) **Negative mismatch persists (warn every time):**
   - If `total_extra(P) < -tolerance`, always show the existing mismatch confirmation.
   - Rationale: this indicates missing SC vs expected and should not be suppressed.

2) **Extra SC becomes delta-based (reduce repeats):**
   - If `total_extra(P) > +tolerance`, only show the mismatch confirmation when the *increase* in total extra is meaningful vs the previous purchase in the same basis period.
   - `delta_extra(P) = total_extra(P) - total_extra(prev_purchase_in_period)`
   - Show the confirmation if `delta_extra(P) > +tolerance`.

   Notes on sessions:
   - Sessions are inherently accounted for via `expected_pre` when a session is closed (because `compute_expected_balances()` uses the last closed session as a checkpoint). This ensures a purchase’s mismatch check reflects the expected current state from purchases + closed sessions + redemptions, not just the previous purchase.

3) **Ignore negative delta for extra tracking:**
   - If `delta_extra(P) < 0`, do nothing special (no message).

Notes:
- Values should be computed on-the-fly from recorded closed sessions + purchases + redemptions. Do **not** persist an "acknowledged extra" baseline in the DB for v1.
- Because it is computed from the timeline, any edits/recalcs/deletes automatically cascade.

## Acceptance Criteria
- Related tab in Add/View/Edit Purchase dialogs shows basis-period purchases for that user+site as-of the purchase timestamp.
- First time extra SC appears in a basis period, the existing mismatch confirmation triggers (as today).
- Subsequent purchases with the same `total_extra` do **not** re-trigger the confirmation.
- If extra SC increases within the same basis period, the mismatch confirmation triggers again (for the new incremental increase).
- If pre-purchase balance is lower than expected (negative beyond tolerance), mismatch confirmation triggers every time (not suppressed).
- Edits anywhere in the chain (purchases/sessions/redemptions, scoped recalcs/full recalcs, deletions) automatically affect expected balances and delta logic (no manual reset needed).

Implementation notes (to prevent ambiguity):
- Ordering/tie-breakers for events should be stable: order by `(date, COALESCE(time,'00:00:00'), id)`.
- When editing an existing purchase, exclude its own id when computing the “previous purchase” checkpoint.
- Keep UI compact: reuse the existing mismatch confirmation dialog; do not add new persistent baseline state.

## Non-Goals
- Do not change core accounting / FIFO / basis consumption semantics.
- Do not add new persistent state for extra-tracking in v1.

## Test Plan (Red → Green → Review)
Happy paths:
- Extra SC appears once in a basis period; later purchases don’t re-warn unless extra increases.
- Negative mismatch persists and always warns.

Edge cases:
- Purchase after a closed session: expected uses that session’s ending balance checkpoint.
- Purchase while a session is open (no ended session yet): expected uses last closed checkpoint; behavior remains consistent.

Failure injection:
- Edit an earlier purchase/session/redemption and verify later purchase dialogs recompute totals/deltas correctly (no stale persisted baseline).

Invariants:
- UI continues to call through facade/services (no UI → repo direct calls).

## Pitfalls / Follow-ups
- Confirm basis boundary rules align with current FULL redemption / close marker semantics.
- Ensure timestamp ordering is stable when events share a date (times, tie-breakers).