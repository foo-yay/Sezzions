# Feature request: Tax withholding estimates (settings + per-session override + historical storage)

## Problem / motivation
Users often want to set aside an estimated % of taxable P/L for taxes. Today Sezzions can compute taxable P/L per session, but it does not:
- Let users configure an estimated withholding %.
- Show a per-session “set aside” amount in Daily Sessions.
- Persist this estimate historically so it can be summed for reporting (e.g., quarterly estimates).

We want this to be configurable globally, optionally overridable per session, and recalculable in bulk.

## Proposed solution
What:
- Add a tax withholding estimate feature driven by Settings:
  - Global toggle: enable/disable tax withholding estimates.
  - Global default withholding rate (percent).
- Store withholding values per closed game session:
  - `tax_withholding_rate_pct` (rate used for this session; stored historically)
  - `tax_withholding_is_custom` (whether the session used a user-entered override)
  - `tax_withholding_amount` (estimated amount to set aside for taxes)
- Add optional per-session override in the Add/Edit/End/View Session UI:
  - If user leaves blank: use the global default rate.
  - If user enters a custom rate: use it and mark the session as custom.
- Add Settings action: “Recalculate Withholding”:
  - Recalculate everything or filter by site/user.
  - Option to overwrite custom inputs.
- Add a Daily Sessions column that shows the estimated withholding per session and aggregates at user/day level.

Why:
- Makes tax estimates visible where users already review results (Daily Sessions).
- Enables future reporting/statistics: total estimated set-aside across arbitrary ranges.
- Avoids retroactive drift by storing the rate used at the time of calculation.

Notes:
- No popups; this is a reporting/estimation feature (not a notification).
- This is an estimate only; not “actual taxes withheld/paid”.

Dependencies:
- This feature depends on having a first-class Settings entry point/section (e.g., a Settings gear in the main header) as described in Issue #28.
- If Issue #28 lands later, this issue may temporarily add a minimal Settings entry point to host the withholding settings, then later unify with the global Settings UI.

## Scope
In-scope:
- Database schema:
  - Add 3 new columns to `game_sessions`:
    - `tax_withholding_rate_pct` (REAL or TEXT; percent in range 0..100)
    - `tax_withholding_is_custom` (INTEGER 0/1)
    - `tax_withholding_amount` (TEXT money, like other stored monetary fields)
  - Add migration via `repositories/database.py` `_migrate_game_sessions_table()`.
- Service-layer logic:
  - Compute withholding at session close (and any recalculation that recomputes `net_taxable_pl`).
  - Provide bulk recalculation API:
    - filter by `site_id` and/or `user_id`
    - `overwrite_custom: bool`
    - uses current global rate from Settings
    - runs in a transaction; invariant: only withholding columns change.
- UI changes:
  - Settings UI:
    - Toggle: enable tax withholding estimates.
    - Input: default withholding rate (%).
    - Action: “Recalculate Withholding…” dialog with:
      - scope: all vs filter by site/user
      - checkbox: overwrite custom session rates
      - confirmation prompt + summary of affected rows
  - Game Sessions dialogs:
    - Add optional “Withholding % (optional)” field (blank = global).
    - Show “Withholding amount (est.)” as read-only on view dialogs.
  - Daily Sessions tab:
    - Add a column “Tax set-aside (est.)” on session rows and aggregate totals.

Out-of-scope:
- Tracking actual tax payments.
- Quarterly payment scheduling.
- Complex rules per user/site/region tax jurisdiction.

## UX / fields / checkboxes
Screen/Tab:
- Settings (global)
- Game Sessions dialogs (end/edit/view)
- Daily Sessions hierarchy

Fields:
- Settings:
  - “Enable tax withholding estimates” (checkbox)
  - “Default withholding rate (%)” (numeric input)
- Session dialog:
  - “Withholding % (optional)” (numeric input, blank allowed)
  - Read-only “Estimated withholding amount”

Checkboxes/toggles:
- “Enable tax withholding estimates”
- In recalculation dialog: “Overwrite custom session withholding %”

Buttons/actions:
- “Recalculate Withholding…”
- Confirmations for bulk recalculation

Warnings/confirmations:
- Bulk recalculation updates historical stored values; must prompt and confirm.

## Implementation notes / strategy
Approach:
- Introduce a small service (or extend `GameSessionService`) to compute and store withholding:
  - `withholding_amount = max(0, net_taxable_pl) * (rate_pct / 100)`
  - If feature disabled, compute nothing and/or store 0.00; pick one behavior and document.
- Persist a per-session override choice:
  - If user enters a custom rate: store rate + `is_custom=1`.
  - If blank: store global rate at the time + `is_custom=0`.
- Bulk recalculation:
  - For each closed session:
    - If `is_custom=1` and `overwrite_custom=False`: skip.
    - Else set `rate_pct = current_global_rate`, set `is_custom=0`, recompute amount.

Data model / migrations (if any):
- Yes: add columns to `game_sessions`.

Risk areas:
- Historical semantics: recalculation is intentionally retroactive; UI must make that explicit.
- Precision: use `Decimal` for computations; store amount as string with 2 decimals.

## Acceptance criteria
- Given withholding estimates are disabled, when a closed session is created/ended, then withholding fields are not shown in Daily Sessions (and stored values remain unchanged or are 0 per chosen semantics).
- Given withholding estimates are enabled and default rate is 20%, when a session is closed with `net_taxable_pl = 100.00`, then the stored withholding amount is `20.00` and `tax_withholding_is_custom = 0`.
- Given withholding estimates are enabled, when a user enters a custom withholding rate for a session (e.g., 30%), then the session stores `rate_pct=30`, `is_custom=1`, and amount matches.
- Given a session has `net_taxable_pl <= 0`, then withholding amount is `0.00`.
- Given “Recalculate Withholding” runs with `overwrite_custom=False`, then only non-custom sessions are updated.
- Given “Recalculate Withholding” runs with `overwrite_custom=True`, then custom sessions are overwritten to the current global rate and recomputed.
- Given “Recalculate Withholding” runs filtered by a specific site/user, then only matching sessions are updated.
- Daily Sessions shows a “Tax set-aside (est.)” column and aggregates correctly for a date/user.

## Test plan
Automated tests (scenario-based):
- Happy path:
  - Close session with positive taxable P/L + global rate → correct stored rate/is_custom/amount.
- Edge cases:
  - Negative/zero taxable P/L → amount 0.00.
  - Custom rate session is skipped on bulk recalc unless overwrite_custom.
  - Filtered recalc updates only the specified site/user.
- Failure injection:
  - Force an exception mid-bulk-recalc and assert transaction rollback (no partial updates).
- Invariants:
  - Bulk recalc changes only withholding columns; does not change `net_taxable_pl`, balances, or session identity fields.

Manual verification:
- Enable setting, set default %, close a session → verify Daily Sessions shows the estimate.
- Create a session with a custom % → verify it persists.
- Change global %, run recalc non-custom only → verify behavior.

## Area
UI / Services / Database/Repositories / Tests

## Notes
- [X] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [X] This change likely requires adding/updating scenario-based tests.
- [X] This change likely touches the database schema or migrations.
- [X] This change includes destructive actions (must add warnings/backup prompts).
