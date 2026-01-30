# Sezzions — Master Product & Implementation Spec

Version: 2026-01-29

This document is intended to be the **single consolidated project file** describing Sezzions end-to-end. It should be usable by a developer team (or an AI) to recreate Sezzions with high functional parity.

## 1) Product Overview

### Purpose
Sezzions is a desktop application for tracking casino sweepstakes activity with accounting-grade outputs:
- Purchases (adds basis / SC)
- Redemptions (consumes basis via FIFO, yields cashflow P/L)
- Game sessions (taxable P/L derived from gameplay / balance movements)
- Recalculation tools to keep derived data consistent
- Import/export and database safety tooling

### Primary Users
- Individual player (single operator)
- Potential future: multi-user support, multiple casinos (“sites”)

### Key Non-Goals (for now)
- Web/multi-tenant deployment
- Real-time sync
- Automated bank/casino integrations

## 2) Architecture (Current Paradigm)

### Layering
- `models/`: domain entities
- `repositories/`: database access (SQLite via `DatabaseManager`)
- `services/`: business logic and orchestration
- `ui/`: PySide6 UI; must call services, not repositories directly

Key rule: UI must not talk to the database directly.

### Primary Entrypoint
- Run the app via `python3 sezzions.py` (repo root)
- The app uses `./sezzions.db` by default, or `SEZZIONS_DB_PATH` override.

### Repo Workflow (Source of Truth)
The development workflow (including PR expectations and the "Ready for Review" handoff) is defined in `AGENTS.md` and should be treated as the canonical process.

## 3) Data Model (High-Level)

SQLite database. Core tables and purpose:

- `schema_version`: schema tracking
- `users`, `sites`, `cards`: core entities
- `purchases`: basis lots; `remaining_amount` tracks unconsumed basis
- `redemptions`: cashouts; `more_remaining` differentiates closeout vs partial behavior
- `redemption_allocations`: redemption → purchase mapping (FIFO allocations)
- `realized_transactions`: derived cashflow P/L rows (rebuildable)
- `game_sessions`: derived taxable-session rows (rebuildable)
- `redemption_methods`, `games`, `game_types`: catalogs
- `audit_log`, `settings`: compliance/config

Derived invariants:
- For each purchase: `0 <= remaining_amount <= amount` (unless explicitly allowing edge-case bookkeeping)
- For each redemption: `cost_basis = sum(allocations)` and `net_pl = payout - cost_basis` (except special $0 “close balance” loss entries)

## 4) Core Accounting Semantics

### 4.1 FIFO Basis (Purchases → Redemptions)

- Purchases add basis.
- Redemptions consume basis in chronological order.
- Derived tables (`redemption_allocations`, `realized_transactions`) must be rebuildable from the authoritative purchases/redemptions.

#### Closeout vs Partial Redemption
- `more_remaining = 0` (default behavior): treat redemption as a **closeout**; consume *all remaining basis* up to timestamp.
- `more_remaining = 1`: treat redemption as **partial**; consume only the redemption amount.

This distinction is intentionally “business semantic” and must be preserved.

### 4.2 Cashflow P/L

- Cashflow P/L is primarily produced from redemptions (payout vs basis).
- Unrealized positions represent remaining basis/SC not yet realized.

### 4.3 Taxable P/L (Gameplay Sessions)

Game sessions compute taxable P/L based on redeemable vs locked balances and basis consumption rules.
This is one of the highest-risk correctness areas.

Tax-session logic is high-risk correctness territory. Any changes should be anchored by explicit scenario tests and validated via recalculation.

## 5) UI/UX (Product Behavior)

### Navigation
Main UI is a PySide6 window with primary tabs:
- Purchases
- Redemptions
- Game Sessions
- Daily Sessions
- Unrealized
- Realized
- Expenses
- Setup (sub-tabs: Users, Sites, Cards, Method Types, Redemption Methods, Game Types, Games, Tools)

UI rules:
- UI calls services; no direct SQL in UI.
- Prefer View-first dialog flows; edits are deliberate.
- Bulk actions and destructive actions require confirmation.

## 6) Tools (Operational)

Tools are accessible via Setup → Tools sub-tab and provide "production readiness" capabilities:
- CSV import/export (schema-driven)
- Backup/restore/reset
- Recalculation (full and scoped)

### 6.1 Database Tools (Backup/Restore/Reset)

**Architecture:**
- All database tools operations (backup/restore/reset) execute in background workers off the UI thread
- Workers create independent database connections for SQLite thread safety
- Exclusive operation lock prevents concurrent destructive operations
- Progress dialogs provide user feedback during long-running operations
- Data-changed signal emitted after operations for future cross-tab refresh support

**Worker-Based Execution:**
- `DatabaseBackupWorker`: Creates backup in background thread with own DB connection
- `DatabaseRestoreWorker`: Restores database in background thread with own DB connection
- `DatabaseResetWorker`: Resets database in background thread with own DB connection
- All workers use `QRunnable` pattern with `WorkerSignals` for progress/completion/error
- Workers receive `db_path` (not connection object) to create thread-local connections
- AppFacade provides worker factory methods with exclusive lock management

**Exclusive Operation Lock:**
- AppFacade manages `_tools_lock` (threading.Lock) and `_tools_operation_active` flag
- `acquire_tools_lock()` returns True if lock acquired, False if operation already active
- `release_tools_lock()` releases lock after operation completes
- UI checks `is_tools_operation_active()` before starting new operations
- User sees warning: "Another database tools operation is currently running"
- Prevents data corruption from concurrent backup/restore/reset operations

**Backup Operations:**
- Manual backup: User selects directory, creates timestamped backup files
- Automatic backup: Configurable scheduling (1-168 hours), JSON-based settings, non-blocking QTimer execution
- Backup format: `backup_YYYYMMDD_HHMMSS.db` or `auto_backup_YYYYMMDD_HHMMSS.db`
- Uses SQLite online backup API for consistency
- Optional audit log exclusion during backup
- Settings stored in `settings.json` under `automatic_backup` key
- Runs in background worker with progress dialog

**Restore Operations:**
- **Replace Mode**: Full database replacement (destructive, requires confirmation)
  - Closes connection, replaces file, reopens connection
  - UI must handle connection lifecycle
  - Use case: Complete rollback to backup state
  - Creates pre-restore safety backup automatically
  - Runs in background worker with progress dialog
- **Merge All Mode**: Non-destructive merge of all tables from backup
  - Uses `INSERT OR IGNORE` to skip duplicates based on primary keys
  - Preserves existing data not in backup
  - Use case: Combining data from multiple sources
  - Runs in background worker with progress dialog
- **Merge Selected Mode**: Selective table restoration
  - User specifies exact tables to merge
  - Same INSERT OR IGNORE strategy
  - Use case: Restore specific data only (e.g., purchases)
  - Runs in background worker with progress dialog
- All modes include pre-restore backup integrity verification
- Safety features: automatic backups before destructive operations, confirmation dialogs
- UI remains responsive during restore (worker-based execution)

**Reset Operations:**
- **Full Reset**: Clears all data including setup tables (users, sites, cards, etc.)
  - Multiple confirmation steps including typing "DELETE"
  - Optional pre-reset backup prompt
  - Runs in background worker with progress dialog
- **Partial Reset** (Preserve Setup Data): Clears only transaction tables
  - Preserves: users, sites, cards, redemption_methods, game_types, games
  - Clears: purchases, redemptions, game_sessions, daily_sessions, expenses
  - Use case: Start fresh transactions while keeping configuration
  - Runs in background worker with progress dialog
- **Table-Specific Reset**: Reset individual tables
- Resets autoincrement counters via sqlite_sequence
- Foreign keys temporarily disabled during reset for safe deletion
- Preview mode: shows table counts and records to be deleted without modifying data
- UI remains responsive during reset (worker-based execution)

**Audit Logging:**
- All backup/restore/reset operations log to `audit_log` table
- Entries include: action type, table name, details (file paths, record counts), timestamp
- Action types: `BACKUP`, `RESTORE_REPLACE`, `RESTORE_MERGE`, `RESET_FULL`, `RESET_PARTIAL`
- Audit log can be preserved during reset operations (keep_audit_log flag)
- Backup can optionally exclude audit log for privacy

**Event-Driven Refresh Architecture (Issue #9):**
- **Global Data Change Notifications**: AppFacade provides centralized event emission for all data-modifying operations
  - `DataChangeEvent` payload with `OperationType` enum (CSV_IMPORT, RECALCULATION, RESTORE, RESET, PURCHASE, REDEMPTION, etc.)
  - `AppFacade.emit_data_changed(operation_type, **details)` sends notifications to all registered listeners
  - Services call `emit_data_changed()` after completing write operations
- **Debounced UI Refresh**: MainWindow orchestrates tab refreshes with 250ms debouncing
  - Single `QTimer` (single-shot mode) consolidates multiple rapid data changes into one refresh cycle
  - Prevents performance degradation from cascading/redundant refreshes during bulk operations
  - MainWindow calls `refresh_data()` on all tabs when timer fires
- **Standardized Tab Refresh Contract**: All tabs implement `refresh_data()` method
  - Tabs reload their display data from services (no direct DB access)
  - Idempotent: safe to call multiple times
  - Pattern: disconnect signals → reload data → reconnect signals (prevents feedback loops)
- **Maintenance Mode**: Write-blocking during destructive operations (restore, reset)
  - `AppFacade.enter_maintenance_mode()` / `exit_maintenance_mode()` toggle flag
  - Services check `is_in_maintenance_mode()` and reject writes with user-friendly error
  - Prevents data corruption from concurrent writes during database replacement
  - Automatically exits maintenance mode on operation completion or error
- **Benefits**: Eliminates need for tabs to know about each other, reduces coupling, scales to future multi-window/multi-tab scenarios

**Settings Persistence Architecture:**
- Settings stored in `settings.json` with nested structure (e.g., `automatic_backup` object)
- Each `Settings()` instantiation loads fresh from disk—no singleton pattern currently
- **Critical Pattern**: Components that partially update settings.json must reload from disk first
  - Example: `MainWindow.closeEvent()` reloads settings before saving window geometry to avoid overwriting other components' changes (e.g., ToolsTab's automatic_backup config)
  - Pattern: `self.settings.settings = self.settings._load_settings()` before partial update
- **Signal Management**: Qt widgets emit signals during `setValue()` even during initialization
  - Pattern: Block signals before loading values, unblock after all widgets set
  - Example: `ToolsTab._load_automatic_backup_settings()` blocks spinbox/checkbox signals during load to prevent premature saves
- **Disk Sync**: Settings.save() uses `flush()` and `fsync()` to force OS buffer writes, preventing data loss on crash

**UI Integration:**
- Tools tab provides unified interface for all database operations
- Manual backup: directory picker, "Backup Now" button, status display with file size, last backup timestamp
- Restore: compact mode selection via combo box with progressive disclosure of mode-specific details
  - Restore action is disabled until a backup is selected and a restore mode is chosen
  - Merge Selected shows a two-column table picker (Setup vs Transactions) and requires at least one table selected
  - Dialog sizing: Uses show/hide pattern instead of QStackedWidget for reliable dynamic height adjustment
    - Each mode's detail widget is added directly to layout and shown/hidden based on selection
    - Hidden widgets don't contribute to layout size calculations
    - Standard Qt pattern: hide all widgets → show selected widget → `layout.activate()` → `adjustSize()` → explicit resize
    - Avoids QStackedWidget's tendency to reserve space for largest page
- Reset: dialog with table counts, preserve setup data checkbox, typed confirmation
- Automatic backup: enable toggle, directory selection, frequency spinner (1-168 hrs), status label (color-coded), test button, last backup timestamp display
Helpful maintenance scripts:
- Validate schema vs spec: `python3 tools/validate_schema.py`

Status snapshots:
- [docs/status/TOOLS_DATABASE_PHASE_3_STATUS.md](status/TOOLS_DATABASE_PHASE_3_STATUS.md)
- [docs/status/TOOLS_RECALCULATION_PHASE_4_STATUS.md](status/TOOLS_RECALCULATION_PHASE_4_STATUS.md)

## 7) Testing Strategy

Tests live under `tests/` and use `pytest`.

- Run: `pytest`
- Coverage: `pytest --cov=. --cov-report=html`

Rules:
- Tests should reflect current product semantics.
- If accounting behavior is changed, it must be anchored by an explicit “golden scenario” test.

Recommended additions:
- A small set of scenario-based tests that assert final outputs (basis roll-forward, cashflow P/L, taxable P/L) for hand-computable datasets.

## 8) Development Workflow (Team + AI)

### Canonical docs
See [docs/INDEX.md](INDEX.md) and ADR [docs/adr/0001-docs-governance.md](adr/0001-docs-governance.md).

### Change control
- For non-trivial accounting changes: add/modify a golden scenario test first.
- For architectural decisions: record an ADR.
- For progress tracking: update `docs/status/STATUS.md`.

### Required Workflow (Do Not Deviate)

1. Pick work from a GitHub Issue (preferred) or from `docs/TODO.md` (offline mirror).
2. Implement changes with minimal, surgical edits.
3. Update/add tests to match intended semantics.
4. Update this spec (`docs/PROJECT_SPEC.md`) when behavior/architecture/workflows change.
5. Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes.
6. Open a Pull Request and request owner review.
7. After approval/merge, close the Issue (and only then update any related TODO mirror item).

### Branching & PR Policy

- Default branch (typically `main`) is the stable integration branch.
- For any non-trivial work item, use a feature branch per Issue:
  - Naming: `issue-<id>-<short-slug>` (preferred), or `bug/<slug>`, `feature/<slug>`, `chore/<slug>`.
  - Commit early and often (small, coherent commits).
  - Open a PR early (draft is fine) to get CI feedback.
- Merge via PR after CI is green and owner review is complete.
- Avoid rewriting published history (no force-push) unless explicitly coordinating a cleanup.

## 9) Legacy Relationship

Legacy code is quarantined in `.LEGACY/`.
- It is reference-only.
- Sezzions is the product under active development.

## 10) Open Questions (To Resolve Explicitly)

- Define a single authoritative reconciliation between:
  - FIFO basis/cashflow P&L (redemptions/realized/unrealized)
  - Taxable P&L (gameplay sessions)
- Lock down a minimal set of golden scenarios that “prove” correctness.
