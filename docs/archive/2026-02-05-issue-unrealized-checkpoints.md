# Feature: Unrealized — treat Purchase / Session Start as checkpoints for Total SC (Est.)

## Problem
Unrealized currently estimates `Total SC (Est.)` using a **closed session end** as the baseline checkpoint when available, otherwise it falls back to summing purchases (and subtracting redemptions).

This creates confusing/incorrect UX in common real-world flows:

- After a purchase, the user often records a **starting SC balance** (site snapshot) that can include non-purchase SC (dailies/bonuses/adjustments). Unrealized does not use that snapshot, so `Total SC (Est.)` can lag behind what the user actually sees on the site.
- After starting a session, the user provides **starting total SC** and **starting redeemable SC** (another snapshot). Unrealized does not treat session start as a checkpoint, so Total SC may look wrong until a session is closed.

Example (Stake):
- Purchase 2026-02-04: $2500 for 2506.25 SC.
- Session start: starting total 2507.25 SC (includes +1 daily redeemable).
- Unrealized should reflect that latest known site snapshot for `Total SC (Est.)` (and still keep accounting rules intact).

## Proposal
Upgrade Unrealized estimation to use **the most recent reliable checkpoint** among:

1. **Session End** (Closed sessions) — current behavior
2. **Session Start** (Active or Closed) — new checkpoint
3. **Purchase Snapshot** when a purchase row has `starting_sc_balance` (or equivalent) — new checkpoint

Then estimate:

- `estimated_total_sc = checkpoint_total_sc + purchases_since_checkpoint - redemptions_since_checkpoint`

Also optionally improve `Redeemable SC (Position)` display by anchoring it to the checkpoint when available (session start/end redeemable), but keep P/L math based on total SC.

## Scope
In scope:
- Unrealized tab calculation changes only (repository-level).
- Deterministic selection of a single baseline checkpoint for each (site_id, user_id).
- Regression tests capturing the Stake flow and double-counting pitfalls.

Out of scope:
- Changing FIFO / basis allocation behavior.
- Changing the definition of Remaining Basis.
- Changing taxable/realized logic.

## Acceptance Criteria
- Unrealized uses the newest available checkpoint event for each site/user, with precedence based on event timestamp (not source type).
- Unrealized does **not** double-count purchase SC when a purchase snapshot is used as a checkpoint.
- Stake scenario: after creating a session with starting total > purchase sc_received (because of dailies), Unrealized shows `Total SC (Est.)` equal to the session start total (unless there are later transactions).
- If the newest checkpoint is a purchase snapshot, `Total SC (Est.)` reflects that snapshot (plus later deltas).
- Redemptions/purchases after the checkpoint still adjust the estimate correctly.
- Existing Issue #44 behaviors remain correct.

## Test Matrix (Required)
Happy paths:
1) Purchase with `sc_received` only (no snapshot) + no sessions → Total SC sums purchases.
2) Purchase with snapshot + no sessions → Total SC uses snapshot as checkpoint.
3) Session start snapshot newer than purchase snapshot → Total SC uses session start snapshot.

Edge cases:
- Multiple purchases where some have snapshots and some don’t; newest snapshot wins.
- Checkpoint at same date with different times; ordering respects time, and missing times default consistently.

Failure-injection / invariants:
- Invariant: **no double counting** when checkpoint source is a purchase row. If checkpoint_total_sc is taken from purchase.starting_sc_balance, that purchase’s `sc_received` must not also be included in `purchases_since_checkpoint`.
- Invariant: only the selected site/user pair’s estimate changes; other pairs unaffected.

## Implementation Notes
- Add a helper to compute the “latest checkpoint datetime + checkpoint totals” for a site/user.
- Define exact timestamp rules for purchase time/session time when missing (treat missing as '00:00:00').
- Keep Unrealized P/L formula unchanged:
  - `current_value = total_sc * sc_rate`
  - `unrealized_pl = current_value - remaining_basis`

## Links
- Follow-up to Issue #58 (Unrealized positions stay visible when SC remains but basis is fully allocated).
- Related: Issue #44 (Unrealized incorporates purchases/redemptions since last session).
