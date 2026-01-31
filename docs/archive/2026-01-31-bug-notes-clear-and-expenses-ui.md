# Bug: Notes dialogs missing Clear button; Expenses tab selection/actions/refresh broken

## Summary
1) Notes dialogs for Daily Sessions / Unrealized / Realized are missing a **Clear** button (only Cancel/Save).
2) Expenses tab: selecting rows doesn’t reveal View/Edit/Delete; double-click does nothing; and newly added expenses do not appear until app restart.

## Impact / scope
Impact:
- **Medium (workflow impaired)**
- Slower note entry UX (no one-click clear).
- Expenses workflow is effectively broken: can’t view/edit/delete from table, and can’t confirm an add succeeded without restarting.

Scope:
- Affects three Notes dialogs and the Expenses tab UI.

## Steps to reproduce

### A) Notes dialogs lack Clear button
1. Open app
2. Go to **Daily Sessions** tab → open notes dialog
3. Observe action buttons only include **Cancel** and **Save**
4. Repeat in **Unrealized** tab (Position Notes) and **Realized** tab (Notes for date)

### B) Expenses tab selection/actions + add refresh
1. Open app
2. Go to **Expenses** tab
3. Click a cell/row in the expenses table
4. Observe View/Edit/Delete buttons do not appear
5. Double-click a row/cell
6. Observe nothing happens (should open view dialog)
7. Click **Add Expense**, enter valid data, Save
8. Observe confirmation dialog "Expense added"
9. Observe the new expense does **not** appear in the table even after **Refresh**
10. Close and reopen the app
11. Observe the new expense now appears

## Expected behavior

### A) Notes dialogs
- Notes dialogs show **Cancel / Clear / Save** buttons.
- **Clear** is between Cancel and Save.
- Clear styling matches the Purchase dialog clear button (label/icon + styling).

### B) Expenses tab
- Clicking any cell in a row causes View/Edit/Delete to show appropriately:
  - View/Edit visible when exactly one row is selected
  - Delete visible when one or more rows are selected
- Double-click opens View dialog.
- After adding an expense, the table updates to show the new expense immediately (subject to current filters/search), without requiring app restart.

## Actual behavior

### A) Notes dialogs
- Only **Cancel** and **Save** are present.

### B) Expenses tab
- View/Edit/Delete remain hidden after selecting table rows/cells.
- Double-click has no visible effect.
- Adding expense shows success dialog, but table does not show new row until app restart.

## Investigation notes / likely causes

### A) Notes dialogs
Dialogs are implemented in:
- `ui/tabs/daily_sessions_tab.py`: `DailySessionNotesDialog`
- `ui/tabs/unrealized_tab.py`: `UnrealizedNotesDialog`
- `ui/tabs/realized_tab.py`: `RealizedDateNotesDialog`

These currently build a button row with only Cancel + Save.
Reference for desired Clear button styling/placement:
- `ui/tabs/purchases_tab.py` Purchase dialog action row uses: `✖️ Cancel`, `🧹 Clear`, `💾 Save`.

### B) Expenses tab (selection/actions)
- `ui/tabs/expenses_tab.py` configures the table with:
  - `setSelectionBehavior(SelectItems)`
  - `_on_selection_changed()` uses `selectionModel().selectedRows()`

With SelectItems, `selectedRows()` can be empty even when cells are selected, so buttons never become visible and `_selected_ids()` returns empty.
This also causes double-click view to do nothing because `_view_expense()` depends on `_selected_ids()`.

### B) Expenses tab (new expense not visible until restart)
Likely one of:
- Search text or header filters hiding the newly inserted row; refresh does not clear filters.
- TableHeaderFilter state may be unintentionally hiding all rows post-refresh.

Suggested debugging:
- After `create_expense()` + `refresh_data()`, inspect `self.expenses` length and whether it includes the new expense.
- Check whether `TableHeaderFilter.apply_filters()` is hiding the row.

## Severity
Medium (workflow impaired)

## Environment
- macOS
- Python version: (fill in)

## Acceptance
- [ ] I’ve checked `docs/PROJECT_SPEC.md` and this is unexpected.
- [ ] I’m willing to help test a fix.
- [ ] This bug involves data correctness (should add/adjust a scenario-based test).
