# Sezzions — Changelog (Human + AI Parsable)

Purpose: a chronological log of noteworthy changes.

Rules:
- One entry per meaningful change set.
- Prefer adding here over creating a new markdown file.
- Entries must include the metadata block.

---

## 2026-02-06

```yaml
id: 2026-02-06-03
type: bugfix
areas: [ui, tests]
summary: "Game Sessions tab search now filters by user/site/game names (resolves Issue #71)"
issue: "#71"
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_game_sessions_search.py (new)
```

Notes:
- Fixed Game Sessions search to resolve user/site/game names using lookup dictionaries (same as table display logic).
- Previously searched non-existent model attributes (`user_name`, `site_name`, `game_name`), causing empty results.
- Search now matches displayed text: searching "Alice" finds sessions by that user, "CasinoX" finds sessions at that site, etc.
- Added comprehensive integration tests (7 test cases): search by user/site/game name, numeric values, case-insensitive, clear search, no results.
- Tests set date filter to "All Time" to ensure visibility of test data.

```yaml
id: 2026-02-06-02
type: bugfix
areas: [services, ui, app_facade, tests]
summary: "Repair/rebuild robustness: adjustment-aware tools rebuilds, event-link rebuild coverage, and safer tax recompute"
issue: "#55"
files_changed:
  - app_facade.py
  - services/game_session_service.py
  - services/recalculation_service.py
  - services/tax_withholding_service.py
  - ui/tools_workers.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_issue_49_purchase_exclusion.py
  - tests/unit/test_recalculation_service.py
  - tests/unit/test_tax_withholding_service.py
```

Notes:
- Tools rebuild pipeline is now fully adjustment/checkpoint-aware and rebuilds `game_session_event_links` after scoped/all rebuilds.
- Redemption delete cascades now rebuild event links consistently (single + bulk paths).
- Expected-balance computation is deterministic for same-timestamp purchase edits (prevents drift/regressions).
- Tax withholding recompute (`apply_to_date`) preserves an existing custom rate when no override is provided.
- Pair discovery for rebuild (`iter_pairs`) now includes non-deleted account adjustments.

```yaml
id: 2026-02-06-01
type: bugfix
areas: [ui, app_facade]
summary: "Purchase balance check now respects balance checkpoints and adjustments"
issue: "#54"
files_changed:
  - app_facade.py (adjustment_service initialization order)
  - ui/tabs/purchases_tab.py (balance check logic)
  - ui/adjustment_dialogs.py (date/time field patterns)
```

Notes:
- **Bug Fix:** Purchase dialog balance check was using legacy logic that bypassed checkpoint calculations
  - Previously: When period_purchases existed, used prev_purchase.starting_sc_balance as expected value
  - Now: Always calls facade.compute_expected_balances() which respects checkpoints and adjustments
  - Fixed in: ADD purchase flow, EDIT purchase flow, and live balance check (_update_balance_check)

- **Bug Fix:** adjustment_service was initialized after game_session_service in AppFacade
  - Moved adjustment_service initialization before game_session_service
  - Now properly passed to game_session_service constructor
  - Enables checkpoint logic in compute_expected_balances()

- **UI Fix:** Adjustment dialogs now use correct date/time field pattern
  - Changed from QDateEdit/QTimeEdit to QLineEdit with placeholders (MM/DD/YY, HH:MM)
  - Added calendar picker button (📅) and "Today"/"Now" quick-fill buttons
  - Matches global UI patterns (Purchase dialog, etc.)
  - Fixed method names: get_user_by_id → get_user, get_site_by_id → get_site

---

## 2026-02-05

```yaml
id: 2026-02-05-06
type: feature
areas: [models, repositories, services, ui, database]
summary: "Adjustments & Corrections (Basis Adjustments + Balance Checkpoints)"
issue: "#54"
files_changed:
  - models/adjustment.py (new)
  - repositories/adjustment_repository.py (new)
  - repositories/database.py (account_adjustments table)
  - services/adjustment_service.py (new)
  - services/game_session_service.py (checkpoint integration)
  - services/recalculation_service.py (basis adjustment integration)
  - ui/tabs/tools_tab.py (adjustments section)
  - ui/adjustment_dialogs.py (new)
  - tests/unit/test_adjustment_model.py (12 tests)
  - tests/unit/test_adjustment_repository.py (10 tests)
  - tests/unit/test_adjustment_service.py (15 tests)
```

Notes:
- **Feature:** Two types of manual adjustments for correcting accounting issues:
  1. **Basis Corrections** (BASIS_USD_CORRECTION): Delta adjustments to cost basis (e.g., missed fees, refunds)
     - Integrated into FIFO pipeline as synthetic purchases with negative IDs
     - Ordered by effective datetime for correct FIFO sequencing
  2. **Balance Checkpoints** (BALANCE_CHECKPOINT_CORRECTION): Known balance anchors at specific timestamps
     - Override closed sessions in expected balance calculations
     - Used for reconciliation or importing external data

- **Data Layer:**
  - New `account_adjustments` table with soft delete support
  - Indexes on (user_id, site_id, effective_date, effective_time) and (type, deleted_at)
  - Fields: type, delta_basis_usd, checkpoint_total_sc, checkpoint_redeemable_sc, reason (required), notes, related_table/id

- **Service Layer:**
  - AdjustmentService with validation (delta != 0, checkpoints have non-zero balances)
  - GameSessionService.compute_expected_balances() uses latest checkpoint before cutoff
  - RecalculationService injects basis adjustments as synthetic lots in FIFO rebuild

- **UI (Tools Tab):**
  - New Adjustments section with three buttons: New Basis Adjustment, New Balance Checkpoint, View Adjustments
  - BasisAdjustmentDialog: form for delta, user/site, date/time, reason
  - CheckpointDialog: form for total/redeemable SC, user/site, date/time, reason
  - ViewAdjustmentsDialog: table view with filters, soft delete, restore

- **Test Coverage:** 37 new unit tests (100% coverage on new models/repos/services), 685 total tests passing

```yaml
id: 2026-02-05-05
type: feature
areas: [ui]
summary: "Game Sessions: End & Start New convenience flow"
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_switch_game_flow.py
```

Notes:
- Adds a fast workflow to end an Active session and immediately start a new session with carried-forward starting balances.
- End Session dialog now includes **"🎮 End & Start New"**.
- The Start Session dialog is prefilled with same User/Site and starting balances equal to the ended session’s ending balances; game selection is intentionally left blank.
- Validation: scenario-based pytest-qt integration tests cover happy path, cancel, and failure injection.

```yaml
id: 2026-02-05-04
type: feature
areas: [ui, facades, services]
summary: "Purchase dialogs: balance chain warnings + full basis-period display"
issue: "#66"
files_changed:
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - tests/integration/test_purchase_edit_balance_check.py
```

Notes:
- **Problem:** Purchase dialogs didn't track balance chains correctly, leading to misleading warnings and lack of context for multi-purchase basis periods.
- **Solution:** 
  1. Implemented proper balance chain tracking: expected balance uses previous purchase's actual `starting_sc_balance` (not just sum of SC received)
  2. Added "Full Basis Period" section to Purchase View dialog showing ALL purchases (past, current, future) in the basis period
  3. Added View Purchase buttons for easy navigation through purchase chains
  4. Simplified warnings: warn on ANY non-zero mismatch (no tolerance, no confusing delta display)

- **Basis Period Rules (Clarified):**
  - Period starts after most recent FULL redemption (`more_remaining=0`)
  - Partial redemptions (`more_remaining>0`) do NOT start new period
  - Example: Redeem 2500 SC but leave 200 SC → NOT full → period continues
  - Subsequent purchases continue same basis period until next FULL redemption

- **Balance Chain Logic (Critical Fix):**
  - If previous purchase exists in basis period: `expected_pre = prev_purchase.starting_sc_balance`
  - If first purchase in period: `expected_pre = compute_expected_balances()`
  - This creates proper balance chain accounting for actual entered balances
  - `total_extra = (actual_pre - expected_pre).quantize(Decimal("0.01"))`

- **Warning Logic (Simplified):**
  - Warn if `total_extra != 0` (any mismatch, no tolerance)
  - Real-time label shows: "✓ Balance Check: OK" or "✗ Balance Check: X.XX SC HIGHER/LOWER than expected (Y.YY SC)"
  - Submission warning dialog explains if mismatch indicates tracked loss or untracked wins

- **Bug Fixes During Implementation:**
  1. Fixed `exclude_purchase_id` not being passed when computing previous purchase's total_extra
  2. Fixed expected balance using `compute_expected_balances` instead of actual balance chain
  3. Fixed real-time label using old 0.50 tolerance logic instead of matching submission check
  4. Removed confusing delta display per user feedback ("just show if balance matches or not")

- **UI Enhancements:**
  - Current purchase shown in **bold** in basis period table
  - Table fills available space (min 3 rows visible, scales with content)
  - View Purchase buttons styled like View Session buttons
  - Clicking button highlights purchase in main table and opens its dialog

- **Facade Methods Added:**
  - `get_basis_period_start_for_purchase()`: finds most recent FULL redemption datetime
  - `get_basis_period_purchases()`: returns ALL purchases in basis period (past, current, future), ordered by (date, time, id)
  - `compute_purchase_total_extra()`: computes total_extra given entered balance values

- **Validation:** All 645 tests pass. Updated `test_purchase_edit_balance_check_excludes_edited_purchase` to expect new balance chain logic.

```yaml
id: 2026-02-05-01
type: fix
areas: [repositories, tests]
summary: "FULL redemptions (more_remaining=0) now close Unrealized positions"
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
```

Notes:
- **Problem:** When users cash out everything they want to (FULL redemption: `more_remaining=0`), the position would remain visible in the Unrealized tab even though they consider it dormant/closed. This clutters the Unrealized view with negligible balances (e.g., 0.43 SC left after $100 redemption).
- **Fix:** Expanded `_get_close_balance_dt()` to check both "Balance Closed" markers AND FULL redemptions (`more_remaining IS NOT NULL AND more_remaining = 0`). Returns the most recent closure datetime. Positions are excluded from Unrealized tab when closure datetime >= last activity datetime.
- **Semantics:** `more_remaining=0` means "I'm cashing out everything I want to/can right now; treat remaining balance as dormant." `more_remaining=1` means "partial redemption, balance remains active." Position reopens automatically when new activity (purchases, sessions) occurs after closure.
- **Validation:** Added 4 regression tests covering: (1) FULL redemption closes position, (2) partial redemption keeps position visible, (3) FULL redemption followed by later activity reopens position, (4) newest closure wins when both "Balance Closed" and FULL redemption exist. Updated 3 existing tests to use `more_remaining=1` to maintain position visibility for their test scenarios.

```yaml
id: 2026-02-05-02
type: fix
areas: [ui]
summary: "Fix Unrealized Close Position crash (current_sc -> total_sc)"
files_changed:
  - ui/tabs/unrealized_tab.py
```

Notes:
- **Problem:** Clicking "Close Position" could raise an `AttributeError` because the UI referenced `pos.current_sc` but the model uses `total_sc`.
- **Fix:** Use `pos.total_sc` for the close-balance confirmation and close call.

```yaml
id: 2026-02-05-03
type: fix
areas: [services, ui, tests]
summary: "Fix redemption deletion impact check on DBs without fifo_allocations"
files_changed:
  - services/redemption_service.py
  - tests/unit/test_redemption_deletion_impact.py
```

Notes:
- **Problem:** Deleting a redemption could log `no such table: fifo_allocations` while checking deletion impact.
- **Fix:** `RedemptionService.get_deletion_impact()` now queries `redemption_allocations` (the real FIFO allocation table).

---

## 2026-02-04

```yaml
id: 2026-02-04-08
type: feature
areas: [repositories, tests, docs]
summary: "Unrealized Total SC estimation now uses purchase snapshots and session starts as checkpoints (Issue #61)."
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
  - docs/PROJECT_SPEC.md
issue: 61
```

Notes:
- **Problem:** Total SC (Est.) only used last closed session ending balance as checkpoint, ignoring dailies/bonuses added before first session start or between sessions. Purchases with `starting_sc_balance` (snapshots) and Active session starting balances were not recognized as valid checkpoints. Additionally, Redeemable SC (Position) was incorrectly showing checkpoint value without subtracting redemptions that occurred after the checkpoint.
- **Fix:** Expanded checkpoint sources to three types: (1) purchase snapshots (WHERE `starting_sc_balance > 0.001`), (2) session starts (`starting_balance` from any session), (3) session ends (`ending_balance` from Closed sessions only). Checkpoint selection: most recent by datetime. Formula: `Total SC = checkpoint_total_sc + purchases_since_checkpoint - redemptions_since_checkpoint`. Redeemable SC now correctly subtracts non-free-SC redemptions after checkpoint: `Redeemable SC = checkpoint_redeemable_sc - redeemable_redemptions_since_checkpoint`.
- **No-double-counting:** When checkpoint is a purchase snapshot, that purchase's `sc_received` is excluded from "purchases since checkpoint" delta to prevent adding the same SC twice.
- **Validation:** Added 9 regression tests (7 for checkpoint expansion + 2 for redeemable SC after redemptions) covering purchase snapshot precedence, session start checkpoints, session end checkpoints, checkpoint source ordering, no-double-counting invariant, multiple purchases with snapshots, redemptions after snapshots, and redeemable SC estimation. Updated 3 existing test expectations to reflect new checkpoint behavior.

```yaml
id: 2026-02-04-07
type: feature
areas: [repositories, tests, docs]
summary: "Unrealized positions remain visible when SC remains but basis is fully allocated (Issue #58)."
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
  - docs/PROJECT_SPEC.md
issue: 58
```

Notes:
- **Problem:** Partial redemptions could consume all remaining basis (via FIFO allocation) but leave SC on the site (e.g., Moonspin 2500 SC cap scenario left ~175 SC remaining). The position would disappear from Unrealized even though it wasn't fully closed.
- **Fix:** Unrealized now includes positions where `Total SC (Est.) > 0` even if `Remaining Basis = $0.00`, reflecting that the position is still open with profit-only SC.
- **Removal criteria:** Position removed when (a) estimated SC < 0.01, or (b) explicit "Balance Closed" marker exists.
- **Validation:** Added 3 regression tests (basis=0 + SC>0 shows, basis=0 + SC<threshold doesn't show, Balance Closed marker still suppresses).

```yaml
id: 2026-02-04-06
type: fix
areas: [ui, tests]
summary: "End Session dialog notes start collapsed; dialog resizes on expand/collapse."
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_edit_session_dialog_notes_layout.py
  - tests/integration/test_end_session_dialog_notes_layout.py
issue: null
```

Notes:
- **Problem:** Ending a session with pre-existing notes could open the dialog in a cramped state (especially when notes were visible), compressing the "Session Details" section.
- **Fix:** Start with notes collapsed (even if notes exist) and compute tight/expanded dialog heights from Qt size hints so expand/collapse resizes cleanly.
- **Validation:** Added headless regression tests for End Session + Edit Session + Edit Closed Session collapsed → expanded → collapsed behavior.

```yaml
id: 2026-02-04-05
type: fix
areas: [ui, tests]
summary: "End Session dialog now shows Game Type correctly."
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_end_session_dialog_game_type.py
issue: null
```

Notes:
- **Problem:** `EndSessionDialog` attempted to load game/game-type via repo attributes that are not part of `AppFacade`, causing the Game Type chip to render as blank/"—".
- **Fix:** Fetch game + game type via `AppFacade.get_game()` / `AppFacade.get_game_type()`.
- **Validation:** Added a headless regression test.

```yaml
id: 2026-02-04-04
type: fix
areas: [ui]
summary: "Fix purchase add/edit crash after removing _balance_check_cutoff helper."
files_changed:
  - ui/tabs/purchases_tab.py
issue: null
```

Notes:
- **Problem:** Purchase add/edit flows still referenced `_balance_check_cutoff()`, causing `NameError` when editing purchase timestamps.
- **Fix:** Remove the stale helper calls and use `compute_expected_balances()` directly (edit flow passes `exclude_purchase_id`).
- **Validation:** Full pytest suite passes.

```yaml
id: 2026-02-04-03
type: docs
areas: [docs, accounting]
summary: "Clarify 'redeemable' vs 'recognized/earned' SC and when taxable gameplay P/L is recognized."
files_changed:
  - docs/PROJECT_SPEC.md
issue: null
```

Notes:
- Documented the intentional semantics: Sezzions does not try to recognize taxable gains at the moment redeemable SC appears on a site; gains are recognized only when a session is closed.
- Clarified how `discoverable_sc` works and why off-session freebies net out if they are lost during play.

```yaml
id: 2026-02-04-02
type: fix
areas: [services, ui, tests]
summary: "Exclude edited purchase by ID in balance checks (replaces 1-second time epsilon)."
files_changed:
  - services/game_session_service.py
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - tests/integration/test_issue_49_purchase_exclusion.py
issue: "#49"
```

Notes:
- **Problem:** Purchase balance checks used a "1 second before purchase" cutoff to avoid including the edited purchase itself. This broke when two purchases shared the same timestamp.
- **Solution:** Added `exclude_purchase_id` parameter throughout the balance check call chain:
  - `GameSessionService.compute_expected_balances()`: Skip purchase by ID instead of timestamp cutoff
  - `AppFacade.compute_expected_balances()`: Pass through parameter
  - `PurchasesTab._update_balance_check()`: Pass `self.purchase.id` when editing
- **Behavior change:** Balance checks now correctly exclude only the edited purchase, even when multiple purchases share the same timestamp. No more false positives or false negatives due to time-based approximations.
- **Test coverage:** Added regression test suite (`test_issue_49_purchase_exclusion.py`) covering same-timestamp scenarios and edge cases.
- **Removed code:** Deleted obsolete `_balance_check_cutoff()` helper function from `purchases_tab.py`.

```yaml
id: 2026-02-04-01
type: feature
areas: [ui, tests, cleanup]
summary: "Default date filter presets per tab + close SQLite resources in workers/tests."
files_changed:
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/expenses_tab.py
  - ui/tabs/unrealized_tab.py
  - ui/tools_workers.py
  - tests/integration/test_default_date_filter_presets.py
  - tests/integration/test_issue_20_recalc_completion.py
  - tests/integration/test_issue_9_global_refresh.py
  - tests/integration/test_reset_database_flow.py
  - tests/integration/test_settings_dialog_smoke.py
  - tests/integration/test_csv_import_integration.py
  - tests/integration/test_csv_import_user_scoped_methods.py
  - tests/unit/test_database_write_blocking.py
  - tests/unit/test_tools_workers.py
issue: null
```

Notes:
- **UX:** Tabs now start with consistent default date ranges:
  - Purchases / Redemptions / Game Sessions / Expenses: current calendar year
  - Unrealized: all time (2000-01-01 → today)
- **Regression coverage:** Added a headless integration test asserting these tab defaults.
- **Test hygiene:** Ensured worker and test-created SQLite connections/temp files are closed deterministically to avoid `ResourceWarning` noise under newer Python versions.

## 2026-02-03

```yaml
id: 2026-02-03-03
type: fix
areas: [ui]
summary: "Fix spreadsheet selection stats to ignore hidden rows/columns (filtered table selections)."
files_changed:
  - ui/spreadsheet_ux.py
  - tests/unit/test_spreadsheet_ux.py
issue: "#50"
```

Notes:
- **Problem:** After filtering/searching (hidden rows), selection stats could sum values from hidden rows when using range selection.
- **Root cause:** `SpreadsheetUXController._extract_table_selection()` treated any cell inside a selected range as selected, even if its row/column was hidden.
- **Fix:** Exclude hidden rows/columns when extracting selection grids for both QTableWidget and QTableView.
- **Validation:** Added a regression unit test for the hidden-row-in-range case; full pytest suite passes.

```yaml
id: 2026-02-03-02
type: fix
areas: [ui]
summary: "Fix purchase edit balance check to exclude the edited purchase from expected balances."
files_changed:
  - ui/tabs/purchases_tab.py
  - tests/integration/test_purchase_edit_balance_check.py
issue: "#47"
commits: c6b39b0
```

Notes:
- **Problem:** Editing a purchase showed a different (smaller) SC balance mismatch than adding the same purchase.
- **Root cause:** Edit/dialog balance-check computed expected balances at the purchase timestamp; `compute_expected_balances()` includes purchases where `purchase_dt <= cutoff`, so the purchase being edited self-included.
- **Fix:** Standardize purchase balance-check cutoff to “1 second before purchase” (date+time safe, handles midnight rollover) for both edit flow and live dialog checks.
- **Validation:** Added a headless regression test reproducing the Zula example; full pytest suite passes.

```yaml
id: 2026-02-03-01
type: fix
areas: [ui, cleanup]
summary: "Remove dead per-session tax withholding code from EditClosedSessionDialog."
files_changed:
  - ui/tabs/game_sessions_tab.py
commits: 70cfd53
```

Notes:
- **Problem:** `EditClosedSessionDialog.collect_data()` contained orphaned code referencing `self.tax_rate_edit`, a field that never existed in the dialog's `__init__`.
- **Root cause:** Template/copy-paste leftover from the 2026-01-31 tax withholding refactor (commit `153cdf0`), where all per-session tax UI was intentionally removed.
- **Context:** Tax withholding moved entirely to daily-level (not per-session) to fix incorrect totaling. Individual game sessions no longer have tax fields.
- **Previous defensive fix (2026-02-03):** Added `hasattr(self, 'tax_rate_edit')` check to prevent AttributeError crash when editing closed sessions.
- **Proper fix:** Remove entire dead code block (18 lines) including tax variable declarations and return dict fields.
- **Impact:** Cleaner code, removes maintenance burden, prevents future confusion about per-session tax semantics.
- **Validation:** All tests pass (609 total).

## 2026-02-02

```yaml
id: 2026-02-02-07
type: feature
areas: [backup, notifications, settings, ui]
summary: "Issue #35: Automatic backup checkbox persistence + notification settings"
files_changed:
  - ui/tabs/tools_tab.py (unblock signals after loading settings, emit notifications on success/failure)
  - ui/settings.py (add backup notification settings to default config, merge with stored values)
  - ui/settings_dialog.py (add backup notification UI controls)
  - services/notification_rules_service.py (respect user notification preferences, add on_backup_failed)
  - tests/unit/test_backup_notification_settings.py (4 new tests for settings persistence)
  - tests/unit/test_backup_notification_rules.py (6 new tests for notification logic)
branch: fix/issue-35-backup-checkbox-and-notifications
commits: [e7f4d23, 9b8b419, 4352fb5, 3606a40]
issue: "#35"
notes: |
  Fixed automatic backup checkbox not persisting (signals were blocked but never unblocked).
  Added user-configurable backup notification settings:
  - Notify on backup failure (on/off)
  - Notify when backup overdue (on/off)
  - Overdue threshold (days before showing overdue notification)
  
  Default behavior: notify on failure, notify when overdue by 1+ day.
  
  Notification logic now respects user preferences:
  - Overdue notifications only shown if user has enabled them and backup is overdue by threshold
  - Failure notifications only shown if user has enabled them
  - All backup notifications dismissed when backup completes successfully
  
  All 609 tests passing (10 new tests added).
status: complete
```

```yaml
id: 2026-02-02-06
type: fix
areas: [unrealized, repositories, ui]
summary: "Unrealized tab: scope Redeemable SC to current position only"
files_changed:
  - repositories/unrealized_position_repository.py (redeemable_sc scoped to position start)
  - ui/tabs/unrealized_tab.py (clarify column header)
  - tests/integration/test_issue_44_unrealized_live_balances.py (update expectations)
  - docs/PROJECT_SPEC.md (document semantics)
branch: fix/issue-44-unrealized-live-balances
commits: [a5915f5, 31af440]
issue: "#44"
pull_request: "#45"
notes: |
  Fixed Unrealized tab Redeemable SC to only show values from sessions within the current position:
  - Redeemable SC now only shown if last session end >= position start_date (oldest purchase with remaining basis)
  - If session predates position (e.g., fully redeemed old position, then repurchased), shows 0.00
  - Prevents misleading scenario where old session redeemable leaks into new position
  - Column renamed: "Redeemable SC (Last Session)" → "Redeemable SC (Position)"
  - Total SC (Est.) remains the basis for Current Value and Est. Unrealized P/L.
status: complete
```

```yaml
id: 2026-02-02-05
type: fix
areas: [unrealized, repositories, ui]
summary: "Fix Issue #44: Unrealized tab now reflects purchases/redemptions after last session"
files_changed:
  - repositories/unrealized_position_repository.py (incorporate transactions after last session)
  - ui/tabs/unrealized_tab.py (update column headers for clarity)
  - tests/integration/test_issue_44_unrealized_live_balances.py (new comprehensive tests)
  - models/unrealized_position.py (add total_sc and redeemable_sc fields)
branch: fix/issue-44-unrealized-live-balances
commits: [61ba86e, a599408, 2f28164]
issue: "#44"
pull_request: "#45"
notes: |
  Fixed bug where Unrealized tab "Current SC / Current Value / Unrealized P/L" columns
  remained stuck at last session values even after new purchases or redemptions.
  
  Root cause: once any session existed, current_sc was pulled from the most recent
  session's ending balance and ignored all subsequent transactions.
  
  Solution: estimate current balances by taking last session as baseline and applying
  purchases/redemptions that occurred after that session:
  - estimated_total_sc = session_ending_balance + purchases_since - redemptions_since
  - estimated_redeemable_sc = session_ending_redeemable + purchases_since - redemptions_since
  - current_value = estimated_total_sc * sc_rate (uses total, not redeemable)
  - unrealized_pl = current_value - remaining_basis
  
  Semantic clarification (per Issue #44 review discussion):
  - Unrealized P/L represents "money out vs current potential value" (total SC semantics)
  - Use ending_balance (total SC) as baseline when sessions exist, not ending_redeemable
  - Both Total SC and Redeemable SC are shown; Redeemable is informational only
  
  Updated column headers and added columns:
  - "Purchase Basis" → "Remaining Basis"
  - "Current SC" → "Total SC (Est.)" and "Redeemable SC" (two columns)
  - "Unrealized P/L" → "Est. Unrealized P/L"
  
  Added 6 new integration tests covering purchase-after-session, redemption-after-session,
  multiple transactions, no-sessions, last-activity tracking, and basis invariants.
  All 597 tests passing.
status: complete
```

```yaml
id: 2026-02-02-04
type: fix
areas: [tax, recalculation, services]
summary: "Fix Issue #42: Daily Sessions tax withheld missing after CSV import + Recalculate Everything"
files_changed:
  - services/recalculation_service.py (add tax_withholding_service param to __init__)
  - app_facade.py (pass tax_withholding_service to RecalculationService)
  - ui/tools_workers.py (accept settings_dict; create TaxWithholdingService in worker thread)
  - ui/tabs/tools_tab.py (add _get_settings_dict(); pass settings to all RecalculationWorker calls)
branch: fix/issue-42-tax-withholding-after-recalc
commits: [0ed82f2]
issue: "#42"
pull_request: "#43"
notes: |
  Fixed bug where Daily Sessions tab showed Tax Set-Aside = $0.00 after CSV import +
  "Recalculate Everything", particularly for multi-day sessions. Root cause:
  RecalculationService.rebuild_all() had tax recalculation code but it never executed
  because RecalculationService.__init__() didn't accept tax_withholding_service parameter.
  Worker threads creating their own RecalculationService had no tax service wired.
  
  Solution: Wire tax_withholding_service through the full stack:
  1. RecalculationService now accepts and stores tax_withholding_service
  2. AppFacade passes it when creating RecalculationService
  3. RecalculationWorker accepts settings_dict and creates TaxWithholdingService in thread
  4. ToolsTab extracts settings from MainWindow hierarchy for worker threads
  
  Result: Tax withholding now calculates correctly during full rebuild and post-CSV-import
  recalculation. No more manual Settings → Recalculate Tax needed after import.
  All 591 tests passing.
```

```yaml
id: 2026-02-02-03
type: fix
areas: [ui, tables]
summary: "Fix table rows showing wrong/duplicate data after sorting + refresh/search"
files_changed:
  - ui/tabs/redemptions_tab.py (disable sorting during repopulation; reapply header sort after items are set)
  - ui/tabs/purchases_tab.py (same)
  - ui/tabs/game_sessions_tab.py (same)
  - ui/tabs/unrealized_tab.py (same)
  - ui/tabs/expenses_tab.py (same)
  - ui/tabs/sites_tab.py (same)
  - ui/tabs/cards_tab.py (same)
  - ui/tabs/users_tab.py (same)
  - ui/tabs/games_tab.py (same)
  - ui/tabs/game_types_tab.py (same)
  - ui/tabs/redemption_methods_tab.py (same)
  - ui/tabs/redemption_method_types_tab.py (same)
  - tests/unit/test_redemptions_table_sort_repopulate_consistency.py (NEW: regression test)
branch: main
commits: [pending]
issue: "N/A (user-reported UI data display corruption)"
notes: |
  Fixed a QTableWidget gotcha where leaving sorting enabled (via the header sort menu)
  while repopulating rows can cause the widget to reorder rows mid-population.
  That manifests as mixed columns (e.g., wrong Amount for a Site) and apparent duplicates
  that don't exist in the database.

  The fix temporarily disables sorting + UI updates while setting items, then reapplies
  the active header sort once the table is fully populated.
```

```yaml
id: 2026-02-02-02
type: fix
areas: [redemptions, ui, validation]
summary: "Fix Issue #40: Receipt-date-only redemption updates skip unnecessary balance validation"
files_changed:
  - ui/tabs/redemptions_tab.py (skip balance check in dialog when accounting fields unchanged; detect metadata-only changes in tab)
  - tests/integration/test_issue_40_redemption_receipt_date.py (NEW: 5 integration tests)
branch: fix/issue-40-redemption-receipt-date-warning
commits: [b09081c, b660061, f33ebbf, 2a6269f, c5bb89c, fe866bf]
issue: "#40"
pull_request: "#41"
notes: |
  Fixed bug where updating only metadata fields (receipt_date, processed flag, notes) on a
  redemption would trigger full FIFO reprocessing and balance validation, even though no
  accounting changes occurred. This caused false warnings about session balance mismatches
  when purchases existed after the redemption date.
  
  Root cause: Balance validation was happening in TWO places:
  1. In the dialog's _validate_and_accept() method (runs when user clicks OK)
  2. In the tab's _edit_redemption() method (runs after dialog closes)
  
  The dialog validation was running FIRST and blocking the update before we could detect
  metadata-only changes in the tab.
  
  Solution implemented in two layers:
  
  Layer 1 (Dialog - fe866bf): In RedemptionDialog._validate_and_accept(), skip balance
  validation when editing and accounting fields (amount, user, site, date, time) are unchanged.
  This prevents the session balance warning when only metadata fields change.
  
  Layer 2 (Tab - 2a6269f, earlier commits): In RedemptionsTab._edit_redemption(), detect
  metadata-only changes and route to lightweight update_redemption() instead of 
  update_redemption_reprocess(). Normalize redemption_time comparison (None vs "00:00:00").
  
  Tests cover happy path, edge cases with complex purchase timelines, and verify both paths.
```

```yaml
id: 2026-02-02-01
type: fix
areas: [startup, transactions, data-integrity, ui]
summary: "Fix startup crash on corrupted data + add atomic transaction wrapping"
files_changed:
  - ui/main_window.py (wrap tab creation in try/except to force maintenance mode on data errors)
  - ui/tabs/game_sessions_tab.py (remove orphaned tax_rate_edit reference in EndSessionDialog)
  - app_facade.py (wrap create/update/delete purchase and create redemption in transactions)
branch: main
commits: [pending]
issue: "N/A (urgent bug fix)"
notes: |
  Fixed two critical issues:
  1. App crashed at startup before maintenance mode could activate when corrupted data existed
     (e.g., purchases with remaining_amount > amount). Now wraps tab creation in try/except
     to catch ValueError during data loading and gracefully enter maintenance mode.
  2. Database operations could fail mid-operation, leaving partial writes and corrupted data.
     Added transaction wrapping (with self.db.transaction()) to create_purchase, update_purchase,
     delete_purchase, and create_redemption in AppFacade. Operations now roll back entirely on
     failure, ensuring no partial data corruption.
  
  Discovered 3 corrupted purchases in production DB (remaining_amount > amount), likely from
  previous partial operation failure. Transaction wrapping prevents recurrence.
```

## 2026-02-01

```yaml
id: 2026-02-01-04
type: feature
areas: [data-integrity, services, ui, startup]
summary: "Feature Issue #38: Maintenance mode for data integrity violations at startup"
files_changed:
  - services/data_integrity_service.py (NEW: detect violations with quick mode)
  - ui/maintenance_mode_dialog.py (NEW: user-friendly dialog with violation summary)
  - ui/main_window.py (integrity check before tab creation, restricted tab access)
branch: feature/issue-38-maintenance-mode
commits: [5f41b5e, c502e93]
pr: "#38"
issue: "#38"
notes: |
  Prevents app crashes from data integrity violations (e.g., remaining_amount > amount from
  incomplete CSV imports). At startup, runs quick integrity check and shows user-friendly
  dialog if violations detected. Restricts access to Setup tab only (maintenance mode) until
  user completes imports and runs recalculate. Supports 3 check types: invalid remaining_amount,
  negative amounts, orphaned FKs. Fixed refresh_all_tabs() AttributeError in maintenance mode.
  Critical for multi-session CSV import workflows.
```

```yaml
id: 2026-02-01-03
type: fix
areas: [csv-import, services, tests]
summary: "Fix Issue #36: User-scoped FK resolution for redemption methods and cards in CSV imports"
files_changed:
  - services/tools/fk_resolver.py (scope parameter, clear() method, sqlite3.Row keys() fix)
  - services/tools/csv_import_service.py (user_id scope for redemption_methods and cards)
  - tests/integration/test_csv_import_user_scoped_methods.py (new: 4 integration tests)
  - tests/integration/test_csv_export_integration.py (fix: user_id column on cards table)
branch: fix/issue-36-redemption-method-csv-user-scope
commits: [920e1ff, 2934d14]
pr: "#37"
issue: "#36"
notes: |
  CSV imports were failing when multiple users had redemption methods with the same name
  (e.g., 'USAA Checking'). Added scope filtering to FK resolver to match by user_id context.
  Fixed sqlite3.Row 'in' operator bug - must use .keys() for column existence checks.
  All 585 tests passing.
```

```yaml
id: 2026-02-01-02
type: feature
areas: [tax, database, services, ui]
summary: "Complete Issue #29: Tax withholding with date-level calculation, cascade recalc, and Settings UI."
files_changed:
  - repositories/database.py (daily_date_tax table, daily_sessions uses end_date)
  - services/tax_withholding_service.py (date-level with date range filter)
  - services/game_session_service.py (auto-recalc on close/edit, cascade support)
  - services/recalculation_service.py (end_date grouping, tax recalc in rebuild_all)
  - services/daily_sessions_service.py (fetch from daily_date_tax, show at date level)
  - ui/settings_dialog.py (tax settings + recalc dialog launcher)
  - ui/tax_recalc_dialog.py (date range picker with calendar buttons)
  - ui/tabs/daily_sessions_tab.py (edit button, dialog with tax display)
branch: feature/issue-29-tax-withholding-ui
commits: [multiple]
pr: "#34"
issue: "#29"
```

**Architecture: Date-Level Tax Withholding**
- Tax calculated on NET P/L of ALL users for each date (winners netted against losers)
- Storage: `daily_date_tax` table keyed by `session_date` only
- Example: User1: +$342.61, User2: -$205.55 → Net: $137.06 → Tax: $27.41 (20%)
- Display: Tax shown at date level only (not per-user) in Daily Sessions tab

**Database Schema Changes:**
- **New table: `daily_date_tax`**
  - Primary key: `session_date` (date only, not per-user)
  - Columns: `net_daily_pnl`, `tax_withholding_rate_pct`, `tax_withholding_is_custom`, `tax_withholding_amount`, `notes`
  - Notes migrated from `daily_sessions` table (date-level, not user-level)
- **daily_sessions grouping change:**
  - Now groups by `end_date` instead of `session_date` (when session closed, not started)
  - Critical for multi-day sessions: tax counted on close date
- **game_sessions columns removed:**
  - All `tax_withholding_*` columns removed (tax is date-level only)

**Services Layer:**

`TaxWithholdingService`:
- `apply_to_date(session_date, custom_rate_pct)`: Calculate and store tax for ONE date (nets all users)
- `bulk_recalculate(start_date, end_date, overwrite_custom)`: Batch recalc with optional date range
- `_calculate_date_net_pl(session_date)`: Sum ALL users' P/L for date from daily_sessions
- Respects custom rates unless `overwrite_custom=True`

`GameSessionService`:
- Auto-recalc on session close: Syncs daily_sessions + recalcs tax for end_date
- Auto-recalc on session edit: Recalcs tax for affected dates (old + new if date changed)
- `_sync_tax_for_affected_dates()`: NEW - called after cascade recalcs (purchase/redemption edits)
- Ensures tax stays accurate during FIFO rebuilds and session recalculations

`RecalculationService`:
- `rebuild_all()`: Now includes tax recalculation in full rebuild workflow
- Uses `end_date` grouping for daily_sessions (not `session_date`)

`DailySessionsService`:
- `fetch_daily_tax_data()`: Queries `daily_date_tax` table for display
- `group_sessions()`: Shows tax at date level, $0.00 at user level

**UI Changes:**

Settings Dialog (`ui/settings_dialog.py`):
- **Tax Withholding section added:**
  - Enable/disable toggle
  - Default rate percentage (with validation)
  - "Recalculate Tax Withholding" button launches dialog

Tax Recalc Dialog (`ui/tax_recalc_dialog.py`):
- **Date range filter with calendar pickers:**
  - From/To date fields with 📅 calendar buttons
  - Clear buttons for each date
  - Leave empty to recalculate all dates
- **Options:**
  - Overwrite custom rates checkbox
- **Removed:** Site/user filters (incompatible with date-level netting)
- Confirmation dialog shows scope and settings

Daily Sessions Tab (`ui/tabs/daily_sessions_tab.py`):
- **Date-level actions:**
  - "✏️ Edit" button (was "+Add Notes")
  - Edit dialog shows: Net P/L (blue), Tax Amount (red), Tax Rate, Notes
  - Tax fields read-only (use Settings to recalc)
- **User-level actions:**
  - Removed edit button (no user-level tax data)
- **Display:**
  - Tax withholding shown at date level only
  - User rows show $0.00 for tax (not calculated per-user)

**Tax Recalculation Triggers:**

1. **Session closed:** Scoped to end_date
2. **Session edited (already closed):** Scoped to affected date(s)
3. **Purchase/redemption edited:** Cascade recalc triggers tax update for all affected dates
4. **Settings → Recalculate Tax Withholding:** Optional date range filter
5. **Tools → Recalculate Everything:** Full rebuild including tax (all dates)

**Migration Path:**
- Old `game_sessions.tax_withholding_*` columns removed
- Old `daily_sessions.notes` migrated to `daily_date_tax.notes`
- Tax recalculated on first "Recalculate Everything" after upgrade
- No data loss: old tax estimates discarded (date-level netting more accurate)

**Testing:**
- All 580 tests passing
- Tax calculation scenarios validated (net-first, not per-user-first)
- Cascade scenarios covered (purchase/redemption edits trigger tax updates)
- Date range filtering tested

**Benefits:**
- **Accurate:** Tax calculated on net P/L (losses offset gains)
- **Automatic:** Updates on session close, edit, and cascade recalcs
- **Flexible:** Date range filtering for targeted recalculation
- **Transparent:** Clear display in Daily Sessions tab
- **Compliant:** Settings UI for rate configuration and bulk operations

```yaml
id: 2026-02-01-01
type: fix
areas: [repositories, tests, ui]
summary: "Complete tax withholding test fixes and repository cleanup for daily-only semantics."
files_changed:
  - repositories/game_session_repository.py (remove tax column references from INSERT/UPDATE)
  - repositories/database.py (add tax columns to daily_sessions CREATE TABLE)
  - tests/unit/test_tax_withholding_service.py (rewrite for daily_sessions)
  - ui/tax_recalc_dialog.py (update messaging to 'daily sessions')
branch: feature/issue-29-tax-withholding-ui
commits: 644609d
pr: "#34"
issue: "#29"
```

Notes:
- **Problem:** Tests failing after tax refactor; game_session_repository still trying to INSERT/UPDATE removed columns
- **game_session_repository fixes:**
  - Removed tax_withholding_* columns from INSERT statement (25 params → 22 params)
  - Removed tax_withholding_* columns from UPDATE statement
  - Set tax fields to None/False in _row_to_model (columns no longer exist in DB)
- **database.py fix:**
  - Added tax columns to daily_sessions CREATE TABLE statement
  - Previously only added via migration (for existing DBs)
  - Fresh test databases now include tax columns by default
- **test_tax_withholding_service.py rewrite:**
  - Changed from game_sessions to daily_sessions table
  - Updated _insert_daily_session helper (no site_id, keyed by date+user)
  - Fixed queries to use (session_date, user_id) primary key instead of id
  - Fixed type assertions: 20.0 (float) not "20.00" (string)
- **tax_recalc_dialog.py:**
  - Updated UI messaging: "daily sessions" instead of "closed sessions"
  - Updated tooltips and confirmation dialogs
- **Result:** All 580 tests passing
- **Deferred:** Edit Daily Session dialog with per-day tax override (users can use bulk recalc tool for now)

## 2026-01-31

```yaml
id: 2026-01-31-17
type: refactor
areas: [database, services, ui, tax]
summary: "Complete tax withholding refactor: move from game sessions to daily sessions only."
files_changed:
  - repositories/database.py (add tax columns to daily_sessions, remove from game_sessions)
  - services/tax_withholding_service.py (rewrite for daily-only semantics)
  - services/daily_sessions_service.py (add fetch_daily_tax_data, update group_sessions)
  - ui/tabs/game_sessions_tab.py (remove tax UI from all dialogs)
  - ui/tabs/daily_sessions_tab.py (fetch and display daily tax data)
branch: feature/issue-29-tax-withholding-ui
commits: 153cdf0, 22c3925, 3a0220a
pr: "#34"
issue: "#29"
```

Notes:
- **Problem:** Tax withholding was stored per-game-session but taxable events are daily rollups, causing incorrect totaling
- **Solution:** Complete architectural change to daily-only tax withholding
- **Database changes:**
  - Added `tax_withholding_rate_pct`, `tax_withholding_is_custom`, `tax_withholding_amount` to `daily_sessions` table
  - Removed all tax columns from `game_sessions` CREATE TABLE statement
  - Migration tested: columns added successfully to existing databases
- **Service layer changes:**
  - `TaxWithholdingService`: Removed `apply_to_session_model()`, added `apply_to_daily_session(session_date, user_id, net_daily_pl, custom_rate_pct)`
  - `TaxWithholdingService.bulk_recalculate()`: Now targets `daily_sessions` table, respects custom rates
  - `DailySessionsService.fetch_daily_tax_data()`: NEW - queries daily_sessions for tax data by (date, user)
  - `DailySessionsService.group_sessions()`: Updated to accept daily_tax_data parameter, calculate tax at user+date level
- **UI changes:**
  - Removed ~270 lines of tax UI from EditClosedSessionDialog, EndSessionDialog, ViewSessionDialog
  - Daily Sessions tab: Fetches daily tax data, displays at user+date level only
  - Individual sessions and sites show dash (—) in tax column (tax not applicable at those levels)
- **Semantics:** Tax withholding now calculated from daily net P/L: `max(0, net_daily_pl) × (rate_pct/100)` for each (date, user) pair
- **Validation:** App starts without errors, data flow tested
- **Remaining work:** Add Edit Daily Session dialog with tax override, update bulk recalc dialog UI, fix/update tests

```yaml
id: 2026-01-31-16
type: fix
areas: [services, ui, tax]
summary: "Include tax withholding data in daily sessions query for proper display."
files_changed:
  - services/daily_sessions_service.py (add tax fields to query and session dictionary)
```

Notes:
- **Issue:** Tax withholding amounts showing as blank/not displaying in Daily Sessions tab
- **Root cause:** Query in `fetch_sessions()` didn't include tax withholding fields from database
- **Fix:** Added tax_withholding_amount, tax_withholding_rate_pct, and tax_withholding_is_custom to SELECT
- **Result:** Tax Set-Aside column now displays correct amounts for all sessions
- **EditClosedSessionDialog:** Already loads and displays tax values correctly - tax fields show custom rates and computed amounts when editing closed sessions
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-15
type: fix
areas: [ui, tax]
summary: "Fix tax column not appearing at startup and site/user dropdowns not populating."
files_changed:
  - ui/tabs/daily_sessions_tab.py (add showEvent to rebuild columns when tab shown)
  - ui/tax_recalc_dialog.py (fix facade method calls for site/user loading)
```

Notes:
- **Issue 1:** Tax Set-Aside column now appears correctly at startup when enabled
  - Added `showEvent()` override to DailySessionsTab
  - Rebuilds columns when tab is first shown to ensure settings are loaded
  - Previously columns were built during `__init__` before settings were fully initialized
  - Now column structure is refreshed when tab becomes visible
- **Issue 2:** Site/User dropdowns now populate correctly in TaxRecalcDialog
  - Fixed method calls from `facade.site_service.get_all_sites()` to `facade.get_all_sites()`
  - Fixed method calls from `facade.user_service.get_all_users()` to `facade.get_all_users()`
  - Dropdowns now show all available sites and users with placeholder text
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-14
type: fix
areas: [ui, tax]
summary: "Reorder tax fields in EndSessionDialog to match EditClosedSessionDialog layout."
files_changed:
  - ui/tabs/game_sessions_tab.py (move tax fields after Game Type/Game in EndSessionDialog)
```

Notes:
- **Purpose:** Consistent field ordering across End and Edit dialogs
- **Change:** Tax withholding fields now positioned after Game Type/Game in EndSessionDialog
- **Previous order:** Net P/L → Tax fields → Game Type/Game → RTP
- **New order:** Net P/L → Game Type/Game → Tax fields → RTP
- **Matches:** EditClosedSessionDialog layout (Session Details section)
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-13
type: fix
areas: [ui, tax]
summary: "Fix tax withholding UI issues: styling, field visibility, layout reordering."
files_changed:
  - ui/tabs/game_sessions_tab.py (fix ViewSessionDialog styling, add field visibility logic, reorder fields in EditClosedSessionDialog)
```

Notes:
- **Issue 1:** ViewSessionDialog "Tax Set-Aside" label now matches "Net P/L:" styling (font-weight: bold)
- **Issue 2:** Fixed AttributeError in EditClosedSessionDialog - tax fields already exist and are properly initialized
- **Issue 3:** Tax withholding fields now hidden when feature is disabled
  - Added visibility logic to both EndSessionDialog and EditClosedSessionDialog
  - Fields check `facade.tax_withholding_service.get_config().enabled` at init
  - Labels and inputs hidden via `setVisible(False)` when disabled
- **Issue 4:** Reordered fields in EditClosedSessionDialog to improve UX
  - Moved tax withholding fields below Game Type/Game in Session Details section
  - Moved Wager and RTP to Balance Details section (after Balance Check)
  - Dialog height already increased to 700px to accommodate fields
  - Tax fields appear after Game Type/Game as requested
- **User Experience:** When tax withholding is disabled in Settings, tax input fields don't appear in End/Edit dialogs
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-12
type: feature
areas: [ui, tax]
summary: "Add dynamic column refresh for Daily Sessions when tax settings change."
files_changed:
  - ui/tabs/daily_sessions_tab.py (add rebuild_columns method for dynamic column updates)
  - ui/main_window.py (call rebuild_columns when settings dialog closes)
```

Notes:
- **Purpose:** Tax Set-Aside column now dynamically shows/hides when tax withholding feature is enabled/disabled in Settings
- **Implementation:**
  - Added `rebuild_columns()` method to DailySessionsTab that:
    - Rebuilds the columns list based on current tax withholding feature state
    - Updates tree widget column count and headers
    - Refreshes data to re-render with new columns
  - Updated MainWindow._show_settings_dialog() to call `rebuild_columns()` after settings are saved
  - Column structure is now rebuilt immediately when settings change (no app restart required)
- **User Experience:** Toggle tax withholding checkbox in Settings → Save → Daily Sessions column appears/disappears instantly
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-11
type: fix
areas: [ui, tax]
summary: "Fix tax recalc dialog dropdowns and add EditClosedSessionDialog tax fields."
files_changed:
  - ui/tax_recalc_dialog.py (use placeholder text for Site/User combo boxes, handle empty selections as 'all')
  - ui/tabs/game_sessions_tab.py (add tax withholding fields to EditClosedSessionDialog with real-time calculation)
```

Notes:
- **Issue 1:** Site/User dropdowns in tax recalc dialog now populate correctly
  - Removed "All Sites" and "All Users" as items in combo boxes
  - Made them placeholder text only (displayed when combo box is empty)
  - Empty/blank selection now treated as "all" (null filter)
  - `_on_recalculate()` handles empty `currentText()` by checking item data by text
- **Issue 2:** EditClosedSessionDialog now has full tax withholding override support
  - Added `tax_rate_edit` (optional % override input) and `tax_amount_display` (computed amount display)
  - Added `_update_tax_withholding_display()` method for real-time calculation as user edits balances
  - Connected all relevant fields (start_total, end_total, start_redeem, end_redeem) to trigger tax updates
  - Modified `_load_session()` to load existing custom rate if `tax_withholding_is_custom` is true
  - Modified `collect_data()` to persist custom rate and is_custom flag
  - UI layout matches EndSessionDialog pattern
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-10
type: fix
areas: [ui, tax]
summary: "Fix tax withholding UI issues (column visibility, combo boxes, custom override location)."
files_changed:
  - ui/tabs/daily_sessions_tab.py (conditionally show Tax Set-Aside column only when feature enabled)
  - ui/tax_recalc_dialog.py (make Site/User dropdowns editable/searchable combo boxes)
```

Notes:
- **Issue 1:** Tax Set-Aside column now hidden when tax withholding is disabled in Settings
  - Column list built dynamically based on `facade.tax_withholding_service.get_config().enabled`
  - All column index references updated to handle dynamic column presence
  - Column width adjustments handled automatically
- **Issue 2:** TaxRecalcDialog Site/User dropdowns converted to editable/searchable combo boxes
  - Added `setEditable(True)` and `setInsertPolicy(NoInsert)` for type-ahead autocomplete
  - Matches pattern used in AddPurchaseDialog
- **Issue 3:** Custom override field location clarified
  - Field exists in EndSessionDialog at line 3734: "Tax Withholding % (optional)"
  - Positioned after Net P/L, before Game Type/RTP
  - User can enter custom rate or leave blank for default
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-09
type: feature
areas: [ui, tax]
summary: "Complete Issue #29 deferred UI items: per-session override + Daily Sessions column."
files_changed:
  - ui/tabs/game_sessions_tab.py (add withholding fields to EndSessionDialog + ViewSessionDialog)
  - ui/tabs/daily_sessions_tab.py (add Tax Set-Aside column to Daily Sessions tab)
  - services/daily_sessions_service.py (aggregate tax_withholding_amount at date/user/site levels)
```

Notes:
- **Purpose:** Complete Issue #29 by adding the "deferred" UI polish items (previously noted as non-blocking).
- **Changes:**
  - **EndSessionDialog:**
    - Added "Tax Withholding % (optional)" input field (QLineEdit, user can override default rate).
    - Added "Tax Withholding (est.)" display (QLabel ValueChip, shows computed amount in real-time).
    - Fields positioned after Net P/L, before Game Type/RTP.
    - Real-time calculation: `_update_tax_withholding_display(net_pl)` updates amount as user types.
    - `collect_data()` now captures custom rate and sets `tax_withholding_is_custom` flag.
  - **ViewSessionDialog:**
    - Added read-only "Tax Set-Aside" row in Balances/Outcomes table (shows rate used, amount, and "(custom)" suffix if applicable).
    - Only displays if feature enabled and session is closed.
  - **Daily Sessions tab:**
    - Added "Tax Set-Aside" column (index 6, between Net P/L and Details).
    - Shows aggregated withholding amounts at date/user/site/session levels.
    - Column sorting and filtering supported.
  - **Service layer:**
    - `daily_sessions_service.group_sessions()` now computes `tax_withholding` aggregates at user/site/date levels.
- **Workflow:**
  - User ends session → sees optional override rate field → can customize withholding for this session or leave blank for default.
  - Viewing closed sessions → see tax withholding details in dialog and Daily Sessions summary.
- **Tests:** All 580 tests passing (no new tests; UI-only additions; backend logic already tested).
- **PR:** #34 (Issue #29 complete — Settings UI + deferred UI items)

```yaml
id: 2026-01-31-08
type: feature
areas: [ui, settings, tax]
summary: "Complete tax withholding estimates Settings UI + bulk recalc (Issue #29, Part 2)."
files_changed:
  - ui/settings_dialog.py (replace placeholder with enable toggle, default rate spinner, recalc button)
  - ui/tax_recalc_dialog.py (new, bulk recalculation UI with site/user filters + overwrite-custom option)
  - ui/main_window.py (wire settings to tax_withholding_service on startup)
  - docs/PROJECT_SPEC.md (update § 6.5 tax withholding to reflect completed state)
```

Notes:
- **Purpose:** Provide user-facing controls for tax withholding estimates (Issue #29 Part 2).
- **Architecture:**
  - Settings → Taxes section: enable/disable toggle, default rate (%) spinner (0-100, 0.1 step), "Recalculate Withholding…" button.
  - TaxRecalcDialog: filters by site/user (dropdowns), "Overwrite custom rates" checkbox, confirmation prompt with scope summary.
  - MainWindow init: wires `self.settings` to `facade.tax_withholding_service.settings` so service can read config.
- **Workflow:**
  - Enable withholding estimates → enter default rate → close sessions (withholding computed automatically).
  - Bulk recalc: select scope/filters → confirm → updates historical closed sessions atomically.
- **Deferred to follow-up:**
  - Per-session override UI (field in session editor dialogs for custom withholding %).
  - Daily Sessions column/aggregates ("Tax set-aside (est.)" display).
  - Both deferred items are non-blocking; backend is ready (values stored/computed); just UI display left.
- **Tests:** All 580 tests passing (no new tests; backend tested in Part 1 PR #32).
- **PR:** TBD (Issue #29, Part 2 — enables closing Issue #29)

```yaml
id: 2026-01-31-05
type: feature
areas: [notifications, ui, services]
summary: "Add notification system with bell widget and periodic evaluation (Issue #28)."
files_changed:
  - models/notification.py (new, Notification model with severity/state)
  - services/notification_service.py (new, CRUD + state management)
  - repositories/notification_repository.py (new, JSON persistence to settings.json)
  - services/notification_rules_service.py (new, backup + redemption rules)
  - ui/notification_widgets.py (new, bell + notification center + item widgets)
  - ui/main_window.py (integrate bell, periodic QTimer)
  - app_facade.py (wire notification services)
  - tests/test_notification_service.py (new, 19 unit tests)
  - docs/PROJECT_SPEC.md (add notification system section 6.4)
```

Notes:
- **Purpose:** Passive, persistent notifications for backup reminders and redemption pending-receipt tracking. No modal popups.
- **Architecture:**
  - Notification model: severity (INFO/WARNING/ERROR), state (read/dismissed/snoozed/deleted), composite key de-duplication (type + subject_id).
  - NotificationService: CRUD, state transitions (mark_read/unread, dismiss, snooze, delete), bulk operations.
  - NotificationRepository: JSON persistence to settings.json (v1; future split to DB-backed for scalability).
  - NotificationRulesService: evaluates backup rules (directory missing, backup due/overdue) and redemption rules (pending receipt > threshold).
- **UI:**
  - Notification bell: lightweight overlay button (no pill background) pinned to the main content inset; shows a red badge when unread > 0.
  - NotificationCenterDialog: grouped sections (Unread / Read / Snoozed) with collapsible headers.
  - Per-item actions: Open (when available), Snooze, Dismiss, Delete, Mark Read, Mark Unread.
  - Badge count updates immediately after dialog actions.
  - macOS theme fix: dialog/scroll viewport forced to paint theme "surface" to avoid dark palette bleed.
  - Periodic evaluation: startup + hourly QTimer.
- **Rules:**
  - Backup: Creates notifications when automatic backup enabled but directory missing, or last backup > frequency threshold.
  - Redemption pending-receipt: Queries redemptions where `receipt_date IS NULL` and older than the configured threshold days; one notification per redemption.
  - Auto-dismiss when conditions resolve (backup completed, redemption received).
- **Tests:** 19 unit tests covering CRUD, de-duplication, state transitions, unread count, bulk operations. All passing.
- **Future:** Integration tests for rule evaluators, headless UI smoke test, split persistence (DB vs settings).
- **Issue:** #28

```yaml
id: 2026-01-31-06
type: feature
areas: [accounting, services, models, repositories]
summary: "Add tax withholding estimates foundation (Issue #29, Part 1/2)."
files_changed:
  - models/game_session.py (add tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount)
  - repositories/database.py (add game_sessions columns + migration)
  - repositories/game_session_repository.py (persist withholding fields)
  - services/tax_withholding_service.py (new, config + compute + bulk recalc)
  - services/game_session_service.py (wire withholding into closed-session recalc)
  - app_facade.py (construct TaxWithholdingService, pass to GameSessionService)
  - tests/unit/test_tax_withholding_service.py (new, 6 unit tests including rollback)
```

Notes:
- **Purpose:** Store and compute per-session tax withholding estimates for informational tax planning (not legal advice).
- **Architecture (Part 1 — backend foundation):**
  - GameSession model: adds `tax_withholding_rate_pct` (Decimal), `tax_withholding_is_custom` (bool), `tax_withholding_amount` (Decimal).
  - DB schema + migration: new columns in `game_sessions`; ALTER TABLE path for existing DBs.
  - TaxWithholdingService: computes `max(0, net_taxable_pl) * (rate / 100)` with Decimal rounding; provides config parsing, apply-to-session, and bulk recalculation.
  - Bulk recalc: transactional, atomic; updates only withholding columns; skips custom-rate sessions unless `overwrite_custom=True`.
  - GameSessionService: optionally calls `apply_to_session_model()` after computing `net_taxable_pl` for closed sessions.
- **Config (placeholder):** Settings keys planned: `tax_withholding_enabled` (bool), `tax_withholding_default_rate_pct` (float).
- **Tests:** 6 unit tests (compute positive/zero/negative, bulk recalc, skip custom, rollback atomicity). All 579 tests passing.
- **Part 2 (pending):** UI + wiring (Settings controls, per-session override in session editor, Daily Sessions column/aggregates, bulk recalc dialog).
- **PR:** #32 (Issue #29, Part 1 — does not close Issue #29)

```yaml
id: 2026-01-31-07
type: feature
areas: [ui, settings]
summary: "Add Settings entry point: gear icon + dialog shell + notification badge (Issue #31)."
files_changed:
  - ui/settings_dialog.py (new, Settings dialog with Notifications + Taxes sections)
  - ui/notification_widgets.py (notification bell with widget-based pill badge)
  - ui/main_window.py (add gear button overlay + bell overlay, wire Settings dialog, badge z-order management)
  - tests/integration/test_settings_dialog_smoke.py (new, headless UI smoke test)
  - requirements.txt (add pytest-qt)
```

Notes:
- **Purpose:** Provide a first-class Settings entry point for notifications configuration and future cross-cutting features (like Issue #29 tax withholding estimates).
- **Architecture:**
  - SettingsDialog: left-nav + stacked content sections (Notifications, Taxes placeholder).
  - Notifications section: `redemption_pending_receipt_threshold_days` spinner (0..365 days).
  - Taxes section: placeholder message for Issue #29 (no functionality yet).
  - Settings persistence: uses existing `ui/settings.py` → `settings.json`.
- **UI:**
  - Settings gear button: 32x32 pill overlay pinned to top-right of main content inset, matches bell styling.
  - Notification bell: includes scalable badge overlay (QLabel) with pill styling; counts cap at "10+"; non-bold, centered text; left edge anchored to bell's horizontal center for stable growth to the right; badge raised above bell/gear via explicit z-order management in MainWindow.
  - Badge styling iterations: increased vertical padding (+1px); decreased font size (-1px); rounded pill shape.
  - Testing override: `SEZZIONS_FORCE_BADGE_TEXT` environment variable to force badge text for UI verification.
- **Tests:** headless UI smoke test passes; full suite (580 tests) passing.
- **PR:** #33
- **Issue:** #31
  - Gear icon (⚙️): transparent button overlay, pinned to the left of the notification bell.
  - Positioning: same top margin as bell; dynamically placed via `_position_notification_bell()`.
  - Settings dialog: modal, ESC to close, Cancel/Save buttons.
  - Saving: persists immediately to `settings.json`; notification rules re-evaluated after close.
- **Tests:** 1 headless UI smoke test (MainWindow → gear exists → dialog can open/close). All 580 tests passing.
- **Future:** Issue #29 will add tax withholding controls to the Taxes section.
- **Issue:** #31

```yaml
id: 2026-01-31-04
type: bug-fix
areas: [ui, ux]
summary: "Add Clear button to notes dialogs; fix Expenses tab selection/actions (Issue #26)."
files_changed:
  - ui/tabs/realized_tab.py (add Clear button to RealizedDateNotesDialog)
  - ui/tabs/unrealized_tab.py (add Clear button to UnrealizedNotesDialog)
  - ui/tabs/daily_sessions_tab.py (add Clear button to DailySessionNotesDialog)
  - ui/tabs/expenses_tab.py (change SelectItems to SelectRows)
```

Notes:
- **Problem 1:** Notes dialogs for Daily Sessions, Unrealized, and Realized tabs lacked a Clear button (only Cancel/Save).
- **Problem 2:** Expenses tab selection didn't reveal View/Edit/Delete buttons; double-click had no effect.
- **Root Cause:** Expenses table used `SelectItems` behavior, so `selectedRows()` was always empty.
- **Solution:**
  - Added `🧹 Clear` button to all three notes dialogs, positioned between Cancel and Save.
  - Changed Expenses table to `SelectRows` selection behavior.
- **Result:** Clear button provides one-click note reset; Expenses tab now shows action buttons and supports double-click to view.
- **Tests:** All 554 tests passing.
- **PR:** #27 (Issue #26)

```yaml
id: 2026-01-31-03
type: bug-fix
areas: [architecture, layering, services]
summary: "Fix UI→DB layering violations (Issue #23)."
files_changed:
  - services/realized_notes_service.py (new)
  - services/redemption_service.py (add get_deletion_impact method)
  - services/game_session_service.py (add get_deletion_impact method)
  - app_facade.py (wire up realized_notes_service)
  - ui/tabs/realized_tab.py (use service instead of direct SQL)
  - ui/tabs/redemptions_tab.py (use service instead of cursor access)
  - ui/tabs/game_sessions_tab.py (use service instead of cursor access)
  - tests/unit/test_realized_notes_service.py (new, 9 tests)
```

Notes:
- **Problem:** UI tabs directly executed SQL or accessed repository cursors (layering violation)
- **Evidence:**
  - `realized_tab.py`: Direct `self.db.execute()` for daily notes CRUD
  - `redemptions_tab.py`: Direct cursor access via `self.facade.redemption_repo.db._connection.cursor()`
  - `game_sessions_tab.py`: Direct cursor access for deletion impact checks
- **Solution:**
  - Created `RealizedNotesService` for daily notes CRUD operations
  - Added `get_deletion_impact(id)` methods to `RedemptionService` and `GameSessionService`
  - Updated UI tabs to call service methods via `AppFacade`
  - All direct SQL/cursor access removed from UI layer
- **Tests:** Added 9 unit tests for RealizedNotesService (554 total tests passing)
- **Architecture:** Enforces UI → Service → Repository layering
- **PR:** #25 (Issue #23)

```yaml
id: 2026-01-31-02
type: decision
areas: [architecture, rollback]
summary: "QTableView migration rejected - reverted PR #24 (Issue #15 closed as won't do)."
files_changed:
  - docs/adr/0002-qtableview-migration-rejected.md (new)
  - ui/tabs/sites_tab.py (reverted to QTableWidget)
  - tests/ui/test_sites_tab_qtableview.py (removed)
  - docs/status/CHANGELOG.md
```

Notes:
- **Decision:** Do NOT migrate tabs from QTableWidget to QTableView
- **Rationale:**
  - Critical functionality loss: TableHeaderFilter (per-column filtering UI) incompatible with QTableView
  - Weak benefits without inline editing (which was removed from scope)
  - Trade-off: Lost user-facing features for minimal architectural improvement
  - This is architecture for architecture's sake without concrete need
- **Actions:**
  - Closed PR #24 without merge
  - Closed Issue #15 as "won't do"
  - Reverted Sites tab to QTableWidget
  - Infrastructure code (BaseTableModel, SpreadsheetUX QTableView support) remains but unused
- **ADR:** See `docs/adr/0002-qtableview-migration-rejected.md` for full rationale
- **If Revisited:** Only if we implement inline editing OR solve column filtering UI for QTableView

```yaml
id: 2026-01-31-01
type: feature
areas: [ui, architecture, tests]
summary: "Add spreadsheet UX with cell selection, copy, and statistics (Issue #14, Phase 1)."
files_changed:
  - ui/spreadsheet_ux.py (new, 325 lines)
  - ui/spreadsheet_stats_bar.py (new, 95 lines)
  - tests/unit/ui/test_spreadsheet_ux.py (new, 32 tests)
  - tests/unit/ui/widgets/test_spreadsheet_stats_bar.py (new, 7 tests)
  - ui/tabs/*.py (14 tabs integrated)
  - docs/status/CHANGELOG.md
  - docs/PROJECT_SPEC.md
```

Notes:
- **Spreadsheet UX Module** (`ui/spreadsheet_ux.py`):
  - Excel-like cell-level selection with multi-cell highlights
  - Copy selection to clipboard as TSV (Tab-Separated Values) via Cmd+C
  - Context menu: Copy, Copy With Headers
  - Selection statistics: Count, Numeric Count, Sum, Avg, Min, Max
  - Currency parsing: handles `$1,234.56`, `(123.45)`, `100%`, `N/A`, empty strings
  - Widget-agnostic: supports QTableWidget (11 tabs) and QTreeWidget (2 tabs)
  - Phase 1: Read-only features (no inline editing or paste yet)

- **Stats Bar Widget** (`ui/spreadsheet_stats_bar.py`):
  - Horizontal layout showing 6 statistics for current selection
  - Format-neutral: works with currency, percentages, raw numbers
  - Updates dynamically on selection change

- **QTreeWidget Support** (Daily Sessions, Realized):
  - Qt limitation: QTreeWidget doesn't support true cell-level selection
  - Workaround: Detect single-cell clicks using `currentColumn()` and `currentItem()`
  - Single-cell selection → extracts only clicked column value for stats
  - Multi-selection → falls back to full row extraction (all columns)
  - Added `setSelectionBehavior(SelectItems)` for visual consistency

- **14 Tabs Integrated**:
  - **QTableWidget (11 tabs)**: Purchases, Redemptions, Games, Game Types, Sites, Users, Cards, Redemption Methods, Redemption Method Types, Unrealized, Game Sessions, Expenses
  - **QTreeWidget (2 tabs)**: Daily Sessions, Realized
  - All tabs: Cell selection, Cmd+C copy, context menu, stats bar integration
  - Selection logic: `_get_selected_row_numbers()` for action button visibility
  - Stats updates: `_on_selection_changed()` handlers update stats bar on selection

- **Tests**: 39 new tests (32 core + 7 widget)
  - Core: Currency parsing, TSV formatting, grid extraction, stats computation
  - Widget: Stats bar display, format handling, empty/numeric/mixed scenarios
  - All 545 tests passing

- **Implementation Fixes** (this session):
  - Fixed runtime errors: Moved methods from dialog classes to main tab classes
  - Fixed clipboard operations: Extract grid first, then pass to clipboard (not widget)
  - Fixed tree cell detection: `currentColumn()` approach for single-cell statistics
  - Fixed selection handlers: Added stats bar updates to all tabs
  - Fixed corrupted method definitions: Restored missing `def` statements (4 tabs)
  - Fixed old method references: Replaced `_get_fully_selected_rows()` with `_get_selected_row_numbers()`

- **Future Work** (Phase 2/3, separate issues):
  - Inline cell editing
  - Paste from clipboard
  - Advanced selection (Shift+Click, range selection)
  - Export with selection preserved

---

## 2026-01-30

```yaml
id: 2026-01-30-03
type: bugfix
areas: [ui, services, tests]
summary: "Fix recalculation crash and TableHeaderFilter AttributeError (Issue #20, PR #21)."
files_changed:
  - services/recalculation_service.py
  - ui/tools_workers.py
  - ui/tabs/tools_tab.py
  - ui/table_header_filters.py
  - tests/integration/test_issue_20_recalc_completion.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Recalculation Crash Fix**: `AttributeError: 'RebuildResult' object has no attribute 'operation'`
  - Added optional `operation: Optional[str]` field to `RebuildResult` dataclass
  - `RecalculationWorker.run()` uses `dataclasses.replace(result, operation=self.operation)` to pass operation through
  - `ToolsTab._on_recalculation_finished()` uses `getattr(result, 'operation', 'all')` for backward compatibility
  - Crash prevented `emit_data_changed()` from completing, masking Games tab RTP auto-refresh
- **Games Tab RTP Auto-Refresh**: Now works via Issue #9 event system
  - Recalculation completion → emits `DataChangeEvent` → MainWindow → setup_tab → games_tab.refresh_data()
  - Fixing crash allowed event emission to complete, automatically fixing RTP refresh
- **TableHeaderFilter AttributeError**: Fixed Qt cleanup race condition
  - Added `hasattr(self, 'table')` guard before accessing `self.table` in `eventFilter()`
  - Prevents AttributeError during widget destruction (common in tests)
- **Tests**: 10 new tests in `test_issue_20_recalc_completion.py`
  - RebuildResult operation field contract (3 tests)
  - RecalculationWorker operation propagation (2 tests)
  - ToolsTab completion handling with/without operation field (3 tests)
  - Games tab refresh contract and event integration (2 tests)
  - All 506 tests passing cleanly (no AttributeError warnings)

```yaml
id: 2026-01-30-01
type: feature
areas: [architecture, ui, services, tests]
summary: "Unified global refresh system with event-driven debouncing and maintenance mode (Issue #9, PR #17)."
files_changed:
  - app_facade.py
  - services/data_change_event.py
  - ui/main_window.py
  - ui/tabs/daily_sessions_tab.py
  - ui/tabs/realized_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_issue_9_global_refresh.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Event-Driven Architecture**: Introduced `DataChangeEvent` with operation types and affected tables
  - Single notification channel via `AppFacade.emit_data_changed()`
  - All tabs register listeners via `AppFacade.add_data_change_listener()`
  - Replaces fragmented direct refresh calls and ad-hoc signals
- **Debounced Refresh**: MainWindow debounces rapid events (250ms window) to prevent refresh storms
  - Uses QTimer single-shot mechanism
  - Multiple rapid events (e.g., CSV imports) trigger only one UI refresh
  - Improves UX during bulk operations
- **Standardized Tab Contract**: All tabs now expose `refresh_data()` method
  - DailySessionsTab, RealizedTab, GameSessionsTab, ToolsTab
  - Consistent refresh API across the application
  - MainWindow calls `refresh_data()` on all tabs when events fire
- **Maintenance Mode**: AppFacade coordinates write-blocking during destructive operations
  - `enter_maintenance_mode()` / `exit_maintenance_mode()` wrap reset/restore flows
  - Prevents mid-operation writes that could corrupt state
  - Safe coordination of long-running database operations
- **Tools Integration**: Tools operations (CSV import, recalc, restore, reset) emit unified events
  - Replaced `ToolsTab.data_changed` signal with facade events
  - Consistent event emission across all data-modifying operations
- **Testing**: New integration test suite `test_issue_9_global_refresh.py` with 11 tests:
  - Event propagation and listener registration
  - Maintenance mode write blocking
  - Tab refresh contract verification
  - All 496 tests pass

Architecture Benefits:
- Single source of truth for data change notifications
- Decoupled components (tabs don't directly call each other)
- Predictable refresh behavior (debounced, ordered)
- Safe coordination of destructive operations
- Scalable event-driven design

Refs: Issue #9, PR #17

```yaml
id: 2026-01-30-02
type: fix
areas: [ui, tools, tests]
summary: "ResetDialog button gating and API regressions fixed; comprehensive test coverage added (Issue #18, PR #19)."
files_changed:
  - ui/tools_dialogs.py
  - tests/unit/test_reset_dialog.py
  - tests/integration/test_reset_database_flow.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Bug Context**: ResetDialog had regressed during RestoreDialog sizing refactors (copy/paste bleed)
  - Missing `should_preserve_setup()` API method
  - Broken button gating logic (referenced restore-only `_is_updating_size` attribute)
  - Reset workflow was unusable (button never enabled, crashes on dialog accept)
- **Fixes Applied** (in PR #17, then locked by tests in PR #19):
  - Restored `ResetDialog._update_button_state()` to only check checkbox + "DELETE" text
  - Restored `ResetDialog.should_preserve_setup()` API for Tools tab reset flow
  - Removed restore-dialog sizing logic from ResetDialog
- **Test Coverage Added** (PR #19):
  - **Unit tests** (`test_reset_dialog.py`): 17 tests
    - Button gating: checkbox + "DELETE" confirmation (case-insensitive, whitespace-tolerant)
    - API contract: `should_preserve_setup()` reflects checkbox state
    - Invariants: no restore-only attributes in ResetDialog
  - **Integration smoke tests** (`test_reset_database_flow.py`): 8 tests
    - Headless dialog construction and API validation
    - Tools tab can construct dialog and read options without exceptions
    - Reset flow invariants verified
- **All 496 tests pass** (100% pass rate)
- **Regression Prevention**: Tests explicitly guard against:
  - Missing `should_preserve_setup()` (AttributeError from Tools tab)
  - Missing `_is_updating_size` (AttributeError from button update)
  - Copy/paste bleed from other dialogs

Refs: Issue #18, PR #19

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
- **Dialog Sizing Solution**: Replaced QStackedWidget with show/hide pattern for reliable dynamic height adjustment
  - **Problem**: QStackedWidget's `sizeHint()` tends to reflect the largest page, causing dialogs to stay tall after visiting a larger page
  - **Solution**: Each mode detail widget added directly to layout and shown/hidden based on selection
  - **Pattern**: Hide all widgets → show selected → `layout.activate()` → `adjustSize()` → explicit resize
  - **Result**: Dialog height correctly shrinks/grows to match visible content across all mode switches
  - Standard Qt best practice for dynamic dialog content where size varies significantly between options

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
