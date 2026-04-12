## Problem / Motivation

Phase 4e of the web port: the Expenses entity needs a full CRUD implementation on the web app, matching the desktop app's existing expense tracking feature.

The desktop app (`desktop/ui/tabs/expenses_tab.py`) already supports:
- Expense CRUD with Date, Time, Amount, Vendor, Category, User (optional FK), Description, and Notes
- 19 IRS-aligned expense categories (dropdown with custom text support)
- Vendor autocomplete from existing expense vendors
- Notes autocomplete from existing expense notes
- Collapsible notes section in the dialog
- 2-column grid layout: Amount + Category on row 1, Vendor + User on row 2

## Proposed Solution

Port the full Expenses entity to the web app:

**Backend:**
- `HostedExpense` dataclass in `services/hosted/models.py`
- Update existing `HostedExpenseRecord` ORM (add `notes` column, change user FK to `SET NULL`)
- `HostedExpenseRepository` with standard CRUD + LEFT JOIN to users
- `HostedWorkspaceExpenseService` with list/create/update/delete/batch-delete
- 5 API endpoints in `api/app.py`: GET list, POST create, PATCH update, DELETE single, POST batch-delete

**Frontend:**
- `ExpensesTab/` directory: `ExpensesTab.jsx`, `ExpenseModal.jsx`, `expensesConstants.js`, `expensesUtils.js`
- Desktop-parity modal layout (date/time row, 2-col grid, vendor autocomplete, category TypeaheadSelect, optional user)
- Vendor + notes autocomplete from existing data via `buildSuggestions`
- Wire into `AppShell.jsx` as top-level nav tab with "expenses" icon

## Scope

- [x] HostedExpense model with validation
- [x] ORM record updates (notes column, SET NULL FK)
- [x] Expense repository (CRUD + JOIN)
- [x] Expense service (workspace-scoped CRUD)
- [x] API endpoints (5 standard endpoints)
- [x] Frontend: ExpensesTab + ExpenseModal + constants + utils
- [x] AppShell wiring + Icon

## Acceptance Criteria

- Expenses tab appears in top-level navigation
- Full CRUD: create, view, edit, delete, batch-delete
- Desktop parity: 19 IRS categories, vendor autocomplete, optional user FK, date/time, amount, description, notes
- User FK uses SET NULL (not CASCADE) matching desktop behavior
- All existing tests pass (1342 passed)

## Test Plan

- Existing test suite passes with no regressions
- Manual verification: navigate to Expenses tab, create/edit/view/delete expenses
