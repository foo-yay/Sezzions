## Summary

Full Expenses CRUD port to the web app (Phase 4e), matching desktop parity.

Closes #276

## Changes

### Backend
- **Model**: `HostedExpense` dataclass in `services/hosted/models.py` with validation (vendor required, amount >= 0, date required)
- **ORM**: Updated existing `HostedExpenseRecord` — added `notes` column, changed user FK from `CASCADE` to `SET NULL` (matching desktop behavior)
- **Repository**: New `repositories/hosted_expense_repository.py` — standard CRUD with LEFT JOIN to users for `user_name` display
- **Service**: New `services/hosted/workspace_expense_service.py` — workspace-scoped list/create/update/delete/batch-delete
- **API**: 5 endpoints in `api/app.py` — GET list, POST create, PATCH update, DELETE single, POST batch-delete

### Frontend
- **ExpensesTab**: `useEntityTable` hook integration with search, sort, filter, pagination
- **ExpenseModal**: Desktop-parity layout — date/time row, 2-column grid (Amount + Category / Vendor + User), description, notes
- **Categories**: 19 IRS-aligned expense categories via TypeaheadSelect dropdown
- **Autocomplete**: Vendor + notes autocomplete from existing expense data via `buildSuggestions`
- **Navigation**: Wired into `AppShell.jsx` as top-level nav tab with "expenses" icon

## Desktop Parity

| Feature | Desktop | Web |
|---------|---------|-----|
| 19 IRS categories | Editable QComboBox | TypeaheadSelect |
| Vendor autocomplete | PredictiveLineEdit | Dropdown suggestions |
| Notes autocomplete | PredictivePlainTextEdit | Dropdown suggestions |
| Optional user FK | QComboBox (SET NULL) | TypeaheadSelect (SET NULL) |
| 2-column grid layout | QGridLayout | CSS pf-grid |
| Date/Time row | QHBoxLayout | pf-datetime-row |

## Test Results

- 1342 passed, 1 skipped, 0 failures

## Pitfalls / Follow-ups

- The `hosted_expenses` table may need a migration on existing databases to add the `notes` column (currently only defined in SQLAlchemy ORM; existing production DBs may not have it)
- Vendor autocomplete uses simple substring match; could be enhanced with prefix-first matching to mirror desktop `PredictiveLineEdit` behavior
- No integration tests for the new expense API endpoints yet (existing test suite covers model/ORM compatibility)
