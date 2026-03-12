## Summary
Expected starting balances should be derived from a single chronological event timeline as of the cutoff timestamp. Current behavior can produce pre-redemption expectations when a purchase snapshot overwrite runs after redemption application.

## Problem
`GameSessionService.compute_expected_balances()` currently applies redemptions first and then applies purchases, where purchases overwrite `expected_total` (and potentially `expected_redeemable`) using purchase checkpoint snapshots.

In scenarios where a redemption occurs after a purchase but before the cutoff, this ordering can erase the redemption effect and produce stale pre-redemption expected balances.

## Reproduction
1. Create a user/site with `sc_rate = 0.01`.
2. Ensure there is a valid anchor state before event timeline (checkpoint or last closed session).
3. Add a purchase before cutoff with snapshot balances (e.g., total/redeemable = 1300).
4. Add a redemption after that purchase but before cutoff (e.g., $5.00 => 500 SC).
5. Open Start Session / compute expected balances at cutoff after both events.

### Actual
Expected balances remain at purchase snapshot values (e.g., 1300) as if redemption did not occur.

### Expected
Expected balances reflect chronological state at cutoff (e.g., 1300 - 500 = 800), with all event types (gameplay/checkpoints, purchases, redemptions) applied by timestamp order.

## Scope
- Update `compute_expected_balances()` to process event effects in chronological order.
- Preserve existing semantics for anchors, exclusion behavior, and unit conversion (redemption USD -> SC via site rate).
- Add regression coverage for post-purchase redemption before cutoff.

## Acceptance Criteria
- Given purchase before cutoff and redemption after purchase before cutoff, expected balances include redemption effect.
- Same-timestamp ordering remains deterministic.
- Excluding purchase during purchase edit still behaves correctly.
- Existing conversion semantics (`redemption.amount` in USD) remain correct for non-unit site rates.

## Test Plan
- Add/extend integration tests in expected-balance suite:
  - Happy path: purchase then redemption before cutoff.
  - Edge: same timestamp deterministic behavior.
  - Edge: with `exclude_purchase_id` and same timestamp earlier purchase IDs.
  - Failure/invariant: verify only events before cutoff are included.

## Risks / Notes
- Purchase snapshots are still authoritative state checkpoints, but timeline processing must not wipe later events.
- Keep changes minimal and localized to expected-balance timeline assembly.
