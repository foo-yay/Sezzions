## Do this first: Fix FIFO allocation to respect redemption timestamp.

In business_logic.py, FIFOCalculator.calculate_cost_basis(site_id, redemption_amount, user_id, redemption_date, redemption_time optional):
- Ensure the SELECT that pulls candidate purchases includes only purchases on or before the redemption timestamp:
  (purchase_date < redemption_date) OR (purchase_date = redemption_date AND (purchase_time IS NULL OR purchase_time <= redemption_time))
- Thread redemption_time through process_redemption() calls (it already has redemption_time) and pass it into calculate_cost_basis.
- Apply same cutoff when computing total_remaining for final redemption (already doing it there, but make consistent).
Goal: never allocate basis from a purchase that happened after the redemption.
Add a small unit-like test or debug print to confirm.


## Prompt 0 — One-time schema + rebuild: add gameplay↔event links (BEFORE/DURING/AFTER)

In this repo, we have two accounting paths:
- Cashflow/FIFO: purchases, redemptions, redemption_allocations, tax_sessions, site_sessions
- Gameplay: game_sessions (sessions are strictly gameplay)

Implement explicit, queryable linkage between gameplay sessions and cashflow events (purchases and redemptions) WITHOUT changing FIFO math.

1) Add a new SQLite table `game_session_event_links`:
   - id INTEGER PRIMARY KEY
   - game_session_id INTEGER NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE
   - event_type TEXT NOT NULL CHECK(event_type IN ('purchase','redemption'))
   - event_id INTEGER NOT NULL  (id from purchases or redemptions depending on event_type)
   - relation TEXT NOT NULL CHECK(relation IN ('BEFORE','DURING','AFTER','MANUAL'))
   - created_at TEXT DEFAULT CURRENT_TIMESTAMP
   - UNIQUE(game_session_id, event_type, event_id, relation)

Also add helpful indexes:
- idx_gsel_session on (game_session_id)
- idx_gsel_event on (event_type, event_id)

2) In business_logic.py (SessionManager), add a rebuild function:
   `rebuild_game_session_event_links_for_pair(site_id, user_id)`
   - Loads CLOSED game_sessions ordered by end_dt ASC
   - For each session, compute start_dt and end_dt using existing _dt()
   - Determine prev_end_dt (prior closed session end) and next_start_dt (next closed session start) for gaps
   - Link purchases:
       * DURING: purchase_dt in [start_dt, end_dt]
       * BEFORE: purchase_dt in (prev_end_dt, start_dt)  (or prev_end_dt is None => all < start_dt)
     Link redemptions:
       * DURING: redemption_dt in [start_dt, end_dt]
       * AFTER: redemption_dt in (end_dt, next_start_dt) (or next_start_dt is None => all > end_dt)
   - Use half-open windows to avoid double-linking across adjacent sessions; pick a consistent rule:
       DURING = dt >= start_dt AND dt <= end_dt
       BEFORE = dt > prev_end_dt AND dt < start_dt
       AFTER  = dt > end_dt AND dt < next_start_dt
   - Ignore events with NULL datetime.
   - Clear existing links for that (site_id,user_id) pair first:
       delete links where game_session_id IN (SELECT id FROM game_sessions WHERE site_id=? AND user_id=?)
   - Insert links deterministically.

3) Call this rebuild from rebuild_all_derived() after _rebuild_session_tax_fields_for_pair() (or inside it once sessions loaded), so links stay updated whenever sessions recalculated.

4) Do NOT modify purchases.remaining_amount or redemption_allocations logic as part of this. This is metadata linkage only.

Add small helper query methods to SessionManager:
- get_links_for_purchase(purchase_id) -> returns linked sessions with relation
- get_links_for_redemption(redemption_id) -> returns linked sessions with relation
- get_links_for_session(session_id) -> returns purchases/redemptions with relation

Make sure code works even if the new table doesn't exist yet by ensuring schema migration runs at app startup (where other tables are created).

## Prompt A — Purchase detail view: show Sessions + Redemptions tables + “Open” buttons

Update the Purchase detail/view dialog (qt_app.py / relevant UI module):

Requirement:
When viewing a purchase, show:
1) A table "Linked Game Sessions" listing game_sessions rows that link to this purchase via game_session_event_links where event_type='purchase' and event_id=purchase_id.
   Columns: Session Date, Start Time, End Date/Time, Game Type, Status, Relation (BEFORE/DURING/AFTER/MANUAL)
   Add a button/column "Open" that opens that session in the existing Session view dialog.

2) A table "Allocated Redemptions" showing all redemptions that consumed this purchase via redemption_allocations.
   Query:
     SELECT r.id, r.redemption_date, r.redemption_time, r.amount, ra.allocated_amount
     FROM redemption_allocations ra
     JOIN redemptions r ON r.id = ra.redemption_id
     WHERE ra.purchase_id = ?
     ORDER BY r.redemption_date, COALESCE(r.redemption_time,'00:00:00'), r.id
   Columns: Redemption Date, Time, Redemption Amount, Allocated From This Purchase
   Add "Open" button for each redemption row.

Also show summary labels above/below tables:
- total allocated from this purchase = SUM(allocated_amount)
- remaining basis for this purchase = purchases.remaining_amount
- original amount = purchases.amount

Implement in a way consistent with existing UI patterns: reuse existing table widget class, selection model, and open-dialog functions (search for how redemptions/sessions are opened elsewhere).


## Prompt B — Redemption detail view: show Purchases table + Sessions table (and handle “unbased winnings”)

Update the Redemption detail/view dialog:

Requirement:
When viewing a redemption, show:
1) A table "Allocated Purchases (FIFO)" listing all purchases allocated to this redemption via redemption_allocations.
   Query:
     SELECT p.id, p.purchase_date, p.purchase_time, p.amount, p.sc_received, ra.allocated_amount
     FROM redemption_allocations ra
     JOIN purchases p ON p.id = ra.purchase_id
     WHERE ra.redemption_id = ?
     ORDER BY p.purchase_date, COALESCE(p.purchase_time,'00:00:00'), p.id
   Columns: Purchase Date/Time, Purchase Amount, SC Received, Allocated Amount
   Add "Open" button to open purchase.

2) A table "Linked Game Sessions" listing game_sessions linked to this redemption via game_session_event_links where event_type='redemption' and event_id=redemption_id.
   Columns: Session Date, Start Time, End Date/Time, Relation (DURING/AFTER/MANUAL), Status, Game Type
   Add "Open" button to open session.

3) Display a computed “Unbased / Winnings Portion” for the redemption:
   - cost_basis is in tax_sessions.cost_basis for this redemption_id (already inserted in process_redemption)
   - winnings = redemption.amount - cost_basis
   - If redemption_allocations sum < redemption.amount (or if no allocations), show "Unbased Portion" = redemption.amount - SUM(allocated_amount) when is_free_sc=0 and more_remaining=1 case
   - If is_free_sc=1, show "Cost basis = $0 (Free SC)"

Do not attempt to allocate winnings to purchases. Just display it clearly so "purchaseless" doesn’t look like a bug.

Implementation: add these tables and labels to the existing Redemption view layout.

## Prompt C — Session detail view: show Purchases/Redemptions that affect basis BEFORE or DURING (not AFTER)

Update the Game Session detail/view dialog:

Requirement:
When viewing a session (game_sessions.id = X), show:
1) Table "Purchases Contributing to Basis (Before/During)"
   Use game_session_event_links:
     SELECT p.id, p.purchase_date, p.purchase_time, p.amount, p.sc_received, gsel.relation
     FROM game_session_event_links gsel
     JOIN purchases p ON p.id = gsel.event_id
     WHERE gsel.game_session_id = ?
       AND gsel.event_type='purchase'
       AND gsel.relation IN ('BEFORE','DURING','MANUAL')
     ORDER BY p.purchase_date, COALESCE(p.purchase_time,'00:00:00'), p.id
   Columns: Date, Time, Amount, SC Received, Relation
   Add Open button for purchase.

2) Table "Redemptions Affecting This Session (During only by default)"
   Use game_session_event_links:
     SELECT r.id, r.redemption_date, r.redemption_time, r.amount, gsel.relation
     FROM game_session_event_links gsel
     JOIN redemptions r ON r.id = gsel.event_id
     WHERE gsel.game_session_id = ?
       AND gsel.event_type='redemption'
       AND gsel.relation IN ('DURING','MANUAL')
     ORDER BY r.redemption_date, COALESCE(r.redemption_time,'00:00:00'), r.id
   Add Open button for redemption.

Optionally include a checkbox "Include AFTER cashouts" which adds relation 'AFTER' to the query.

Also show the existing derived session fields prominently (already in DB):
- expected_start_total_sc, expected_start_redeemable_sc
- session_basis, basis_consumed, delta_total, delta_redeem, net_taxable_pl

Do NOT attempt to infer redemption↔purchase within this view. This screen is about session windows, not FIFO allocation.

## Prompt D — Unrealized position view: show Purchases that make up the position + Open buttons

Our current Unrealized Positions already link Open Purchases.  Utilizing that logic as a framework, implement any appropriate changes that allow it to function seamlessly with these other new implementations.  If we need to replace the current method, we can do that.  The below is a potential path for doing so, with the intent of keeping processes consistent, however we don't want to write redundant code.

Update the Unrealized Position detail/view dialog:

Requirement:
If unrealized positions are computed from purchases.remaining_amount (not stored as allocations), then show a table of purchases with remaining_amount > 0 for the same site_id/user_id that match the position filter (site/user).
Query:
  SELECT id, purchase_date, purchase_time, amount, sc_received, remaining_amount
  FROM purchases
  WHERE site_id=? AND user_id=? AND remaining_amount > 0
  ORDER BY purchase_date, COALESCE(purchase_time,'00:00:00'), id

Columns: Purchase Date/Time, Original Amount, SC Received, Remaining Amount (Unrealized Basis)
Add Open button to open purchase.

Make sure this matches how the unrealized position total is calculated so totals reconcile.

