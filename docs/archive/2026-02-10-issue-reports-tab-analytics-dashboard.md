# Issue Draft — Reports Tab: Analytics Dashboard + Tax Analysis

## Problem
Sezzions has strong operational tabs (Purchases/Redemptions/Sessions/etc.) but lacks a unified, filterable analytics surface for:
- overall performance
- performance by user
- performance by site
- performance by game type / game
- key stats like net P/L, cashback, RTP, redemption time, outstanding balances
- tax-sensitive views (pre/post-tax, withholding assumptions, filing method)

This issue proposes a **Reports tab layout + data model** that is flexible, drill-down friendly, and sets up future context navigation (e.g., right-click “View in Reports”).

## Goals
- Provide an intuitive Reports UI with clear sections, consistent filters, and fast “answers at a glance”.
- Support cross-cutting metrics (P/L, cashback, fees, taxes, time-to-redeem, open balances) across multiple grouping dimensions.
- Enable drill-down from summary → breakdown table → detail.
- Establish a scalable architecture: UI → `ReportService` → repositories (no DB calls from UI).
- Design for later feature: right-click anywhere a User/Site/Game appears → “View in Reports”.

## Non-goals (for first implementation phase)
- Building every metric listed here on day one.
- Fully accurate tax filing calculations across every jurisdiction; first phase focuses on **user-configurable what-if analysis**.
- Complex charting library adoption (keep dependencies minimal; tables + a few basic charts only if easy).

---

## Proposed IA (Information Architecture)

### Reports Tab Top-Level Layout
A single Reports tab with a **left nav** (sections) and a **main panel**.

**Top filter bar (always visible)**
- Date range preset + custom range
- User multi-select (All default)
- Site multi-select (All)
- Card multi-select (All)
- Game Type multi-select (All)
- Game multi-select (All)
- “Include Soft-Deleted” toggle (default off)
- “Include Repair Mode anomalies” toggle (optional later)
- Search box (filters rows in breakdown tables)
- “Save View” / “Load View” (saved filter presets)

**Snapshot KPI strip (always visible under filters)**
- Net P/L (pre-tax)
- Net P/L + Cashback (pre-tax)
- Net P/L (post-tax — based on Tax settings)
- Net P/L + Cashback (post-tax)
- Total Cashback
- Total Fees
- Total Redeemed
- Total Purchased
- Outstanding SC balance (open positions)
- Avg RTP (if definable from available data)
- Avg redemption time (site-weighted + overall)

**Main body (sectioned)**
Left nav sections (suggested):
1) Overview
2) By User
3) By Site
4) By Game Type
5) By Game
6) Cashback
7) Time & Flow (Redemption time / cadence)
8) Balances (Outstanding / unrealized)
9) Tax Analysis
10) Custom Builder (phase 2+)

---

## Section Details

### 1) Overview (default landing)
**Purpose:** “How am I doing?” in one screen.

**Panels**
- KPI Snapshot strip (global)
- Trend (optional phase 2): Net P/L over time (daily/weekly/monthly toggle)
- Breakdown Table: “Top Drivers” (sortable)
  - columns: Dimension (User/Site/Game), Net P/L, Cashback, P/L+Cashback, Fees, Redeemed, Purchased, Count Sessions, Count Redemptions
  - segmented tabs inside this table: Top Users | Top Sites | Top Games

**Actions**
- Click a row → opens drill-down drawer (right) with detail metrics and links.

---

### 2) By User
**Primary table:** Users leaderboard.

**Columns (first phase)**
- User
- Net P/L
- P/L + Cashback
- Total Cashback
- Total Fees
- Purchases $ / SC
- Redemptions $ / SC
- # Sessions
- # Purchases
- # Redemptions
- Avg session duration (if available)
- Outstanding balance (unrealized)

**Secondary panels**
- Per-user trend (optional)
- “User × Site” pivot (matrix): rows Users, cols Sites, value = Net P/L or P/L+Cashback

---

### 3) By Site
**Primary table:** Sites leaderboard.

**Columns (first phase)**
- Site
- Net P/L
- P/L + Cashback
- Total Cashback
- Total Fees
- Purchases
- Redemptions
- # Redemptions
- Avg redemption time (purchase→redemption, or redemption lag)
- Outstanding balance

**Secondary panels**
- “Site × User” pivot
- “Site × Game Type” pivot

---

### 4) By Game Type
**Primary table:** Game Types summary.

**Columns**
- Game Type
- Net P/L
- P/L + Cashback
- Total Cashback
- Purchases
- Redemptions
- # Sessions
- Avg wager (if defined)
- Avg RTP proxy (see notes)

---

### 5) By Game
**Primary table:** Games summary.

**Columns**
- Game
- Game Type
- Net P/L
- P/L + Cashback
- Sessions
- Purchases
- Redemptions
- Avg duration / cadence metrics (if available)

---

### 6) Cashback
**Sub-tabs**
- Cashback Overview (totals + rate)
- Cashback by Site
- Cashback by User
- Cashback by Card
- Cashback by Game / Game Type (if attributable)

**Key metrics**
- Cashback total
- Cashback as % of purchases
- Cashback-adjusted P/L

---

### 7) Time & Flow
**Focus:** velocity and friction.

**Sub-tabs**
- Redemption Time by Site (avg/median/p95)
- Redemption Time by User
- Activity cadence (sessions/week, redemptions/week)

**Metrics**
- Avg time between purchase and redemption (requires clear definition)
- Avg time between redemptions
- Longest outstanding age (oldest open balance)

---

### 8) Balances
**Sub-tabs**
- Outstanding balances by Site/User/Card
- “Aging” table: open balance age buckets (0-7d, 8-30d, 31-90d, 90d+)

**Metrics**
- Outstanding SC / $
- Unrealized P/L (if defined)
- Balance closure frequency

---

### 9) Tax Analysis (design + questions)
**Purpose:** user-configurable what-if analysis.

**Tax settings panel (right-side or top of section)**
- Filing method:
  - Individual (wins/losses)
  - Schedule C (gross receipts minus expenses)
- Cashback treatment:
  - Treat as rebate (reduces purchase cost)
  - Treat as income
  - Ignore
- Withholding model (user-input assumptions):
  - Flat % of wins
  - Flat % of redemptions
  - Custom rules (phase 2)
- Tax rate assumptions:
  - Federal %
  - State %
  - Local %
  - Effective combined %
- Deduction/offset rules (phase 2):
  - Cap losses at winnings (individual)
  - Expenses categories (schedule C)

**Outputs (tables + KPIs)**
- Pre-tax Net P/L
- Post-tax Net P/L
- Estimated tax owed
- Estimated withholding
- “Net after withholding”
- Sensitivity table: Net after tax for tax rate 0–40% step (optional)

**Required clarifications (need discussion)**
1) What is “wins” vs “net profit” in Sezzions terms? Is it redemption amount? Or profit vs cost basis?
2) For Individual method: do we treat redemptions as wins and purchases as losses? Or treat only net session profit?
3) How should cashback affect taxable amounts?
4) How should fees be treated?
5) Any jurisdiction-specific rules we must model explicitly?

---

### 10) Custom Builder (phase 2+)
A “build your own table” interface:
- Choose grouping: User / Site / Card / Game Type / Game / Date bucket
- Choose measures: Net P/L, Cashback, Fees, Purchases, Redemptions, Counts, Avg times
- Choose filters (inherits global)
- Save as named report

---

## Drill-down + Context Navigation (future goal)
**Target UX**
- Right-click a User/Site/Game in any table anywhere in the app → “View in Reports”
- Reports tab opens to the right section and applies an entity filter
- Also provide in Reports: clickable links from leaderboard tables to entity-focused views

**Implementation concept**
- A `ReportsContext` DTO containing:
  - section (overview/by-user/by-site/...)
  - entity type + id (optional)
  - date range + filters

---

## Metric Definitions (proposed)
These should be codified in `ReportService` and shared across UI.

- Net P/L: (total redemptions) − (total purchases) − (fees) [+/- adjustments?]
- P/L + Cashback: Net P/L + cashback
- Outstanding balance: open/unclosed SC positions (tie to Unrealized)
- Redemption time:
  - Option A: time from last purchase → redemption
  - Option B: time from first purchase in open position → redemption
  - Option C: time from session end → redemption
  (Pick one as default; allow switching later)

---

## Architecture Notes
- UI should call `services/report_service.py` (new or existing) and not repositories directly.
- Report queries should be structured for:
  - fast refresh (cached per filter signature)
  - safe against soft-deletes (`deleted_at IS NULL` by default)
- Prefer reusable primitives:
  - `ReportFilter` (date range + entity IDs)
  - `ReportRow` DTOs for tables

---

## Acceptance Criteria (Phase 1)
- Reports tab exists with:
  - Global filter bar
  - Snapshot KPI strip
  - At least 3 functional sections: Overview, By User, By Site
  - Data is filterable by date range + user + site
- Snapshot KPIs include: Net P/L, Net P/L+Cashback, Total Cashback, Outstanding balance
- Basic tables render quickly and are sortable.
- Tax Analysis section exists as a UI shell with configurable inputs and computed outputs for at least one model (TBD after discussion).

## Test Plan
- Unit tests for `ReportService` metric definitions.
- Integration tests for filtering correctness (date/user/site).
- Headless UI smoke test:
  - boot `QApplication`
  - instantiate `MainWindow`
  - open Reports tab
  - verify filter widgets exist and a basic table model populates

---

## Pitfalls / Follow-ups
- Metric definitions must match Sezzions semantics (especially around sessions and cost basis).
- Tax models can get complex fast; keep phase 1 as a user-configurable approximation.
- Large datasets may require pagination or incremental loading.
