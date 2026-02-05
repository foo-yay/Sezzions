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

Definition:
- **Basis period**: the purchase chain contributing to the current FIFO/basis stack until it is reset/closed.
- **Boundary/reset**: basis period ends when basis is fully consumed OR the position is closed via FULL redemption / explicit close marker semantics (consistent with current dormant/close behavior).

UX sketch (compact):
- A small table/list of purchases in the period (date/time, amount, SC received, post-purchase balance; consumed/remaining if available).
- Optional action button: View selected purchase (space-permitting).

### B) Purchase dialogs: switch "extra SC" warnings to a running-delta system
Keep the current purchase mismatch confirmation dialog, but change *when* it triggers for the "extra" case.

At purchase timestamp $P$:
- `actual_pre = entered_post - sc_received`
- `expected_pre = compute_expected_balances(...)` (expected total)
- `total_extra(P) = actual_pre - expected_pre`

Rules:
1) **Negative mismatch persists (warn every time):**
   - If `total_extra(P) < -tolerance`, always show the existing mismatch confirmation.
   - Rationale: this indicates missing SC vs expected and should not be suppressed.

2) **Extra SC becomes delta-based (reduce repeats):**
   - If `total_extra(P) > +tolerance`, only show the mismatch confirmation when the *increase* in total extra is meaningful vs the prior purchase in the same basis period.
   - `delta_extra(P) = total_extra(P) - total_extra(prev_purchase_in_period)`
   - Show the confirmation if `delta_extra(P) > +tolerance`.

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