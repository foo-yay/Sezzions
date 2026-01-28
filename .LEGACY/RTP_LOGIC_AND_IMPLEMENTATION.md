# RTP (Return to Player) Logic and Implementation

## Overview

The RTP (Return to Player) system tracks cumulative game performance across all sessions for each game. It provides two levels of RTP:

1. **Per-Session RTP**: Individual session performance (already existed)
2. **Actual Game RTP**: Cumulative performance across all sessions for a game (newly implemented)

---

## Core RTP Formula

### Per-Session RTP (Existing)
```
session_rtp = ((wager_amount + delta_total) / wager_amount) * 100
```

**Components**:
- `wager_amount`: SC wagered in the session
- `delta_total`: Net SC change during session (ending_total_sc - starting_total_sc)
- Result: Percentage of wager retained by player

**Example**:
- Wager 1000 SC, delta_total = -100 SC (loss)
- RTP = ((1000 + (-100)) / 1000) × 100 = **90%** (player keeps 90% of wager)

---

### Actual Game RTP (New - Cumulative)
```
actual_rtp = ((total_wager + sum_of_all_deltas) / total_wager) * 100
```

**Components**:
- `total_wager`: Sum of all wager_amounts for the game (across all sessions)
- `sum_of_all_deltas`: Sum of all delta_total values for the game
- Result: Cumulative RTP percentage for the entire game

**Example**:
- Session 1: Wager 1000 SC, delta_total = +100 SC (win)
- Session 2: Wager 500 SC, delta_total = -200 SC (loss)
- Total: Wager 1500 SC, sum_delta = -100 SC
- Actual RTP = ((1500 + (-100)) / 1500) × 100 = **93.33%**

---

## Database Schema

### New Table: `game_rtp_aggregates`
```sql
CREATE TABLE game_rtp_aggregates (
    game_id INTEGER PRIMARY KEY REFERENCES games(id),
    total_wager REAL DEFAULT 0,           -- Sum of all wager_amount
    total_delta REAL DEFAULT 0,           -- Sum of all delta_total
    session_count INTEGER DEFAULT 0,      -- Count of sessions with wager_amount > 0
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Modified Table: `games`
```sql
ALTER TABLE games ADD COLUMN actual_rtp REAL DEFAULT 0;
```

**Fields**:
- `actual_rtp`: Calculated field (derived from aggregates)
- `rtp`: Expected RTP (user-provided baseline)

---

## Update Strategy: Streaming Aggregates + Full Recalculation

### Incremental Updates (O(1) Operation)

**When Called**:
- Session is closed/edited via `_rebuild_session_tax_fields_for_pair()`
- Session is deleted
- Triggered by any change to `wager_amount` or `delta_total`

**Process**:
```
1. Load current aggregates for game
2. Calculate deltas:
   - wager_delta = new_wager - old_wager
   - delta_total_delta = new_delta_total - old_delta_total
3. Apply deltas:
   - total_wager += wager_delta
   - total_delta += delta_total_delta
   - if new session: session_count += 1
4. Recalculate actual_rtp = ((total_wager + total_delta) / total_wager) * 100
5. Update games.actual_rtp
```

**Efficiency**: No DB traversal; uses cached aggregates.

---

### Full Recalculation (O(N) SQL Aggregation)

**When Called**:
- User clicks "Recalculate RTP" button in View Game dialog
- Explicit, manual operation for perfect accuracy

**Process**:
```
1. Delete existing aggregates for game
2. Query all closed game_sessions for the game:
   SELECT 
       SUM(wager_amount) as total_wager,
       SUM(delta_total) as total_delta,
       COUNT(*) as session_count
   FROM game_sessions
   WHERE game_id = X AND status = 'Closed'
3. Insert fresh aggregates
4. Recalculate actual_rtp = ((total_wager + total_delta) / total_wager) * 100
5. Update games.actual_rtp
```

**Efficiency**: Single SQL GROUP BY query (efficient even with thousands of sessions).

---

## Implementation Details

### File: `database.py` — Migration 12

Adds the new schema:
- Creates `game_rtp_aggregates` table
- Adds `actual_rtp` column to `games` table
- Idempotent (safe to re-run)

---

### File: `business_logic.py` — `SessionManager` Class

**Method 1: `update_game_rtp_incremental(game_id, wager_delta, delta_total_delta, new_session=False)`**

- **Purpose**: Apply delta to aggregates (incremental update)
- **Complexity**: O(1)
- **Usage**: Called from session rebuild for every session update
- **Safety**: Handles first session (initializes aggregates if none exist)

**Method 2: `recalculate_game_rtp_full(game_id)`**

- **Purpose**: Full recalculation from scratch
- **Complexity**: O(N) via SQL aggregation
- **Usage**: User-triggered via "Recalculate RTP" button
- **Safety**: Starts fresh, avoids accumulated drift

**Method 3: `_recalculate_game_rtp_from_aggregates(game_id, conn=None)`**

- **Purpose**: Internal helper to apply RTP formula
- **Complexity**: O(1)
- **Usage**: Called by both incremental and full methods
- **Reusable**: Accepts optional connection for batching

**Method 4: `remove_session_from_game_rtp(game_id, wager_amount, delta_total)`**

- **Purpose**: Reverse a session's RTP contribution (deletion)
- **Complexity**: O(1)
- **Usage**: Called when session is deleted
- **Behavior**: Applies negative deltas

---

### File: `business_logic.py` — Integration in `_rebuild_session_tax_fields_for_pair()`

**Location**: After session UPDATE statement (lines ~1020-1040)

**Logic**:
```python
# For each session being rebuilt:
if session.get('game_id') and wager:
    # Load old values
    old_wager = session.get('wager_amount', 0.0)
    old_delta_total = session.get('delta_total', 0.0)
    
    # Calculate deltas
    wager_delta = new_wager - old_wager
    delta_total_delta = new_delta_total - old_delta_total
    
    # Detect if session is "new" to RTP (had no wager, now has wager)
    is_new_session = (old_wager == 0) and (new_wager > 0)
    
    # Update aggregates
    self.update_game_rtp_incremental(game_id, wager_delta, delta_total_delta, is_new_session)
```

**Timing**: Triggered for every session during rebuild, AFTER tax field updates.

---

### File: `qt_app.py` — Session Deletion Integration

**Location**: `_delete_selected()` method (lines ~8082-8130)

**Logic**:
```python
# Before deleting session:
if session.get('game_id'):
    self.session_mgr.remove_session_from_game_rtp(
        session['game_id'],
        session.get('wager_amount'),
        session.get('delta_total')
    )

# Then proceed with deletion
c.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
```

**Timing**: Called BEFORE session is deleted, reverses RTP contribution.

---

### File: `qt_app.py` — UI Button in `GameViewDialog`

**Location**: `GameViewDialog` class (lines ~12798-12860)

**Button**: "Recalculate RTP" placed in button row alongside Delete/Edit/Close

**Handler**: `_handle_recalc_rtp()`
```python
def _handle_recalc_rtp(self):
    """Handle Recalculate RTP button click"""
    db = Database()
    fifo = FIFOCalculator(db)
    session_mgr = SessionManager(db, fifo)
    
    game_id = self.game.get('id')
    if game_id:
        session_mgr.recalculate_game_rtp_full(game_id)
        QtWidgets.QMessageBox.information(self, "Success", f"RTP recalculated for '{self.game['name']}'")
```

**User Experience**:
1. User opens View Game dialog
2. Clicks "Recalculate RTP" button
3. Full SQL aggregation runs
4. Success message displayed
5. Dialog can be closed

---

## UI Display Changes

### Games Tab Table — Expected vs Actual RTP Columns

**Location**: `GamesSetupTab.load_data()` (lines ~14000-14130)

**Changes**:
- Updated column headers from `["Name", "Game Type", "RTP", ...]` to `["Name", "Game Type", "Expected RTP", "Actual RTP", ...]`
- Modified SQL query to fetch both `g.rtp` (Expected) and `g.actual_rtp` (Actual)
- Both RTP columns formatted as numeric with 2 decimal places
- Displays side-by-side comparison for all games in setup table

**User Experience**:
- Quick visual comparison of configured (Expected) vs measured (Actual) RTP
- Identifies games performing above/below expected RTP at a glance

---

### View Game Dialog — Dual RTP Display

**Location**: `GameViewDialog` initialization (lines ~12835-12847)

**Changes**:
- Added separate field for "Expected RTP %" (existing `rtp` field from games table)
- Added new field for "Actual RTP %" (calculated from aggregates)
- Both fields displayed as read-only in game details view
- "Recalculate RTP" button allows manual refresh of Actual RTP

**User Experience**:
- View dialog shows both baseline (Expected) and live performance (Actual)
- Clear labeling distinguishes user-configured vs calculated values

---

### Start/Edit Session Dialogs — RTP Tooltip

**Location**: 
- `GameSessionStartDialog._update_rtp_tooltip()` (lines ~2667-2695)
- `GameSessionEditDialog._update_rtp_tooltip()` (lines ~3609-3637)

**Changes**:
- Added `rtp_tooltip` QLabel widget below game dropdown
- Tooltip queries database for selected game's Expected and Actual RTP
- Displays format: `"Exp RTP: 95.00% / Act RTP: 93.50%"` (or "N/A" if missing)
- Updates dynamically when user changes game selection
- Light gray styling to differentiate from primary form fields

**Implementation Details**:
```python
def _update_rtp_tooltip(self):
    game_id = self.game_combo.currentData()
    if game_id:
        conn = Database.get_connection()
        c = conn.cursor()
        c.execute("SELECT rtp, actual_rtp FROM games WHERE id = ?", (game_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            exp_rtp = f"{row['rtp']:.2f}" if row['rtp'] else "N/A"
            act_rtp = f"{row['actual_rtp']:.2f}" if row['actual_rtp'] else "N/A"
            self.rtp_tooltip.setText(f"Exp RTP: {exp_rtp}% / Act RTP: {act_rtp}%")
```

**User Experience**:
- Provides RTP context during session creation/editing
- Helps users make informed decisions about session planning
- No extra clicks required — automatic display when game selected

---

## Data Flow: Session Lifecycle

### 1. Session Creation (New Wager)
```
UI creates session with wager_amount = 100 SC
→ Session initially Active (no end_date/time)
→ RTP not yet calculated (no delta_total)
→ No RTP contribution yet
```

### 2. Session Closure (Completion)
```
User ends session, sets ending_balance
→ _rebuild_session_tax_fields_for_pair() called
→ Calculates delta_total from balances
→ Calculates per-session RTP
→ Calls update_game_rtp_incremental():
    - old_wager = 0 (new session)
    - old_delta_total = NULL
    - is_new_session = True
    - Adds to aggregates
    - Recalculates game RTP
→ games.actual_rtp updated
```

### 3. Session Edit (Change Wager or Outcome)
```
User edits session wager or ending balance
→ _rebuild_session_tax_fields_for_pair() called
→ Calculates new delta_total
→ Calls update_game_rtp_incremental():
    - old_wager = previous value
    - old_delta_total = previous value
    - is_new_session = False (already in aggregates)
    - Applies delta changes
    - Recalculates game RTP
→ games.actual_rtp updated
```

### 4. Session Deletion
```
User deletes session
→ Qt UI calls _delete_selected()
→ Calls remove_session_from_game_rtp():
    - Applies negative deltas
    - Decrements session_count
    - Recalculates game RTP
→ games.actual_rtp updated
→ Session deleted from DB
```

### 5. Manual Full Recalculation
```
User clicks "Recalculate RTP" in View Game
→ Calls recalculate_game_rtp_full()
→ Deletes old aggregates
→ SQL query sums ALL closed sessions
→ Inserts fresh aggregates
→ Recalculates game RTP
→ games.actual_rtp updated
→ Success message shown
```

---

## Edge Cases & Safety

### Edge Case 1: First Session for Game
**Issue**: Aggregates don't exist
**Solution**: `update_game_rtp_incremental()` detects None, initializes with new values

### Edge Case 2: Session with Zero Wager
**Issue**: RTP = 0 / 0 (undefined)
**Solution**: Filtered by `if wager and float(wager) > 0` in session rebuild
- Sessions with zero wager are excluded from RTP
- No delta applied to aggregates

### Edge Case 3: Game Reassignment
**Issue**: Session moves to different game
**Handling**: 
- Reverse old game's RTP (negative delta)
- Add to new game's RTP (positive delta)
- Requires old game_id to know which aggregates to update

### Edge Case 4: Negative Total Wager (Shouldn't Happen)
**Safety**: `total_wager = max(0, new_wager)` prevents negative aggregates

### Edge Case 5: Empty Game (No Sessions)
**Behavior**: `actual_rtp = 0` (no aggregates exists)
- Games with no sessions show RTP = 0
- Distinguishable from games with data via `session_count = 0`

---

## Performance Profile

| Operation | Complexity | Example Time |
|-----------|-----------|--------------|
| Incremental update (1 session) | O(1) | <1ms |
| Batch update (100 sessions) | O(100) | ~10ms |
| Full recalc (10,000 sessions) | O(N) via SQL | ~50-100ms |

**Key Insight**: Incremental updates are extremely fast; full recalc acceptable as manual, explicit operation.

---

## Validation & Verification

### Verify Aggregates Are Correct
```sql
-- Check totals match DB
SELECT 
    game_id,
    (SELECT SUM(wager_amount) FROM game_sessions WHERE game_id = gra.game_id AND status='Closed') as check_wager,
    total_wager,
    (SELECT SUM(delta_total) FROM game_sessions WHERE game_id = gra.game_id AND status='Closed') as check_delta,
    total_delta
FROM game_rtp_aggregates gra;
```

### Verify RTP Calculation
```sql
-- Check RTP matches formula
SELECT 
    id,
    name,
    actual_rtp,
    CASE 
        WHEN total_wager > 0 THEN ROUND(((total_wager + total_delta) / total_wager) * 100, 2)
        ELSE 0
    END as calculated_rtp
FROM games g
JOIN game_rtp_aggregates a ON g.id = a.game_id;
```

---

## Testing Scenarios

### Test 1: Create Session, Close Session
```
1. Create game "Test Game"
2. Create session: start 1000 SC, end 1100 SC (wager 100, delta +100)
3. Verify game.actual_rtp = ((100 + 100) / 100) * 100 = 200%
```

### Test 2: Multiple Sessions
```
1. Session A: wager 100, delta +50 → RTP = 150%
2. Session B: wager 100, delta -25 → RTP = 75%
3. Combined: wager 200, delta +25 → actual_rtp = ((200 + 25) / 200) * 100 = 112.5%
```

### Test 3: Edit Session (Change Outcome)
```
1. Session: wager 100, delta +50 (RTP = 150%)
2. Edit session: delta becomes -50 (loss)
3. Delta change: -50 - (+50) = -100
4. New RTP: ((100 + (-50)) / 100) * 100 = 50%
5. Verify aggregates updated correctly
```

### Test 4: Delete Session
```
1. Game has 2 sessions: wager 200, delta +50
2. Delete session 1 (wager 100, delta +25)
3. Remaining: wager 100, delta +25
4. New RTP: ((100 + 25) / 100) * 100 = 125%
```

### Test 5: Full Recalculation
```
1. Manually corrupt aggregates (set total_wager = 999999)
2. Click "Recalculate RTP"
3. Verify aggregates rebuilt from scratch
4. RTP restored to correct value
```

---

## Summary

The RTP system uses **streaming aggregates** for efficiency with an optional **full recalculation** for accuracy. This provides:

- ✅ **O(1) Updates**: Fast incremental changes when sessions close/edit
- ✅ **O(N) Full Recalc**: Accurate rebuilding via SQL aggregation when needed
- ✅ **User Control**: "Recalculate RTP" button allows explicit full traversal
- ✅ **Data Integrity**: Aggregates always match session data (verified by full recalc)
- ✅ **Scalability**: Handles thousands of sessions efficiently

This design balances real-time responsiveness (incremental) with audit compliance (full recalc).
