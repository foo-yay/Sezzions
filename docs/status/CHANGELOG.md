# Sezzions — Changelog (Human + AI Parsable)

Purpose: a chronological log of noteworthy changes.

Rules:
- One entry per meaningful change set.
- Prefer adding here over creating a new markdown file.
- Entries must include the metadata block.

---

## 2026-01-29

```yaml
id: 2026-01-29-01
type: feature
areas: [tools, services, ui, architecture]
summary: "Database tools off UI thread with worker-based execution and exclusive operation locking (Issue #7)."
files_changed:
  - app_facade.py
  - ui/tools_workers.py
  - ui/tabs/tools_tab.py
  - tests/unit/test_tools_workers.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Worker-Based Execution**: Backup, restore, and reset operations now run in background workers (`QRunnable`) off the UI thread
  - Each worker creates its own database connection via `db_path` for SQLite thread safety
  - Workers emit signals for progress, completion, and errors
  - UI remains responsive during long-running database operations
- **Exclusive Operation Lock**: Added `AppFacade._tools_lock` (threading.Lock) to prevent concurrent destructive operations
  - `acquire_tools_lock()` / `release_tools_lock()` manage operation state
  - UI checks `is_tools_operation_active()` before starting new operations
  - Users see clear warning if another tools operation is running
- **AppFacade Integration**: Added worker factory methods to facade layer
  - `create_backup_worker()`, `create_restore_worker()`, `create_reset_worker()`
  - UI calls facade methods instead of directly instantiating services
  - Clean separation: UI → Facade → Workers → Services
- **Data-Changed Signal**: Added `ToolsTab.data_changed` signal emitted after restore/reset operations
  - Enables future cross-tab refresh mechanism
  - Currently triggers refresh indicator/prompt (full architecture in future issue)
- **Progress Dialogs**: All operations show indeterminate progress during execution
- **Restore Atomicity**: Merge restore modes now commit once (all-or-nothing) to avoid partial merges on failure
- **Safety Backups**: Pre-restore and pre-reset safety backups run via background worker (no UI-thread blocking)
- **Maintenance Read-Only Mode**: While a tools operation is active, UI-driven DB writes are blocked (prevents adding/deleting records mid-restore/reset)
- **Testing**: New test suite `test_tools_workers.py` with 14 tests covering:
  - Exclusive lock acquisition/release/thread safety
  - Worker creation and parameter passing
  - Independent database connection architecture
  - All tests pass (100% coverage of new code)
- **No Logic Changes**: Backup/restore/reset service logic unchanged—only execution model refactored

Architecture Benefits:
- UI responsiveness during database operations
- Correctness via atomic operations with proper connection lifecycle
- Clean layering (UI never touches DB directly; always via facade/services)
- Thread-safe concurrent operation prevention

Refs: Issue #7 (Phase 3 follow-up — DB tools off UI thread + facade orchestration + exclusive ops safety)

```yaml
id: 2026-01-29-02
type: fix
areas: [tools, ui]
summary: "Fix DB reset progress dialog crash; prevent Reset worker from emitting spurious errors; stabilize Setup success popups on macOS."
files_changed:
  - ui/tabs/tools_tab.py
  - ui/tools_workers.py
  - ui/tabs/users_tab.py
  - ui/tabs/sites_tab.py
  - ui/tabs/cards_tab.py
  - ui/tabs/redemption_methods_tab.py
  - ui/tabs/redemption_method_types_tab.py
  - ui/tabs/game_types_tab.py
  - ui/tabs/games_tab.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Reset Crash**: `Reset` flow now uses `ProgressDialog.update_progress(...)` instead of calling nonexistent `setLabelText/setRange` on `RecalculationProgressDialog`.
- **Worker Correctness**: `DatabaseResetWorker` no longer emits an error signal unconditionally in `finally` (which could cause false error dialogs or raise `UnboundLocalError`).
- **Restore UX**: Restore now uses the same worker-lifetime safeguards as Backup (strong `QRunnable` reference, `setAutoDelete(False)`, queued signal delivery) so the progress dialog reliably closes on completion.
- **Setup Auto-Refresh**: Setup sub-tabs refresh automatically after Tools restore/reset via `ToolsTab.data_changed` → `SetupTab.refresh_all`.
- **Setup Popups**: “Created” success message boxes in Setup sub-tabs now parent to the top-level window (`self.window() or self`) to avoid odd oversized/blank dialog presentation on macOS.
- **Stray Header Popups**: Header filter menus now require a real header mouse press before acting on release, reducing accidental off-screen popups after dismissing modal dialogs.
- **Debug Aid**: Added optional popup tracing via `SEZZIONS_DEBUG_POPUPS=1` to log which widget is being shown (class/flags/stack) when the remaining popup appears.
- **Main Window**: Fixed stale references to a removed top-level `tools_tab`; Tools menu now navigates to Setup → Tools and refresh-all covers Setup correctly.

---

```yaml
id: 2026-01-29-03
type: fix
areas: [tools, services, tests]
summary: "Fix MERGE_ALL restore failing on empty DB due to foreign key ordering (post-reset)."
files_changed:
  - services/tools/restore_service.py
  - tests/integration/test_database_tools_integration.py
  - docs/status/CHANGELOG.md
```

Notes:
- **FK-Safe Merge**: Merge restores temporarily disable FK enforcement during the atomic merge, then run `PRAGMA foreign_key_check` before commit.
- **Better Failure Mode**: If FK violations remain after a merge (e.g., MERGE_SELECTED without parent/setup data), the restore fails with a clearer error and rolls back.
- **Regression Test**: Added an integration test for backup → full reset (setup wiped) → MERGE_ALL restore.

---

```yaml
id: 2026-01-29-04
type: fix
areas: [tools, ui]
summary: "Run automatic backups in background and add passive in-app busy indicator during tools operations."
files_changed:
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Auto-Backup Worker**: Automatic backups now use the same background `DatabaseBackupWorker` path (no UI-thread blocking).
- **Passive Indicator**: Main window shows a small indeterminate progress indicator + text while any tools operation is active.

---

```yaml
id: 2026-01-29-05
type: fix
areas: [ui]
summary: "Fix macOS Help menu visibility and make Tools → Recalculate navigate to Setup → Tools reliably."
files_changed:
  - ui/main_window.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Help Menu**: Added a non-About Help action so the Help menu remains visible on macOS (Qt can move About into the application menu).
- **Recalculate Navigation**: Recalculate menu action now uses the same Setup → Tools navigation path as other Tools menu entries.

---

```yaml
id: 2026-01-29-06
type: feature
areas: [tools, ui, tests]
summary: "Complete Merge Selected restore UX (Issue #8): compact Restore dialog, table selection, and integration tests."
files_changed:
  - ui/tools_dialogs.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_merge_selected_restore.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Restore Dialog UX**: Restore mode selection moved to a combo box with a mode-specific details panel (progressive disclosure).
- **Validation**: Restore action is disabled until a backup is chosen and a mode is selected; Merge Selected additionally requires at least one table chosen.
- **Table Picker Layout**: Merge Selected uses a two-column table picker (Setup vs Transactions) to keep the dialog compact.
- **Testing**: Added integration coverage for MERGE_SELECTED table selection semantics and failure cases.

Refs: Issue #8, PR #13

---

## 2026-01-28

```yaml
id: 2026-01-28-15
type: refactor
areas: [ui, tools, themes]
summary: "Tools tab visual polish: align Tools with Setup tab styling, use SectionBackground cards, and standardize spacing/buttons." 
files_changed:
  - ui/themes.py
  - ui/tabs/tools_tab.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Page Header**: Tools matches other Setup sub-tabs (simple title, no blurb)
- **Section Styling**: Uses theme-consistent `SectionHeader` + `SectionBackground` cards (rounded, higher-contrast)
- **Typography**: Replaced inline `color: #666` styles with `HelperText` objectName for proper dark theme support
- **Button Styles**: Standardized Tools buttons (emoji + no ellipses); only Reset remains red (`DangerButton`)
- **Spacing/Alignment**: Compact 3-card layout with primary + advanced actions; backup location display is elided with tooltip
- **No Logic Changes**: All business logic, service calls, handlers, and threading behavior unchanged—pure UI refactor
- **Testing**: All 433 tests pass; manual verification confirms Tools operations work identically

Refs: Issue #5 follow-up (visual polish)

```yaml
id: 2026-01-28-14
type: refactor
areas: [ui, tools]
summary: "Tools UI redesign and navigation move (Issue #5): moved Tools from top-level tab to Setup sub-tab, standardized styling to match global app patterns without changing logic."
files_changed:
  - ui/main_window.py
  - ui/tabs/setup_tab.py
  - ui/tabs/tools_tab.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Navigation Change**: Tools is no longer a top-level tab; it's now accessible via Setup → Tools (as a sub-tab alongside Users/Sites/Cards/etc.)
- **Why**: Tools is "periodic/maintenance" functionality and doesn't need prime horizontal space in the main tab bar; legacy also placed Tools within Setup
- **UI Standardization**: Removed inline `setStyleSheet()` calls and replaced with object names (`PrimaryButton`, `SuccessButton`, `DangerButton`) for theme consistency
- **Spacing/Layout**: Standardized margins (16px), spacing (12px/8px), button heights (36px), and group box layouts to match other tabs
- **Typography**: Consistent description label styling (`color: #666; font-style: italic;`)
- **No Logic Changes**: All business logic, service calls, signal handlers, and workflows remain identical—this is a pure UI refactor
- **Settings Persistence**: "last_tab" still works (top-level tabs only; Setup sub-tab state not currently persisted, consistent with other sub-tabbed areas)
- **Testing**: Manual verification of all Tools operations (backup/restore/reset, CSV import/export, recalculation) to confirm no regressions

Refs: Issue #5

```yaml
id: 2026-01-28-13
type: fix
areas: [tools, ui, settings, repository]
summary: "Post-PR improvements (Issue #2 follow-up): fixed settings persistence bugs (MainWindow reload pattern, signal blocking), UI polish (spacing, separator removal), repository hygiene (removed 139 .pyc files, added .gitignore), and service bug fixes."
files_changed:
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - ui/settings.py
  - services/tools/reset_service.py
  - services/tools/restore_service.py
  - ui/tools_dialogs.py
  - .gitignore
```

Notes:
- **Problem Discovered**: User testing revealed settings persistence bugs—backup directory, auto-backup checkbox state, and frequency spinner weren't saving across app restarts
- **Root Cause**: Two interacting issues:
  1. `QSpinBox.setValue()` triggered `valueChanged` signal during load, causing premature saves with incomplete state
  2. `MainWindow.closeEvent()` created fresh Settings instance with stale data, overwrote automatic_backup config when saving window geometry
- **Signal Blocking Fix**: Block signals before setValue(), set all widgets while blocked, unblock after—prevents premature signal emission during initialization
- **MainWindow Reload Pattern**: Added `self.settings.settings = self.settings._load_settings()` in closeEvent() before saving geometry—ensures latest settings from disk are loaded before partial update
- **Explicit Disk Sync**: Added flush() and fsync() to Settings.save()—forces OS to write buffers immediately, prevents data loss on crash
- **Attribute Init**: Added `self.backup_dir = ''` in __init__—ensures attribute always exists, simplified conditional logic
- **UI Polish**: Removed vertical separator, added spacing (15px between dir/buttons, 20px before checkbox)—cleaner visual hierarchy
- **Repository Hygiene**: Created .gitignore (Python/IDE/OS exclusions), untracked 139 .pyc files—prevents future cache pollution
- **Service Fixes**: reset_service.py, restore_service.py fixed to use DatabaseManager API correctly (fetch_all/fetch_one/execute_no_commit), tools_dialogs.py added missing imports and fixed font rendering
- **Testing**: Manual verification of settings persistence, signal blocking, reload pattern, git status
- **Design Insight**: Qt signals fire during setValue() even if widget not visible; Settings() creates new instance each call, loads from disk; multiple components sharing settings file must reload before partial updates

Refs: Issue #2, PR #3

```yaml
id: 2026-01-28-12
type: feature
areas: [tools, database, ui, testing]
summary: "Complete database tools implementation (Issue #2): backup/restore/reset with automatic scheduling, audit logging, and comprehensive testing."
files_changed:
  - ui/tabs/tools_tab.py
  - ui/tools_dialogs.py
  - ui/settings.py
  - services/tools/backup_service.py
  - services/tools/restore_service.py
  - services/tools/reset_service.py
  - repositories/database.py
  - settings.json
  - tests/integration/test_database_tools_integration.py
  - tests/integration/test_database_tools_audit.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Manual Backup UI**: Directory selection, "Backup Now" button, timestamped files (backup_YYYYMMDD_HHMMSS.db), status display with file size
- **Restore UI**: RestoreDialog with three modes (Replace/Merge All/Merge Selected), safety backups, file validation, confirmations
- **Reset UI**: ResetDialog with preserve setup data option, table count preview, typed "DELETE" confirmation, optional pre-reset backup
- **Automatic Backup**: JSON-based configuration in settings.json with enable toggle, directory selection, frequency (1-168 hrs), QTimer scheduling (5-min checks), non-blocking execution, color-coded status, test button
- **Audit Logging**: DatabaseManager.log_audit() method, all operations log to audit_log table with action type/table/details/timestamp
- **Testing**: 19 tests total (9 existing database tools + 10 new audit logging tests), all passing
- **Services**: BackupService, RestoreService, ResetService use SQLite online backup API
- **Safety Features**: Integrity checks, automatic safety backups, multiple confirmations, typed confirmations for destructive actions

Refs: Issue #2

```yaml
id: 2026-01-28-01
type: docs
areas: [docs, workflow]
summary: "Consolidated docs governance; created master spec, index, status, and reduced root markdown sprawl."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/status/STATUS.md
  - docs/status/CHANGELOG.md
  - docs/TODO.md
  - docs/adr/0001-docs-governance.md
  - .github/copilot-instructions.md
  - AGENTS.md
```

Notes:
- Canonical docs are now in `docs/`.
- Historical docs are archived under `docs/archive/`.

```yaml
id: 2026-01-28-02
type: docs
areas: [docs, tooling]
summary: "Archived phase-era docs into a dated folder; updated canonical pointers; moved schema validation to tools."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/adr/0001-docs-governance.md
  - docs/status/CHANGELOG.md
  - README.md
  - GETTING_STARTED.md
  - tools/validate_schema.py
  - docs/archive/2026-01-28-docs-root-cleanup/README.md
```

Notes:
- `docs/` root now only contains the canonical set (spec/index/todo + status/adr/incidents).
- Phase/checklist documents are preserved under `docs/archive/2026-01-28-docs-root-cleanup/`.

```yaml
id: 2026-01-28-03
type: docs
areas: [docs, workflow]
summary: "Codified the required human+AI development workflow (TODO → code → tests → spec → changelog)."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/TODO.md
  - docs/adr/0001-docs-governance.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

Notes:
- Future work should follow the documented loop so TODO/spec/changelog stay authoritative.

```yaml
id: 2026-01-28-04
type: docs
areas: [docs, onboarding, workflow]
summary: "Added a contributor-facing workflow section to README so new humans+AI discover the required process immediately."
files_changed:
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-05
type: docs
areas: [tools, documentation]
summary: "Created tools/README.md listing supported utilities and clarifying archive folder status."
files_changed:
  - tools/README.md
  - docs/TODO.md
  - docs/status/CHANGELOG.md
```

Notes:
- Tools directory now has clear documentation for supported utilities (schema validation, CRUD matrix).
- Archive folder explicitly marked as not maintained.

```yaml
id: 2026-01-28-06
type: docs
areas: [workflow, governance]
summary: "Documented explicit ad-hoc request and rollback protocols so work stays auditable even when assigned verbally."
files_changed:
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-07
type: docs
areas: [workflow, governance, onboarding]
summary: "Added an owner-approval gate for closing TODO items and clarified when to use incidents vs TODO."
files_changed:
  - docs/TODO.md
  - docs/INDEX.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-08
type: tooling
areas: [github, ci, workflow]
summary: "Added GitHub-native team workflow scaffolding (Issue templates, PR template, CI workflow)."
files_changed:
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - .github/ISSUE_TEMPLATE/feature_request.yml
  - .github/pull_request_template.md
  - .github/workflows/ci.yml
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-09
type: docs
areas: [workflow, governance, github]
summary: "Made GitHub Issues the primary work tracker; kept docs/TODO.md as an optional offline mirror; added CODEOWNERS."
files_changed:
  - docs/TODO.md
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/adr/0001-docs-governance.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - .github/CODEOWNERS
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-10
type: docs
areas: [workflow, github]
summary: "Documented a branching/PR policy (feature branches per Issue; PR review + CI before merge)."
files_changed:
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-11
type: docs
areas: [github, workflow]
summary: "Enhanced GitHub Issue templates to capture implementation/testing detail; instructed agents to draft issues using templates."
files_changed:
  - .github/ISSUE_TEMPLATE/feature_request.yml
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```
