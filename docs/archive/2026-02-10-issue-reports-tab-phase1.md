# Issue Draft — Reports Tab (Phase 1): Overview + By User + By Site + KPI Snapshot

Tracks implementation work derived from the broader design/spec in Issue #101.

Parent spec: #101 (Reports tab: analytics dashboard + tax analysis)

## Goal (Phase 1)
Deliver a first, shippable Reports tab that answers:
- “What’s my overall performance for this date range?”
- “How are users performing?”
- “How are sites performing?”

With:
- a consistent filter bar
- a KPI snapshot strip
- sortable breakdown tables
- correct filtering + correct exclusion of soft-deleted rows

## Scope
### UI
Add a new primary tab: **📈 Reports** with:

1) **Global filter bar** (top of Reports tab)
- Date range preset + custom range
- User filter (All / multi-select)
- Site filter (All / multi-select)
- Optional toggle: Include inactive entities (default off)
- Optional toggle: Include soft-deleted activity (default off)

2) **KPI snapshot strip** (always visible under filters)
Minimum KPIs:
- Session Net P/L (sum of `game_sessions.net_taxable_pl`)
- Total Cashback (sum of `purchases.cashback_earned`)
- Session Net P/L + Cashback
- Total Purchases (sum of `purchases.amount`)
- Total Redemptions (sum of `redemptions.amount`)
- Total Redemption Fees (sum of `redemptions.fees`)
- Outstanding Balance (sum of `purchases.remaining_amount`)

3) **Overview section**
- A compact “Totals” / “At a glance” summary using the KPIs above

4) **By User table** (sortable)
Columns:
- User
- Session Net P/L
- Cashback
- Net P/L + Cashback
- Purchases
- Redemptions
- Fees
- # Sessions
- Outstanding Balance

5) **By Site table** (sortable)
Columns:
- Site
- Session Net P/L
- Cashback
- Net P/L + Cashback
- Purchases
- Redemptions
- Fees
- # Sessions
- Outstanding Balance

### Services
Extend/adjust [services/report_service.py](services/report_service.py) to support Phase 1:

- Introduce a `ReportFilter` (date range + user_ids + site_ids + include_deleted)
- Add service methods:
  - `get_kpi_snapshot(filter) -> SnapshotDTO`
  - `get_user_breakdown(filter) -> list[UserBreakdownRow]`
  - `get_site_breakdown(filter) -> list[SiteBreakdownRow]`

### Data semantics (Phase 1)
To stay consistent with Sezzions’ current computed accounting:
- **Session Net P/L** is defined as $\sum \texttt{game_sessions.net_taxable_pl}$ within filters.
- **Cashback** is $\sum \texttt{purchases.cashback_earned}$.
- **Outstanding Balance** is $\sum \texttt{purchases.remaining_amount}$.
- Purchases/Redemptions totals come from their respective `amount` columns.
- Fees come from `redemptions.fees`.

### Soft-delete behavior
Default behavior excludes soft-deleted activity:
- `purchases.deleted_at IS NULL`
- `redemptions.deleted_at IS NULL`
- `game_sessions.deleted_at IS NULL`

(Provide an optional UI toggle to include deleted later; Phase 1 can keep it hard-off if preferred.)

### Date filtering (Phase 1)
- `purchases.purchase_date` between start/end (inclusive)
- `redemptions.redemption_date` between start/end
- `game_sessions.session_date` between start/end

## Non-goals
- Tax Analysis UI/logic (tracked by #101 follow-ups)
- By Game / By Game Type / Custom builder
- Right-click “View in Reports” navigation (future)

---

## Acceptance Criteria
- Reports tab is available as a primary tab and loads without errors.
- Changing date range updates KPIs + both breakdown tables.
- Filtering by user/site updates KPIs + tables consistently.
- Breakdown table totals reconcile:
  - sum(User rows) == overall KPIs (within rounding)
  - sum(Site rows) == overall KPIs (within rounding)
- Soft-deleted activity is excluded by default.
- Reports UI never queries repositories directly (service layer only).

---

## Test Matrix (Mandatory)

### Happy paths
1) **Overall + breakdown match**
- Seed: 2 users, 2 sites, multiple purchases/redemptions/sessions across both.
- Assert snapshot KPIs equal expected sums.
- Assert `sum(user_breakdown.session_net_pl) == snapshot.session_net_pl` and same for cashback/purchases/redemptions/fees/outstanding.

2) **Filter by site**
- Apply site filter.
- Assert only site-specific data contributes to snapshot and breakdown.

### Edge cases (at least 2)
3) **No data in range**
- Date range with no rows.
- Snapshot shows zeros; breakdown tables empty (or rows with zeros—pick one and codify).

4) **Soft-deleted exclusion**
- Create purchase/session/redemption, then soft-delete them.
- Assert they do not appear in snapshot or breakdown.

### Failure injection (at least 1)
5) **DB failure does not crash UI**
- Close the DB (or monkeypatch `ReportService` to raise) then open Reports tab / refresh.
- Assert UI shows a user-friendly error state (banner/message) and remains responsive.

### Invariants
- KPI snapshot and breakdown tables apply identical filters.
- All queries respect `deleted_at IS NULL` unless include-deleted is explicitly enabled.

---

## Implementation Notes
- Prefer adding a dedicated UI tab: `ui/tabs/reports_tab.py`.
- Keep `ReportService` as the single source of truth for definitions.
- Consider lightweight caching keyed by `ReportFilter` if refresh feels slow.

## Follow-ups
- Tax Analysis refinement questions live in #101.
- Add By Game Type / By Game sections.
- Add context navigation (“View in Reports”).
