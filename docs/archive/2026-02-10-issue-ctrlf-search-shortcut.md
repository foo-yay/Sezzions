## Problem / motivation
Across many tabs, users rely on the search bar to filter rows. Currently there’s no consistent keyboard shortcut to jump focus into that search field.

This creates friction during data entry / review (mouse travel + extra clicks), and it’s inconsistent with common desktop app expectations.

## Proposed solution
Add a global-ish “Find” shortcut that focuses the tab’s search bar:

- Shortcut: `Cmd+F` on macOS, `Ctrl+F` on Windows/Linux
- Behavior: when invoked, focus the search input for the **currently visible tab** (and select all text so typing immediately replaces the query)
- If the tab has no search bar, do nothing (or show a subtle status message—optional)

Tabs requested:

**Main tabs**
- Purchases
- Redemptions
- Game Sessions
- Daily Sessions
- Unrealized
- Realized
- Expenses

**Setup tabs**
- Users
- Sites
- Cards
- Method Types
- Redemption Methods
- Game Types
- Games

## Scope
In-scope:
- Wire `Cmd+F` / `Ctrl+F` to focus the tab’s search bar
- Consistent behavior across all listed tabs
- Ensure no conflict with existing shortcuts

Out-of-scope (for this issue):
- Implementing a new search bar on tabs that don’t currently have one
- “Find next/previous” navigation
- Highlighting matches inside text fields

## UX / fields / checkboxes
Shortcut:
- `Cmd+F` / `Ctrl+F`

Action:
- Focus the tab’s search `QLineEdit` (or equivalent)
- Select all existing text

## Implementation notes / strategy
Recommended approach:
- Add a single handler in `MainWindow` (or a shared base tab class) that routes the shortcut to the active widget.
- Define a small interface/contract on tabs, e.g. `focus_search()` or `get_search_widget()`.
- For Setup sub-tabs, ensure the shortcut routes to the currently selected Setup page.

Notes:
- Use `QShortcut(QKeySequence.Find, ...)` or platform-correct key sequence.
- Ensure the shortcut is active when the main window has focus (not only when a particular widget has focus).

## Acceptance criteria
- Given any of the listed tabs is visible, when the user presses `Cmd+F` (macOS) / `Ctrl+F` (Win/Linux), then the search input for that tab receives focus.
- The search input text is fully selected after focusing.
- Shortcut works on Setup sub-tabs as well as main tabs.
- No regression to existing shortcuts.

## Test plan
Automated tests:
- Add a headless UI test that:
  - boots a `QApplication`
  - instantiates `MainWindow(AppFacade(...))`
  - navigates to at least 2–3 representative tabs (one main tab + one Setup sub-tab)
  - triggers the `Find` shortcut programmatically
  - asserts the expected widget has focus

Manual verification:
- On macOS: verify `Cmd+F` focuses the search bar on all listed tabs.
- On Windows/Linux: verify `Ctrl+F` focuses the search bar on all listed tabs.

Area: UI
