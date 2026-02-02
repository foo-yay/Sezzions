# Bug: Daily Sessions tax withheld missing after CSV import + Recalculate Everything (multi-day sessions)

## Summary
After importing `game_sessions` via CSV and running **Tools → Recalculate Everything**, the **Daily Sessions** view sometimes shows **Tax Set-Aside / tax withheld = $0.00** even though the sessions (and net P/L) display correctly. This appears to happen most often (or only) when a session starts on one day and ends on the next (i.e., `end_date != session_date`).

If the user then goes to **Settings → Recalculate Tax Withholding** and runs the tax recalculation, the tax amount immediately becomes correct.

## Impact
- Misleading accounting display in Daily Sessions after import.
- Users may incorrectly believe there is no tax set-aside required for affected dates.
- Creates inconsistent behavior between “Recalculate Everything” vs. “Recalculate Tax Withholding”.

## Environment
- App: Sezzions desktop app
- Platform: macOS (reported)
- Date discovered: 2026-02-02

## Preconditions
- Tax withholding feature enabled in Settings.
- At least one imported session has `end_date` on the following day.

## Steps to Reproduce (one concrete path)
1. Ensure **Settings → Tax withholding enabled** is ON, with a non-zero default rate.
2. Use **Tools → Import CSV → game_sessions** to import a CSV containing at least one *Closed* session where:
   - `session_date = 2026-02-01`
   - `end_date = 2026-02-02`
   - net taxable P/L for that session is positive (so date-level net should be positive)
3. After import, run **Tools → Recalculate Everything**.
4. Open **Daily Sessions** tab and locate the date row for `2026-02-02`.

### Actual
- Sessions appear correctly grouped/displayed, but **Tax Set-Aside** / withheld value for that date is **$0.00**.

### Expected
- Tax withheld should be calculated for the accounting date (typically `end_date` for closed sessions) and should be non-zero when date-level net P/L is positive.

## Diagnostic Notes / Suspected Root Cause
Current architecture stores withholding in `daily_date_tax` and reads it in Daily Sessions via `DailySessionsService.fetch_daily_tax_data()`.

There is code that *looks* like it should run tax recomputation during a full rebuild, but it may never execute due to service wiring:

- The “recalculate everything” engine is `RecalculationService.rebuild_all()`.
- `RecalculationService.rebuild_all()` contains a final step:
  - “Recalculate tax withholding (if enabled in settings)”
  - guarded by `hasattr(self, 'tax_withholding_service')`
- However, `RecalculationService.__init__()` does not accept or set a `tax_withholding_service`.
- When `RecalculationService` is constructed ad-hoc (e.g., by worker threads) it likely has **no `tax_withholding_service` attribute**, so tax recomputation is skipped entirely.

This explains why:
- **Settings → Recalculate Tax Withholding** fixes the problem (it calls `TaxWithholdingService.bulk_recalculate()` directly).
- **Tools → Recalculate Everything** may rebuild `daily_sessions` but not create/update `daily_date_tax`.
- The issue can appear “only for some sessions/dates” (e.g., multi-day sessions create accounting dates that didn’t previously have a `daily_date_tax` row).

Relevant code pointers:
- `services/recalculation_service.py` (`RecalculationService.rebuild_all`, tax recalculation step)
- `services/tax_withholding_service.py` (`bulk_recalculate`, `apply_to_date`)
- `services/daily_sessions_service.py` (`_sync_daily_sessions` uses `gs.end_date`, grouping uses `end_date` as accounting date)
- `app_facade.py` creates `TaxWithholdingService(..., settings=None)` (wired from `MainWindow`)

## Proposed Fix Options (do not implement yet)
1. **Wire `TaxWithholdingService` into `RecalculationService`**
   - Add an optional constructor argument `tax_withholding_service` (or a setter) and always call it during `rebuild_all()` when enabled.
2. **Ensure worker-thread recalculation has access to settings**
   - Today `TaxWithholdingService.get_config()` returns disabled if `settings is None`.
   - If worker threads create their own services, they may not have settings injected.
   - Options:
     - Persist tax settings in DB (so workers can read config without UI injection).
     - Pass a serialized settings snapshot into the worker.
3. **Add a targeted post-import rebuild step**
   - After importing `game_sessions`, force a `daily_sessions` sync + tax bulk recalc for affected dates.

## Acceptance Criteria
- After CSV importing game sessions (including multi-day sessions) and running **Tools → Recalculate Everything**, Daily Sessions shows correct **Tax Set-Aside** for all affected dates.
- No regression for existing same-day sessions.
- Tax recalculation respects custom rates (i.e., does not overwrite unless explicitly requested).

## Test Plan (automation)
Happy path:
- Import sessions spanning dates; run rebuild; assert `daily_date_tax.tax_withholding_amount` populated for the `end_date` and matches expected rate * net.

Edge cases:
- Multi-day session where `end_date` exists but `end_time` missing.
- Multi-day session where date-level net is negative (tax should be 0, but still should have a `daily_date_tax` row if feature is enabled).

Failure injection / invariants:
- If tax bulk recalc fails mid-run, ensure rebuild transaction safety and that existing `daily_date_tax` rows are not partially corrupted.
- Invariant: rebuild should not change raw imported `game_sessions` rows.
