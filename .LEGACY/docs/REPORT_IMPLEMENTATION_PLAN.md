## Prompt 1 — Create Reports Hub UI + navigation

Implement a Reports section UI:
- Left navigation categories: Dashboard, Games, Sites, Sessions, Redemptions, Spending, Cashback, Tax Center, Forms
- Right panel includes a reusable FilterBar widget:
  date range, group interval (D/W/M/Q/Y), user, site, game (optional), Apply, Reset, Export CSV
- Each report view uses the same layout: KPI cards, charts, table.
Reuse existing Qt patterns and keep dialogs manageable.
Remember sqlite3.Row has no .get(); convert rows to dicts in reporting service layer.

## Prompt 2 — Build reporting.py service layer

Create reporting.py with a unified API:
run_report(report_id: str, filters: dict) -> dict with keys: kpis, series, rows.

Requirements:
- Filters: date range, user_id, site_id, game_id, method_id, card_id, group_interval
- All DB query results converted to dicts (no sqlite3.Row escapes the service layer).
- Helper: bucket_sql(group_interval) that returns group key expr and label.
- Return rows suitable for both table display and CSV export.

## Prompt 3 — Implement critical reports first (MVP)

Implement MVP reports using reporting.py:
1) Overall Dashboard (kpis + net cashflow chart + session net chart + top sites table)
2) Site Summary (group by site)
3) Game Performance (group by game, includes sessions count, wager, net, RTP)
4) Redemptions Timing (avg lag per site + redemptions volume)
5) Tax Center: Session-method Winnings/Losses summary (wins, losses, net) + export

Ensure each report supports grouping interval and date range filters.

## Prompt 4 — Tax Forms tracker

Add a Forms Tracker section:
- Create table tax_forms(user_id, tax_year, payer, form_type, amount, date_received, notes)
- CRUD UI for adding/editing forms
- Report comparing forms totals vs internal totals by payer/site/user for selected year
CSV export for CPA packet.

## Prompt 5 — “Explain this number” tooltips

Add tooltip/help text for KPIs:
Each KPI card has a small info icon that displays:
- formula used
- source tables/fields (e.g., game_sessions.net_taxable_pl sum)
This is static text per KPI and reduces confusion.

## DESIGN PRINCIPLES

0) Core design principles (so the whole Reports section doesn’t become spaghetti)

    Single “unit of account”
	    •	USD everywhere for analytics + tax.
	    •	Redemptions/purchases remain authoritative USD amounts.
	    •	Fees are separate fields but still USD.

    One reporting pipeline

    All reports should be built on a shared set of:
	    •	Filters: date range, user, site, game, card, method, grouping interval.
	    •	Time bucketing: daily / weekly / monthly / quarterly / yearly
	    •	Exports: every report has CSV export of the current filtered dataset.

    Separate “Cashflow” vs “Gameplay”

    To avoid confusion:
	    •	Cashflow layer = purchases, redemptions, fees, net received, cashback.
    	•	Gameplay/session layer = game_sessions and its derived fields (delta_total, delta_redeem, net_taxable_pl, rtp, wagers, etc.)
    	•	Reports should never “mix” these without an explicit reconciliation view.

1) Reports UI layout (simple + scalable)

    A) Reports Hub (left nav + right panel)

    Create a “Reports” main view with:
	    •	Left: report categories
	    •	Right: report content with top filter bar

    Top filter bar (global)
	    •	Date range picker (from/to)
	    •	Group by: Daily / Weekly / Monthly / Quarterly / Yearly
	    •	User dropdown (All + individual)
	    •	Site dropdown (All + individual)
	    •	Game dropdown (optional; enabled on Game reports)
	    •	Buttons: Apply, Reset, Export CSV

    Standard widgets (reused everywhere)
	    •	KPI cards row (3–6 cards)
	    •	1–2 charts (line/bar)
	    •	Table view with sortable columns + pagination

2) Report set (what to build)

    Category 1: Dashboard (high-level “at-a-glance”)

        Report: Overall Performance Dashboard
        KPI cards:
        	•	Net cashflow (net received − purchases)
        	•	Session net (sum of session net results)
        	•	Total wager
        	•	RTP avg (weighted)
        	•	Redemption fees
        	•	Cashback earned

        Charts:
	        •	Net cashflow over time
        	•	Session net over time

        Table:
    	    •	Top sites by profit
    	    •	Top games by profit

        Report: Site/User Pair Dashboard
            Same template but filtered to a single site+user.
            Add:
	            •	Open position snapshot (total remaining basis + count open purchases)
	            •	Avg redemption lag (submit → receipt) for that site
    
    Category 2: Game performance

        Report: Game Performance Summary
            Group by game:
	            •	sessions
	            •	total wager
	            •	total delta_total (or whichever you use)
	            •	total net session result (sum net_taxable_pl or equivalent)
	            •	average RTP
	            •	win rate (% sessions positive)

        Charts:
	        •	Game profit over time (top game selected)
	        •	RTP trend (optional)

        Table:
	        •	per game: sessions, wager, net, RTP, avg session length (if you have duration)

        Data source: game_sessions + game_rtp_aggregates (or equivalent equation)
        Use weighted RTP: sum(wager + delta_total) / sum(wager) * 100 for the period.
    
    Category 3: Site performance

        Report: Site Summary
            Group by site:
	            •	purchases total
	            •	redemptions gross
	            •	fees
	            •	net received
	            •	session net
	            •	open basis
	            •	avg redemption lag

        Charts:
	        •	purchases vs redemptions over time
	        •	site net performance over time

        Data sources: purchases, redemptions (+ fee field), game_sessions, plus open basis from purchases.remaining_amount.

    Category 4: Session analytics

        Report: Session Trend
            Grouped by time bucket:
	            •	sessions
	            •	avg session net
	            •	median session net (nice)
	            •	total net
	            •	win rate
	            •	avg wager
	            •	avg RTP

        Charts:
	        •	session net by day/month
	        •	distribution histogram (optional)

        Data source: game_sessions WHERE status='Closed'

    Category 5: Redemption metrics (operations + friction)

        Report: Redemptions & Timing
        Metrics:
	        •	total redemptions count
	        •	gross redeemed
	        •	fees total
	        •	net received
	        •	avg redemption lag (submit→receipt)
	        •	% processed/unprocessed

        Breakdowns:
	        •	by site
	        •	by redemption method
	        •	by user

        Charts:
	        •	lag trend by site (line)
	        •	redemptions volume (bar)

        Data source: redemptions with redemption_date/time and receipt_date (and processed)

     Category 6: Purchases & spending behavior

        Report: Spending
        Breakdowns:
	        •	by site
	        •	by card
	        •	by user
	        •	by day/month

        Metrics:
	        •	total purchases
	        •	avg daily spend
	        •	max day spend
	        •	purchases count
	        •	avg cost per SC (if you have sc_received)

        Charts:
	        •	daily purchases over time
	        •	spend by card / site (bar)

        Data source: purchases + card assignment logic you already added.

    Category 7: Cashback (if you track it)

        Report: Cashback Summary
	        •	cashback total by card
	        •	cashback total by site
	        •	cashback total by user
	        •	effective cashback % (cashback / purchases)

        Charts:
	        •	cashback over time
	        •	cashback by card

        Data source: wherever you store cashback now (purchases field? separate table?).    

    Category 8: Tax Center (separate section)

        This section is “tax-facing,” but still useful.

        Tax Center report A: Session-method Winnings/Losses Summary
        For date range:
	        •	Total session wins (sum of positive session results)
	        •	Total session losses (sum of absolute negatives)
	        •	Net (wins − losses)
	        •	Total business expenses (from Expenses tab)
	        •	Fees totals (purchase fees likely baked in, redemption fees explicit)

        This is the core “diary method” summary.

        Tax Center report B: Mock Schedule C (configurable)
        This should be a report generator, not your accounting engine.
        Toggles:
	        •	Cashback treatment:
	        •	reduce expenses
	        •	other income
	        •	ignore
	        •	Include redemption fees as expenses vs reduce proceeds (display both options)
	        •	Show “session method totals” vs “cashflow totals” side-by-side

        Outputs:
	        •	a “Schedule C-style” layout (not claiming official)
	        •	export CSV/PDF (CSV mandatory, PDF optional)

        Tax Center report C: Forms tracker (1099/W-2G)
        Create a small CRUD screen:
	        •	Payer (site/processor)
	        •	Form type (1099-MISC / 1099-K / W-2G / other)
	        •	Amount
	        •	Tax year
	        •	Date received
	        •	Notes
	        •	Attachment path optional (skip upload for now)

        Then report:
	        •	“Forms total” vs “Internal totals” (by payer)
	        •	Show variance and let user add notes (“site reports turnover, not winnings”, etc.)

3) Usability features that matter

    A) “Report bookmarks”

        Let user save:
	        •	current filters (date range, user, site, group interval)
	        •	selected report
        So “Monthly review” becomes 1 click.

    B) “Explain this number”

        Add a small “?” icon next to key metrics:
	        •	Opens a tooltip with the formula and data sources.
        This massively reduces confusion and bug reports.

    C) “Drill-down everywhere”

        Every summary table row should allow:
	        •	double click to open detail
	        •	or “View underlying rows” (opens the raw list filtered)

4) Data + logic implementation plan (how to build without chaos)

    Step 1: Build a reporting service layer (Python)

        Create reporting.py (or similar) with:
	    •	build_filters(where_clauses, params)
	    •	bucket_expr(group_by) helper
	    •	run_report(report_id, filters) returning:
	    •	kpis: dict
	    •	series: [{x, y}] for charts (or multiple series)
	    •	rows: list[dict] for tables
	    •	All outputs must be dicts, not sqlite3.Row.

        Important: add a tiny helper:
	        •	row_to_dict(row) and always convert.
        This ends your .get misery forever in report code.

    Step 2: Standardize timestamps

        Define a canonical timestamp expression in SQL:
	        •	COALESCE(date_col,'') || ' ' || COALESCE(time_col,'00:00:00')
        And ALWAYS treat NULL time as 00:00:00.

    Step 3: Implement bucketing

        For SQLite, implement time buckets using:
	        •	daily: date(date_col)
	        •	monthly: strftime('%Y-%m', date_col)
	        •	quarterly: compute from month
	        •	yearly: strftime('%Y', date_col)

    Step 4: Add exports

        Every report:
	        •	Export CSV exports the table rows as displayed.
	        •	Also offer “Export Raw Rows” for some reports (optional).

5) What schema changes may be needed

    Based on our goals:

    Required / strong recommendations
	    •	redemptions.fee_amount REAL NOT NULL DEFAULT 0.0 (you already planned)
	    •	Ensure redemptions have receipt_date (sounds like you already do)
	    •	Forms tracker table:
	    •	tax_forms(id, user_id, tax_year, payer, form_type, amount, date_received, notes)

    Optional
	    •	“Saved reports” table:
	    •	report_bookmarks(id, name, config_json, created_at)

6) What to build first (the “don’t boil the ocean” order)
	1.	Reports Hub + filter bar + CSV export plumbing
	2.	Overall Dashboard
	3.	Site Summary + Game Summary
	4.	Redemptions timing + Spending
	5.	Tax Center: session wins/losses + mock Schedule C view
	6.	Forms tracker
	7.	Bookmarks + drilldowns + “Explain this number” polish