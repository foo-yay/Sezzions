# Feature request — Repair Mode (Edit Without Auto-Cascade + Explicit Rebuild)

## MVP scope (hand-off target)

This issue should be implemented as **Phase 1** only (minimal risk): disable auto-cascades + track staleness + explicit rebuild actions. It should NOT attempt to relax “consumed row” delete/edit restrictions yet.

- Add global Repair Mode toggle + persistence
- When Repair Mode is ON and user edits authoritative rows (purchase/redemption/session):
  - write the authoritative change
  - skip auto-cascade rebuild calls
  - mark the affected (user_id, site_id) as stale with reason + timestamps
- Add Tools status panel/banner with:
  - Repair Mode ON/OFF
  - stale pair count + table
  - “Recalculate selected pair(s)” and “Recalculate everything” actions
- Rebuild actions must use existing APIs (avoid inventing new ones):
  - per-pair: `RecalculationService.rebuild_for_pair(user_id, site_id)`
  - global: `RecalculationService.rebuild_all(...)`
  - plus rebuild game-session event links for the affected pair(s) so UI/report linking stays coherent

Stretch (explicitly optional for MVP):
- Disabling exports/reports while stale
- Any “force delete/edit consumed rows” mechanics (that is Phase 2)

Implementation order checklist:
1) Persistent state: add `repair_stale_pairs` table (preferred) OR settings-backed store
2) Settings/UI: Repair Mode toggle + clear, unavoidable banner when ON
3) Write-path guard: in `AppFacade`, skip cascade rebuild calls when Repair Mode is ON
4) Stale marking: record affected pair + reason on every write that would normally cascade
5) Tools UI: stale pair table + rebuild buttons
6) Rebuild actions: call `RecalculationService.rebuild_for_pair` / `rebuild_all` + rebuild event links; clear stale marks on success
7) Tests: happy path + 2 edge cases + 1 failure-injection rollback
8) Docs: spec + changelog

## Problem / motivation

Sezzions currently recalculates derived tables automatically as a side effect of editing authoritative rows (purchases/redemptions/sessions). This is correct for normal operations, but it makes “surgery” repairs dangerous and cumbersome:

- Editing an old record can trigger cascades that rewrite large swaths of downstream derived data.
- Deleting a redemption reallocates FIFO basis forward (and forward, and forward), which can create a huge blast radius.
- The UI prevents many edits/deletes once rows are “consumed”, forcing users into destructive workarounds.

Even with an Adjustment system, we still need a safe way to:
- make a set of coordinated edits,
- stop the system from “thrashing” derived tables mid-repair,
- and then explicitly rebuild when the user is ready.

We need a **Repair Mode** that is distinct from today’s “Maintenance Mode” (integrity violation mode). Repair Mode is an intentional workflow for power users.

## Proposed solution

Add **Repair Mode** (aka “Edit-Repair Mode”) which changes write behavior:

- While Repair Mode is enabled:
  - **Auto-cascade recalculations are disabled** for user-driven edits.
  - The app **records which user/site pairs are now stale** (derived data may be incorrect).
  - The UI clearly warns that reports/derived views may be wrong until explicit rebuild.

- Repair Mode provides explicit rebuild actions:
  - **Recalculate Selected Pair(s)** (user/site)
  - **Recalculate Everything**

This mode enables practical, real-world repairs without requiring deletion of months of downstream history.

### Where it lives in the app

Entry points (must have at least one; recommended two):

1) **Settings gear → Advanced / Repair Mode**
- Toggle with scary confirmation + explanation

2) Setup → Tools
- A visible status banner + toggle + rebuild buttons

Rationale:
- Settings gear is “global state,” good for enabling/disabling.
- Tools is “ops center,” good for rebuild actions and seeing stale-pair status.

## Scope

### In-scope

- Add Repair Mode global state + persistence (settings.json)
- Disable auto-cascades triggered by UI edits when Repair Mode is enabled
- Track stale user/site pairs affected by edits
- Provide explicit rebuild actions:
  - Recalculate pair
  - Recalculate everything
- UX affordances:
  - prominent banner when mode is ON
  - warnings/disablements for reports that rely on derived tables

### Out-of-scope

- Changing today’s automatic Maintenance Mode behavior (integrity violation startup lock)
- Building a full “undo stack” for repairs
- Automatically inferring which edits should be allowed (this can be incremental)

## UX / fields / checkboxes

### Settings gear — Repair Mode toggle

Add a new section in Settings dialog (likely left nav item: “Advanced” or “Maintenance/Repair”):

Controls:
- Checkbox/toggle: “Enable Repair Mode”
- Description text (must be explicit):
  - Auto recalculation is disabled
  - Derived tables may be stale
  - Use Tools to rebuild

Enable confirmation:
- Modal confirmation requiring typing a word (e.g., REPAIR)
- Must recommend taking a backup first (button: “Open Backup Tools”)

Disable confirmation:
- If stale pairs exist, must prompt:
  - “Run rebuild now?” (buttons: Recalculate affected pairs / Later)

### Setup → Tools — Repair Mode status

New banner/panel near top:
- Status: ON/OFF
- Count of stale pairs
- Buttons:
  - “Recalculate Selected Pair(s)…” (opens picker)
  - “Recalculate Everything”
  - “View stale pairs” (opens table)

### Stale pairs view

Table columns:
- User
- Site
- First stale timestamp
- Last edit timestamp
- Reason (e.g., “Purchase edited”, “Redemption deleted”, “Adjustment created”)

Actions:
- “Recalculate this pair”
- “Clear stale mark” (danger; only if user really wants; probably out-of-scope)

### UI indicators when Repair Mode is ON

- Global banner at top of main window:
  - “⚠️ REPAIR MODE: Derived data may be stale. Run rebuild from Tools.”

- Tabs whose numbers are derived (Realized, Unrealized, Daily Sessions, Tax summaries) should:
  - show a small warning badge “stale”
  - optionally disable export/report actions

Keep this minimal and non-annoying.

## Implementation notes / strategy

### Settings/state

- Add setting key: `repair_mode_enabled` (bool)
- Add setting key: `repair_mode_stale_pairs` (list) or store in DB table (preferred for robustness)

Recommended: store stale pairs in DB:

- New table `repair_stale_pairs`:
  - `id`
  - `user_id`
  - `site_id`
  - `first_stale_at`
  - `last_stale_at`
  - `last_reason`

Rationale:
- DB-backed state survives settings resets/merges better
- Allows reliable queries from services

### Disabling cascades

Define what “auto-cascade” means concretely:

- Today: editing purchase/redemption/session triggers:
  - FIFO rebuild
  - realized rebuild
  - closed session recalculation
  - daily/tax sync

In Repair Mode, UI-driven operations should:
- still write authoritative row changes
- but **skip**:
  - FIFO rebuild (`RecalculationService.rebuild_fifo_for_pair_from(...)` / `rebuild_for_pair(...)`)
  - closed-session recalculation (`GameSessionService.recalculate_closed_sessions_for_pair_from(...)` / `recalculate_all_sessions(...)`)
  - daily/tax sync hooks that are triggered by session recalculation
  - game-session event link rebuilds
  - cashback recalculation

Instead:
- record stale mark for that user/site
- emit a data-changed event that causes UI refresh, but with “stale” warning

Important:
- The Tools “Recalculate” actions must still work in Repair Mode.
- Recalculate Everything should clear stale marks when complete.

Implementation guidance (non-binding): most cascades are initiated from `AppFacade` methods after repository/service writes. Phase 1 can be implemented by guarding those cascade calls behind the Repair Mode flag.

### Allowed vs blocked edits

MVP: keep existing validation, except:
- allow edits that were previously blocked *only because they would require cascade*?

Be careful here:
- Repair Mode should NOT allow edits that break basic integrity constraints (FKs, null required fields).
- But it can relax “cannot delete because consumed” if we are not rebuilding allocations immediately.

Proposed staged approach:

Phase 1 (minimal risk):
- Repair Mode only disables auto-cascade.
- It does NOT change delete/edit permissions.

Phase 2 (higher power):
- Add “Force edit/delete” options for consumed purchases/redemptions with explicit warnings.

This issue can target Phase 1, with a follow-up for Phase 2.

### Rebuild actions

- Implement/ensure scoped rebuild exists:
  - `RecalculationService.rebuild_pair(user_id, site_id)`
  - Must rebuild:
    - redemption_allocations
    - realized_transactions
    - game_sessions derived fields (closed sessions)
    - daily_sessions + tax (if applicable)

- Tools UI should allow selecting multiple pairs.

### Atomicity / rollback

- Recalculate pair/everything must be atomic per operation.
- If rebuild fails, stale marks remain.

### Documentation

Update `docs/PROJECT_SPEC.md`:
- Define Repair Mode behavior
- Clarify the difference between:
  - Maintenance Mode (integrity violation at startup; restricts UI)
  - Repair Mode (user-enabled; edits allowed but derived is stale)

Add changelog entry.

## Acceptance criteria

- Repair Mode toggle exists in Settings and status is visible in Tools.
- When Repair Mode is enabled, editing a purchase/redemption/session:
  - writes the change
  - does not trigger cascade rebuild
  - marks the relevant user/site pair as stale
- Tools provides explicit actions:
  - Recalculate selected pair(s)
  - Recalculate everything
- Running rebuild clears stale marks for rebuilt pairs.
- UI shows a clear banner/warning when Repair Mode is ON and/or stale pairs exist.

## Test plan

### Automated tests

Happy path:
- Enable Repair Mode.
- Edit a purchase that normally triggers cascade.
- Assert:
  - authoritative purchase row updated
  - derived tables NOT rebuilt (verify a known derived value remains unchanged)
  - stale pair record created

Edge cases (at least 2):
- Multiple edits on same pair update `last_stale_at` but do not duplicate stale records.
- Rebuild pair clears only that pair’s stale record.

Failure injection (at least 1):
- Force rebuild pair to fail mid-operation and assert:
  - derived data unchanged (transaction rollback)
  - stale mark still present

Invariants:
- Repair Mode does not bypass database integrity constraints.

### UI smoke (mandatory)

- Headless test:
  - boot MainWindow offscreen
  - open Settings dialog
  - toggle Repair Mode (can mock confirmation)
  - open Tools tab and verify rebuild buttons exist

### Manual verification

- Turn on Repair Mode and make a deliberately “illegal in normal workflow” edit (if Phase 2 implemented).
- Confirm nothing auto-rebuilds.
- Run “Recalculate Everything” and confirm outputs stabilize.

## Pitfalls / follow-ups

- **Repair Mode must be obvious:** Always show a global banner; users must not forget they’re in a non-standard correctness mode.
- **Don’t weaken integrity constraints:** Repair Mode can skip cascades, but must not allow FK/orphan/null-required corruption.
- **Avoid “half repaired” states:** If stale pairs exist, exports/reports should warn or be disabled to prevent trusting stale numbers.
- **Follow-up (Phase 2):** Add explicit “force delete/edit consumed rows” paths only after Phase 1 is stable, with very strong confirmations and clear stale-pair marking.
- **Follow-up (nice-to-have):** Add a rebuild preview (“what will change”) for a selected pair before running the rebuild.
