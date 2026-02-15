Summary
Unrealized tab drops the site/user position after a partial redemption even when balance remains on site.

Impact / scope
Impact:
- Unrealized positions disappear after partial redemptions, blocking visibility of remaining balance.

Scope:
- Observed on 2026-02-14 partial redemption for Sixty6 (balance left on site).

Steps to reproduce
1. Record a closed session with a redeemable balance.
2. Create a redemption for less than the session balance and mark it Partial (more remaining).
3. Observe Unrealized tab.

Expected behavior
Unrealized position remains and updates to show the remaining balance.

Actual behavior
Unrealized position disappears after the partial redemption.

Logs / traceback
None.

Severity
Medium (workflow impaired)

Environment
macOS. Time zone setting in use (America/New_York).

Acceptance
- This bug involves data correctness (should add/adjust a scenario-based test).
