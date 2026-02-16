## Problem / motivation
Right now the main list tabs require using column header filters/search to answer a few very common questions. These are frequent enough to warrant dedicated, one-click quick filters that are visible, persistent, and easily cleared.

Requested quick filters:
- Purchases: show only purchases with remaining basis.
- Redemptions: show only “pending” and/or “unprocessed” items.
- Game Sessions: show only active sessions.

## Proposed solution
Add persistent checkbox/toggle quick filters to the tab toolbars.

What:
- Purchases tab: add `Basis Remaining` checkbox.
- Redemptions tab: add `Pending` and `Unprocessed` checkboxes.
- Game Sessions tab: add `Active Only` checkbox.

Why:
- These are binary filters users frequently toggle on/off.
- They should be faster than typing into filters and reduce mistakes.

Notes:
- These filters should combine cleanly with existing date filters, search, and column header filters.
- The filter state should persist across app restarts.

## Scope
In-scope:
- Add the UI controls in the requested locations.
- Apply the filters to the displayed table rows.
- Persist the checkbox states across restarts.
- Ensure they are cleared by the same “clear filters” mechanism used for existing column filters.
- Add automated tests for core behavior (filtering + persistence).

Out-of-scope:
- Any changes to accounting semantics.
- Changes to CSV schema (unless needed for test coverage).
- Replacing the existing header filters/search UX.

## UX / fields / checkboxes
### Purchases tab
- Control: checkbox `Basis Remaining`
- Placement: immediately left of the `📤 Export CSV` button in the Purchases toolbar.
- Behavior:
  - When checked: only show purchases where `remaining_amount > 0`.
  - When unchecked: show all purchases (subject to other filters).

### Redemptions tab
- Controls:
  - checkbox `Pending`
  - checkbox `Unprocessed`
- Placement: immediately left of the `📤 Export CSV` button in the Redemptions toolbar.
- Definitions:
  - `Pending`: redemptions whose receipt is pending (currently displayed as `PENDING` when `receipt_date` is empty/NULL).
  - `Unprocessed`: redemptions where `processed == False` (no ✓ in the Processed column).
- Combination rules:
  - If both are checked, apply an AND filter (pending AND unprocessed).

### Game Sessions tab
- Control: checkbox `Active Only`
- Placement: between the `Active Sessions: X` label and the `📤 Export CSV` button.
- Behavior:
  - When checked: only show sessions with `status == 'Active'`.

### Persistence + clearing
- Each quick filter is persistent: state is restored on app startup.
- Clearing:
  - Quick filters should be cleared by the same “clear filters” action used to clear existing column filters (e.g., `Clear All Filters` or equivalent on each tab).
  - Quick filters should also be independently uncheckable by clicking them.

## Implementation notes / strategy
Approach:
- Store quick filter states using the existing settings mechanism (e.g., `QSettings` / app settings layer) under stable keys, per tab.
- Apply the quick filters in the same place the tab currently applies filters (after loading data, before rendering rows, or by filtering the already-loaded row set).
- Ensure refresh logic (`Refresh`, date filter changes, header filter changes) respects the quick filters.

Risk areas:
- Avoid duplicating filter logic across tabs; consider a small helper if it reduces bug surface.
- Ensure the filters don’t conflict with export behavior (confirm whether Export CSV exports filtered rows; if so, this should follow the current convention).

## Acceptance criteria
- Purchases tab:
  - `Basis Remaining` checkbox appears immediately left of `📤 Export CSV`.
  - When checked, no purchase rows with `remaining_amount == 0` are visible.
  - State persists across restart.
  - “Clear filters” clears this checkbox.
- Redemptions tab:
  - `Pending` and `Unprocessed` checkboxes appear immediately left of `📤 Export CSV`.
  - `Pending` shows only rows with pending receipt (`receipt_date` empty/NULL; receipt cell shows `PENDING`).
  - `Unprocessed` shows only rows where processed is unchecked.
  - If both checked, only rows meeting both conditions are shown.
  - States persist across restart.
  - “Clear filters” clears both checkboxes.
- Game Sessions tab:
  - `Active Only` checkbox appears between the active sessions label and `📤 Export CSV`.
  - When checked, only active sessions are shown.
  - State persists across restart.
  - “Clear all filters” clears this checkbox.

## Test plan
Automated tests:
- Unit/integration tests for the filtering predicates (basis remaining / pending / unprocessed / active-only).
- UI-level (headless) smoke test that:
  - toggles the checkbox,
  - triggers refresh,
  - and verifies the row set changes,
  - and verifies persistence via settings reload (as feasible).

Manual verification:
- Toggle each quick filter on/off and confirm the row list updates immediately.
- Restart app and confirm toggles are restored.
- Use existing “clear filters” button and confirm quick filters clear as expected.

Area: UI
Notes:
- [x] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [x] This change likely requires adding/updating scenario-based tests.
