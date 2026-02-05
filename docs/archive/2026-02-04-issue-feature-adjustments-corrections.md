# Feature request — Adjustments & Corrections (Basis + Balance)

## MVP scope (hand-off target)

This section is the intended “Claude implementation target” for a first PR. Everything else in this issue can be treated as stretch unless it is required to satisfy the acceptance criteria.

- Add `account_adjustments` table + repository + basic CRUD service (create/list/soft-delete)
- Add Tools UI section (Setup → Tools) with:
  - list/filter of adjustments
  - “New Basis Adjustment…” dialog
  - “New Balance Checkpoint…” dialog
  - “Delete (soft)…” action with strong confirmation
- Rebuild behavior on create/delete:
  - Use the existing per-pair rebuild path (`RecalculationService.rebuild_for_pair(user_id, site_id)`) and per-pair event link rebuild so derived tables update without global rebuild.
- Integration points (important):
  - Balance checkpoint adjustments must affect BOTH:
    - `GameSessionService.compute_expected_balances(...)` (balance checks in dialogs)
    - closed-session recalculation (`recalculate_closed_sessions_for_pair` / `recalculate_closed_sessions_for_pair_from`) so session-derived/taxable fields actually incorporate the checkpoint.
  - Basis adjustments must affect the FIFO/realized pipeline used by the rebuild engine in `RecalculationService` (not only “live” redemption creation).

Stretch (explicitly optional for MVP):
- “Health / Validation” mini-panel
- Convenience entry points from Purchases / Game Sessions tabs
- Wizards (e.g., redemption reversal helper)

Implementation order checklist:
1) Migration + repository for `account_adjustments` (incl. soft delete)
2) Service layer: CRUD + validation + “apply to computations” helpers
3) Recalc integration: hook adjustments into `RecalculationService` rebuild path (per-pair)
4) Session integration: incorporate checkpoint adjustments into closed-session recalculation
5) UI: Tools section list + create dialogs + delete flow
6) Tests: one golden scenario + 2 edge cases + 1 failure-injection rollback
7) Docs: update spec + changelog

## Problem / motivation

Sezzions’ accounting model intentionally cascades derived data (FIFO allocations, realized transactions, taxable session fields) to stay internally consistent. This is correct-by-construction for normal usage, but it makes “late discovery” data entry errors (wrong amount, wrong date/time, wrong start balance) extremely expensive to fix:

- A single typo in an old purchase can force the user to delete or heavily edit many downstream redemptions/sessions, because:
  - purchases become “consumed” by FIFO allocations,
  - deleting a redemption reallocates basis to later redemptions,
  - and the system actively prevents edits/deletes that would break invariants.

Real-world scenario: user discovers a wrong purchase amount months later after dozens/hundreds of redemptions. The current workflow (delete downstream history to unlock edits) is not realistic.

We need an **accounting-grade, auditable correction mechanism** that allows users to fix errors without rewriting or deleting large downstream history.

## Proposed solution

Implement an **Adjustments & Corrections** capability that supports two primary correction classes:

1) **Basis adjustments** (USD cost basis corrections)
2) **Balance checkpoint adjustments** (SC total/redeemable continuity anchors)

Key design principle:
- Adjustments are first-class transactions with explicit intent and audit metadata.
- They integrate into expected-balance calculations and basis roll-forward in a controlled way.
- They are clearly marked as adjustments (never silently masquerade as ordinary casino activity).

### High-level model

Create a new authoritative table:

- `account_adjustments` (name flexible; this issue assumes this name)

Each row is scoped to a user/site pair and has an effective timestamp.

Adjustment types (MVP):

- `BASIS_USD_CORRECTION`
  - Purpose: fix purchase basis errors without editing historical consumed purchases.
  - Affects: FIFO basis pool / remaining basis / realized P&L.

- `BALANCE_CHECKPOINT_CORRECTION`
  - Purpose: establish a continuity anchor so expected-balance computations do not explode when there are missing/incorrect session boundaries.
  - Affects: expected start balances + discoverable calculation inputs.

Optional in MVP (can be deferred):
- `REDEMPTION_REVERSAL` helper wizard (creates reversal + replacement; uses existing redemption flows).

### How it appears in the product (no dedicated Adjustments tab)

Primary location (must exist):
- **Setup → Tools**: new section **“Adjustments & Corrections”**
  - Contains a list/table of adjustments (filter by user/site/date range)
  - Buttons:
    - “New Basis Adjustment…”
    - “New Balance Checkpoint…”
    - “Delete Adjustment…” (with safeguards)
    - “Recalculate Affected Pairs” (optional button here; may be implemented in Repair Mode issue)

Convenience entry points (optional but strongly recommended):
- Purchases tab:
  - Context menu / button on a selected purchase row: “Create basis correction…”
- Game Sessions tab:
  - Context menu / button on a selected session: “Create balance checkpoint…”

Rationale:
- Corrections are rare/advanced. Tools is the canonical “advanced operations” home.
- Convenience entry points reduce friction during real incidents.

## Scope

### In-scope (MVP)

Data model + services:
- New `account_adjustments` table + repository
- New `AdjustmentService` (or integrated into existing services) for CRUD + validation
- Integrate adjustments into:
  - `GameSessionService.compute_expected_balances(...)` (balance checkpoint adjustments)
  - FIFO / realized pipeline (basis adjustments)

UI:
- Tools UI section + dialogs that match app styling
- Minimal list view of adjustments with delete action and strong confirmations

Visual indicators (stretch, optional in MVP):
- Add a **Health / Validation** mini-panel within Tools section (not row-level spam) showing:
  - “Largest continuity gaps” per user/site
  - “Likely basis issues” (e.g., negative remaining basis after correction attempt, or purchases with remaining_amount inconsistencies)
  - Buttons: “Open details…”, “Create checkpoint…”, “Create basis adjustment…”

Tests:
- Scenario-based tests proving adjustments work and don’t require deleting downstream history.

Docs:
- Update `docs/PROJECT_SPEC.md` describing adjustments as an official repair mechanism.
- Add changelog entry.

### Out-of-scope (for this issue)

- Full “Repair Mode” (explicitly a separate issue)
- Fully general “reverse/redact any old record without recalculation”
- Automatic inference of the correction amount (we can help compute it but user must confirm)
- A dedicated Adjustments tab

## UX / fields / checkboxes

### Screen/Tab

- Setup → Tools → **Adjustments & Corrections** section
- Dialogs should match existing global QSS styling:
  - Reference: Tools dialogs patterns (backup/restore/reset), session edit dialogs, and any existing form dialogs with ValueChip/labels.
  - Use consistent:
    - label alignment
    - spacing/margins
    - “primary action” button on the right
    - danger actions in red/outlined style consistent with existing delete confirmations

### List panel (Tools section)

Controls:
- Filters:
  - User (combo)
  - Site (combo)
  - Date range (DateFilterWidget or consistent date inputs)
  - Type filter (All / Basis / Balance)

Table columns (suggested):
- Effective Date/Time
- Type
- Δ Basis ($)
- Δ Total SC
- Δ Redeemable SC
- Reason (short)
- Status (Active/Deleted)

Buttons:
- New Basis Adjustment…
- New Balance Checkpoint…
- Delete Selected…
- View Details…

### Dialog: New Basis Adjustment

Field ordering (top → bottom):
- User (required)
- Site (required)
- Effective date (required)
- Effective time (optional; default 00:00:00)
- Amount Δ Basis ($) (required; signed decimal)
- Reason (required short text)
- Notes (optional multiline)

Validation:
- Δ Basis cannot be 0
- Decimal parsing uses existing patterns (Decimal)

Warnings / confirmations:
- Must warn that this impacts FIFO/realized results for that user/site from the effective timestamp forward.
- Confirm dialog shows:
  - user/site
  - effective timestamp
  - delta
  - impacted subsystems: “FIFO allocations”, “Realized P/L”, “Unrealized remaining basis”

### Dialog: New Balance Checkpoint

Purpose: treat this as an *explicit continuity anchor*, not a “fake session”.

Field ordering:
- User (required)
- Site (required)
- Effective date (required)
- Effective time (optional; default 00:00:00)
- “Checkpoint Total SC” (required)
- “Checkpoint Redeemable SC” (required)
- Reason (required)
- Notes (optional)

Semantics:
- This sets the expected-balance checkpoint at that timestamp to these values.
- It should be used only when the true site balance is known but the chain of sessions is unreliable.

Confirmations:
- Warn that this will change “discoverable_sc”/taxable calculations for later sessions.

### Delete adjustment

Deletion semantics options (choose one and implement consistently):

Option A (recommended): **Soft delete**
- `deleted_at`, `deleted_reason`
- Adjustment remains visible in list (status = Deleted)
- Excluded from computations

Hard delete is risky for auditability.

Delete safeguards:
- Must show the affected user/site + timestamp + type
- Must show “This will change derived outputs; you likely need a recalculation”

## Implementation notes / strategy

### Data model / migrations

Add table `account_adjustments` (suggested columns):

- `id` INTEGER PK
- `user_id` INTEGER NOT NULL
- `site_id` INTEGER NOT NULL
- `effective_date` TEXT NOT NULL
- `effective_time` TEXT NULL
- `type` TEXT NOT NULL (enum-like string)
- `delta_basis_usd` TEXT NOT NULL default '0.00'
- `checkpoint_total_sc` TEXT NOT NULL default '0.00'  (only used for checkpoint type)
- `checkpoint_redeemable_sc` TEXT NOT NULL default '0.00'
- `reason` TEXT NOT NULL
- `notes` TEXT NULL
- `related_table` TEXT NULL
- `related_id` INTEGER NULL
- `created_at` TIMESTAMP default CURRENT_TIMESTAMP
- `updated_at` TIMESTAMP
- `deleted_at` TIMESTAMP NULL
- `deleted_reason` TEXT NULL

Indexes:
- (user_id, site_id, effective_date, effective_time)
- (type)

### Service integration details

#### 1) Expected balance integration (checkpoint adjustments)

Update `GameSessionService.compute_expected_balances(...)`:
- While computing expected totals/redeemable up to cutoff, incorporate adjustments:
  - For checkpoint type:
    - Treat it as a checkpoint candidate similar to “last closed session”
    - The latest checkpoint prior to cutoff wins among:
      - closed sessions
      - checkpoint adjustments
  - After checkpoint, apply purchases/redemptions and also apply any adjustments that are “delta” style (if we add delta SC adjustments later).

MVP simplification:
- Only checkpoint adjustments affect expected computation, not delta SC adjustments.

#### 2) Basis integration (basis adjustments)

Goal: correct basis without rewriting historical purchases.

Approach (MVP):
- Treat basis adjustments as an additional “basis lot stream” that participates in FIFO consumption.

Options:

Option 1: Introduce a virtual purchase-lot abstraction in FIFO allocator:
- When building FIFO lots for a user/site, include:
  - purchases (as usual)
  - basis adjustments as synthetic lots with:
    - amount = delta_basis_usd
    - sc_received = 0
    - starting_sc_balance = 0
- Constraints:
  - Positive adjustments behave like extra basis available
  - Negative adjustments reduce basis; allocator must never allocate more basis than available; if it would go negative, surface a clear integrity violation and require a follow-up correction.

Option 2: Apply basis adjustment as an offset to purchase.remaining_amount totals (harder to reason about; less audit-friendly).

Recommend Option 1 for auditability.

### Rebuild / cascade integration (important)

The codebase already has a centralized per-pair rebuild engine:

- `RecalculationService.rebuild_for_pair(user_id, site_id)` (FIFO + sessions + cashback)

For the MVP, adjustments should reuse this rather than inventing a parallel recalculation pathway. When an adjustment is created or soft-deleted:

- write adjustment row
- run `rebuild_for_pair(...)` for the affected (user_id, site_id)
- rebuild game-session event links for that pair (to preserve “derived tables parity”)

All of the above must be inside one transaction; on failure, the adjustment write rolls back.

#### Cascades / recalculation

When an adjustment is created/edited/deleted:
- Mark affected (user_id, site_id) as needing rebuild of:
  - redemption allocations
  - realized transactions
  - closed session recalculations
- Trigger a scoped recalculation:
  - Either immediately (normal mode) OR defer to Repair Mode later.

For MVP in normal mode:
- Perform immediate scoped rebuild for the affected pair only (preferred), not global rebuild.

If scoped rebuild doesn’t exist yet:
- Implement it here as an internal service method used by adjustments only.

Atomicity:
- Adjustment create + cascade recalculation must be within a transaction.
- Failure must roll back the adjustment write.

### Visual indicators (digestible, low-noise)

Do NOT decorate every transaction row.

Instead, implement a Tools “Health / Validation” summary that is:
- Opt-in (user opens Tools)
- Thresholded (only show meaningful problems)

Indicator set (MVP):

1) **Continuity gap detector** (per user/site):
- Compute expected total/redeemable at each closed session start.
- Compute gaps:
  - `gap_total = starting_balance - expected_start_total`
  - `gap_redeem = starting_redeemable - expected_start_redeemable`
- Show only if abs(gap_total) >= configurable threshold (default e.g. $25) OR abs(gap_redeem) >= threshold.
- Display “Top N gaps” table:
  - user, site, date/time, gap_total, gap_redeem
  - action buttons:
    - “Open session”
    - “Create checkpoint at this timestamp” (pre-fills dialog)

2) **Basis stress signals**:
- Purchases with remaining_amount inconsistent with allocations (if any integrity violations exist)
- Redemptions whose allocations sum != expected basis behavior

3) **Stale derived data** (future for Repair Mode):
- If any pair is marked stale, show banner in Tools.

Config:
- Add settings keys for thresholds later; for MVP hardcode but structure for future.

### Documentation

Update `docs/PROJECT_SPEC.md`:
- Add a subsection under accounting semantics describing adjustments:
  - when to use
  - types
  - how they cascade
  - deletion semantics

Add changelog entry.

## Acceptance criteria

### Functional

- Given a user/site with many downstream redemptions, when a basis error is discovered in an old purchase, user can correct basis via a Basis Adjustment without deleting downstream redemptions.
- Given a user/site where session boundaries are unreliable, user can create a Balance Checkpoint such that future expected-balance computations use it as the continuity anchor.
- Adjustments appear in Setup → Tools and can be filtered and reviewed.
- Adjustments can be deleted (soft delete) and the system returns to the prior state after recalculation.

### Accounting correctness / invariants

- Basis adjustments are included in FIFO lot availability deterministically.
- Creating or deleting an adjustment is atomic: either adjustment + cascade rebuild succeeds, or nothing changes.
- Rebuild scope is restricted: only the selected user/site derived rows change.

### UX

- Dialog layouts match global styling and existing form patterns.
- Confirmations clearly communicate cascading effects.

### Performance

- Scoped recalculation for one user/site completes in reasonable time for typical datasets.

## Test plan

### Automated tests (mandatory; add scenario-based tests)

Add integration tests that set up a small dataset:

Happy path:
- Create purchases + several redemptions consuming them.
- Introduce a Basis Adjustment (+$X) effective before the first redemption.
- Assert:
  - allocations/realized totals change as expected
  - no deletions were needed

Edge cases (at least 2):
- Negative basis adjustment that would cause insufficient basis: must fail with clear error and roll back.
- Two checkpoint adjustments: latest before cutoff wins.

Failure injection (at least 1):
- Simulate a mid-rebuild failure (e.g., mock repository write raising) and assert transaction rollback leaves DB unchanged.

Invariants:
- Only affected user/site rows change.

### UI smoke

If new dialogs/Tools section added:
- Add a headless smoke test that boots `MainWindow(AppFacade(...))` with `QT_QPA_PLATFORM=offscreen`, opens Tools tab, opens the Adjustment dialog, and closes cleanly.

### Manual verification

- Create an adjustment on a real-ish DB copy, confirm derived numbers change only for that pair.
- Delete the adjustment, run scoped rebuild, confirm numbers revert.

## Pitfalls / follow-ups

- **Don’t silently rewrite history:** Adjustments must be clearly marked and never appear indistinguishable from purchases/sessions/redemptions.
- **Negative basis is dangerous:** If negative basis adjustments are allowed, allocator behavior must be explicit (fail-fast + rollback) and errors must be user-readable.
- **Scoped rebuild is required:** Without a fast per-(user,site) rebuild, adjustments will feel unusable on large DBs.
- **UI discoverability:** Keep adjustments “advanced”; avoid normal workflows accidentally creating them.
- **Follow-up (recommended):** Add a “Find first divergence” wizard that leads directly into creating a checkpoint adjustment.
