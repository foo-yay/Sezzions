## Project Overview
This is a desktop Python application for tracking session-based casino play,
including purchases, redemptions, and taxable profit/loss calculations.
Accuracy and auditability are critical.

## Agent Roles

### Planner
- Makes architectural and accounting decisions
- Proposes strategies and tradeoffs
- Does NOT modify code

### Implementer
- Writes code only after planning decisions exist
- Makes minimal, scoped changes
- Does NOT refactor unless explicitly instructed

## Tech Stack
- Python 3.11+
- Qt GUI, ported from a legacy/deprecated TKinter UI found in the deprecated session2.py file
- SQLite database
- No web frameworks currently
- No cloud services currently

## Architecture Rules
- Do NOT create new app entry points without approval
- Primary entry file: qt_app.py
- GUI logic lives in gui_tabs.py
- Database logic lives in database.py
- Other accounting logic lives in business_logic.py
- Other display and helpers are found in table_helpers.py
- Reuse existing patterns before introducing new ones
- Aim for modular code and reusable methods that can be called on as needed.  Avoid redundant code, or methods that perform the same function, but written in multiple places.
- Before implementing new features, check our project to see if a method already exists handling this event.  For example, if you need to create a Game Session from the Purchases tab, and a method already exists to create a new Session, attempt to utilize the existing method rather than writing a new Create Session method from within the purchase scope.  Reusable code is important.

## Agent Rules
- Do not refactor working code unless explicitly asked
- Do not delete deprecated code without confirmation
- Prefer minimal, targeted changes
- Ask before changing data models or schemas

## Domain Rules
- Taxable Profit/loss is calculated per session, not per transaction
- A session may close at zero redemption (total loss)
- Gameplay balance is NOT a source of truth
- Purchases establish basis
- Redemptions reduce basis, then create profit.
- We treat cashflow as separate from profit & loss.
- Cashflow is ascertained in the Unrealized and Realized sections of the app, whereas taxable profit & loss is realized in the Game Sessions and Daily Sessions sections.
- The ratio of SC:Dollar will always be 1:1 unless otherwise specified.

## Database Access Patterns

### sqlite3.Row Objects
- Database queries return `sqlite3.Row` objects (set via `row_factory = sqlite3.Row`)
- **sqlite3.Row is NOT a Python dict** — it does not support `.get()` method
- Access columns using bracket notation: `row["column_name"]`
- Check column existence: `"column_name" in row.keys()`
- Access by index: `row[0]`, `row[1]`, etc.

## Protected Areas
- Do not reintroduce Gameplay P/L columns
- Do not remove session tracking fields
- Do not modify historical data migration logic
- Do not reintroduce other deprecated logic

## Change Workflow
1. Explain intended changes in plain English
2. List files to be modified
3. Make minimal edits
4. Preserve backward compatibility