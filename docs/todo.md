# Sezzions — TODO (Offline Mirror)

Last updated: 2026-01-28

Rules:
- Primary work tracking lives in GitHub Issues.
- This file is an optional offline/lightweight queue (and may be kept roughly in sync with Issues when useful).
- Keep items small and outcome-based.
- When an item changes meaning, close it and create a new one.
- Do not mark/remove items as done until the project owner approves.
- When you think an item is done, move it to "Ready for Review" with brief validation steps.
- Add newly discovered bugs/work here as you find them (keep titles action-oriented).

## Now


- [ ] Define 3–6 “golden scenario” accounting tests (basis + cashflow P/L + taxable P/L)
- [ ] Reconcile Game Session taxable P/L algorithm vs current implementation
- [ ] Confirm whether UI still fetches via repos (enforce UI→services only)

## Ready for Review (Owner Approval Required)

- [x] **Tax withholding moved to daily sessions only** (PR #34, Issue #29)
  - Validation: Database migration added tax columns to daily_sessions, removed from game_sessions schema
  - TaxWithholdingService rewritten for daily-only semantics (apply_to_daily_session, bulk_recalculate)
  - All tax UI removed from game session dialogs (Edit/End/View)
  - Daily Sessions tab updated: fetches tax from daily_sessions table, calculates at user+date level
  - App starts without errors, data flow tested
  - Commits: 153cdf0, 22c3925, 3a0220a on feature/issue-29-tax-withholding-ui
  - **Remaining**: Add Edit Daily Session dialog with tax override, update bulk recalc dialog UI, fix/update tests

## Next

- [ ] UI parity pass: view-first dialogs and consistent button visibility rules
- [ ] Tools tab UX: clear flows for backup/restore/reset/import/export/recalc
- [ ] Add pre-destructive-action backup prompts (sessions, cascades)

## Later

- [ ] Packaging strategy (pyinstaller) and versioned releases
- [ ] Optional: migration assistant from `.LEGACY` datasets

## Done (Approved)

- (none)
