## Problem
Sezzions currently **auto-cascades derived rebuilds** (FIFO allocations, session P/L, event links, etc.) immediately after many writes (create/update/delete purchases/redemptions/sessions/adjustments).

This is correct for safety, but it makes certain repair workflows painful:
- making many small corrections becomes slow (rebuild repeated many times)
- if data is already inconsistent, auto-cascade can fail mid-flow and block incremental fixes

We need a power-user mode that lets users **make edits first**, then run **explicit, controlled rebuilds** afterward.

## Proposal: Repair Mode
Add a **Repair Mode** that:
1) **Disables auto-cascade rebuilds** during normal CRUD writes
2) **Marks affected (user_id, site_id) pairs as stale** (with an earliest rebuild boundary)
3) Provides UI + tools to **explicitly rebuild per pair** (and/or rebuild all stale pairs)
4) Persists stale state so it survives app restart

This is distinct from existing **Maintenance Mode** (Issue #9) which blocks writes when data integrity checks fail (and/or during destructive tools operations).

## What already exists (do not re-implement)
PR #70 merged rebuild/cascade robustness that Repair Mode should rely on:
- Tools rebuilds now adjustment/checkpoint-aware
- Tools rebuilds rebuild `game_session_event_links`
- Redemption delete cascades rebuild links consistently (single + bulk)
- Expected-balance edit semantics deterministic for same-timestamp purchases
- Tax `apply_to_date` preserves existing custom per-date rate when no override provided
- Rebuild pair discovery includes non-deleted `account_adjustments`

Repair Mode itself (disable auto-cascade; explicit per-pair rebuild + stale marking + UI/setting + tests) is still pending.

## Intended Behavior
### When Repair Mode is ON
- Writes (create/update/delete) still perform their primary DB mutations and validations.
- **No automatic calls** to derived rebuilds, including:
  - `RecalculationService.rebuild_*` and scoped FIFO rebuilds (`rebuild_fifo_for_pair_from(...)`)
  - `GameSessionService.recalculate_*`
  - `GameSessionEventLinkService.rebuild_links_*`
- Instead, the app records a stale marker for the impacted pair(s):
  - key: `(user_id, site_id)`
  - value: earliest `(from_date, from_time)` boundary to rebuild from (if available)
  - optional: `reason` list for UI (purchase edit, redemption delete, etc.)

Stale boundary rules:
- If multiple edits hit the same pair, keep the **earliest** boundary.
- If an edit moves data between pairs (e.g., forced user/site change), mark **both old + new** pairs stale.
- Boundary should match the semantics used by current cascade paths (including “containing session boundary” helpers where relevant).

### When Repair Mode is OFF (default)
- Behavior remains unchanged: auto-cascade rebuilds happen as they do today.

## UI / UX
- Provide a **manual toggle** to enter/exit Repair Mode (prefer Tools since it is operational).
- Add a clear, always-visible indicator when Repair Mode is enabled:
  - window title suffix: `REPAIR MODE`
  - static red banner at top of the main window: `REPAIR MODE — Auto-rebuild disabled` (similar visibility to the existing maintenance-mode banner)

### Entering Repair Mode (required warning)
When the user turns Repair Mode ON, show a blocking confirmation dialog with explicit warnings.

Suggested copy (exact wording can be tuned, intent must remain):
- Title: `Enable Repair Mode? (Advanced)`
- Body:
  - `Auto-rebuild/auto-cascade is DISABLED (FIFO allocations, session P/L, event links).`
  - `Reports and balances may look wrong until you explicitly rebuild.`
  - `You are responsible for rebuilding affected pairs after edits.`
  - `Use only if you understand the risks.`
- Require an acknowledgement checkbox before enabling:
  - `I understand derived calculations will not update automatically.`

Guardrails:
- Do not allow enabling Repair Mode while Maintenance Mode is active.
- Repair Mode disables derived recomputation/cascades, but should not intentionally disable basic input validation/DB constraints.
- Provide a “Stale Pairs” list UI:
  - shows `(user, site)` + boundary + last-updated time
  - actions:
    - “Rebuild selected pair”
    - “Rebuild all stale pairs”
    - “Clear stale list” (with confirmation)

Optional (nice-to-have): when turning Repair Mode OFF and stale pairs exist, prompt:
- “Rebuild now” / “Keep stale (remind me)” / “Cancel”

## Data / Persistence
Persist in app settings (settings.json), e.g.:
- `repair_mode_enabled: bool`
- `repair_mode_stale_pairs: {"<user_id>:<site_id>": {"from_date": "YYYY-MM-DD", "from_time": "HH:MM:SS", "updated_at": "...", "reasons": ["..."]}}`

## Acceptance Criteria
- Toggle ON prevents auto-cascade rebuilds from write operations.
- Stale markers are created/updated correctly (including earliest-boundary merge and cross-pair moves).
- Manual rebuild (existing Tools “Recalculate Pair” and/or a new “Rebuild stale pairs”) produces the same derived results as the current auto-cascade path would.
- Stale markers persist across app restart.
- Toggle OFF returns app to current behavior.
- No UI crashes; add/update a headless UI smoke test if UI wiring changes.

## Test Matrix (required)
Happy paths:
- Repair Mode ON -> edit purchase amount/date -> derived tables unchanged until explicit rebuild -> rebuild fixes derived state.
- Repair Mode ON -> delete redemption -> stale pair marked -> rebuild restores consistency.

Edge cases:
- Multiple edits to same pair accumulate earliest boundary.
- Move purchase/redemption between pairs (forced site/user change) marks both pairs stale.
- Stale list empty: rebuild-all-stale is a no-op (friendly message).

Failure injection:
- Force rebuild error (raise in rebuild path or corrupt data) and assert:
  - base write succeeded
  - stale marker is NOT cleared
  - app remains usable and user can retry rebuild

Invariants:
- When Repair Mode ON, only base tables mutate during CRUD writes; derived rebuild tables do not.
- When Repair Mode OFF, existing cascade behavior is unchanged.

## Implementation Notes
- Prefer a small backend service (e.g., `RepairModeService` / `StalePairTracker`) owned by the backend and called by `AppFacade`.
- UI must not talk to repositories/DB directly.
- Reuse existing Tools rebuild plumbing (RecalculationWorker) where possible.
