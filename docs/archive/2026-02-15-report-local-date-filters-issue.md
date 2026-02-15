## Summary
Report date filters (tax report, realized transactions, session P/L) use raw UTC dates and can exclude records that fall on a different UTC day from the user’s local date/time.

## Impact / scope
Impact:
- Report totals and lists can be incorrect for late-night sessions/redemptions.
- Filters in the Reports UI can show “missing” rows when local dates span UTC boundaries.

Scope:
- Tax report (realized transactions)
- Realized transactions list/filtering
- Session P/L report date filtering

## Steps to reproduce
1. Set time zone to America/New_York.
2. Create a redemption on 2026-01-01 at 23:30 local time with FIFO allocation.
3. Run a tax report filtered to 2026-01-01.
4. Observe the redemption missing from the totals.

## Expected behavior
Local-date filters should include records that occurred on the selected local day, even if UTC storage crosses midnight.

## Actual behavior
UTC date-only filters exclude records whose UTC date differs from the local date.

## Logs / traceback
N/A

## Severity
High (data incorrect / frequent accounting discrepancy)

## Environment
macOS (local), Python 3.x

## Acceptance
- [x] I’ve checked docs/PROJECT_SPEC.md and this is unexpected.
- [ ] I’m willing to help test a fix.
- [x] This bug involves data correctness (should add/adjust a scenario-based test).
