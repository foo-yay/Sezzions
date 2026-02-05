# Summary
Unrealized Positions currently drop off the Unrealized tab when a partial redemption consumes all remaining purchase basis (FIFO allocation reduces purchases.remaining_amount to 0), even if there is still SC left on the site (e.g., payout cap forces multiple partial redemptions).

Example: Moonspin has a max redeem cap of 2500 SC. A partial redemption of 2500 SC consumed the remaining basis, but ~175 SC remained on the site pending approval. The app removed the position from Unrealized even though the position is not fully redeemed/closed.

# Impact / scope
Impact:
- Workflow: Users lose visibility of an open position that still has SC remaining to redeem.
- Data semantics: Unrealized is currently conflated with “remaining basis” rather than “position still open”.
- Potential downstream confusion: Reports/UX may imply a position is “done” when it is not.

Scope:
- Primary: Unrealized Positions logic (repository + Unrealized tab display semantics).
- Secondary: Documentation of the intended semantics.
- Non-goals: Changing redemption “processed/approved” workflows in this issue.

# Steps to reproduce
1. Create purchases on a site/user (basis exists).
2. Create a partial redemption where FIFO allocation consumes all remaining basis (`purchases.remaining_amount` becomes 0), but the user still has SC remaining on-site (e.g., redemption capped to 2500 SC, leaving a remainder).
3. Navigate to Unrealized Positions.
4. Observe the site/user no longer appears.

# Expected behavior
Unrealized should continue to show a position as long as there is remaining SC value on the site (position still open), even if remaining basis is $0.00.

At minimum, the Moonspin cap scenario should remain visible until:
- the remaining SC is redeemed down to (near) zero, OR
- the user explicitly closes the position ("🔒 Close Position") / performs an explicit close-out action.

# Actual behavior
The position disappears from Unrealized once remaining basis reaches 0 (because the Unrealized query is driven by `purchases.remaining_amount > 0`).

# Severity
High (data correctness / workflow impaired).

# Environment
- macOS
- Sezzions desktop app

# Acceptance criteria
- Given a site/user has **remaining SC > 0** but **remaining basis == 0**, when Unrealized Positions are refreshed, then the position is still listed.
- Given a site/user has remaining SC <= threshold (e.g. <= 0.01) and remaining basis == 0, then it is not listed.
- Given a site/user has a "Balance Closed" $0 redemption (close-out marker), then it is not listed even if historic artifacts would otherwise include it.
- Existing Issue #44 behavior remains true: `Total SC (Est.)` should incorporate purchases/redemptions after the last session.

# Implementation notes / strategy
Current behavior:
- Unrealized positions are currently defined as “site/user with remaining purchase basis”.
  - See repository query in `repositories/unrealized_position_repository.py` (`purchases.remaining_amount > 0.001`).
- FIFO allocation is applied at redemption creation time, so partial redemptions can reduce remaining basis immediately even if the redemption is not yet "approved" in the real world.

Proposed behavior:
- Redefine Unrealized positions as “site/user with remaining SC (estimated)”, not strictly remaining basis.
- Keep "Remaining Basis" as a displayed metric (can be $0.00).
- Continue honoring the existing "Balance Closed" marker logic (`notes LIKE 'Balance Closed%'` and amount==0) to suppress positions that were explicitly closed.

Candidate approach (repo):
- Build the candidate site/user pairs from activity tables (at least purchases OR sessions OR redemptions), not only from purchases with remaining_amount > 0.
- For each candidate pair:
  - Compute remaining basis (sum of remaining_amount) as today.
  - Compute estimated_total_sc as today (baseline from last session ending balance plus purchases/redemptions after).
  - Include the position if `estimated_total_sc > sc_threshold` (e.g., 0.01) AND not Balance Closed.

Notes:
- This likely requires updating docstrings and the Unrealized tab’s description text (it currently says “remaining purchase basis”).
- Confirm whether `redemptions.amount` should be counted even when `processed=0`. Today, Unrealized SC estimation subtracts *all* redemptions since the last session regardless of processed state.

# Test plan
Automated tests (pytest):
- Add a new integration regression test (adjacent to `tests/integration/test_issue_44_unrealized_live_balances.py`) covering the “basis==0 but SC>0 still appears” scenario.
- Edge cases:
  - No sessions exist (estimate uses purchase sums); verify listing still works.
  - Multiple site/user pairs: ensure only those with SC>threshold are included.
- Failure injection / invariant:
  - If candidate computation fails for one pair (e.g., malformed time), ensure repository still returns other positions (no crash) and does not silently include incorrect rows.

Manual verification (5 min):
- Reproduce Moonspin cap scenario in a test DB.
- Confirm Unrealized shows the position with Remaining Basis = $0.00 and Total SC (Est.) ~= remainder.
- Confirm it disappears after the final redemption is logged (SC ~ 0) or after explicit Close Position.

# Notes
- This change likely requires updating `docs/PROJECT_SPEC.md` (semantics of "Unrealized Positions").
- This change likely requires adding/updating scenario-based tests.
