Summary
Tax Set-Aside column in Daily Sessions shows “—” for all rows even when daily_date_tax has amounts.

Impact / scope
Impact:
- Tax withholding totals are hidden in the Daily Sessions UI.
- Users cannot see daily set-aside amounts.

Scope:
- All Daily Sessions rows.

Steps to reproduce
1. Open Daily Sessions tab.
2. Observe Tax Set-Aside column values show “—” for every row.
3. Verify daily_date_tax has non-zero tax_withholding_amounts.

Expected behavior
Tax Set-Aside column shows the daily tax withholding amount for each date.

Actual behavior
Tax Set-Aside column shows “—” for all rows.

Logs / traceback
None.

Severity
Medium (workflow impaired)

Environment
macOS; Sezzions using sezzions.db.

Acceptance
- This bug involves data correctness (should add/adjust a scenario-based test).
