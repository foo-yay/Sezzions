# Copilot / AI agent instructions — Session App (Casino Tracker)

Short: help a coding agent be productive immediately in this repo.

1) Big picture
- Primary purpose: desktop accounting for social-casino sweeps coins. Taxable events are session-based; redemptions move cash. Core accounting lives in `business_logic.py` (FIFO, basis, session reconciling) and is orchestrated from `session2.py` (UI glue, recompute triggers).
- Data store: local SQLite database `casino_accounting.db` (see `database.py`). All code opens short-lived connections via `Database.get_connection()` (row factory -> `sqlite3.Row`). Migrations are additive and idempotent (ALTER TABLE guarded by try/except).

2) Major components & responsibilities
- `business_logic.py`: FIFOCalculator, SessionManager — implement cost-basis, apply/reverse allocations, rebuild sessions, detect freebies. Edit here only for accounting logic changes.
- `session2.py`: GUI event handlers, high-level orchestration, strict business-rule checks (edit/delete protections). Many critical guards live here (e.g., block changing purchase site/amount if consumed).
- `database.py`: schema creation + migrations. Default DB path and PRAGMA-based column checks live here; keep migrations additive.
- `gui_tabs.py`: UI widgets and tab builders. Reusable helpers (date filter, autosuggest) and where import/export buttons call backend methods.
- `table_helpers.py`: `SearchableTreeview` and export helpers. Note data format: `set_data()` expects list of `(values, tags)`; tags are typically `(color_tag, str(id))` and code uses the tag id to map back to DB rows.

3) Critical developer workflows
- Install deps: `pip install -r requirements.txt` (needs `tkcalendar`, `matplotlib`).
- Run the app (dev): `python3 session2.py` (UI main is in this workspace; some headers reference `casino_main_app.py` historically).
- DB lifecycle: code auto-creates and migrates DB on `Database()` init. Use the UI Tools tab for Backup / Restore / Refactor / Recalculate operations; CSV import flow is two-step (upload → then click "Process Imported Data (Purchases, Redemptions, Sessions)").

4) Project-specific conventions & patterns
- Dates: YYYY-MM-DD strings; Times: HH:MM:SS (many parsers accept HH:MM and append :00). Use `parse_date()` from `gui_tabs.py` when parsing user input.
- Monetary inputs: validated via `validate_currency()` in `session2.py` (rejects >2 decimal places, negative values). Follow that formatting when constructing tests.
- UI tables: use `SearchableTreeview.set_data([(values, tags), ...])`. Tags: `(color_tag, str(id))`. Example: `refresh_purchases()` builds `tags = (tag, str(row['id']))`.
- DB access: pattern is open conn -> cursor -> execute -> commit -> close. Many business functions intentionally open/close connections per operation to avoid long transactions.
- Safe migrations: add columns guarded by try/except sqlite3.OperationalError — safely repeatable.

5) Accounting safety rules (must preserve)
- Do NOT change purchase `amount`, `site`, or `user` if `consumed > 0`. The guard is in `session2.save_purchase()`.
- Edits to redemptions involve: reversing tax_session, restoring FIFO basis, then reprocessing (see `save_redemption()` + `delete_redemption()` flows). Follow that exact order when modifying logic.
- FIFO rules: use `FIFOCalculator.calculate_cost_basis`, then `apply_allocation`; to undo use `reverse_cost_basis`.

6) Integration points & extension hooks
- CSV import paths: `import_purchases_data`, `import_redemptions_data`, `import_sessions_data` in `session2.py` — they insert rows then expect a separate processing step that computes FIFO / tax sessions.
- UI Tools: `process_imported_transactions`, `refactor_database`, `recalculate_everything` are entry points for large recomputations (trigger `SessionManager` methods).
- Tests or scripts that need to exercise accounting should import `Database`, `FIFOCalculator`, `SessionManager` directly and run against a disposable SQLite path.

7) Quick examples (how to inspect or re-run logic)
- Recompute all derived data for a pair: in a Python REPL
  from database import Database
  from business_logic import FIFOCalculator, SessionManager
  db=Database('test.db')
  sm=SessionManager(db, FIFOCalculator(db))
  sm.rebuild_all_derived(site_id=1, user_id=1)

8) Files to inspect first when changing behavior
- `business_logic.py` — accounting rules
- `session2.py` — UI guards, import/export, orchestration
- `database.py` — schema/migrations
- `SESSION_APP_ENGINE_HANDOFF.md` — authoritative design notes and constraints

9) When in doubt
- Preserve ordering: redemptions/purchases must be processed chronologically (code explicitly sorts by date/time during imports). Avoid changing that behavior.
- Prefer changing `business_logic.py` for pure accounting fixes and `session2.py` only for orchestration/guarding code.

Feedback: I added this file with repository-specific guidance — tell me which sections need more detail or any missing patterns to include.

10) We have MIGRATED to a new OOP architecture in the /sezzions folder.  See sezzions/IMPLEMENTATION_PLAN.md for details as well as sezzions/README.md and other docs in sezzions/docs.  The legacy code in the root folder (session2.py, business_logic.py, etc) is still the main app for now, but new development should happen in the sezzions/ folder, with reference to the legacy app to ensure strict adherance to logic and algorithmic processing of data.