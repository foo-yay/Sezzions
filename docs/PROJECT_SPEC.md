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

Key rules:
- UI must not talk to the database directly.
- **Transaction Atomicity**: All multi-step database operations (create/update/delete with cascading recalculations) use `with self.db.transaction()` context manager in `AppFacade` to ensure atomicity. Operations either fully succeed or fully roll back—no partial writes.

### Primary Entrypoint
- Run the app via `python3 sezzions.py` (repo root)
- The app uses `./sezzions.db` by default, or `SEZZIONS_DB_PATH` override.
- **Startup Safety**: If data integrity violations or loading errors occur during startup, the app automatically enters maintenance mode (Setup tab only) to allow database repair via Tools without crashing.

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

### 4.2 Expected Balance Checks (Purchase/Session Editing)

When editing a purchase or creating/editing a game session, the system computes "expected" SC balances as of that timestamp to validate user-entered starting balances. This helps catch data entry errors and ensure balance continuity.

**Balance computation logic (`GameSessionService.compute_expected_balances`):**
- Takes a user/site/timestamp cutoff (and optionally an `exclude_purchase_id`)
- Sums all purchases/redemptions up to and including that timestamp
- Uses the last closed session before the cutoff as a checkpoint (if available)
- Returns (expected_total, expected_redeemable)

**Exclusion parameter (Issue #49, 2026-02-04):**
- When editing a purchase, the system must exclude that purchase from its own expected balance calculation to avoid circular inclusion.
- Originally implemented as a "1 second before purchase" time cutoff, which failed when multiple purchases shared the same timestamp.
- Now uses explicit `exclude_purchase_id` parameter passed through the call chain:
  - `PurchasesTab._update_balance_check()` → `AppFacade.compute_expected_balances()` → `GameSessionService.compute_expected_balances()`
- **Behavior:** At a given timestamp, all purchases/redemptions at that timestamp are included in the expected balance **except** the one being edited. This ensures stable, deterministic balance checks even when multiple purchases share the same timestamp.

**Balance chain warnings (Issue #66, 2026-02-05):**
- Purchase dialogs now track balance chains through basis periods to detect balance mismatches accurately.
- **Basis Period:** Bounded by FULL redemptions (`more_remaining=0`). Partial redemptions (`more_remaining>0`) do NOT start new period. Example: Redeem 2500 SC but leave 200 SC → period continues.
- **Balance Chain Logic:**
  - If previous purchase exists in basis period: `expected_pre = prev_purchase.starting_sc_balance` (uses actual balance chain)
  - If first purchase in period: `expected_pre = compute_expected_balances()` (sums SC received from sessions)
  - `total_extra = (actual_pre - expected_pre).quantize(Decimal("0.01"))`
- **Warning behavior:** Warns on ANY non-zero `total_extra` (no tolerance). Real-time label shows "✓ Balance Check: OK" or "✗ Balance Check: X.XX SC HIGHER/LOWER than expected (Y.YY SC)".
- **UI visibility:** Purchase View dialog's Related tab includes a "Full Basis Period" section showing ALL purchases (past, current, future) in the basis period. Current purchase shown in **bold**. View Purchase buttons enable easy navigation through the purchase chain.

**Active session warning (Issue #88, 2026-02-08):**
- When saving a purchase for a (user, site) pair with an **Active** gaming session, the UI shows a blocking confirmation dialog before save.
- Dialog displays session details: start date/time, game/game type, starting balance, and reminds user to verify Post-Purchase SC accuracy.
- If user confirms, purchase is saved and explicitly linked to the active session with relation `DURING`.
- Success message includes a "View Session" button to navigate directly to the linked session.
- **Link Builder Enhancement:** Link rebuilder now classifies purchases as `DURING` for active sessions (timestamp >= session start) in addition to closed sessions (timestamp within session window).
- Rationale: "Current SC" is a moving target during play; explicit confirmation reduces risk of incorrect balance entry and ensures immediate session-event linkage.

### 4.3 Cashflow P/L

- Cashflow P/L is primarily produced from redemptions (payout vs basis).
- Unrealized positions represent sites with remaining SC (position still open).
- **Issue #44 (2026-02-02):** Unrealized tab estimates current balances by incorporating purchases/redemptions after the most recent checkpoint.
- **Issue #61 (2026-02-05):** Unrealized now uses **the most recent checkpoint** among:
  1. **Purchase snapshots** (`starting_sc_balance` when recorded) — captures site SC including dailies/bonuses at purchase time
  2. **Session starts** (`starting_balance` + `starting_redeemable`) — both Active and Closed sessions
  3. **Session ends** (`ending_balance` + `ending_redeemable`) — Closed sessions only
  4. **Balance checkpoints** (`account_adjustments` of type `BALANCE_CHECKPOINT_CORRECTION`) — explicit known balances captured in Setup → Tools
  - Formula: `estimated_total_sc = checkpoint_total_sc + purchases_since_checkpoint - redemptions_since_checkpoint`
  - When checkpoint is a purchase snapshot, that purchase's `sc_received` is **not** double-counted in the deltas.
  - Redeemable SC formula: `estimated_redeemable_sc = checkpoint_redeemable_sc - redeemable_redemptions_since_checkpoint` (if checkpoint is within current position start_date). Informational only; free SC redemptions (`is_free_sc=1`) are excluded from this calculation as they don't affect redeemable balance.
  - **Unrealized P/L calculation:** Uses total SC × sc_rate for current value (not redeemable SC). Represents "money out vs current potential value."
  - This provides a "site-realistic" current view (dailies/bonuses captured via snapshots).
  - Columns: "Total SC (Est.)", "Redeemable SC (Position)", "Est. Unrealized P/L"
- **Issue #58 (2026-02-04):** Unrealized positions remain visible when `Total SC (Est.) > 0` even if `Remaining Basis = $0.00`.
  - This allows partial redemptions that consumed all basis (via FIFO) to still show in Unrealized if profit-only SC remains on the site.
- **Related tab scoping (2026-02-13):** The Unrealized “View Position” dialog’s Related tab anchors to the position’s basis window when basis remains; for profit-only positions (basis = $0), Related anchors to the latest non-adjustment checkpoint to avoid showing lifetime history. The “Related Purchases” list prefers FIFO-attributed purchases from `redemption_allocations` so contributing purchases still appear even when remaining basis is $0.
- **Position closure (2026-02-05):** Positions are removed from Unrealized when a closure event datetime >= last activity datetime. Closure events:
  - Explicit "Balance Closed" marker (`amount=0, notes LIKE 'Balance Closed%'`)
  - FULL redemption (`more_remaining IS NOT NULL AND more_remaining = 0`)
  - **Semantics:** `more_remaining=0` means "I'm cashing out everything I want to/can; treat remaining balance as dormant." Position automatically reopens when new activity (purchases, sessions) occurs after closure datetime.
  - **Position visibility:** Positions removed when: (a) estimated SC < threshold (0.01), (b) closure event datetime >= last activity, or (c) no checkpoint available.

### 4.4 Taxable P/L (Game Sessions)

Sezzions computes **taxable gameplay P/L** using game sessions. This is one of the highest-risk correctness areas.

#### Key terms (dogmatic semantics)

- **Redeemable SC (site state):** SC that the casino site currently shows as redeemable/withdrawable. This number can change *outside* of tracked sessions (free spins, bonus drops, adjustments, etc.).
- **Recognized / “earned” SC (Sezzions accounting):** Sezzions intentionally does **not** recognize taxable gains at the moment redeemable SC appears on a site.
  - Instead, Sezzions recognizes taxable outcomes **only when a game session is closed**.
  - This is a deliberate tradeoff to avoid requiring the user to monitor dozens of sites continuously.
- **Expected start redeemable:** the redeemable SC that Sezzions believes was already “recognized” as of the session start (typically prior closed session ending redeemable, after applying any redemptions).
- **Discoverable SC:** redeemable SC that is present at session start above the expected checkpoint.
  - `discoverable_sc = max(0, starting_redeemable - expected_start_redeemable)`
  - Interpretation: “redeemable that appeared since the last checkpoint, and is now being recognized within this session.”

#### Session taxable P/L formula

Per closed session:

- `delta_redeem = ending_redeemable - starting_redeemable`
- `net_taxable_pl = ((discoverable_sc + delta_redeem) * sc_rate) - basis_consumed`

Important identity (why off-session freebies don’t get taxed if lost):

- `discoverable_sc + delta_redeem = ending_redeemable - expected_start_redeemable`

So if redeemable SC appears between sessions (becomes discoverable at next start) and is then lost during play, the loss nets it out automatically because the end redeemable is lower.

#### Basis consumption and cash-in/cash-out alignment

- `basis_consumed` is **not** simply “cash spent this session”. It is consumed when locked/bonus SC is processed into redeemable through play, and it can draw from a rolling pending-basis pool.- **Calculation**: The amount of locked SC processed is calculated as: `locked_start + purchases_during_sc - locked_end`, where:
  - `locked_start` = locked SC at session start
  - `purchases_during_sc` = total SC from purchases made during the session (linked as DURING)
  - `locked_end` = locked SC at session end
  - This ensures purchases made during an active session are properly accounted for in basis consumption.- As a result, **single-session net taxable P/L may diverge from a simple money-in/money-out story** whenever:
  - purchases are not fully “processed” (locked SC remains locked),
  - basis is carried across sessions (pending basis pool is non-zero),
  - or session segmentation/balances are inaccurate.
- Over a longer horizon, as locked SC is processed and the pending basis pool returns to ~0, the cumulative taxable results will generally align much more closely with “net redeemable produced minus paid-in basis,” but it is not guaranteed session-by-session.

#### Testing and change control

Tax-session logic is high-risk correctness territory. Any changes must be anchored by explicit scenario tests (hand-computable datasets) and validated via full recalculation.

### 4.5 Cross-Event Timestamp Uniqueness (Issue #90)

To maintain data integrity and prevent ambiguous event ordering, Sezzions enforces **cross-event timestamp uniqueness** across all transaction and session event types.

#### Uniqueness Rules

- **Event types**: purchases, redemptions, session_start, session_end
- **Scope**: Per (user_id, site_id) pair
- **Enforcement**: `services/timestamp_service.py` → `ensure_unique_timestamp(user_id, site_id, date_str, time_str, event_type, exclude_id)`
- **Behavior**: If the requested timestamp conflicts with an existing event, auto-increment by 1 second until unique (max 3600 attempts)
- **Return value**: `(adjusted_date_str, adjusted_time_str, was_adjusted)`

#### UI Integration (Real-Time Warnings)

**Affected dialogs**: All transaction/event entry/edit dialogs:
- PurchaseDialog, EditPurchaseDialog
- RedemptionDialog, EditRedemptionDialog
- StartSessionDialog, EditSessionDialog
- EndSessionDialog
- EditClosedSessionDialog (two banners: start and end timestamps)

**Banner behavior**:
- QLabel with `ObjectName="HelperText"`, `status="info"`
- Text: "ℹ️ Time will be adjusted to HH:MM:SS (original already in use)"
- Hidden by default; shown when conflicts detected
- Connected to user/site/date/time field changes via `_update_timestamp_info()` methods
- Uses `ensure_unique_timestamp()` to check for conflicts and display adjusted time

**Layout management**:
- Banners inserted into existing datetime_section layouts
- `updateGeometry()` calls force Qt to recalculate dialog height
- No explicit height management needed; Qt handles resizing automatically

#### Validation Impact

**Redemption validation** (Issue #90 bug fix):
- Previously checked for game sessions using user-entered timestamp → false "No game sessions" errors
- Now uses ADJUSTED timestamp from `ensure_unique_timestamp()` and converts to UTC for session queries
- Code: `ui/tabs/redemptions_tab.py` (session check block)

**Session end validation**:
- Previously used wrong event_type ("session_start" instead of "session_end")
- Fixed to use correct event_type and `self.session.user_id/site_id`

#### Implementation Notes

**Lookup patterns**: Different dialogs use different lookup dictionary patterns:
- Purchases: `{name.lower(): user_id}` → use `user_id` directly
- Redemptions: `{name.lower(): id}` → use `id` directly (not `object.id`)
- Sessions: `{name.lower(): object}` → use `object.id`

**EditClosedSessionDialog**: Requires TWO timestamp banners:
- `start_timestamp_info_label` (event_type="session_start")
- `end_timestamp_info_label` (event_type="session_end")
- Each connected to separate `_update_start_timestamp_info()` and `_update_end_timestamp_info()` methods

**Transaction atomicity**: Timestamp adjustments occur during save operation within `AppFacade` transaction context; rollback on any failure prevents partial writes.

### 4.6 Adjustments & Corrections

Sezzions supports two types of manual adjustments to correct accounting issues or incorporate external data:

#### 4.6.1 Basis Corrections (BASIS_USD_CORRECTION)

Basis adjustments allow manual corrections to cost basis when errors occur or external factors require adjustment.

- **Purpose**: Correct purchase cost basis errors (e.g., missed fees, refunds, chargebacks)
- **Mechanism**: Adds a delta (positive or negative) to the FIFO pipeline as a synthetic purchase
- **Integration**: Synthetic adjustments are inserted into the FIFO rebuild with negative IDs (to avoid collisions with real purchases)
- **Effective timestamp**: Adjustments participate in FIFO ordering based on their `effective_date` and `effective_time`
- **Use case example**: A $25 purchase fee was missed; create a +$25 basis adjustment to correct total cost

#### 4.6.2 Balance Checkpoints (BALANCE_CHECKPOINT_CORRECTION)

Balance checkpoints establish known balances at specific timestamps, overriding prior calculations.

- **Purpose**: Correct balance continuity errors or import external balance data
- **Mechanism**: Checkpoints take priority over closed sessions in expected balance calculations
- **Integration**: `compute_expected_balances()` uses the most recent checkpoint before a given timestamp as the anchor
- **Fields**: `checkpoint_total_sc` and `checkpoint_redeemable_sc` specify known balances
- **Use case example**: After reconciling with casino site, establish a known $1,500 SC balance at a specific date/time

#### 4.6.3 Adjustment Properties

All adjustments share:
- **Soft delete**: Adjustments can be deleted without losing audit history (`deleted_at`, `deleted_reason`)
- **Restoration**: Deleted adjustments can be restored
- **Filtering**: Adjustments can be filtered by user, site, type, date range
- **Recalculation trigger**: Creating/deleting/restoring adjustments requires recalculation for the affected (user_id, site_id) pair
- **Audit fields**: `reason` (required), `notes` (optional), `related_table`/`related_id` (optional foreign reference)

#### 4.6.4 UI Access (Tools Tab)

The Tools tab provides:
- **New Basis Adjustment** dialog: user/site selectors, date/time, delta amount, reason
- **New Balance Checkpoint** dialog: user/site selectors, date/time, total SC, redeemable SC, reason
- **View Adjustments** dialog: table view with filters, soft delete, restore functionality

#### 4.6.5 UI Visibility + Basis-Period Scoping

- **View dialogs**: Purchase / Redemption / Game Session / Realized / Unrealized dialogs show a brief “Adjustments & Checkpoints” section and a conditional “Adjustments” tab when relevant adjustments/checkpoints exist.
- **Adjusted badges**: Purchase / Redemption / Game Session list tables display an “Adjusted” info icon when adjustments/checkpoints exist inside the record’s basis window.
- **Basis window**: Basis-period windows are anchored by checkpoints **and** full-redemption boundaries to avoid cross-period leakage when a redemption fully resets remaining balance.
- **Autocomplete + time normalization**: Adjustment and Checkpoint dialogs use editable combo boxes with autocomplete (matching Add Purchase behavior) and accept HH:MM or HH:MM:SS, storing times as HH:MM:SS (defaulting seconds to :00).

### 4.7 Audit Logging, Soft Delete, and Undo/Redo (Issue #92)

Sezzions provides comprehensive audit trails, soft deletion for core entities, and Excel-like in-order undo/redo functionality to enable safe data recovery and change tracking.

#### 4.7.1 Soft Delete for Core Entities

**Schema:**
- `purchases.deleted_at TIMESTAMP NULL`
- `redemptions.deleted_at TIMESTAMP NULL`
- `game_sessions.deleted_at TIMESTAMP NULL`
- Indexes: `idx_purchases_deleted`, `idx_redemptions_deleted`, `idx_sessions_deleted`

**Behavior:**
- "Delete" operations set `deleted_at = CURRENT_TIMESTAMP` instead of removing rows
- All default queries filter `WHERE deleted_at IS NULL`
- Soft-deleted records are excluded from calculations, reports, and UI lists
- Records can be restored by clearing `deleted_at` (via undo/redo or explicit restore)

**Rationale:**
- Enables recovery from accidental deletions
- Preserves audit history
- Supports undo/redo without data loss

#### 4.7.2 Audit Logging

**Purpose:**
Capture a durable, structured log of all CRUD operations on core entities (purchases, redemptions, game_sessions, account_adjustments) with sufficient detail to drive undo/redo and provide compliance/debugging trails.

**Schema (`audit_log` table):**
- `action`: CREATE, UPDATE, DELETE, RESTORE, UNDO, REDO
- `table_name`: Entity table (purchases, redemptions, game_sessions)
- `record_id`: Primary key of affected record
- `user_name`: Operator (defaults to "system")
- `timestamp`: Operation timestamp (CURRENT_TIMESTAMP)
- `details`: Human-readable summary
- `old_data`: JSON snapshot before change (TEXT, nullable)
- `new_data`: JSON snapshot after change (TEXT, nullable)
- `group_id`: UUID linking related operations (e.g., bulk deletes)

**Implementation Architecture:**
Audit logging happens at the **service layer** (not AppFacade). See ADR-0002 for detailed rationale.

**Adjustments/Checkpoints:**
- `account_adjustments` now emits CREATE/DELETE/RESTORE audit entries for basis adjustments and balance checkpoints.
- Undo/redo stacks include adjustment operations so changes can be reversed and replayed like purchases/redemptions/sessions.

**Pattern (service methods):**
```python
# UPDATE example
def update_entity(self, entity_id, **kwargs):
    entity = self.repo.get_by_id(entity_id)
    old_data = asdict(entity)  # Capture BEFORE mutations
    
    # Apply changes...
    result = self.repo.update(entity)
    
    if self.audit_service:
        self.audit_service.log_update('table', entity.id, old_data, asdict(result))
    return result
```

**Key characteristics:**
- Services own audit logging (purchases, redemptions, sessions)
- `old_data` captured immediately after fetch, before any modifications
- `AuditService` injected via property (not constructor) in `AppFacade`
- `auto_commit=True` by default; services can use `auto_commit=False` for explicit transaction management
- Bulk operations use `group_id` to link related audits
- Snapshots use `dataclasses.asdict()` to serialize model state as JSON

**Atomicity:**
- Audit calls happen within the same service method as data mutation
- Services manage transactional boundaries
- Audit logging uses `auto_commit` parameter to participate in parent transactions
- If operation fails, both data change and audit log roll back together

**Audit Retention (Issue #97):**
- Two-tier retention system: meaningful summaries retained long-term, full old_data/new_data pruned after limit
- `audit_log.summary_data` column: compact JSON summaries for critical fields
  - Purchases: `{amount, user_id, site_id, starting_sc}`
  - Redemptions: `{amount, user_id, site_id}`
  - Game sessions: `{start_datetime, end_datetime, starting_sc, ending_sc, user_id, site_id}`
- Configurable row limit: default 10,000 rows, 0 = unlimited
- Pruning: atomic deletion of oldest rows when limit exceeded (preserves summaries)
- Settings UI: "Audit Log Retention" spinbox in Settings → Data section
- Auto-prune triggered when limit changes in Settings dialog

**CSV Export (Issue #97):**
- `AuditService.export_audit_log_csv(output_path, start_date=None, end_date=None)`
- Exports all columns including `summary_data`
- Optional date range filtering (inclusive)
- Returns count of rows exported
- Accessible via "Export to CSV" button in Audit Log Viewer dialog

#### 4.7.3 In-Order Undo/Redo

**Behavior:**
Excel-like undo/redo: strictly in-order (LIFO for undo, FIFO for redo). New operations after undo clear the redo stack.

**Persistence:**
- Undo/redo stacks stored in `settings` table as JSON arrays
- Each stack entry references an `audit_log` entry via `group_id`
- Stacks survive app restart

**Service (`UndoRedoService`):**
- `can_undo()` / `can_redo()`: Check stack state (for UI enable/disable)
- `undo()`: Pop undo stack, reverse operation, push to redo stack
- `redo()`: Pop redo stack, replay operation, push to undo stack
- `record_undoable(group_id)`: Push new operation to undo stack, clear redo stack

**Reversal strategy:**
- CREATE → soft-delete
- UPDATE → restore old snapshot (calculated fields excluded for game_sessions)
- DELETE → restore (clear deleted_at)
- Operations go through same service layer to ensure downstream recalculation
- Post-operation callback triggers P/L recalculation for affected user/site pairs (Issue #97)

**Limitations:**
- Cannot selectively undo past operations (no "undo item from last week")
- Stack cleared on certain operations (e.g., bulk rebuild, schema migration)
- UI must call `_update_undo_redo_states()` after operations to refresh menu states

#### 4.7.4 UI Access

**Main Menu (Tools):**
- **Undo** (Ctrl+Z / Cmd+Z): Undo last operation
- **Redo** (Ctrl+Shift+Z / Cmd+Shift+Z): Redo last undone operation
- **View Audit Log…**: Open audit viewer dialog
- Actions disabled when stacks are empty

**Tools Tab (Setup → Tools):**
- **Audit Log section**: Collapsible section with description of audit capabilities
- **Open Audit Log…** button: Opens viewer dialog

**Audit Log Viewer Dialog:**
- Date range presets: All Time, Today, Last 7 Days, Last 30 Days, This Month, This Year, Custom
- Filters: Date range (via presets or custom dates), table name, action type, limit
- Table: Sortable columns (ID, Timestamp, Action, Table, Record ID, User, Group ID)
- Details panel: Expandable JSON view of old_data/new_data/summary_data
- Export to CSV: Exports current filter results with optional date range filtering (Issue #97)

**Undo/Redo Confirmation:**
- Simple confirmation dialog: "Undo last change? This will recalculate derived totals."
- No "undo preview" (complex to implement accurately)

#### 4.7.5 Architectural Decision (ADR-0002)

Audit logging was implemented at the **service layer** rather than centralized in `AppFacade`, despite the Issue #92 preference for centralization.

**Rationale:**
- Atomicity: Services own transactional boundaries
- Simplicity: Services know what changed (old vs new state)
- Type safety: No reflection/introspection needed
- Flexibility: Per-entity customization possible

**Trade-offs:**
- Distributed code (audit calls in multiple services)
- Requires discipline when adding new CRUD methods

See `docs/adr/0002-audit-logging-at-service-layer.md` for full justification.

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
- Dialog secondary labels use theme-managed `MutedLabel` styling for dark-theme readability.
- Global Qt stylesheet is maintained in `resources/theme.qss` with theme variables substituted at runtime by `ui/themes.py`.

Window Constraints (Issue #76):
- Tools tab wrapped in QScrollArea to prevent off-screen expansion
- Collapsible sections can be expanded without resizing window beyond screen bounds
- Scroll bars appear automatically when content exceeds visible area
- Tools tab styling follows global theme patterns (no local overrides)

Game Sessions convenience:
- Sezzions keeps **1 game per session** (accounting clarity), but provides a fast workflow to chain sessions across games:
  - End Session dialog: **"End & Start New"**
  - New Start Session dialog is prefilled with the ended session’s ending balances (same user/site); game selection is intentionally left blank.

### Default Date Filter Presets

Many primary tabs use `DateFilterWidget` as the first-level time scoping control.

Default presets (on initial tab load):
- Purchases / Redemptions / Game Sessions / Daily Sessions / Realized / Expenses: **current calendar year**
- Unrealized: **all time** (implemented as 2000-01-01 → today)

### Quick Filter Toggles (Issue #121)

In addition to date/search/header filters, key tabs provide persistent one-click quick filters:

- **Purchases tab**: `Basis Remaining`
  - Placement: immediately left of `📤 Export CSV`
  - Behavior: shows only purchases with `remaining_amount > 0`

- **Redemptions tab**: `Pending`, `Unprocessed`
  - Placement: immediately left of `📤 Export CSV`
  - `Pending`: receipt not recorded (`receipt_date` empty/NULL)
  - `Unprocessed`: `processed == False`
  - If both are checked, both predicates are applied (AND behavior)

- **Game Sessions tab**: `Active Only`
  - Placement: between `Active Sessions: X` and `📤 Export CSV`
  - Behavior: shows only sessions with `status == 'Active'`

Persistence and clearing rules:
- States persist via application settings across restarts.
- Existing per-tab “Clear All Filters” actions also clear these quick toggles.

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
- Repair Mode (Issue #55)

### 6.1 Repair Mode

**Purpose:**
Provides controlled environment for troubleshooting derived data corruption by disabling automatic rebuilds and tracking affected (user, site) pairs.

**Problem:**
When derived data (FIFO allocations, cost basis, P/L) becomes corrupted, automatic rebuilds after every edit make it difficult to isolate the root cause or perform systematic repairs.

**Architecture:**
- `RepairModeService`: Manages enabled state and stale pair list (settings.json persistence)
  - `is_enabled()`: Check if repair mode is active
  - `set_enabled(bool)`: Toggle repair mode state
  - `mark_pair_stale(user_id, site_id, from_date, from_time, reason)`: Record affected pair
  - `clear_pair(user_id, site_id)`: Remove from stale list
  - `clear_all()`: Clear entire stale list
  - `get_stale_pairs()`: Retrieve list of stale pairs with metadata
- `AppFacade._rebuild_or_mark_stale()`: Conditional helper method used by all CRUD operations
  - Normal mode: Immediately rebuilds derived data (FIFO allocations + session-event links) for affected pair
  - Repair mode: Marks pair as stale and skips rebuild
- Stale pair tracking:
  - Key: `{user_id}:{site_id}`
  - Value: `{from_date, from_time, updated_at, reasons: []}`
  - Persisted in settings.json under `repair_mode_stale_pairs`
  - Cross-pair operations (e.g., reassigning purchase to different site) mark both old and new pairs stale

**UI Components:**
- Tools tab section (collapsible):
  - Status indicator: 🔴 ENABLED (red bold) or 🟢 Disabled (green)
  - Toggle button: Styled red in normal mode to indicate danger of enabling
  - Stale pairs count: Shows number of pairs needing rebuild (red if > 0)
  - "Rebuild Stale Pairs" button: Uses existing recalculation worker
  - "Clear Stale List" button: Remove stale markers without rebuilding
- MainWindow integration:
  - Red banner at top: "🔧 REPAIR MODE — Auto-rebuild disabled" (mirrors Maintenance Mode pattern)
  - Window title suffix: " - REPAIR MODE"
  - `refresh_repair_mode_ui()`: Rebuilds tabs to update banner/title when mode toggled
- `RepairModeConfirmDialog`: Blocking confirmation dialog on enable
  - Warning bullets explaining consequences
  - Required acknowledgment checkbox
  - Red "Enable Repair Mode" button (disabled until checkbox checked)

**Workflow:**
1. Enable Repair Mode via Tools tab (confirmation required)
2. Perform troubleshooting edits/imports/corrections
3. Review stale pairs list (shows which (user, site) pairs are affected)
4. Rebuild selected/all stale pairs when ready (or clear list if manually verified)
5. Disable Repair Mode to resume normal auto-rebuild behavior

**Safety:**
- Cannot enable while Maintenance Mode is active (blocking check per Issue #55)
- Disable is immediate (no confirmation needed)
- All CRUD operations affected: purchases, redemptions, sessions, expenses, adjustments
- Stale pairs persist across app restarts (settings.json)

**Implementation Notes:**
- Refactored 10+ CRUD methods in `AppFacade` to use `_rebuild_or_mark_stale()` instead of direct rebuild calls
- Cross-pair moves (e.g., `update_purchase()` with site_id change) mark both old and new pairs stale
- Rebuild uses existing `RecalculationWorker` infrastructure with progress dialog
- Clear stale list warns user that data won't be recalculated (useful if manually verified)

### 6.2 Database Tools (Backup/Restore/Reset)

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
- Workers must close their thread-local database connections in a `finally:` block to avoid leaked resources and test warning noise
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
  - Settings: `enabled`, `directory`, `frequency_hours`, `last_backup_time`
  - Notification settings (Issue #35): `notify_on_failure`, `notify_when_overdue`, `overdue_threshold_days`
  - Timer checks every 5 minutes if backup is due
  - Automatic backups create notifications on failure (if enabled) and when overdue (if enabled and past threshold)
  - Checkbox state persists correctly (signals properly unblocked after load)
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

**Time Zone & UTC Storage (Issue #107 / #117):**
- `settings.json` stores `accounting_time_zone`, `current_time_zone`, `travel_mode_enabled`, plus legacy `time_zone` (IANA names).
- All user-entered timestamps are stored in UTC in the database (purchases, redemptions, sessions, adjustments, expenses, audit log).
- Repository/services convert UTC → local for display and business logic.
- **Accounting Time Zone** controls daily bucketing/reporting; stored in `accounting_time_zone_history` for effective-dated changes.
- **Entry Time Zone** controls how new timestamps are interpreted; Travel Mode allows Entry TZ to differ from Accounting TZ.
  - On edit/save, if the stored entry TZ differs from current mode, the user is prompted to optionally re-stamp the entry TZ.
- Accounting TZ changes recompute derived daily tables from the effective UTC timestamp.
- Audit log date filters convert local date ranges to UTC bounds before querying.
- Unrealized positions convert UTC timestamps to local dates for start/last-activity filtering in the UI.
- Daily Sessions merges `daily_date_tax` by local session dates so Tax Set-Aside aligns with displayed rows.
- Tax withholding rollups compute net daily P/L using local end dates (local day boundaries).
- Tax and session P/L reports (and realized transaction filters) convert local date ranges to UTC bounds using stored timestamps.
- Realized tab groups transactions by local day using redemption timestamps; view-position dialogs display related purchase/session times in local time.
- Game session recalculation uses local timestamps converted to UTC when finding containing sessions.
- Expected balance checks compare UTC instants across entry time zones to avoid out-of-order inclusion.
- Session close validation blocks saves when end time is before start time after UTC conversion.
- Soft-deleted redemptions are excluded from FIFO rebuilds and realized transaction listings.
- Expected redeemable balances are derived from sessions/checkpoints (purchases do not increase redeemable).
- One-time migration converts existing local timestamps to UTC using the currently selected time zone.

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

### 6.2 CSV Import/Export

**Architecture:**
- Schema-driven import/export using `EntitySchema` definitions
- Foreign key resolution with user-scoped support for multi-user environments
- Import preview with validation, duplicate detection, and conflict resolution
- Export with FK name expansion (IDs → human-readable names)

**Foreign Key Resolution (ForeignKeyResolver):**
- **Cache-based resolution**: Loads FK tables into memory for fast lookup
- **Name normalization**: Case-insensitive, punctuation-insensitive matching (handles quotes, hyphens, spaces)
  - Example: "USAA Checking", "USAA-Checking", "usaa checking" all match the same record
- **User-scoped FK resolution (Issue #36)**: Filters FK matches by context (e.g., user_id) for user-scoped tables
  - Scope parameter: `resolve_fk(value, table, scope={'user_id': 1})`
  - Prevents ambiguity when multiple users have methods/cards with same name
  - Error messages include scope context: "'USAA Checking' not found in redemption_methods for user_id=1"
  - Applied to: `redemption_methods` (by user_id), `cards` (by user_id)
- **Ambiguity detection**: Returns error when multiple records match after normalization/scoping
- **Technical note**: sqlite3.Row objects require `.keys()` for column existence checks (not `in` operator)

**Import Workflow:**
1. **Preview Phase** (`preview_import()`):
   - Parse CSV using DictReader (column order independent)
   - Resolve foreign keys with optional user-scoped filtering
   - Validate all fields using field-specific validators
   - Detect duplicates (exact matches by natural key)
   - Classify records: to_add, to_update, conflicts, invalid_rows
   - Return `ImportPreview` DTO with all classifications

2. **Execution Phase** (`execute_import()`):
   - Re-runs preview to ensure data consistency
   - Bulk insert/update using `BulkToolsRepository`
   - Atomic transaction (all-or-nothing)
   - Emits data-changed event for UI refresh

**Export Workflow:**
- Query records with optional filters (date range, user, site)
- Resolve FK IDs to names using cached lookups
- Write CSV with human-readable column headers
- Optional timestamp in filename: `purchases_20260201_143022.csv`

**User Experience:**
- Import dialog shows preview with tabs: Records to Add, To Update, Conflicts, Errors, CSV Duplicates
- Color-coded validation errors (red for errors, orange for warnings)
- Conflict resolution: skip, overwrite, or cancel modes
- Template generation: Creates empty CSV with correct headers for each entity type

**Edge Cases:**
- CSV imports without recalculation: May create temporary data inconsistencies (e.g., `remaining_amount > amount`)
  - Expected during multi-session imports (user hasn't imported all data yet)
  - Solution: Run "Recalculate Everything" after completing all imports
  - **Maintenance Mode (Issue #38)**: Automatically detects integrity violations at startup and restricts UI access

### 6.3 Data Integrity & Maintenance Mode (Issue #38)

**Purpose:**
Prevent app crashes from data integrity violations (common during multi-session CSV imports) by detecting issues at startup and restricting access until resolved.

**Implementation:**
- `services/data_integrity_service.py`: Detects violations with quick mode (stops at first violation for performance)
  - `check_integrity(quick=bool)`: Returns `IntegrityCheckResult` with violations list
  - **Checks**: Invalid remaining_amount (> purchase amount), negative amounts, orphaned FKs, null required fields
  - **Fix methods**: Auto-fix for simple cases (e.g., cap remaining_amount at amount)
- `ui/maintenance_mode_dialog.py`: User-friendly dialog explaining violations and remediation options
  - Shows summary (count by type) and details (first 50 violations)
  - Buttons: "Continue in Maintenance Mode" (access Setup/Tools only) or "Exit Application"
- `ui/main_window.py`: Integrity check before tab creation
  - If violations detected: sets `maintenance_mode=True`, shows dialog, restricts to Setup tab only
  - Warning banner at top: "⚠️ MAINTENANCE MODE - Data integrity issues detected"
  - Normal mode: creates all 8 tabs as usual

**User Workflow:**
1. App detects violations at startup (e.g., 29 purchases with invalid remaining_amount)
2. Dialog appears with violation summary and instructions
3. User clicks "Continue in Maintenance Mode" to access Tools/Setup tab
4. User completes CSV imports and/or runs "Recalculate Everything"
5. User restarts app → violations resolved → normal mode resumes

**Performance:**
- Quick mode enabled by default (stops at first violation)
- Full scan available for comprehensive reporting

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
- **State**: created_at, read_at, dismissed_at, snoozed_until, deleted_at, suppressed_until (Issue #73)
- **Properties**: is_read, is_dismissed, is_snoozed, is_deleted, is_suppressed, is_active
- **De-duplication**: Composite key (type, subject_id) ensures only one notification per monitored condition

**Notification Service:**
- `create_or_update()`: De-dupes by composite key; updates existing if found
  - **Suppression-aware** (Issue #73): Returns existing notification without updates if `is_suppressed` (during cooldown)
  - **Resurfacing**: When cooldown expires + condition still true → clears deleted_at/read_at, resurfaces as new/unread
- `get_all()`, `get_active()`, `get_by_id()`, `get_unread_count()`
- State transitions: `mark_read(cooldown_days=0)`, `mark_unread()`, `mark_all_read()`
- User actions: `dismiss()`, `snooze()`, `snooze_for_hours()`, `snooze_until_tomorrow()`, `delete(cooldown_days=0)`
  - **Cooldown suppression** (Issue #73): `delete()` and `mark_read()` accept `cooldown_days` parameter
    - Sets `suppressed_until = datetime.now() + timedelta(days=cooldown_days)`
    - Prevents immediate reappearance when rules re-evaluate (fixes "nag loop")
    - Cooldown duration based on notification type's threshold:
      - Redemption pending: `redemption_pending_receipt_threshold_days` (default 7 days)
      - Backup notifications: backup `interval_days` (default 1 day)
      - Other: 1 day default
    - **Delete vs Mark Read**: Both set cooldown; delete hides notification completely, mark read moves to "Read" group
- Bulk: `clear_dismissed()`, `dismiss_by_type()`

**Notification Rules Service:**
- `evaluate_all_rules()`: Entry point called by QTimer (hourly) and on app startup
- **Backup rules** (Issue #35):
  - `backup_directory_missing`: automatic_backup enabled but directory not configured
  - `backup_due`: last backup > frequency + overdue_threshold (warning severity)
    - Respects user settings: only shown if `notify_when_overdue` enabled
    - Threshold configurable: `overdue_threshold_days` (default: 1 day)
    - Shows days overdue in notification body
  - `backup_failed`: automatic backup failed (error severity)
    - Respects user settings: only shown if `notify_on_failure` enabled
    - Dismisses on successful backup
  - Rules auto-dismiss when conditions resolve or backup completes
- **Redemption pending-receipt rules**:
  - Queries: `SELECT * FROM redemptions WHERE receipt_date IS NULL AND redemption_date <= ?`
  - Creates one notification per pending redemption (subject_id = redemption_id)
  - Severity: INFO if < 30 days, WARNING if ≥ 30 days
  - Auto-dismisses when redemption_service marks receipt_date
- Event handlers: `on_backup_completed()`, `on_backup_failed(error_msg)`, `on_redemption_received(redemption_id)` called by Tools/Redemptions tabs

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
- 7 integration tests (Issue #73) covering cooldown lifecycle:
  - Delete with cooldown prevents immediate recreation
  - Mark read with cooldown prevents immediate recreation
  - Cooldown expiration allows resurfacing as unread
  - Past suppression timestamps don't suppress
  - Redemption rules respect suppression during evaluation
  - Condition resolution during cooldown
  - Multiple notifications with independent cooldowns
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
- Calls `TaxWithholdingService.bulk_recalculate()` after syncing daily_sessions
- **Fixed (Issue #42)**: Tax service is now properly wired through `__init__` parameter and passed from `AppFacade`; worker threads create their own `TaxWithholdingService` with settings from UI thread
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
    - **Notifications**: 
      - Redemption section: `redemption_pending_receipt_threshold_days` spinner (0..365 days, suffix " days")
      - Backup section (Issue #35):
        - "Notify on backup failure" checkbox (default: enabled)
        - "Notify when backup overdue" checkbox (default: enabled)
        - "Overdue threshold" spinner (1..30 days, enabled only when overdue notifications enabled)
    - **Display**: Theme selection dropdown (Light/Dark/Blue), changes take effect immediately after saving
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
