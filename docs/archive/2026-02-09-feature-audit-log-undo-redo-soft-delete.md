# Feature request — Audit Log viewer + in-order Undo/Redo + soft-delete for core events

## Problem / motivation
Users occasionally make data-entry mistakes (wrong amount/date/user/site; accidental delete), and Sezzions currently has limited “safety net” for recovery:

- Backup/restore exists, but it’s heavy-handed for undoing a small mistake.
- There is no general-purpose, accurate per-change audit trail for core CRUD.
- Many deletes are hard deletes (e.g., purchases/redemptions/sessions), meaning recovery is not practical.

We want a reliable “Excel-like” undo/redo experience (strictly in-order) backed by a durable audit log, plus the ability to recover from accidental deletions via soft delete.

## Proposed solution
Build three additive capabilities (with one intentional behavioral change: converting hard deletes to soft deletes for core event tables):

1) **Audit logging for core CRUD**
- Extend audit logging beyond Tools (backup/restore/reset) so core data mutations (purchases, redemptions, sessions) are logged.
- Log entries include structured JSON snapshots (before/after) sufficient to drive undo/redo.
- Logging should happen at a single orchestration layer (prefer `AppFacade`) to avoid scattering concerns across UI/services/repositories.

2) **In-order Undo/Redo (cursor-based, like Excel)**
- Only undo/redo the most recent change(s) in exact order.
- If a new change occurs after undo, the redo stack is cleared.
- Undo/redo operations must be atomic and must trigger the same downstream rebuild/mark-stale behaviors as the original operations.

3) **Soft delete for purchases/redemptions/game sessions (instead of hard delete)**
- Replace `DELETE FROM …` with `UPDATE … SET deleted_at = CURRENT_TIMESTAMP`.
- Default reads must exclude soft-deleted rows.
- Undo/redo can restore by clearing `deleted_at`.

Access points:
- Program menu: add an “Audit Log…” viewer and Undo/Redo.
- Setup → Tools: add an “Audit Log” section with an entry point to the viewer (and any future export/settings).

## Scope
In-scope:
- Add `deleted_at` to `purchases`, `redemptions`, `game_sessions` and update repositories/services/queries so soft-deleted rows behave as “deleted”.
- Expand audit logging for core CRUD operations (at least: purchases/redemptions/game_sessions create/update/delete/restore).
- Add a read-only audit viewer UI + menu entries.
- Add in-order undo/redo backed by persisted audit snapshots.
- Add/extend automated tests + at least one headless UI smoke test (because menus/dialogs are touched).
- Docs updates: `docs/DATABASE_DESIGN.md`, `docs/PROJECT_SPEC.md`, `docs/status/CHANGELOG.md`.

Out-of-scope (explicit non-goals):
- Selective historical rollback (“undo item from last week while keeping later edits”).
- Multi-user identity/permissions (assume single local user; `user_name` defaults to system unless settings provide a value).
- Tamper-proof audit log / cryptographic integrity.
- Soft-delete rollout for *all* tables (users/cards/sites/etc.) — keep it to the 3 core event tables for now.
- Export to Google Sheets (can be separate issue).

## UX / fields / checkboxes

### Program menu (MainWindow)
Add to Tools menu (or Edit menu if present; if not, keep Tools for consistency):
- Action: **Undo** (shortcut `Cmd+Z`)
  - Disabled when nothing to undo.
  - Tooltip: “Undo last change (in order)”.
- Action: **Redo** (shortcut `Shift+Cmd+Z`)
  - Disabled when nothing to redo.
- Action: **Audit Log…**
  - Opens Audit Log viewer dialog.

### Setup → Tools tab
New section: **Audit Log**
- Helper text: explain what’s tracked and that undo/redo is in-order.
- Button: **Open Audit Log…**
- Optional (if easy without scope creep):
  - Checkbox: “Include system/tool entries” (default ON)
  - Button: “Export visible entries…” (CSV) — if not in scope, omit.

### Audit Log viewer dialog
- Filters:
  - Date range (optional)
  - Table/entity: purchases/redemptions/game_sessions/tools
  - Action type: CREATE/UPDATE/DELETE/RESTORE/UNDO/REDO
  - Search box (search in details/user_name)
- Table columns:
  - Timestamp
  - User
  - Action
  - Entity
  - Record ID
  - Summary (human-readable)
- Details panel:
  - Render JSON details in a readable way (raw JSON text is acceptable v1).
- Buttons:
  - Close
  - Optional: “Undo to here” is **out-of-scope** for v1 (only in-order undo/redo).

Warnings/confirmations:
- Undo/Redo should show a confirmation dialog if the operation affects accounting totals (likely always for these entities). Keep wording simple: “Undo last change? This will recalculate derived totals.”

## Implementation notes / strategy

### Key references (existing)
- Schema + audit table definition: `docs/DATABASE_DESIGN.md` (§12 Audit Log).
- Current audit usage (Tools only): `services/tools/backup_service.py` etc.
- Current DB helper: `DatabaseManager.log_audit()` in `repositories/database.py` (currently commits immediately).
- Transaction atomicity guidance: `DatabaseManager.transaction()` warns to use `execute_no_commit`/`executemany_no_commit`.
- Core CRUD orchestration: `app_facade.py` methods wrap operations and trigger rebuild-or-mark-stale (Repair Mode).
- Current hard deletes:
  - `repositories/purchase_repository.py::delete`
  - `repositories/redemption_repository.py::delete`
  - `repositories/game_session_repository.py::delete`

### Data model / migrations
1) Add soft-delete columns:
- `purchases.deleted_at TIMESTAMP NULL`
- `redemptions.deleted_at TIMESTAMP NULL`
- `game_sessions.deleted_at TIMESTAMP NULL`

2) Add indexes (pattern matches `account_adjustments`):
- `CREATE INDEX IF NOT EXISTS idx_purchases_deleted ON purchases(deleted_at)`
- `CREATE INDEX IF NOT EXISTS idx_redemptions_deleted ON redemptions(deleted_at)`
- `CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON game_sessions(deleted_at)`

3) Migrations must be idempotent (`ALTER TABLE … ADD COLUMN` guarded by `PRAGMA table_info`).

### Repository/service changes (soft delete)
- Replace hard deletes with soft delete updates.
- Add `restore()` methods for these repos.
- Ensure all “list” and “get” queries used for calculations and UI default to `WHERE deleted_at IS NULL`.
  - This is part of the soft-delete conversion: a soft-deleted record must behave like it is absent.
- Derived/linked tables:
  - `redemption_allocations` and `realized_transactions` reference `redemptions` with `ON DELETE CASCADE`, but soft delete will no longer cascade.
  - Rebuild flows should handle this by recomputing allocations/realized from non-deleted redemptions/purchases; do not rely on FK cascades.

### Audit logging strategy
Goals:
- **Accurate** and **atomic** with the mutation it describes.
- **Centralized** to minimize drift and missing coverage.

Approach:
- Add `AuditService` (or extend existing patterns) that:
  - Generates a `group_id` (UUID) per high-level user action (e.g., “Create Redemption”).
  - Records one or more audit rows for that group (e.g., the primary row plus any related/derived operations if desired).
  - Stores `details` as JSON string with at least:
    - `group_id`
    - `entity`
    - `operation`
    - `before` snapshot (dict or null)
    - `after` snapshot (dict or null)
    - `source` (UI tab/dialog)
    - `notes` (optional)

Atomicity requirement:
- `DatabaseManager.log_audit()` currently commits immediately; this breaks atomicity when called inside a transaction.
- Add **a no-commit path** (e.g., `log_audit_no_commit()` or `log_audit(commit: bool = True)`), and use it inside `with db.transaction():`.
- For existing Tools logging, keep current behavior (commit) unless those code paths already manage their own transaction boundary.

Where to hook:
- Prefer `app_facade.py` methods that already own the “business operation boundary” (create/update/delete) and already trigger rebuild/mark-stale.
- Capture snapshots via repository `get_by_id()` before and after.

### Undo/Redo design (in-order)
Persistence:
- Add DB tables (preferred over settings-only) so the stacks are durable:
  - `undo_stack(audit_id INTEGER PRIMARY KEY)`
  - `redo_stack(audit_id INTEGER PRIMARY KEY)`
  - Or a single `undo_redo_state` table with `audit_id`, `state`, `stack_position`.

Snapshot requirements:
- Each undoable audit entry must include enough data to apply forward and reverse operations.

Execution:
- Implement `UndoRedoService` that:
  - `record_undoable_action(audit_id)` pushes to undo stack and clears redo stack.
  - `undo_last()` pops undo entry, applies reverse operation, pushes to redo.
  - `redo_last()` pops redo entry, applies forward operation, pushes to undo.

Applying operations:
- To preserve invariants and downstream recalculation, Undo/Redo should go through the same facade/service entrypoints that normal edits use.
- If necessary, add facade helpers like:
  - `apply_purchase_snapshot(snapshot)`
  - `apply_redemption_snapshot(snapshot)`
  - `apply_session_snapshot(snapshot)`
  - `soft_delete_*` / `restore_*`
  These helpers are “internal plumbing” to ensure undo can restore exact fields.

Atomicity + failure handling:
- Undo/Redo must run in `with db.transaction():` and use `execute_no_commit` paths.
- Failure injection test must prove rollback: if applying reverse fails mid-way, DB state is unchanged and stacks are not corrupted.

Interaction with Repair Mode / rebuild-or-mark-stale:
- Undo/Redo should call the same rebuild-or-mark-stale hook as normal edits.
- If rebuild is deferred (Repair Mode), undo still records the data change and marks stale; the UI should show stale banners as usual.

### UI wiring
- Menu actions call `UndoRedoService.undo_last()` / `redo_last()`.
- Audit viewer dialog reads from `audit_log` (and optionally merges with tool entries).
- Consistent styling: follow Tools tab patterns (`SectionBackground`, helper text) and existing dialog conventions in `ui/tools_dialogs.py` / `ui/settings_dialog.py`.

### Docs updates
- `docs/DATABASE_DESIGN.md`: add soft-delete columns for the 3 tables; document undo/redo stack tables; document audit details JSON contract.
- `docs/PROJECT_SPEC.md`: define semantics (“soft delete acts like delete”; undo/redo is in-order; audit is append-only).
- `docs/status/CHANGELOG.md`: add an entry describing the feature.

### Pitfalls / follow-ups
- Performance: `audit_log` can grow unbounded; plan retention policy (future issue) or simple “Export/Prune” tool.
- Transaction correctness: ensure no-commit audit logging is used inside transactions.
- Cross-entity operations: some actions touch multiple rows; use `group_id` to keep them navigable.
- Privacy: audit details include amounts/notes; treat as local-only data.

## Acceptance criteria
- Soft delete:
  - Given an existing purchase, when it is deleted, then it is excluded from all default UI lists and from all calculations, but the row still exists in DB with `deleted_at` set.
  - Given a soft-deleted redemption, when it is restored (via undo/redo or explicit restore), then it reappears in lists and calculations.

- Audit log capture:
  - Given a create/update/delete/restore on purchases/redemptions/game_sessions, then an `audit_log` row is created with a JSON `details` payload containing at least `before` and `after` (as applicable) and a `group_id`.
  - Given an operation executed inside a facade transaction, then the audit row is committed atomically with the change (no “audit without change” or “change without audit”).

- Undo/Redo:
  - Given a user creates a redemption, when they invoke Undo, then that redemption is effectively removed (soft-deleted) and derived totals match the pre-create state.
  - Given a user undoes the last action, when they invoke Redo, then the change is re-applied and derived totals match the post-change state.
  - Given a user undoes an action and then performs a new edit, then redo is cleared and Redo is disabled.

- UI:
  - Tools menu shows Undo/Redo/Audit Log actions; Undo/Redo are enabled/disabled correctly.
  - Setup → Tools includes an Audit Log section with a button that opens the viewer.

## Test plan
Automated tests (pytest):
- Soft delete behavior:
  - Unit/integration test that repository `delete()` sets `deleted_at` and that fetch/list methods exclude deleted by default.
  - Calculation/regression tests: create purchase + redemption, delete redemption (soft delete), verify realized/unrealized recompute matches expected.

- Audit logging:
  - Integration test: perform facade create/update/delete and assert an audit row is created with required JSON keys.
  - Atomicity test (failure injection): force an exception after data mutation but before audit insert (or vice versa) inside a single transaction and assert rollback leaves neither applied.

- Undo/Redo:
  - Happy path: create → undo → redo for each entity type (purchase/redemption/session).
  - Edge cases:
    - undo with empty stack (no-op; disabled UI action)
    - redo with empty stack
    - undo then new action clears redo

- Headless UI smoke test:
  - Create a `QApplication`, instantiate `MainWindow(AppFacade(...))`, ensure menu actions exist, process events briefly, exit cleanly.

Manual verification:
- Create a purchase, verify it appears; Undo, verify it disappears and totals revert; Redo, verify it returns.
- Delete a redemption, verify it disappears; open Audit Log viewer and see the entry; Undo and confirm restoration.

---

Labels / Area suggestion: UI, Services, Database/Repositories, Tests, Docs
