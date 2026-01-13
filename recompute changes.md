You are the IMPLEMENTER. Implement SCOPED (suffix) recomputation *and keep FULL rebuild behavior intact*. 
You MUST update BOTH `business_logic.py` (core algorithms) and `qt_app.py` (UI save/edit wiring) in this repo.  If there are other files that are linked and need to be uploaded, present those changes as well.

# Goal
When the user edits/creates/deletes any Purchase / Redemption / Game Session item, do NOT do a full (site,user) rebuild unless necessary.
Instead:
- Compute boundary T = start of containing CLOSED session window for the earliest affected timestamp (consider BOTH old and new timestamps on edits)
- Recompute FIFO + session-derived fields forward from T only
- Full rebuild remains available and unchanged (used for "Rebuild All" or fallback).

# Part A — business_logic.py (core)
## 1) Add boundary helper
Add on SessionManager:
- `find_containing_session_start(site_id, user_id, d, t) -> (start_date, start_time) | None`

**Uses BOTH closed AND open sessions.** Users frequently edit open sessions.

A session contains timestamp ts if:
- `start_dt = (start_date, COALESCE(start_time,'00:00:00')) <= ts`
- AND `(end_date IS NULL OR ts <= end_dt)` where `end_dt = (COALESCE(end_date, start_date), COALESCE(end_time,'23:59:59'))`

Return the containing session's (start_date, start_time) ordered by latest start (DESC) LIMIT 1.

SQL pattern:
```sql
SELECT start_date, COALESCE(start_time,'00:00:00') as start_time
FROM game_sessions
WHERE site_id = ? AND user_id = ?
  AND (start_date < ? OR (start_date = ? AND COALESCE(start_time,'00:00:00') <= ?))
  AND (end_date IS NULL OR ? < end_date OR (? = end_date AND ? <= COALESCE(end_time,'23:59:59')))
ORDER BY start_date DESC, COALESCE(start_time,'00:00:00') DESC
LIMIT 1
```

## 2) Extend auto_recalculate_affected_sessions to support scoped mode
- Keep existing calls working.
- New parameters (choose a clean signature, but must support old+new):
  - `old_ts: tuple[str,str] | None` and `new_ts: tuple[str,str] | None`
  - `scoped: bool = True` default for edit operations; allow forcing full.
- Compute boundary candidates:
  - for each ts in {old_ts,new_ts} that exists:
    - b = find_containing_session_start(...) if found else ts itself
  - T = min(b candidates)
- If boundary cannot be computed safely -> fallback FULL.

## 3) Implement scoped FIFO rebuild using redemption_allocations undo + replay
Add:
- `_rebuild_fifo_for_pair_from(site_id, user_id, from_date, from_time)`
It must:
1) Identify affected redemptions where redemption_dt >= from_dt for that (site,user), ordered (date,time,id).

2) **VALIDATE Free SC allocations (BEFORE undo):**
   - For each redemption in suffix:
     - If `is_free_sc = 1` (or equivalent flag): allow zero allocations ✓
     - If `is_free_sc = 0`: **REQUIRE** allocations exist AND sum to redemption.amount
     - If validation fails for any non-free redemption → **FALLBACK to full rebuild**

3) For valid redemptions only:
   - Restore purchases.remaining_amount by adding back allocations:
     ```sql
     UPDATE purchases 
     SET remaining_amount = MIN(amount, remaining_amount + allocated_amount)
     WHERE id IN (SELECT purchase_id FROM redemption_allocations WHERE redemption_id IN (...))
     ```
   - DELETE those redemption_allocations rows
   - DELETE tax_sessions rows for those redemption_ids

4) Replay affected redemptions only (chronological) by calling existing `process_redemption(..., is_edit=True)` or equivalent (ensure it writes allocations + tax_sessions again).

5) **After replay, recompute site_session aggregates (authoritative):**
   ```sql
   -- Identify affected site_sessions
   SELECT DISTINCT site_session_id FROM redemptions WHERE id IN (suffix_redemption_ids)
   
   -- Update aggregates via SQL
   UPDATE site_sessions
   SET total_redeemed = (
       SELECT COALESCE(SUM(amount), 0)
       FROM redemptions
       WHERE site_session_id = site_sessions.id
   ),
   total_buyin = (...),  -- if applicable
   -- other aggregate fields
   WHERE id IN (affected_site_session_ids)
   ```

6) Ensure deterministic ordering: ORDER BY date, COALESCE(time,'00:00:00'), id

**IMPORTANT:** Do not globally reset all purchases remaining_amount; only revert lots touched by allocations in the suffix.

## 4) Implement scoped session-derived rebuild
Add:
- `_rebuild_session_tax_fields_for_pair_from(site_id, user_id, from_date, from_time, old_session_values=None)`
Safe approach:
- Recompute sessions where session_end_dt >= from_dt (inclusive), because later sessions depend on chain.
- Seed running state by processing earlier sessions without writing changes (or compute initial checkpoint state from the last session before the recompute boundary).
- Then write updates for suffix sessions like current full method.
- Ensure redemption↔session links are consistent for suffix:
  - before recompute suffix, clear redemption.game_session_id for suffix sessions, then relink as you compute tax sessions.

## 5) Keep FULL rebuild unchanged
Existing:
- `_rebuild_fifo_for_pair(site_id, user_id)`
- `_rebuild_session_tax_fields_for_pair(site_id, user_id, old_session_values)`
Must still work exactly as before.

## 6) auto_recalculate_affected_sessions execution
If scoped:
- call `_rebuild_fifo_for_pair_from(..., T)`
- call `_rebuild_session_tax_fields_for_pair_from(..., T, old_session_values)`
Else:
- call existing full rebuild path (unchanged)

# Part B — qt_app.py (UI wiring)
You MUST ensure edits/creates/deletes pass correct old/new timestamps into SessionManager.auto_recalculate_affected_sessions.

## 1) Purchases: add/edit/delete handlers
Find the functions/methods in qt_app.py where purchases are saved/updated/deleted.
Common patterns to search:
- `add_purchase`, `edit_purchase`, `save_purchase`, `update_purchase`, `delete_purchase`
- handlers called after `PurchaseDialog.collect_data()`
In each case:

### Add purchase
- After inserting purchase row, call:
  - `session_mgr.auto_recalculate_affected_sessions(site_id, user_id, old_ts=None, new_ts=(purchase_date, purchase_time), scoped=True)`

### Edit purchase
- BEFORE update, fetch old row from DB by purchase_id: old_date, old_time, old_site_id, old_user_id
- AFTER update, call scoped recompute for OLD pair and NEW pair (in case site/user changed):
  - For old pair: `auto_recalculate_affected_sessions(old_site_id, old_user_id, old_ts=(old_date, old_time), new_ts=None, scoped=True)`
  - For new pair: `auto_recalculate_affected_sessions(new_site_id, new_user_id, old_ts=None, new_ts=(new_date, new_time), scoped=True)`
  - If site/user unchanged, just call once with both old_ts and new_ts:
    `auto_recalculate_affected_sessions(site_id,user_id, old_ts=(old_date,old_time), new_ts=(new_date,new_time), scoped=True)`

### Delete purchase
- BEFORE delete, fetch old row ts + pair
- AFTER delete, call:
  `auto_recalculate_affected_sessions(site_id,user_id, old_ts=(old_date,old_time), new_ts=None, scoped=True)`

## 2) Redemptions: add/edit/delete handlers
Repeat the same pattern for RedemptionDialog:
- old/new ts = (redemption_date, redemption_time)
- pair = site_id/user_id (lookup by name -> id like existing code does)
- Ensure both-pair handling if site/user changed.

## 3) Sessions: edits that affect ordering or balances
Locate where game sessions are closed/edited (search `end_game_session`, `close session`, `update_session`, `save_session`).
When a session is edited (start/end changed or balances changed):
- capture old session start/end ts + pair before update
- after update, call `auto_recalculate_affected_sessions` with old_ts/new_ts computed from the changed timestamp(s) that should define boundary:
  - If session window changed, use the earlier of old/new start timestamps as the boundary inputs.
  - Pass both old and new timestamps so SessionManager can take min(containing(old), containing(new)).

## 4) Keep explicit "Rebuild All" UI action using full rebuild
If qt_app.py has a "Rebuild All" / "Recalculate All" button/menu:
- keep it calling the existing full rebuild method (scoped=False or call rebuild_all_derived).
Do not change expected behavior.

# Part C — RTP Integration (CRITICAL)
During scoped rebuild, RTP must be updated for any session whose wager_amount or delta_total changes.

## RTP Update Strategy (Option B - Change Detection)
In `_rebuild_session_tax_fields_for_pair_from()`:

1) **Before processing suffix sessions:**
   - Query all sessions >= T that will be recomputed
   - Capture old state: `{session_id: (old_wager_amount, old_delta_total, game_id)}`

2) **During session processing:**
   - Compute new wager_amount (unchanged if user didn't edit it)
   - Compute new delta_total = ending_balance - starting_balance
   - Compare to old values

3) **After updating session in DB:**
   - If wager_amount OR delta_total changed:
     - Calculate deltas: wager_delta = new - old, delta_total_delta = new - old
     - Call `update_game_rtp_incremental(game_id, wager_delta, delta_total_delta, is_new_session=False, conn)`
   - If game_id changed (rare):
     - Remove from old game: deltas = (0 - old_wager, 0 - old_delta)
     - Add to new game: deltas = (new_wager - 0, new_delta - 0)

4) **Use existing connection:**
   - Pass conn to update_game_rtp_incremental to prevent database locks

## RTP for Non-Session Edits
- Editing purchases/redemptions only affects sessions indirectly (expected_balance chain)
- If those changes don't affect ending_balance or user-edited wager, delta_total may not change
- Change detection handles this automatically: no change = no RTP update

## Field-Specific Skip Logic (Dual Implementation)

### Field Classifications:

**Purchases Financial Fields:**
- date, time, amount, site_id, user_id, sc_received, starting_sc

**Purchases Non-Financial Fields:**
- (none identified - all fields affect accounting)

**Redemptions Financial Fields:**
- date, time, amount, site_id, user_id, partial, full
- **EXCLUDED:** receipt_date (metadata only, no recalc trigger)

**Redemptions Non-Financial Fields:**
- redemption_method_id (descriptive only)

**Sessions Financial Fields:**
- start_date, start_time, end_date, end_time
- starting_balance, ending_balance, locked_sc
- site_id, user_id

**Sessions Partial-Financial Fields (RTP-only):**
- wager_amount: Only affects RTP, not FIFO/tax
- game_id: Only affects RTP grouping

**Sessions Non-Financial Fields:**
- notes (descriptive only)

---

### Implementation (DUAL-LAYER):

#### Layer 1: qt_app.py (Performance Optimization - Primary Path)
In session save/edit handlers (`_save_closed_session`, etc):

```python
# After collecting new values, BEFORE calling auto_recalculate:
changed_fields = {k for k in old_values if old_values.get(k) != new_values.get(k)}

# Skip entirely for notes-only
if changed_fields == {'notes'}:
    return  # No recalculation needed

# RTP-only fast path
rtp_only_fields = {'wager_amount', 'game_id'}
if changed_fields and changed_fields <= rtp_only_fields:
    # Handle RTP update directly, skip auto_recalculate
    session_mgr._update_session_rtp_only(
        session_id, old_values, new_values
    )
    return  # Do NOT call auto_recalculate_affected_sessions

# Otherwise proceed with normal auto_recalculate call
session_mgr.auto_recalculate_affected_sessions(...)
```

**Rationale:** Catches 95% of RTP-only edits at UI layer (fastest path).

---

#### Layer 2: business_logic.py (Safety Net - Fallback Path)
In `auto_recalculate_affected_sessions()`:

```python
# Safety net: check for RTP-only changes if old/new values provided
if old_values and new_values and entity_type == 'session':
    rtp_only_fields = {'wager_amount', 'game_id'}
    changed_fields = {k for k in old_values if old_values.get(k) != new_values.get(k)}
    
    if changed_fields and changed_fields <= rtp_only_fields:
        # Only RTP changed - update and return
        self._update_session_rtp_only(session_id, old_values, new_values)
        return
    
    if changed_fields == {'notes'}:
        # Notes-only - skip entirely
        return

# If old_values/new_values NOT provided, proceed with scoped rebuild (safe default)
# Check redemption_method_id for redemptions
if old_values and new_values and entity_type == 'redemption':
    changed_fields = {k for k in old_values if old_values.get(k) != new_values.get(k)}
    if changed_fields == {'redemption_method_id'}:
        return  # Skip recalculation
```

**Rationale:** 
- Protects other code paths (APIs, scripts, tests) that call orchestrator directly
- Only activates if old/new dicts available
- Defaults to safe scoped rebuild if values missing

---

### RTP-Only Update Method:
Add to SessionManager:
```python
def _update_session_rtp_only(self, session_id, old_values, new_values, conn=None):
    """
    Update RTP aggregates for a session whose ONLY wager/game_id changed.
    Does NOT trigger FIFO or session chain recomputation.
    """
    own_conn = conn is None
    if own_conn:
        conn = self.db.get_connection()
    
    cursor = conn.cursor()
    
    # Get current session wager/delta/game from DB (new values already saved)
    cursor.execute("""
        SELECT wager_amount, delta_total, game_id
        FROM game_sessions WHERE id = ?
    """, (session_id,))
    row = cursor.fetchone()
    
    if not row:
        if own_conn:
            conn.close()
        return
    
    new_wager = row['wager_amount'] or 0
    new_delta = row['delta_total'] or 0
    new_game_id = row['game_id']
    
    old_wager = old_values.get('wager_amount', 0) or 0
    old_delta = old_values.get('delta_total', 0) or 0
    old_game_id = old_values.get('game_id')
    
    # Handle game_id change (remove from old, add to new)
    if old_game_id != new_game_id:
        if old_game_id:
            # Remove from old game
            self.update_game_rtp_incremental(
                old_game_id, -old_wager, -old_delta, False, conn
            )
        if new_game_id:
            # Add to new game
            self.update_game_rtp_incremental(
                new_game_id, new_wager, new_delta, False, conn
            )
    else:
        # Same game - apply deltas
        if new_game_id:
            wager_delta = new_wager - old_wager
            delta_delta = new_delta - old_delta
            if wager_delta != 0 or delta_delta != 0:
                self.update_game_rtp_incremental(
                    new_game_id, wager_delta, delta_delta, False, conn
                )
    
    if own_conn:
        conn.commit()
        conn.close()
```

# Part D — Fallback Conditions
When to use full rebuild instead of scoped:

## Scenario A: NULL/Missing Timestamps
- **Action:** Treat NULL time as '00:00:00', proceed with scoped
- **Rationale:** Safe default, maintains chronological order

## Scenario B: No Containing Session Found
- **Transaction type:** Purchase, redemption, or any timestamped transaction
- **Action:** Use transaction timestamp as boundary T
- **Rationale:** Earliest possible affected point, rebuild everything after

## Scenario C: Transaction Before All Sessions
- **Action:** Use transaction timestamp as boundary T
- **Rationale:** Rebuild all sessions (they're all >= T)

## Scenario D: Site/User Pair Changes
- **Action:** Run scoped rebuild on BOTH old and new pairs
- **Rationale:** Both pairs affected, but can scope each independently

## Scenario E: Multiple Transactions Same Timestamp
- **Action:** Rebuild from that timestamp
- **Rationale:** Deterministic ordering (by id) handles ties

## Scenario F: Boundary Computation Error
- **Action:** Fallback to full rebuild
- **Rationale:** Safety - don't risk incorrect results

## Scenario G: Missing Allocations Detected
- **Action:** Fallback to full rebuild
- **During:** Suffix scan finds non-free redemption with missing allocations
- **Rationale:** FIFO state may be corrupted, undo+replay unreliable

## Scenario H: Checkpoint Validation Fails
- **Action:** Process all sessions before T without writing (Option B), or fallback to full
- **Checks:** 
  - Previous session ending_balance/locked_sc not NULL
  - No negative balances
  - Timestamps monotonic
- **Rationale:** Cannot trust checkpoint state

# Part E — Checkpoint Seeding Logic

## Session Chain Checkpoint (Hybrid Approach)
Default to fast checkpoint read (Option A) with validation, fallback to recompute (Option B).

### Option A (Default - Fast):
```python
def _get_session_checkpoint(self, site_id, user_id, boundary_date, boundary_time):
    """Get checkpoint state from last closed session before boundary."""
    conn = self.db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, end_date, end_time, ending_balance, locked_sc
        FROM game_sessions
        WHERE site_id = ? AND user_id = ? AND closed = 1
          AND (start_date < ? OR (start_date = ? AND start_time < ?))
        ORDER BY 
          COALESCE(end_date, start_date) DESC,
          COALESCE(end_time, start_time) DESC
        LIMIT 1
    """, (site_id, user_id, boundary_date, boundary_date, boundary_time))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # No prior session - start from zero
        return {'ending_balance': 0, 'locked_sc': 0}
    
    # Validate checkpoint
    if row['ending_balance'] is None or row['locked_sc'] is None:
        raise CheckpointValidationError("Checkpoint has NULL values")
    
    if row['ending_balance'] < 0 or row['locked_sc'] < 0:
        raise CheckpointValidationError("Checkpoint has negative values")
    
    return {
        'ending_balance': row['ending_balance'],
        'locked_sc': row['locked_sc'],
        'checkpoint_id': row['id']
    }
```

### Option B (Fallback - Recompute):
If validation fails, process all sessions before T without writing to derive checkpoint state.

## FIFO Checkpoint (Undo+Replay - No Explicit Seeding)
The undo+replay pattern automatically restores correct FIFO state:
1. Undo allocations for redemptions >= T → restores purchases.remaining_amount
2. Replay redemptions >= T → recreates allocations

**No explicit seeding needed** - FIFO state is derived from allocations.

**Free SC validation** happens in Part A step 2 (before undo) - see `_rebuild_fifo_for_pair_from()` for details.

# Acceptance Criteria (manual checks)
1) Edit a redemption date earlier: only suffix recompute runs, FIFO allocations + remaining amounts update correctly, and impacted sessions/tax rows update.
2) Sessions spanning multiple days: boundary is the containing session start, not start-of-day.
3) Full rebuild still works and produces same results.
4) Edits that change site/user trigger scoped recompute for BOTH old and new pairs.
5) No global resets in scoped mode (no resetting ALL purchases remaining_amount).
6) RTP updates for any session whose wager or delta_total changes during rebuild.
7) Notes-only edits skip recomputation entirely.
8) Wager-only edits update RTP but skip FIFO/tax recomputation.
9) Checkpoint validation catches corrupted state and falls back appropriately.
10) Free SC redemptions handled correctly (no allocations expected).

Proceed with implementation now. Make minimal, well-scoped changes and keep deterministic ordering.