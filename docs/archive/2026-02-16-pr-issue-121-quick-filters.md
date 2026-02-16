## Summary
Implements Issue #121 by adding persistent, one-click quick filters to Purchases, Redemptions, and Game Sessions tabs.

## What changed
- Purchases tab:
  - Added `Basis Remaining` checkbox immediately left of `📤 Export CSV`.
  - Filters to rows where `remaining_amount > 0`.
- Redemptions tab:
  - Added `Pending` and `Unprocessed` checkboxes immediately left of `📤 Export CSV`.
  - `Pending` filters redemptions with empty/NULL `receipt_date`.
  - `Unprocessed` filters redemptions where `processed == False`.
  - If both selected, applies both predicates (AND).
- Game Sessions tab:
  - Added `Active Only` checkbox between `Active Sessions: X` and `📤 Export CSV`.
  - Filters to sessions with `status == 'Active'`.

## Persistence / Clear behavior
- All new quick filter states persist via app settings across restart.
- Existing per-tab clear actions now also reset these quick filters:
  - Purchases: `Clear All Filters`
  - Redemptions: `Clear All Filters`
  - Game Sessions: `Clear All Filters`

## Tests
- Added integration tests: `tests/integration/test_issue_121_quick_filters.py`
- Full suite run:
  - `pytest -q`
  - Result: `885 passed, 1 skipped`

## Docs
- Updated `docs/PROJECT_SPEC.md` with quick filter behavior and persistence.
- Updated `docs/status/CHANGELOG.md` with Issue #121 entry.
- Archived issue draft used for issue creation:
  - `docs/archive/2026-02-16-issue-quick-filters-tabs.md`

## Manual verification (quick)
1. Toggle each quick filter and confirm visible rows update immediately.
2. Restart app and confirm quick filters restore to prior state.
3. Click each tab's clear-all control and confirm quick filters reset.

## Pitfalls / Follow-ups
- Current implementation stores quick filter state under global keys; if future tabs are duplicated/embedded with different scopes, keys may need namespacing.
