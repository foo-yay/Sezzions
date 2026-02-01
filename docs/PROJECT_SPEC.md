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

### 5.1 Spreadsheet UX (Issue #14, Phase 1)

**Purpose:**
Provide Excel-like usability across all table/tree views in the application:
- Cell-level selection with multi-cell highlights
- Copy selection to clipboard as TSV (Tab-Separated Values)
- Real-time selection statistics: Count, Numeric Count, Sum, Avg, Min, Max
- Context menu: Copy, Copy With Headers
- Keyboard shortcut: Cmd+C / Ctrl+C for copy

**Architecture:**
- Core controller: `ui/spreadsheet_ux.py` (325 lines)
  - `SpreadsheetUXController`: Static methods for widget-agnostic operations
  - `SelectionStats`: Dataclass for computed statistics
  - Currency parsing: Handles `$1,234.56`, `(123.45)` (negative), `100%`, `N/A`, empty strings
  - TSV formatting: Excel-compatible tab-separated values
  - Widget support: QTableWidget (full), QTreeWidget (hybrid)
- Stats bar widget: `ui/spreadsheet_stats_bar.py` (95 lines)
  - Horizontal layout showing 6 statistics
  - Format-neutral: works with currency, percentages, raw numbers
  - Updates dynamically on selection change via `_on_selection_changed()` handlers

**Widget Support:**

*QTableWidget (11 tabs):*
- Purchases, Redemptions, Games, Game Types, Sites, Users, Cards, Redemption Methods, Redemption Method Types, Unrealized, Game Sessions, Expenses
- Selection mode: `ExtendedSelection` + `SelectItems` behavior
- Full cell-level selection support (Qt native)
- Copy extracts exact selected cells

*QTreeWidget (2 tabs):*
- Daily Sessions, Realized
- Selection mode: `ExtendedSelection` + `SelectItems` behavior
- **Qt Limitation**: QTreeWidget doesn't support true cell-level selection
  - When an item is selected, all columns are selected (Qt architecture)
  - `selectedIndexes()` returns all columns for selected items, not just clicked cell
- **Workaround**: Single-cell detection via `currentColumn()` and `currentItem()`
  - If exactly one item selected AND it's the current item AND currentColumn valid → treat as single-cell
  - Extract only the clicked column's value for stats
  - Multi-selection → falls back to full row extraction (all columns)
- This provides "feels like cell selection" UX while respecting Qt constraints

**Integration Pattern (per tab):**
```python
# 1. Add stats bar to layout
self.stats_bar = SpreadsheetStatsBar(self)
layout.addWidget(self.stats_bar)

# 2. Set selection behavior
self.table.setSelectionBehavior(QAbstractItemView.SelectItems)  # or self.tree
self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

# 3. Connect selection handler
self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

# 4. Update stats on selection change
def _on_selection_changed(self):
    grid = SpreadsheetUXController.extract_selection_grid(self.table)
    stats = SpreadsheetUXController.compute_stats(grid)
    self.stats_bar.update_stats(stats)
    self._update_action_buttons()  # If applicable

# 5. Copy methods
def _copy_selection(self):
    grid = SpreadsheetUXController.extract_selection_grid(self.table)
    SpreadsheetUXController.copy_to_clipboard(grid)

def _copy_with_headers(self):
    grid = SpreadsheetUXController.extract_selection_grid(self.table, include_headers=True)
    SpreadsheetUXController.copy_to_clipboard(grid)

# 6. Context menu and keyboard shortcut
copy_shortcut = QShortcut(QKeySequence.Copy, self.table)
copy_shortcut.activated.connect(self._copy_selection)
self.table.setContextMenuPolicy(Qt.CustomContextMenu)
self.table.customContextMenuRequested.connect(self._show_context_menu)
```

**Phase 1 Scope (Read-Only):**
- Cell selection (multi-cell, rectangular regions)
- Copy to clipboard (TSV format)
- Selection statistics
- Context menu
- Keyboard shortcuts (Cmd+C)

**Future Phases (Separate Issues):**
- Phase 2: Inline cell editing
- Phase 3: Paste from clipboard
- Advanced selection: Shift+Click range selection, non-contiguous selection
- Export with selection preserved

**Tests:**
- 39 new tests: 32 core module tests + 7 stats bar widget tests
- Coverage: Currency parsing, TSV formatting, grid extraction, stats computation
- All 545 tests passing

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

### 6.4 Notification System (Issue #28)

**Purpose:**
Provide passive, persistent notifications for important app events without interrupting user workflow:
- Backup reminders (missing directory, overdue backups)
- Redemption pending-receipt tracking (submitted but not received)
- No modal popups—user has full control over notification lifecycle

**Architecture:**
- `models/notification.py`: Notification model with severity (INFO/WARNING/ERROR), state management (read/dismissed/snoozed/deleted)
- `services/notification_service.py`: CRUD operations, state transitions, de-duplication by composite key (type + subject_id)
- `repositories/notification_repository.py`: JSON persistence to settings.json (v1 implementation)
- `services/notification_rules_service.py`: Rule evaluators for backup and redemption conditions
- `ui/notification_widgets.py`: Bell widget with badge, notification center dialog, snooze/dismiss/delete UI
- Periodic evaluation: Startup + hourly QTimer

**Notification Model:**
- **Identity**: type (string), subject_id (optional), title, body, severity (enum)
- **Actions**: action_key (string), action_payload (dict) for routing user clicks
- **State**: created_at, read_at, dismissed_at, snoozed_until, deleted_at
- **Properties**: is_read, is_dismissed, is_snoozed, is_deleted, is_active
- **De-duplication**: Composite key (type, subject_id) ensures only one notification per monitored condition

**Notification Service:**
- `create_or_update()`: De-dupes by composite key; updates existing if found
- `get_all()`, `get_active()`, `get_by_id()`, `get_unread_count()`
- State transitions: `mark_read()`, `mark_unread()`, `mark_all_read()`
- User actions: `dismiss()`, `snooze()`, `snooze_for_hours()`, `snooze_until_tomorrow()`, `delete()`
- Bulk: `clear_dismissed()`, `dismiss_by_type()`

**Notification Rules Service:**
- `evaluate_all_rules()`: Entry point called by QTimer (hourly) and on app startup
- **Backup rules**:
  - `backup_directory_missing`: automatic_backup enabled but directory not configured
  - `backup_due`: last backup > frequency threshold (warning severity)
  - `backup_overdue`: last backup > 2x frequency threshold (error severity)
  - Rules auto-dismiss when conditions resolve
- **Redemption pending-receipt rules**:
  - Queries: `SELECT * FROM redemptions WHERE receipt_date IS NULL AND redemption_date <= ?`
  - Creates one notification per pending redemption (subject_id = redemption_id)
  - Severity: INFO if < 30 days, WARNING if ≥ 30 days
  - Auto-dismisses when redemption_service marks receipt_date
- Event handlers: `on_backup_completed()`, `on_redemption_received(redemption_id)` called by Tools/Redemptions tabs

**UI Components:**
- **NotificationBellWidget**: lightweight overlay button with badge count; pinned to the top-right of the main content inset
  - Transparent background (no pill); shows a red badge when `unread_count > 0`
  - Click opens NotificationCenterDialog
- **NotificationItemWidget**: QFrame for a single notification
  - Severity icon (ℹ️/⚠️/❌), title (bold if unread), body, timestamp
  - Actions: "Open" (if action_key), "Snooze", "Dismiss", "Delete", "Mark Read", "Mark Unread"
- **NotificationCenterDialog**: grouped, scrollable list of notifications
  - Groups: Unread / Read / Snoozed (Read + Snoozed are collapsed by default)
  - "Mark All Read" button (applies to non-dismissed/non-deleted notifications, including snoozed)
  - Snooze presets: 1hr, 4hrs, 24hrs, "Until tomorrow 8am"
  - Badge refreshes immediately after dialog actions
  - macOS theme fix: dialog + scroll viewport forced to paint theme "surface"

**Integration:**
- MainWindow wires NotificationRulesService to access automatic_backup settings
- QTimer (hourly) calls `_evaluate_notifications()` → updates badge
- Tools tab calls `main_window.on_backup_completed()` after backup success
- Redemptions tab calls `main_window.on_redemption_received(redemption_id)` after marking receipt_date

**Persistence (v1):**
- settings.json backed via NotificationRepository
- Future: Split DB-backed (redemption reminders) vs settings-backed (backup alerts) for scalability

**Tests:**
- 19 unit tests covering: CRUD, de-duplication, state transitions, unread count, bulk operations
- No integration tests for rules evaluators yet (future: mock DB/settings, assert notification creation)
- No headless UI smoke test yet (future: boot MainWindow, assert bell exists, open center)

### 6.5 Tax Withholding Estimates (Issue #29)

**Purpose:**
Store and compute date-level tax withholding estimates for informational tax planning. Tax is calculated on the NET P/L of ALL users for each date (winners netted against losers). This is not legal/tax advice; user must consult a tax professional.

**Architecture:**
- **Date-level calculation:** Tax computed once per date on net P/L across all users, not per-session or per-user
- **Storage:** `daily_date_tax` table (keyed by `session_date` only)
  - Columns: `net_daily_pnl`, `tax_withholding_rate_pct`, `tax_withholding_is_custom`, `tax_withholding_amount`, `notes`
  - Notes migrated from `daily_sessions` (now date-level, not user-level)
- **Display:** Tax shown at date level in Daily Sessions tab; user-level rows show $0.00
- **Grouping:** `daily_sessions` uses `end_date` (when session closed) not `session_date` (when started)

**Services:**

`TaxWithholdingService`:
- `get_config()`: reads `tax_withholding_enabled` + `tax_withholding_default_rate_pct` from settings; clamps rate 0..100
- `compute_amount(net_taxable_pl, rate_pct)`: `max(0, net_taxable_pl) * (rate / 100)` using Decimal rounding to cents
- `apply_to_date(session_date, custom_rate_pct)`: Calculate and store tax for ONE date (nets all users)
- `bulk_recalculate(start_date, end_date, overwrite_custom)`: Batch recalc with optional date range filter
- `_calculate_date_net_pl(session_date)`: Sum ALL users' P/L for date from daily_sessions
- Respects custom rates unless `overwrite_custom=True`

`GameSessionService`:
- Auto-recalc on session close: Syncs daily_sessions + recalcs tax for end_date
- Auto-recalc on session edit: Recalcs tax for affected dates (old + new if date changed)
- `_sync_tax_for_affected_dates()`: Called after cascade recalcs (purchase/redemption edits)
- Ensures tax stays accurate during FIFO rebuilds and session recalculations

`RecalculationService`:
- `rebuild_all()`: Now includes tax recalculation in full rebuild workflow
- Uses `end_date` grouping for daily_sessions

`DailySessionsService`:
- `fetch_daily_tax_data()`: Queries `daily_date_tax` table for display
- `group_sessions()`: Shows tax at date level, $0.00 at user level

**Computation Example:**
```
Date: 2026-01-09
  User 1 (Fooyay): +$342.61
  User 2 (Mrs Fooyay): -$205.55
  Net P/L: $137.06
  Tax (20%): $27.41
```

**Settings UI:**
- `tax_withholding_enabled` (bool): master on/off switch
- `tax_withholding_default_rate_pct` (float): default rate applied to dates (clamped 0..100)
- "Recalculate Tax Withholding" button launches dialog

**Bulk Recalculation Dialog (`ui/tax_recalc_dialog.py`):**
- **Date range filter:** From/To date fields with 📅 calendar pickers
- **Options:** Overwrite custom rates checkbox
- **Removed:** Site/user filters (incompatible with date-level netting)
- Leave dates empty to recalculate all dates
- Confirmation dialog shows scope and settings

**Daily Sessions Tab UI:**
- **Date-level:**
  - "✏️ Edit" button opens dialog
  - Dialog shows: Net P/L (blue), Tax Amount (red), Tax Rate, Notes
  - Tax fields read-only (use Settings to recalc)
- **User-level:**
  - No edit button (no per-user tax)
  - Tax column shows $0.00

**Tax Recalculation Triggers:**
1. Session closed → Scoped to end_date
2. Session edited (already closed) → Scoped to affected date(s)
3. Purchase/redemption edited → Cascade recalc triggers tax update for all affected dates
4. Settings → Recalculate Tax Withholding → Optional date range filter
5. Tools → Recalculate Everything → Full rebuild including tax (all dates)

**Migration:**
- Old `game_sessions.tax_withholding_*` columns removed (tax is date-level only)
- Old `daily_sessions.notes` migrated to `daily_date_tax.notes`
- Tax recalculated on first "Recalculate Everything" after upgrade

**Tests:**
- 4 unit tests in `tests/unit/test_tax_withholding_service.py`:
  - bulk_recalc writes correct rate/amount for non-custom dates
  - skip custom-rate dates unless overwrite=True
  - atomicity: failure rolls back all changes
- All 580 tests passing

**Current State:**
- ✅ Complete: Backend, Settings UI, Daily Sessions display, cascade recalculation
- ✅ Date-level netting architecture implemented
- ✅ Auto-recalc on session close/edit and cascade scenarios

### 6.6 Settings UI Entry Point (Issue #31)

**Purpose:**
Provide a first-class, always-available Settings entry point for managing notifications, taxes, and future cross-cutting preferences.

**Architecture:**
- `ui/settings_dialog.py`: Centralized Settings dialog
  - Left navigation list: section names (Notifications, Taxes, etc.)
  - Right stacked widget: section-specific controls
  - Bottom buttons: Cancel, Save
- `ui/main_window.py`: gear icon overlay button
  - Positioned to the left of the notification bell (same top margin)
  - Transparent background, hover effect
  - Clicking opens SettingsDialog
- Settings persistence: uses existing `ui/settings.py` → `settings.json`

**UI Components:**
- **Gear icon** (⚙️): 32x32 button, transparent, positioned dynamically via `_position_notification_bell()` (also positions gear)
- **SettingsDialog**:
  - Modal dialog, minimum 700x500
  - Left nav: "Notifications", "Taxes" (expandable for future sections)
  - Content sections:
    - **Notifications**: `redemption_pending_receipt_threshold_days` spinner (0..365 days, suffix " days")
    - **Taxes**: Enable toggle, default rate percentage, "Recalculate Tax Withholding" button (launches `TaxRecalcDialog`)
  - Save button: persists settings to settings.json, triggers notification rule re-evaluation
  - ESC key: closes dialog without saving

**Integration:**
- MainWindow creates gear button after notification bell
- Gear click calls `_show_settings_dialog()` → opens Settings dialog
- After Save, calls `_evaluate_notifications()` to refresh notification rules (in case threshold changed)

**Tests:**
- 1 headless UI smoke test in `tests/integration/test_settings_dialog_smoke.py`:
  - Boots MainWindow, asserts gear exists and is accessible
  - Simulates gear click, verifies Settings dialog opens and closes cleanly
- All 580 tests passing

**Future expansion:**
- Issue #29 (Part 2) will populate the Taxes section with withholding controls
- Additional sections (e.g., Backup, Display) can be added by extending the nav list and stacked widget
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
