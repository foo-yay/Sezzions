# Sezzions Web Port — Comprehensive Implementation Plan

**Created**: 2026-04-01
**Purpose**: Master roadmap for porting the desktop app to the web. Covers all entities, tools, settings, and infrastructure in dependency order with implementation notes derived from thorough review of the desktop codebase, PROJECT_SPEC, and CHANGELOG.

---

## Table of Contents

1. [Current State](#1-current-state)
2. [Porting Phases Overview](#2-porting-phases-overview)
3. [Phase 1 — Remaining Setup Entities](#3-phase-1--remaining-setup-entities)
4. [Phase 2 — Accounting Engine Core](#4-phase-2--accounting-engine-core)
5. [Phase 3 — Transaction Tabs](#5-phase-3--transaction-tabs)
6. [Phase 4 — Derived Views & Reports](#6-phase-4--derived-views--reports)
7. [Phase 5 — Tools & Data Operations](#7-phase-5--tools--data-operations)
8. [Phase 6 — Settings & Configuration](#8-phase-6--settings--configuration)
9. [Phase 7 — Operational Modes & Safety](#9-phase-7--operational-modes--safety)
10. [Phase 8 — Polish & Feature Parity](#10-phase-8--polish--feature-parity)
11. [Cross-Cutting Concerns](#11-cross-cutting-concerns)
12. [Supabase-Specific Considerations](#12-supabase-specific-considerations)
13. [Entity Dependency Graph](#13-entity-dependency-graph)
14. [Open Questions & Decision Points](#14-open-questions--decision-points)

---

## 1. Current State

### Already Ported (Web)
| Layer | Entity | Status |
|-------|--------|--------|
| Full stack | Users | ✅ Complete |
| Full stack | Sites | ✅ Complete |
| Full stack | Cards | ✅ Complete (FK → User) |
| Full stack | Redemption Method Types | ✅ Complete |
| Full stack | Redemption Methods | ✅ Complete (FK → User, Method Type) |
| Full stack | Game Types | ✅ Complete (Issue #254) |
| Full stack | Games | ✅ Complete (Issue #255, FK → Game Type) |
| Full stack | Purchases | ✅ Complete (Issue #260, Phase 3a) |
| Full stack | Redemptions | ✅ Complete (Issue #261/262, Phase 3b) — desktop parity polish in Issue #263 |
| Persistence record only | Game Sessions | `HostedGameSessionRecord` exists |

### Shared Web Infrastructure
- `useEntityTable` hook + `EntityTable` component (shared CRUD table pattern)
- `TypeaheadSelect` component (with `allowClear` for optional FKs)
- `ExportModal`, `FilterTreeNode`, `TableContextMenu`, `TableHeaderFilterMenu`
- `tableUtils.js` for sorting, filtering, column values
- API pattern: FastAPI endpoints → workspace-scoped services → repositories
- Auth: Supabase JWT → `AuthenticatedSession` → workspace resolution

### Not Yet Ported
- All transaction/accounting entities (Purchases, Redemptions, Game Sessions)
- FIFO accounting engine
- Recalculation infrastructure
- Event linking
- Adjustments & corrections
- Undo/redo
- Audit log
- Reports & summaries
- Daily sessions
- Realized transactions / unrealized positions
- Expenses
- All Tools (backup/restore/reset/CSV/recalc)
- All Settings (timezone, tax, themes, notifications)
- Repair Mode, Maintenance Mode

---

## 2. Porting Phases Overview

The phases are ordered by **data dependency** and **risk**:

```
Phase 1: Remaining Setup Entities (Game Types, Games)
   ↓ no accounting logic, pure catalog CRUD
Phase 2: Accounting Engine Core (FIFO, timestamps, event links)
   ↓ the foundation all transactions depend on
Phase 3: Transaction Tabs (Purchases → Redemptions → Game Sessions)
   ↓ order matters: purchases create FIFO lots, redemptions consume them, sessions wrap them
Phase 4: Derived Views & Reports (Daily Sessions, Realized, Unrealized, Reports)
   ↓ read from transaction data
Phase 5: Tools (Recalculation, CSV import/export, adjustments)
   ↓ operate on transaction data
Phase 6: Settings (Timezone, Tax, Themes, Notifications)
   ↓ configure behavior
Phase 7: Operational Modes (Repair Mode, Maintenance Mode, Data Integrity)
   ↓ safety nets
Phase 8: Polish (Undo/Redo, Audit Log viewer, UX refinements)
```

**Rationale for this order:**
- Setup entities are trivial, high-confidence, and unblock FK references for transactions.
- The accounting engine MUST exist before any transaction can be created (FIFO, timestamps, recalculation).
- Purchases before Redemptions because redemptions consume purchase lots.
- Game Sessions last among transactions because they reference games, game_types, AND interact with purchases/redemptions during their lifecycle.
- Derived views are read-only projections — easy to add once data exists.
- Tools operate on data, so data must exist first.
- Settings/modes are operational concerns, not data-critical.
- Undo/redo is deferred because it's complex and the web app can function without it initially.

---

## 3. Phase 1 — Remaining Setup Entities

### 3a. Game Types (Issue #254)

**What it is**: Simple catalog entity (name, is_active, notes). No FK dependencies.

**Desktop parity notes:**
- Model: `name` (required, unique per workspace), `is_active`, `notes`
- Desktop UI: name required, notes optional (collapsible section), is_active checkbox
- DB constraint: `UNIQUE(workspace_id, name)` — already in `HostedGameTypeRecord`
- Create: is_active defaults to True (not exposed in create dialog, only edit)

**Implementation**: Standard EntityTable pattern. ~2 hours. Identical structure to Redemption Method Types.

**Backend**: HostedGameType model, hosted_game_type_repository, workspace_game_type_service, 5 API endpoints.
**Frontend**: GameTypesTab/ with EntityTable config, modal, constants, utils.

### 3b. Games (Issue #255)

**What it is**: Catalog entity with FK → Game Types. Includes optional RTP (Return to Player) percentage.

**Desktop parity notes:**
- Model: `name` (required), `game_type_id` (required, FK), `rtp` (optional, 0-100), `actual_rtp` (computed, read-only), `is_active`, `notes`
- Desktop UI: name and game_type required; game_type is editable autocomplete combo; RTP is optional float with range validation
- `actual_rtp` is computed from game session data — displayed read-only, not editable
- Desktop has "Recalculate RTP" button in edit dialog — **defer to follow-up** (requires game sessions)

**Implementation**: Uses the Redemption Methods pattern (single FK JOIN). RTP adds a numeric input field.

**Backend**: HostedGame model, hosted_game_repository (JOIN on game_types), workspace_game_service, 5 API endpoints.
**Frontend**: GamesTab/ with EntityTable + TypeaheadSelect for game_type. Numeric input for RTP with 0-100 validation.

---

## 4. Phase 2 — Accounting Engine Core

This is the **highest-risk, highest-complexity** phase. Every transaction depends on this infrastructure. Must be built and thoroughly tested before any transaction tab.

### 4a. Timestamp Service (Hosted)

**What it does**: Ensures no two events (purchase, redemption, session start/end) for the same (user, site) pair share an exact timestamp. Auto-increments by 1 second on conflict.

**Why it matters**: FIFO allocation order depends on chronological ordering. Duplicate timestamps create ambiguous FIFO.

**Desktop code**: `services/timestamp_service.py` — `ensure_unique_timestamp(user_id, site_id, date, time, exclude_id, entity_type)`

**Web implementation notes:**
- Port directly as a hosted service
- Must query across purchases, redemptions, and sessions for the same (user, site) pair
- Postgres vs SQLite: same logic, different timestamp handling (ISO strings vs native timestamps)

### 4b. FIFO Service (Hosted)

**What it does**: The core cost basis engine. Calculates cost_basis, taxable_profit, and per-purchase allocations for each redemption.

**Desktop code**: `services/fifo_service.py`

**Key semantics:**
- **PARTIAL redemption** (`more_remaining=True`): Consume purchases in FIFO order up to exactly the redemption amount
- **FULL redemption** (`more_remaining=False`): Consume ALL remaining basis (regardless of amount), representing a complete close-out
- `calculate_cost_basis()` → returns `(cost_basis, taxable_profit, allocations[])`
- `apply_allocation()` → decrements `purchase.remaining_amount`
- `reverse_allocation()` → restores `purchase.remaining_amount` (for undo/cancel)
- Allocation source: `purchase_repo.get_available_for_fifo_as_of(user_id, site_id, date, time)` — chronological, non-dormant, remaining > 0

**Web implementation notes:**
- This must be a backend-only service (never expose FIFO internals to the frontend)
- Needs `hosted_redemption_allocation_repository` for the junction table
- Must handle Postgres decimal precision correctly (Decimal, not float)
- Critical: extensive test coverage with golden scenarios before integration

### 4c. Recalculation Service (Hosted)

**What it does**: Orchestrates "suffix rebuilds" — given a (user_id, site_id, boundary_date, boundary_time), reprocesses all FIFO allocations and session P/L from that point forward.

**Desktop code**: `services/recalculation_service.py` — `rebuild_fifo_for_pair_from()`, `rebuild_all()`

**Why it matters**: Every accounting mutation (create/update/delete purchase, redemption, or session) triggers a partial rebuild from the affected timestamp forward. This ensures all derived data is consistent.

**Web implementation notes:**
- Must run synchronously within the same DB transaction as the mutation
- The `_containing_boundary()` logic (finding the enclosing session start) must be ported
- `rebuild_all()` for full recalculation will be expensive — may need async job queue for web (Celery, background task, etc.)
- Consider timeout implications for large datasets

### 4d. Event Link Service (Hosted)

**What it does**: Links purchases and redemptions to game sessions with a relation type: `BEFORE`, `DURING`, or `AFTER`.

**Desktop code**: `services/game_session_event_link_service.py`

**Why it matters**: The "Adjusted" badge in session/purchase/redemption tables, and the session view dialog's cross-references, all depend on event links.

**Web implementation notes:**
- Needs `hosted_game_session_event_link` table/record
- Rebuild links runs as part of the recalculation chain
- Lower priority than FIFO/recalc — can be added incrementally

### 4e. Hosted Persistence Records for Derived Tables

The following ORM records need to be created (or confirmed existing) in `services/hosted/persistence.py`:
- `HostedRedemptionAllocationRecord` — FIFO junction (redemption_id → purchase_id, amount)
- `HostedRealizedTransactionRecord` — cashflow P/L per redemption
- `HostedGameSessionEventLinkRecord` — event linking
- `HostedDailySessionRecord` — aggregated daily view
- `HostedAdjustmentRecord` — basis adjustments & balance checkpoints

**Check**: Some of these may already exist in persistence.py. Must audit before creating.

---

## 5. Phase 3 — Transaction Tabs

These are built on top of Phase 2's accounting engine. Order is critical.

### 5a. Purchases Tab

**What it is**: Logs every sweep coin purchase (cost basis lot). This is the simplest transaction entity because it doesn't trigger FIFO on create — it just creates a new lot.

**Desktop form fields (required in UI):**
- Date (required), Time (optional), User (required), Site (required)
- Amount $ (required, > 0), SC Received (defaults to amount), Post-Purchase SC (required)
- Payment Card (optional, filtered by user)
- Cashback $ (auto-calculated from card rate, manually overridable)
- Notes (optional)

**FK dependencies**: users, sites, cards

**Key business logic to port:**
- `remaining_amount` initialized to `amount` (FIFO lot)
- `starting_redeemable_balance` auto-computed from expected balance
- Active session warning when purchase overlaps an active game session
- Balance check: expected vs actual post-purchase SC
- Cashback auto-calculation from card rate
- Dormant/active status lifecycle
- FIFO protection: cannot change amount/date if consumed

**Desktop-specific behaviors to reinterpret for web:**
- Inline date picker (MM/DD/YY + calendar) → web date input component
- "Today" / "Now" buttons → similar convenience controls
- Timestamp adjustment info banner → informational display
- Post-save prompt "Start session now?" → optional follow-up action
- Travel mode timezone handling → probably defer initially
- Collapsible notes → match web UX pattern

**New web infrastructure needed:**
- Date/time input component (reusable across all transaction tabs)
- Currency input component (decimal formatting, validation)
- Balance check display component
- Active session check API endpoint

**Estimated complexity**: HIGH — first transaction entity, sets the pattern for redemptions and sessions.

### 5b. Redemptions Tab

**What it is**: Logs every cash-out. Triggers FIFO allocation against purchases.

**Desktop form fields (required in UI):**
- Date (required), Time (optional), User (required), Site (required)
- Method Type (optional, filters Method), Method (optional)
- Amount $ (required, ≥ 0), Fees $ (optional)
- Redemption Type: Partial/Full radio (required) — with help tooltip
- Receipt Date (optional), Processed checkbox
- Notes (optional)

**FK dependencies**: users, sites, redemption_methods (which → redemption_method_types)

**Key business logic to port:**
- FIFO allocation on create: PARTIAL vs FULL semantics (see Phase 2)
- Redemption lifecycle: PENDING → received (receipt_date set) → processed (flag)
- Cancel/uncancel: `PENDING_CANCEL` when active session exists (deferred cancel)
- `realized_transaction` creation with FIFO results
- `redemption_allocations` junction table tracking
- Active session block: cannot create redemption while session is active for (user, site)
- Bulk actions: Mark Received (date picker dialog), Mark Processed
- Row color coding by status (pending/canceled/loss/etc.)
- Metadata-only vs accounting-field edit paths
- FIFO reprocessing on accounting-field edits

**Estimated complexity**: VERY HIGH — FIFO integration, status lifecycle, cancel/uncancel, bulk actions.

**Desktop parity status (Issue #263):**

| Feature | Status |
|---------|--------|
| Table columns match desktop order (Date/Time, User, Site, Cost Basis, Amount, Unbased, Type, Receipt, Method, Processed, Notes) | ✅ Done |
| Date column shows full datetime | ✅ Done |
| Unbased column (client-side computed: max(0, amount - cost_basis)) | ✅ Done |
| Processed column (✓ / blank) | ✅ Done |
| Fees/Status/Net P&L removed from table (kept in modal) | ✅ Done |
| Receipt column shows PENDING/CANCELED/PENDING CANCEL when no date | ✅ Done |
| Row color coding: red (loss), gray (canceled), purple (pending_cancel), orange (pending) | ✅ Done |
| Cancel button (single, PENDING w/ no receipt) | ✅ Done (uses existing endpoint) |
| Uncancel button (single, CANCELED) | ✅ Done (uses existing endpoint) |
| Mark Received bulk action (date picker dialog) | ✅ Done (new endpoint) |
| Mark Processed bulk action | ✅ Done (new endpoint) |
| Adjusted badge on Site column | ⏳ Deferred (depends on adjustments infrastructure) |
| Timezone indicator on Date column | ⏳ Deferred (depends on travel mode) |
| Pending / Unprocessed quick-filter checkboxes | ⏳ Deferred (UX enhancement) |
| PENDING_CANCEL auto-resolution on session end | ⏳ Deferred (depends on Game Sessions) |
| Active session block on create/cancel | ⏳ Deferred (depends on Game Sessions) |

### 5c. Game Sessions Tab

**What it is**: The primary transaction entity — two-phase lifecycle (Start → End). Calculates per-session taxable P/L.

**Desktop form fields:**
*Start Session (required in UI):*
- Date (required), Time (optional), User (required), Site (required)
- Game Type (optional), Game Name (optional, filtered by game type)
- Starting Total SC (required, auto-filled from expected), Starting Redeemable SC (required, auto-filled)
- Notes (optional)

*End Session (required in UI):*
- End Date (required), End Time (required)
- Ending Total SC (required), Ending Redeemable SC (required)
- Wager Amount (optional)
- Notes (optional)

**FK dependencies**: users, sites, games, game_types

**Key business logic to port:**
- `compute_expected_balances()` — chronological timeline projection
- Balance auto-fill and balance check display
- Active session guard: one per (user, site)
- P/L calculation formula (see Phase 2 notes): `net_taxable_pl = ((discoverable_sc + delta_redeem) * sc_rate) - basis_consumed`
- Session close triggers: FIFO recalc, event link rebuild, tax withholding recalc, game RTP sync, daily session sync, PENDING_CANCEL processing, low-balance close prompt
- "End & Start New" workflow
- Dormant purchase reactivation on new session start
- Multi-day session support
- Travel mode timezone handling

**Estimated complexity**: EXTREME — the most complex entity in the entire app. Every other accounting concept converges here.

**Implementation strategy:**
1. Start with basic Start Session (create Active) without auto-fill or balance checks
2. Add End Session (update status to Closed) with manual balances
3. Wire up expected balance computation
4. Wire up P/L calculation
5. Add auto-fill and balance check
6. Add "End & Start New"
7. Add low-balance close prompt
8. Add event linking
9. Add tax withholding
10. Add travel mode (if needed)

---

## 6. Phase 4 — Derived Views & Reports

These are read-only projections over transaction data.

### 6a. Daily Sessions View

**What it is**: Aggregated view grouping game sessions by date. Shows daily totals for P/L, purchases, redemptions.

**Desktop code**: `services/daily_sessions_service.py`, `repositories/daily_session_repository.py`

**Web notes**: Could be a virtual computed view or a materialized table. Desktop uses a `daily_sessions` table that's synced on session close.

### 6b. Realized Transactions View

**What it is**: Per-redemption cashflow P/L records (cost_basis, payout, net_pl).

**Desktop code**: Auto-created when redemptions are processed through FIFO.

**Web notes**: Read-only table view. Realized transactions are created by the FIFO engine, not directly by users.

### 6c. Unrealized Positions View

**What it is**: Open FIFO lots — purchases with remaining_amount > 0 grouped by (user, site).

**Desktop code**: `get_unrealized_positions()` in AppFacade

**Web notes**: This is a computed query, not a separate table. Reads from purchases.

### 6d. Reports

**Available reports (all read-only computations):**
1. **User Summary**: Total purchases, redemptions, sessions, P/L, available balance per user (optional site filter)
2. **Site Summary**: Same metrics per site (optional user filter)
3. **Tax Report**: Realized gains/losses via FIFO (user + optional site/date range) — maps to IRS Schedule D concepts
4. **Session P/L Report**: Win/loss rate, avg P/L, best/worst sessions

**Web implementation options:**
- API endpoints that run aggregate queries on demand
- Frontend dashboard components (charts, summary cards)
- CSV/PDF export for tax reporting

### 6e. Expenses

**What it is**: Simple CRUD entity for tracking business expenses (not casino-related). Desktop has it as a separate tab.

**Model**: amount, date, category, description, receipt_url, notes
**Web notes**: Straightforward EntityTable. No FIFO involvement. Can be deferred or prioritized based on user need.

### 6f. Entity Cross-Reference Tabs ("Related" Tabs)

**What it is**: Read-only tabs on transaction entity view/edit dialogs that display linked records from other tables. The desktop app has 5 distinct Related tabs across its dialogs. These are critical for users who need to understand how their transactions connect (FIFO allocations, event links, checkpoint windows).

**Desktop parity inventory:**

| Entity Dialog | Tab Name | Content | Desktop Code |
|---|---|---|---|
| Purchase | Basis Period Purchases | All purchases in the same balance-checkpoint window for that (user, site) | `_load_related_tab()` in `ViewPurchaseDialog` |
| Redemption | Allocated Purchases (FIFO) + Linked Sessions | FIFO allocation breakdown (which purchases were consumed, how much each) + event-linked game sessions | `_load_related_tab()` in `ViewRedemptionDialog` |
| Game Session | Contributing Purchases + Linked Redemptions | Purchases/redemptions linked via event links, grouped by relation type (BEFORE / DURING / AFTER) | `_load_related_tab()` in `ViewGameSessionDialog` |
| Realized Position | Allocated Purchases + Linked Sessions | Same as Redemption Related tab, but accessed from the Realized Transactions view | `ViewRealizedPositionDialog` |
| Unrealized Position | Related Purchases + Sessions | Open FIFO lots and any overlapping sessions for the (user, site) | `ViewUnrealizedPositionDialog` |

**Desktop also has** a conditional **Adjustments tab** on Purchase, Redemption, and Game Session dialogs — visible only when adjustments (basis adjustments or balance checkpoints) affect that entity.

**Backend data availability:**
- FIFO allocations (`redemption_allocations` table) — already populated by the hosted FIFO service on every redemption create/update
- Event links (`game_session_event_links` table) — already populated by the hosted event link service on recalculation
- Checkpoint-window queries — existing `purchase_repo` methods can filter by date range
- All data is **read-only** from the Related tab perspective

**Web implementation:**
- **API endpoints** (new): One endpoint per cross-reference type, e.g.:
  - `GET /v1/workspace/purchases/{id}/related` — basis-period purchases
  - `GET /v1/workspace/redemptions/{id}/allocations` — FIFO allocation detail
  - `GET /v1/workspace/redemptions/{id}/linked-sessions` — event-linked sessions
  - `GET /v1/workspace/game-sessions/{id}/linked-transactions` — event-linked purchases & redemptions
- **Frontend**: Reusable `RelatedTab` component (read-only table rendered inside entity modals as a tab). Each entity modal adds its specific Related tab config.
- **Navigation**: Clicking a row in a Related tab should open the linked entity's view dialog (drill-down).

**Dependencies**: Requires Phase 3 transaction tabs (for the parent dialogs) and Phase 2 accounting engine (for the data). Realized/Unrealized Related tabs additionally require Phase 4a-4c.

**Implementation order:**
1. Purchase → Basis Period Purchases (simplest — just a date-range query)
2. Redemption → FIFO Allocations (uses existing allocations table)
3. Game Session → Linked Transactions (uses existing event links table)
4. Redemption → Linked Sessions (event links, similar to #3)
5. Realized Position → Related (after Phase 4b)
6. Unrealized Position → Related (after Phase 4c)
7. Adjustments tab (after Phase 5d Adjustments)

---

## 7. Phase 5 — Tools & Data Operations

### 7a. Recalculation Tools (Web)

**What it is**: Manual triggers for FIFO/P&L rebuilds. Desktop has scoped (user/site pair) and full recalculation.

**Web implementation:**
- API endpoint: `POST /v1/workspace/tools/recalculate` with optional `user_id`, `site_id` scope
- Full recalculation may be long-running → async job with status polling
- Stats display endpoint: `GET /v1/workspace/tools/recalculation-stats`

### 7b. CSV Import / Export

**What it is**: Schema-driven bulk data operations. Import supports preview/validate/confirm workflow.

**Desktop code**: `services/tools/csv_import_service.py`, `csv_export_service.py`, `schemas.py`

**Web implementation:**
- **Export**: API endpoint generates CSV for any entity → browser download
- **Import**: Multi-step flow: upload → server-side validate/preview → confirm → apply
- Supports 10 entity types (users, sites, cards, games, game_types, redemption_methods, redemption_method_types, purchases, redemptions, game_sessions)
- FK resolution: name→ID mapping (e.g., user name in CSV → user_id)
- Conflict handling: skip or overwrite
- Post-import recalculation prompt for accounting entities

**Web infrastructure needed:**
- File upload endpoint
- Server-side CSV parsing + validation
- Preview/conflict resolution UI
- Batch insert/update with FK resolution

### 7c. Adjustments & Corrections

**What it is**: Manual FIFO corrections — two types:
1. **Basis Adjustment**: Inserts synthetic cost basis at a timestamp (positive or negative delta)
2. **Balance Checkpoint**: Overrides expected SC balance at a timestamp

**Desktop code**: `services/adjustment_service.py`

**Web implementation:** API endpoints + simple form dialogs. Triggers recalculation from the adjustment timestamp.

### 7d. Database Backup & Restore (Web Adaptation)

**Desktop**: SQLite file copy (online backup API). Backup location, manual backup, auto-backup timer, restore with 3 modes (REPLACE, MERGE_ALL, MERGE_SELECTED).

**Supabase adaptation** (see Section 12 for details):
- **Backup**: Supabase provides automated daily backups on Pro plan. Manual backups could be implemented as:
  - CSV export of all workspace data (download as ZIP)
  - Workspace snapshot to a separate schema or timestamped tables
  - Supabase Management API for point-in-time recovery (Pro plan)
- **Restore**: Import from a previous export (CSV ZIP or snapshot)
- **The desktop's file-level backup doesn't translate** — need to think in terms of workspace-level data snapshots

### 7e. Database Reset

**Desktop**: Clears all data (optionally keeping setup entities and/or audit log).

**Web implementation**: API endpoint to delete all workspace data, with option to keep setup entities (users, sites, cards, games, game_types, methods, method_types). Must require explicit confirmation.

---

## 8. Phase 6 — Settings & Configuration

### 8a. Timezone Settings

**Desktop**: Three TZ concepts:
- `accounting_time_zone` — the "legal" TZ for tax calculations and date bucketing
- `current_time_zone` — the user's current wall-clock TZ (may differ if traveling)
- `travel_mode_enabled` — when True, timestamps are stored with both entry TZ and accounting TZ

**Web implementation options:**
- Store timezone preference per workspace (accounting TZ)
- Browser provides `Intl.DateTimeFormat().resolvedOptions().timeZone` for local TZ
- Travel mode: store entry TZ on each transaction when it differs from accounting TZ
- **Change Accounting TZ** dialog: migration from one TZ to another with effective date (complex — desktop has a dedicated `timezone_migration_service.py`)
- **Recommendation**: Start with a single accounting TZ per workspace. Defer travel mode and TZ migration to a later phase.

### 8b. Tax Settings

**Desktop**: Enable/disable withholding estimates, default rate (0-100%), "Recalculate Withholding" bulk action.

**Web implementation:**
- Workspace-level settings: `tax_withholding_enabled`, `default_withholding_rate_pct`
- `tax_withholding_service` port for per-date withholding calculation
- Endpoint to recalculate all withholding
- **Recommendation**: Port after game sessions (Phase 3c), since tax withholding triggers on session close.

### 8c. Themes

**Desktop**: 3 themes (Light, Dark, Blue) applied via QSS with 12 color tokens.

**Web implementation:**
- CSS custom properties (already in use — the web app has a theme system via `styles.css`)
- Theme selector in settings
- Store preference per user/workspace
- Easy to implement — just toggle CSS classes or custom property sets
- **Recommendation**: Implement early for user satisfaction, but low priority vs functionality.

### 8d. Notification Settings

**Desktop**: Configurable thresholds for backup overdue, redemption pending, app updates.

**Web implementation:**
- Notification rules service port (evaluate periodically or on login)
- In-app notification center (bell icon + dropdown — desktop has this pattern)
- Email notifications (optional Supabase integration)
- Browser push notifications (optional)
- **Recommendation**: In-app notifications first. Email/push as follow-up.

---

## 9. Phase 7 — Operational Modes & Safety

### 9a. Repair Mode

**Desktop**: Disables automatic cascade recalculation. Edits mark (user, site) pairs as "stale" instead of rebuilding. User manually triggers rebuild when ready.

**Web options:**
1. **Port directly**: Same concept — workspace-level flag that defers recalculation. Useful for bulk edits or imports where recalculating after every change is expensive.
2. **Replace with "batch mode"**: Instead of a persistent mode toggle, offer batch operations that defer recalculation (e.g., bulk import with post-import recalc).
3. **Hybrid**: Auto-detect when many changes are queued and suggest deferring recalculation.

**Recommendation**: Option 2 (batch mode) for web. Persistent repair mode is a desktop UX pattern that doesn't translate well to multi-user web. Batch operations with explicit "recalculate now" are cleaner.

### 9b. Maintenance Mode

**Desktop**: Triggered by data integrity violations at startup. Restricts UI to setup-only. Also entered during restore/reset.

**Web options:**
1. **Read-only mode**: Lock the workspace from writes during maintenance operations
2. **Operation-level locking**: Lock individual operations (restore/reset) rather than the whole UI
3. **Background maintenance**: Data integrity checks run asynchronously; violations flagged but don't block the UI

**Recommendation**: Option 2. Web users shouldn't be locked out of their entire workspace. Use operation-level locks with progress indicators.

### 9c. Data Integrity Checks

**Desktop**: `data_integrity_service.py` — checks for orphan records, broken FK references, inconsistent FIFO state.

**Web implementation:**
- Periodic background checks (cron job or on-demand API endpoint)
- Results displayed as warnings in a health dashboard
- Auto-repair option for fixable issues
- Postgres constraints provide stronger guarantees than SQLite, so fewer integrity violations expected

---

## 10. Phase 8 — Polish & Feature Parity

### 10a. Undo/Redo

**Desktop**: Excel-like undo/redo stack. JSON snapshots in `settings` table. Max depth configurable (default 100). Undoable entities: purchases, redemptions, game sessions.

**Web implementation options:**
1. **Port directly**: Server-side undo/redo stack per workspace. Same JSON snapshot approach.
   - Pro: Exact parity
   - Con: Complex, storage-heavy
2. **Simplified version**: Only undo last N operations. No redo.
   - Pro: Simpler implementation
   - Con: Less powerful
3. **Audit-log-based undo**: Use audit log entries to reconstruct previous state.
   - Pro: No separate stack needed
   - Con: Slower for complex operations

**Recommendation**: Option 1 for direct parity. The desktop undo/redo is well-tested and users rely on it. Port the service layer as-is, expose via API endpoints.

**API design:**
- `POST /v1/workspace/undo` — undo last operation
- `POST /v1/workspace/redo` — redo
- `GET /v1/workspace/undo-stack` — peek at stack (for UI display of "Undo: Create Purchase")

### 10b. Audit Log

**Desktop**: Structured logging of all CRUD operations with JSON snapshots (old_data, new_data), group_id for multi-step operations, summary_data for compact retention.

**Web implementation:**
- Port `audit_service.py` to hosted backend
- `hosted_audit_log` table
- API endpoint for querying with filters (date range, table, action)
- Audit log viewer in web UI (table + detail panel)
- CSV export of audit entries
- Retention policy (configurable max rows)

### 10c. Spreadsheet UX Features

**Desktop has extensive spreadsheet features that should be web-parity:**
- Copy selection (Cmd+C)
- Copy with headers
- Column header filter dropdowns → **already implemented** in EntityTable
- Text search → **already implemented**
- Spreadsheet stats bar (sum, count, average of selected column values)
- CSV export → **partially implemented** (ExportModal exists)
- Context menu → **already implemented** (TableContextMenu)

**Remaining**: Stats bar, copy-with-headers keyboard shortcut, date range filter.

### 10d. Date Range Filter

**Desktop**: All transaction tabs have a `DateFilterWidget` (default: Jan 1 of current year → today).

**Web implementation**: Reusable date range picker component. Apply to Purchases, Redemptions, Game Sessions tabs.

### 10e. Quick Filters

**Desktop quick filters by tab:**
- Game Sessions: "Active Only" checkbox
- Purchases: "Basis Remaining" checkbox (remaining_amount > 0)
- Redemptions: "Pending" checkbox, "Unprocessed" checkbox

**Web implementation**: Toggle buttons or checkboxes in table toolbar. Server-side filtering via API query params for performance.

---

## 11. Cross-Cutting Concerns

### 11a. Currency & Decimal Handling

**Desktop**: Python `Decimal` throughout. All money fields stored as REAL in SQLite. Renders with 2-decimal formatting and "$" prefix.

**Web**: JavaScript doesn't have native Decimal. Options:
- Store as strings in API transport, convert to numbers for display only
- Use a library like `decimal.js` for client-side calculations
- **All accounting math MUST happen server-side** — client renders only
- API should return currency values as strings to prevent floating-point drift

### 11b. Date/Time Handling

**Desktop**: Stores dates as ISO strings in SQLite. Display in `MM/DD/YY` format. Times as `HH:MM:SS`. UTC conversion via `accounting_time_zone_service.py`.

**Web**: ISO 8601 in Postgres. Display format configurable per user preference (but default to American `MM/DD/YY` for parity). All API transport in ISO 8601.

### 11c. Pagination

**Desktop**: No pagination — loads all rows into memory (QTableWidget). Practical since desktop = single user, local DB.

**Web**: Already paginated for setup entities (limit/offset). Transaction tabs will have MORE data — pagination is essential. Consider:
- Server-side cursors for large datasets
- Infinite scroll or page-based navigation
- Default page size of 100 with fallback to 500

### 11d. Real-Time Refresh

**Desktop**: Direct function calls — UI refreshes after every mutation. No stale data concern.

**Web**: After a mutation, the frontend re-fetches the affected data. Already handled by `useEntityTable`'s `loadPage()` after create/update/delete.

### 11e. Error Handling

**Desktop**: Exception → dialog box with message.

**Web**: HTTP error codes → toast notifications or inline error displays. 409 for conflicts, 400 for validation, 404 for missing, 500 for server errors.

### 11f. Concurrency

**Desktop**: Single-user, single-thread (with QThreadPool for background tasks). No concurrency concerns.

**Web**: Multi-tab, potentially multi-device. Need:
- Optimistic locking on updates (check `updated_at` timestamp)
- Transaction isolation for FIFO operations
- Row-level locks during recalculation

---

## 12. Supabase-Specific Considerations

### 12a. Backup Strategy

Desktop SQLite backup doesn't translate. Supabase options:

1. **Supabase Automated Backups** (Pro plan): Daily backups with point-in-time recovery. No custom code needed, but workspace-level granularity may not be available (it's project-level).

2. **Workspace Data Export**: API endpoint that exports all workspace data as JSON or CSV ZIP. User-triggered "Download My Data" button.
   - Pro: User-controlled, works regardless of Supabase plan
   - Con: Import requires separate restore flow

3. **Snapshot Tables**: Copy workspace data to timestamped tables or a `workspace_snapshots` schema.
   - Pro: Fast restore (just copy back)
   - Con: Storage cost, complexity

4. **Supabase Database Functions**: pg_dump equivalent via custom RPC function.

**Recommendation**: Start with Option 2 (workspace data export/import as ZIP). It's the most portable and doesn't depend on Supabase plan tier. Add snapshot tables later if users want instant restore.

### 12b. Row-Level Security

Supabase RLS policies should ensure:
- Users can only access their own workspace's data
- Workspace membership verified via `workspace_id` on every row
- Service role used for cross-workspace operations (admin only)

### 12c. Database Migrations

Desktop uses `CREATE TABLE IF NOT EXISTS` (auto-create). Supabase needs:
- Alembic or raw SQL migration files
- Version-tracked schema changes
- Rollback capability
- Applied via `supabase db push` or migration tool

### 12d. Performance

SQLite is fast for single-user reads. Postgres may be slower for complex JOINs but better for concurrent access. Monitor:
- FIFO calculation query performance (multiple JOINs on purchases)
- Recalculation time for large datasets
- Index strategy for (workspace_id, user_id, site_id) compound queries

---

## 13. Entity Dependency Graph

```
Users (standalone)
Sites (standalone)
Cards (→ Users)
Game Types (standalone)
Games (→ Game Types)
Redemption Method Types (standalone)
Redemption Methods (→ Users, → Redemption Method Types)
Purchases (→ Users, → Sites, → Cards)
Redemptions (→ Users, → Sites, → Redemption Methods)
Game Sessions (→ Users, → Sites, → Games, → Game Types)
  ├── triggers: FIFO recalc, event linking, daily session sync
  ├── triggers: tax withholding recalc
  └── triggers: game RTP update
Realized Transactions (derived from Redemptions + FIFO)
Redemption Allocations (derived from Redemptions + Purchases + FIFO)
Daily Sessions (derived from Game Sessions)
Unrealized Positions (derived from Purchases)
Event Links (derived from Sessions + Purchases + Redemptions)
Adjustments (standalone, triggers recalc)
Expenses (standalone)
Audit Log (records all mutations)
Undo/Redo Stack (references audit log)
```

---

## 14. Open Questions & Decision Points

These should be discussed and resolved before or during implementation:

### Q1: Travel Mode — Port or Defer?
The desktop tracks `entry_time_zone` on every transaction for users who play from different timezones. This is complex (dual TZ storage, migration prompts, globe badges). **Recommendation**: Defer to Phase 6+ unless the user actively uses travel mode.

### Q2: Undo/Redo Stack — Full Port or Simplified?
The desktop undo/redo is powerful but complex (JSON snapshots, recalculation triggers, stack pruning). **Recommendation**: Full port for parity, but in a later phase. The web app can function without it initially.

### Q3: Auto-Fill Balances — How to Handle Latency?
Desktop auto-fills starting balances instantly (local DB). Web has network latency. Options:
- Pre-fetch expected balances when the dialog opens
- Show loading spinner while computing
- Cache last-known balances client-side

### Q4: "End & Start New" Workflow — Web UX?
Desktop chains dialogs (close → prefill new open). Web could:
- Use a multi-step wizard
- Auto-populate a new "Start Session" form after ending
- Offer a single combined "End & Start New" modal

### Q5: Low-Balance Close Prompt — Web UX?
Desktop shows a secondary confirmation dialog after session close when balance is below threshold. Web could use a toast/modal prompt or make it a configurable auto-action.

### Q6: Bulk Actions (Mark Received, Mark Processed) — Web UX?
Desktop uses multi-select + toolbar buttons + date picker dialog. Web `EntityTable` already supports multi-select + batch delete. Extend with custom bulk action buttons.

### Q7: Supabase Backup — What Tier?
If on Free plan, only workspace data export is available. Pro plan enables automated backups. This affects the backup/restore feature design.

### Q8: Real-Time Notifications — In-App Only or Also Push/Email?
Desktop has in-app bell only. Web could add email alerts. **Recommendation**: In-app first, email as follow-up.

### Q9: Repair Mode — Port or Replace?
See Section 9a. **Recommendation**: Replace with batch-mode semantics for web.

### Q10: Expenses — Priority?
Desktop has expenses as a standalone tab. It's simple CRUD with no FIFO involvement. Priority depends on user need. Can be added at any time.

---

## Appendix: Estimated Implementation Order (Issue-by-Issue)

Each line below represents roughly one GitHub Issue + PR:

```
PHASE 1 — SETUP ENTITIES
  [x] Issue #254: Game Types (full stack)
  [x] Issue #255: Games (full stack, FK → Game Types)

PHASE 2 — ACCOUNTING ENGINE
  [ ] Hosted timestamp service
  [ ] Hosted FIFO service + redemption_allocations table
  [ ] Hosted recalculation service (scoped + full)
  [ ] Hosted event link service

PHASE 3 — TRANSACTION TABS
  [ ] Purchases: backend (model, repo, service, API) + frontend basic CRUD
  [ ] Purchases: balance check + cashback auto-calc + active session warning
  [ ] Redemptions: backend (model, repo, service, API) + FIFO integration
  [ ] Redemptions: frontend CRUD + status lifecycle + bulk actions
  [ ] Game Sessions: backend (model, repo, service, API) + basic start/end
  [ ] Game Sessions: expected balance computation + auto-fill
  [ ] Game Sessions: P/L calculation + recalculation chain
  [ ] Game Sessions: end & start new + low-balance close + event linking

PHASE 4 — DERIVED VIEWS
  [ ] Daily sessions view
  [ ] Realized transactions view
  [ ] Unrealized positions view
  [ ] Reports: user summary, site summary, tax report, session P/L
  [ ] Related tab: Purchase → Basis Period Purchases
  [ ] Related tab: Redemption → FIFO Allocations + Linked Sessions
  [ ] Related tab: Game Session → Linked Transactions (BEFORE/DURING/AFTER)
  [ ] Related tab: Realized Position → Allocations + Sessions (after 4b)
  [ ] Related tab: Unrealized Position → Purchases + Sessions (after 4c)
  [ ] Adjustments tab on entity dialogs (after Phase 5 Adjustments)

PHASE 5 — TOOLS
  [ ] Recalculation tools (scoped + full)
  [ ] CSV export (all entities)
  [ ] CSV import (preview/validate/confirm flow)
  [ ] Adjustments & corrections
  [ ] Workspace data backup (export as ZIP)
  [ ] Workspace data restore (import from ZIP)
  [ ] Database reset

PHASE 6 — SETTINGS
  [ ] Timezone: accounting TZ per workspace
  [ ] Tax: withholding enable/rate/recalculate
  [ ] Themes: Light/Dark toggle
  [ ] Notifications: rules + in-app bell

PHASE 7 — OPERATIONAL MODES
  [ ] Batch mode (deferred recalculation for bulk operations)
  [ ] Data integrity checks (background + health dashboard)

PHASE 8 — POLISH
  [ ] Undo/redo stack
  [ ] Audit log viewer
  [ ] Date range filter component
  [ ] Stats bar (selection sum/avg/count)
  [ ] Keyboard shortcuts (Cmd+Z undo, Cmd+C copy, etc.)
```
