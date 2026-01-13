# Recalculation Scope Optimization Analysis

## Executive Summary

**Problem**: When editing a single game session record (e.g., changing wager amount), the system currently recalculates ALL sessions for the entire (site_id, user_id) pair. For users with 10,000+ sessions, this creates performance bottlenecks.

**Goal**: Reduce recalculation scope from entire pair to only affected records (~50-1000 sessions) while maintaining accounting accuracy.

**Current State**: Working but inefficient - edit 1 record triggers 10,000+ session recalculations.

---

## 1. Current Implementation

### 1.1 Code Flow (business_logic.py)

**Entry Point**: `auto_recalculate_affected_sessions()` (line 1183)
```python
def auto_recalculate_affected_sessions(self, site_id, user_id, 
                                       changed_date, changed_time, 
                                       old_session_values=None):
    """
    After editing/deleting/adding a purchase/redemption/session,
    recalculate affected sessions for (site, user).
    
    Parameters:
    - old_session_values: dict with {session_id, wager_amount, delta_total, game_id}
                         Used for incremental RTP updates
    """
    self._rebuild_fifo_for_pair(site_id, user_id)
    self._rebuild_session_tax_fields_for_pair(site_id, user_id, old_session_values)
```

**Problem**: No scoping logic - always rebuilds entire pair.

---

**Rebuild Implementation**: `_rebuild_session_tax_fields_for_pair()` (line 873)
```python
def _rebuild_session_tax_fields_for_pair(self, site_id, user_id, old_session_values=None):
    """
    Recalculate tax fields for ALL sessions in (site, user) pair.
    """
    conn = self.db.get_connection()
    cursor = conn.cursor()
    
    # Query ALL sessions for pair (line 891)
    cursor.execute("""
        SELECT gs.id, gs.start_date, gs.start_time, gs.end_date, gs.end_time,
               gs.starting_balance, gs.ending_balance, gs.notes, gs.locked_sc,
               gs.closed, gs.wager_amount, gs.game_id, gs.delta_total
        FROM game_sessions gs
        WHERE gs.site_id = ? AND gs.user_id = ?
        ORDER BY gs.start_date, gs.start_time
    """, (site_id, user_id))
    
    sessions = cursor.fetchall()
    
    # Process every session chronologically
    for s in sessions:
        # Calculate expected balance from previous session...
        # Calculate tax fields...
        # Update session in database...
        
        # RTP Update (line 1014) - only if this is the edited session
        if old_session_values and s['id'] == old_session_values.get('session_id'):
            # Calculate deltas using old vs new values
            wager_delta = s['wager_amount'] - old_session_values.get('wager_amount', 0)
            delta_total_delta = s['delta_total'] - old_session_values.get('delta_total', 0)
            
            # Update RTP aggregates incrementally
            self.update_game_rtp_incremental(
                s['game_id'], wager_delta, delta_total_delta, 
                s['delta_total'], conn
            )
```

**Performance Issue**: Processes ALL sessions even if only 1 changed.

---

### 1.2 RTP System (Working Correctly)

**Migration 12** (database.py):
- Created `game_rtp_aggregates` table (total_wager, total_delta, session_count per game)
- Added `actual_rtp` column to `games` table
- Formula: `((total_wager + total_delta) / total_wager) * 100`

**Incremental Update** (business_logic.py line 1267):
```python
def update_game_rtp_incremental(self, game_id, wager_delta, delta_total_delta, 
                               new_session, conn=None):
    """
    Update RTP aggregates and recalculate actual_rtp.
    
    Parameters:
    - wager_delta: change in wager (new - old)
    - delta_total_delta: change in delta_total (new - old)
    - new_session: True if adding new session, False if editing
    - conn: reuse connection to prevent locks
    """
    own_conn = conn is None
    if own_conn:
        conn = self.db.get_connection()
    
    cursor = conn.cursor()
    
    # Get or create aggregate record
    cursor.execute("""
        SELECT total_wager, total_delta, session_count 
        FROM game_rtp_aggregates 
        WHERE game_id = ?
    """, (game_id,))
    
    row = cursor.fetchone()
    if row:
        total_wager = row['total_wager'] + wager_delta
        total_delta = row['total_delta'] + delta_total_delta
        session_count = row['session_count'] + (1 if new_session else 0)
        
        cursor.execute("""
            UPDATE game_rtp_aggregates 
            SET total_wager = ?, total_delta = ?, session_count = ?
            WHERE game_id = ?
        """, (total_wager, total_delta, session_count, game_id))
    else:
        # Create new aggregate
        ...
    
    # Recalculate actual_rtp from aggregates
    self._recalculate_game_rtp_from_aggregates(game_id, conn)
    
    if own_conn:
        conn.commit()
        conn.close()
```

**Status**: ✅ Working correctly with incremental updates, no double-counting.

---

### 1.3 Database Schema (Relevant Tables)

**game_sessions**:
```sql
CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY,
    site_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    game_id INTEGER,  -- Added in migration 13
    start_date TEXT NOT NULL,  -- YYYY-MM-DD
    start_time TEXT NOT NULL,  -- HH:MM:SS
    end_date TEXT,
    end_time TEXT,
    starting_balance REAL,
    ending_balance REAL,
    wager_amount REAL,  -- Total wagered during session
    delta_total REAL,   -- ending_balance - starting_balance
    locked_sc REAL,
    closed INTEGER DEFAULT 0,
    expected_balance REAL,
    expected_starting_sc REAL,
    tax_session INTEGER DEFAULT 0,
    taxable_profit REAL DEFAULT 0,
    cost_basis_used REAL DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (game_id) REFERENCES games(id)
);
```

**purchases**:
```sql
CREATE TABLE purchases (
    id INTEGER PRIMARY KEY,
    site_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    time TEXT NOT NULL,  -- HH:MM:SS
    amount REAL NOT NULL,
    consumed REAL DEFAULT 0,  -- Used by FIFO
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**redemptions**:
```sql
CREATE TABLE redemptions (
    id INTEGER PRIMARY KEY,
    site_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    amount REAL NOT NULL,
    game_session_id INTEGER,  -- Links to tax session
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (game_session_id) REFERENCES game_sessions(id)
);
```

**game_rtp_aggregates**:
```sql
CREATE TABLE game_rtp_aggregates (
    game_id INTEGER PRIMARY KEY,
    total_wager REAL DEFAULT 0,
    total_delta REAL DEFAULT 0,
    session_count INTEGER DEFAULT 0,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
```

---

## 2. Accounting Rules (Must Preserve)

### 2.1 FIFO (First-In-First-Out)
- Purchases establish cost basis in chronological order
- Redemptions consume basis from oldest purchases first
- `purchases.consumed` tracks how much of each purchase is used
- Order critical: changing dates can affect FIFO chain

### 2.2 Session Tax Fields (Derived)
- `expected_balance`: Calculated from previous session ending + interim purchases/redemptions
- `tax_session`: Boolean flag if session closes at redemption
- `taxable_profit`: (redemption_amount - cost_basis_used) for tax sessions
- `cost_basis_used`: FIFO basis consumed by redemption

### 2.3 Chronological Dependency
- Each session depends on previous session's ending balance
- Sessions must be processed in (date, time) order
- Changing date/time of earlier session affects all later sessions

### 2.4 RTP (Return to Player)
- Aggregated per game across ALL sessions
- Formula: `((total_wager + total_delta) / total_wager) * 100`
- Incremental updates preferred over full recalculation
- NOT date-dependent (aggregates entire history)

---

## 3. Performance Metrics

**Current Scenario**:
- User has 10,000 sessions for (Site A, User 1)
- User edits 1 session: changes wager_amount from 5000 to 240
- System recalculates ALL 10,000 sessions

**Desired Scenario**:
- Edit 1 session → recalculate ~50-1000 sessions (those after the change)
- Non-financial edits (e.g., notes) → skip recalculation entirely

**Bottleneck**: `_rebuild_session_tax_fields_for_pair()` has no early exit logic.

---

## 4. Proposed Optimization Strategies

### 4.1 Field-Specific Skip Logic

**Concept**: Some fields don't affect accounting calculations.

**Field Classifications**:

**Financial Fields** (require recalculation):
- `wager_amount` - affects RTP only (incremental update)
- `starting_balance` - affects expected_balance chain
- `ending_balance` - affects expected_balance chain and delta_total
- `locked_sc` - affects available balance calculations
- `start_date`, `start_time` - affects chronological order (FIFO)
- `end_date`, `end_time` - affects chronological order
- `site_id`, `user_id` - affects which pair to recalculate

**Non-Financial Fields** (can skip recalculation):
- `notes` - purely descriptive
- `game_id` - only affects RTP grouping (if changed, update old and new game RTPs)

**Implementation**:
```python
def auto_recalculate_affected_sessions(self, site_id, user_id, changed_date, 
                                       changed_time, old_session_values=None):
    # If only non-financial fields changed, skip recalculation
    if old_session_values:
        financial_fields = ['wager_amount', 'starting_balance', 'ending_balance', 
                           'locked_sc', 'start_date', 'start_time', 'end_date', 'end_time']
        
        # Check if any financial field changed
        needs_recalc = any(
            old_session_values.get(field) != new_session_values.get(field) 
            for field in financial_fields
        )
        
        if not needs_recalc:
            # Only update RTP if game_id changed
            if old_session_values.get('game_id') != new_session_values.get('game_id'):
                # Update both old and new game RTPs
                pass
            return  # Skip full recalculation
    
    # Continue with full or scoped recalculation...
```

---

### 4.2 Time-Windowed Rebuild

**Concept**: Only recalculate sessions >= changed_date/time.

**Assumptions**:
1. Sessions before change_date are unaffected
2. Can use previous session's ending as checkpoint
3. FIFO state at checkpoint is valid

**Implementation Sketch**:
```python
def _rebuild_session_tax_fields_for_pair(self, site_id, user_id, 
                                         old_session_values=None,
                                         start_from_date=None, 
                                         start_from_time=None):
    """
    Recalculate sessions starting from specific date/time.
    """
    conn = self.db.get_connection()
    cursor = conn.cursor()
    
    if start_from_date:
        # Query only sessions >= start_from_date
        cursor.execute("""
            SELECT ... FROM game_sessions gs
            WHERE gs.site_id = ? AND gs.user_id = ?
              AND (gs.start_date > ? OR 
                   (gs.start_date = ? AND gs.start_time >= ?))
            ORDER BY gs.start_date, gs.start_time
        """, (site_id, user_id, start_from_date, start_from_date, start_from_time))
        
        # Get checkpoint: last session before start_from_date
        cursor.execute("""
            SELECT ending_balance, locked_sc
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND (start_date < ? OR 
                   (start_date = ? AND start_time < ?))
            ORDER BY start_date DESC, start_time DESC
            LIMIT 1
        """, (site_id, user_id, start_from_date, start_from_date, start_from_time))
        
        checkpoint = cursor.fetchone()
        previous_ending = checkpoint['ending_balance'] if checkpoint else 0
    else:
        # Full rebuild (current behavior)
        cursor.execute("""
            SELECT ... FROM game_sessions gs
            WHERE gs.site_id = ? AND gs.user_id = ?
            ORDER BY gs.start_date, gs.start_time
        """, (site_id, user_id))
        previous_ending = 0
    
    # Process sessions from checkpoint forward
    sessions = cursor.fetchall()
    for s in sessions:
        # Calculate expected_balance from previous_ending + interim transactions
        # Update session...
        previous_ending = s['ending_balance']
```

**Optimization**: Instead of 10,000 sessions, process ~50-1000 sessions.

---

### 4.3 Combined Approach

**Recommended Strategy**:
1. Check if financial fields changed (field-specific skip)
2. If changed, determine scope (time-windowed rebuild)
3. Keep "Recalculate Everything" as manual fallback

**Pseudo-code**:
```python
def auto_recalculate_affected_sessions(self, site_id, user_id, changed_date, 
                                       changed_time, old_session_values=None):
    # Step 1: Check if recalculation needed
    if old_session_values:
        financial_fields_changed = self._check_financial_changes(old_session_values)
        
        if not financial_fields_changed:
            # Skip recalculation, maybe update RTP for game_id change
            return
    
    # Step 2: Determine scope
    if changed_date and not self._requires_full_rebuild(old_session_values):
        # Time-windowed rebuild
        self._rebuild_fifo_for_pair(site_id, user_id, start_from=changed_date)
        self._rebuild_session_tax_fields_for_pair(
            site_id, user_id, old_session_values,
            start_from_date=changed_date, start_from_time=changed_time
        )
    else:
        # Full rebuild (current behavior)
        self._rebuild_fifo_for_pair(site_id, user_id)
        self._rebuild_session_tax_fields_for_pair(site_id, user_id, old_session_values)
```

---

## 5. Edge Cases & Roadblocks

### 5.1 Backward Date Changes
**Scenario**: Edit session from 2025-06-15 → change date to 2025-01-10.

**Problem**: 
- Time-windowed rebuild starting from 2025-06-15 misses the moved session
- FIFO order changes (session now comes earlier)
- All sessions from 2025-01-10 onward affected

**Detection**:
```python
if old_session_values.get('start_date') > new_session_date:
    # Backward date change - must rebuild from new_session_date
    start_from_date = new_session_date
```

---

### 5.2 Gap Transactions (Purchases/Redemptions)
**Scenario**: 
- Edit session on 2025-06-15
- There's a purchase on 2025-06-10 (between checkpoint and target)
- Checkpoint doesn't account for this purchase

**Problem**: 
- `expected_balance` calculation needs interim transactions
- Current code queries purchases/redemptions for each session individually

**Current Code** (line 932):
```python
# For each session, query purchases/redemptions since previous session
cursor.execute("""
    SELECT SUM(amount) FROM purchases
    WHERE site_id = ? AND user_id = ?
      AND (date > ? OR (date = ? AND time > ?))
      AND (date < ? OR (date = ? AND time <= ?))
""", (site_id, user_id, prev_date, prev_date, prev_time, 
      s['start_date'], s['start_date'], s['start_time']))
```

**Solution**: This is already handled correctly - code queries transactions for each session window.

---

### 5.3 FIFO Order Within Same Day
**Scenario**: 
- Three sessions on 2025-06-15 at 10:00, 12:00, 14:00
- Edit 12:00 session's time to 11:00

**Problem**: 
- Time change affects order
- FIFO recalculation must include all sessions on that date

**Detection**:
```python
if old_session_values.get('start_time') != new_session_time:
    # Time changed - rebuild from start of that date
    start_from_date = new_session_date
    start_from_time = "00:00:00"
```

---

### 5.4 Deletion Creates Basis Shortage
**Scenario**:
- Session 1 (June 1): Purchase $100
- Session 2 (June 15): Tax session uses $100 basis
- Delete Session 1 purchase

**Problem**:
- Session 2 now has no basis available
- Must recalculate from deletion point to detect shortage

**Current Behavior**: Deletion triggers full rebuild (correct).

---

### 5.5 Site/User Pair Changes
**Scenario**: Edit session, change site_id from 1 → 2.

**Problem**: 
- Affects TWO pairs: (old_site, user) and (new_site, user)
- Both pairs need recalculation

**Detection**:
```python
if old_session_values.get('site_id') != new_site_id:
    # Recalculate both old and new pairs
    self.auto_recalculate_affected_sessions(old_site_id, user_id, ...)
    self.auto_recalculate_affected_sessions(new_site_id, user_id, ...)
```

---

### 5.6 Orphaned Redemption
**Scenario**:
- Session 1: Tax session with redemption linked (game_session_id)
- Edit Session 1: change ending_balance so it's no longer a tax session

**Problem**:
- Redemption still links to Session 1 (game_session_id)
- But Session 1 is no longer tax_session=1
- Data inconsistency

**Current Code** (line 967):
```python
# If session closes at redemption, mark as tax session
cursor.execute("""
    SELECT id FROM redemptions
    WHERE site_id = ? AND user_id = ?
      AND date = ? AND time BETWEEN ? AND ?
""", (...))

redemptions_at_end = cursor.fetchall()
if redemptions_at_end:
    tax_session = 1
    # Calculate taxable profit...
else:
    tax_session = 0
```

**Potential Issue**: Code resets tax_session correctly, but redemption.game_session_id not cleared.

**Solution**: Add cleanup logic:
```python
if tax_session == 0 and old_tax_session == 1:
    # Unlink redemptions that were linked to this session
    cursor.execute("""
        UPDATE redemptions SET game_session_id = NULL
        WHERE game_session_id = ?
    """, (session_id,))
```

---

### 5.7 Expected Balance Depends on Future Transactions
**Scenario**:
- Session 1 (June 1): ending_balance = 1000
- Purchase (June 5): +500
- Session 2 (June 10): expected_starting = 1500

**Problem**: 
- If we start rebuild from June 10 using Session 1 as checkpoint
- We miss the June 5 purchase
- Session 2 expected_balance wrong

**Current Solution**: Code already queries transactions per session window (see 5.2).

---

### 5.8 Pending Basis Pool
**Scenario**:
- Purchase 1 (Jan 1): $100, consumed=0
- No sessions for 6 months
- Session 1 (July 1): Tax session, should use Jan 1 purchase

**Problem**: 
- FIFO state includes "pending" purchases not yet consumed
- Checkpoint must include FIFO state, not just session ending

**Current Code**: `_rebuild_fifo_for_pair()` recalculates FIFO separately.

**Issue**: If we scope FIFO rebuild to date range, we might miss pending purchases before that range.

**Solution**: FIFO rebuild must start from beginning OR maintain FIFO state at checkpoint.

---

### 5.9 Locked-to-Redeemable Conversion
**Scenario**:
- Session 1 (June 1): locked_sc = 500 (promo balance)
- Session 2 (June 15): locked_sc released, becomes redeemable

**Problem**: 
- Balance calculations involve locked vs redeemable
- Checkpoint must include both values

**Current Schema**: 
- `starting_balance` (redeemable)
- `locked_sc` (locked/promo)

**Solution**: Checkpoint needs both values (already in schema).

---

### 5.10 RTP Double-Counting Prevention
**Scenario**: Edit session → rebuild triggers → should only update RTP once.

**Problem**: 
- During rebuild, if we treat edited session as "new", RTP gets double-counted
- Must use deltas (new - old) not absolute values

**Current Solution** (line 1014):
```python
if old_session_values and s['id'] == old_session_values.get('session_id'):
    # Calculate deltas
    wager_delta = s['wager_amount'] - old_session_values.get('wager_amount', 0)
    delta_total_delta = s['delta_total'] - old_session_values.get('delta_total', 0)
    
    # Incremental update
    self.update_game_rtp_incremental(s['game_id'], wager_delta, delta_total_delta, 
                                     False, conn)  # new_session=False
```

**Status**: ✅ Already handled correctly.

---

### 5.11 Circular Dependency: Session → Expected → Session
**Scenario**: 
- Session A expected_balance depends on Session B ending_balance
- But Session B might need recalculation too

**Problem**: 
- If we use Session B as checkpoint, but Session B itself needs recalc
- Checkpoint is invalid

**Solution**: 
- Only use sessions BEFORE change date as checkpoint (guaranteed unaffected)
- OR: Always recalculate from beginning if change date moves backward

---

## 6. Critical Decision Questions

### 6.1 Checkpoint Trust
**Question**: Can we trust checkpoint data without recalculating it?

**Options**:
A) Trust checkpoint (faster, risky if checkpoint is stale)
B) Always recalculate checkpoint (safer, defeats optimization)
C) Validate checkpoint before use (middle ground)

**Recommendation**: Option C - quick validation:
```python
# Check if checkpoint session needs recalculation
cursor.execute("""
    SELECT COUNT(*) FROM game_sessions
    WHERE site_id = ? AND user_id = ?
      AND start_date = ? 
      AND id < ?
      AND (tax_session IS NULL OR expected_balance IS NULL)
""", (site_id, user_id, checkpoint_date, checkpoint_id))

if cursor.fetchone()[0] > 0:
    # Checkpoint is stale, do full rebuild
    start_from_date = None
```

---

### 6.2 Gap Transaction Handling
**Question**: How to handle purchases/redemptions between checkpoint and target?

**Current Code**: Already queries transactions per session window. ✅ No change needed.

---

### 6.3 Backward Date Change Limit
**Question**: How far back is "safe" to start windowed rebuild?

**Options**:
A) Always start from new date (safest, less optimization)
B) Start from old date if new date is later (optimal)
C) Define max lookback period (e.g., 30 days)

**Recommendation**: Option A for correctness.

---

### 6.4 Transaction Isolation
**Question**: What if another transaction edits data during rebuild?

**Current Code**: Uses single connection per rebuild (transaction isolation). ✅ Already safe.

---

### 6.5 Verification Strategy
**Question**: How to verify scoped rebuild produces same results as full rebuild?

**Options**:
A) Dual-run in testing (full + scoped, compare results)
B) Periodic full recalculation (nightly job)
C) Checksum validation (hash session tax fields)

**Recommendation**: Option A for initial rollout, Option B for production.

---

## 7. Implementation Phases (Proposed)

### Phase 1: Field-Specific Skip Logic
- Implement `_check_financial_changes()` 
- Skip recalculation for notes-only edits
- Low risk, immediate benefit

### Phase 2: Time-Windowed Rebuild (Forward Changes)
- Implement windowed query with checkpoint
- Only allow forward date changes initially
- Detect backward changes → fallback to full rebuild

### Phase 3: Checkpoint Validation
- Implement checkpoint staleness detection
- Add verification logging

### Phase 4: Backward Date Handling
- Implement logic to detect earliest affected date
- Extend windowing to backward changes

### Phase 5: Full Testing & Verification
- Dual-run testing (scoped vs full)
- Performance benchmarking
- Edge case testing

---

## 8. Code Locations Reference

### Key Files:
- `business_logic.py` (line 873-1100): `_rebuild_session_tax_fields_for_pair()`
- `business_logic.py` (line 1183-1210): `auto_recalculate_affected_sessions()`
- `business_logic.py` (line 1267-1365): RTP incremental update
- `qt_app.py` (line 8043-8150): `_save_closed_session()` with old_session_values

### Database Schema:
- `database.py` (migration 12): RTP aggregates
- `database.py` (migration 13): game_sessions.game_id

---

## 9. Testing Scenarios

### Minimal Test Cases:
1. **Notes-only edit**: Change notes field → verify no recalculation
2. **Wager edit**: Change wager → verify only RTP updates, no tax recalc
3. **Forward date**: Move session from June 1 → June 15 → verify only June 15+ recalc
4. **Backward date**: Move session from June 15 → June 1 → verify full recalc
5. **Same-day time change**: Change time on busy day → verify all same-day sessions recalc
6. **Gap transaction**: Edit session with purchase between checkpoint and target → verify expected_balance correct
7. **Site change**: Change site_id → verify both old and new pairs recalculated
8. **Performance**: 10,000 session pair, edit 1 session → measure time (before/after optimization)

### Validation:
- Compare scoped vs full rebuild results (must be identical)
- RTP aggregates must match session-by-session sum
- No orphaned redemption links

---

## 10. Risk Assessment

### High Risk (Must Handle):
1. **Backward date changes** - affects FIFO order and all downstream sessions
2. **FIFO state at checkpoint** - pending purchases must be tracked
3. **Pair changes** - must recalculate TWO pairs

### Medium Risk (Should Handle):
4. **Orphaned redemptions** - cleanup game_session_id links
5. **Checkpoint validation** - detect stale checkpoints
6. **Same-day time changes** - must include all same-day sessions

### Low Risk (Nice to Handle):
7. **Gap transactions** - already handled by per-session queries
8. **RTP double-counting** - already fixed with incremental updates
9. **Transaction isolation** - already handled by connection management

---

## 11. Alternative Approaches (Not Recommended)

### A. Lazy Recalculation
**Concept**: Don't recalculate until data is viewed.

**Problems**:
- Stale data risk
- Inconsistent state
- Violates accounting accuracy requirements

### B. Background Job
**Concept**: Queue recalculations, process async.

**Problems**:
- Adds complexity (job queue, worker threads)
- User sees stale data temporarily
- Overkill for desktop app

### C. Incremental Only (No Rebuild)
**Concept**: Track all changes, apply deltas only.

**Problems**:
- Complex state management
- Drift over time (small errors accumulate)
- Hard to debug/verify

---

## 12. Recommended Next Steps

1. **Decision Meeting**: Review edge cases, choose approach
2. **Spike Test**: Implement field-specific skip logic (Phase 1) - low risk, quick win
3. **Prototype**: Time-windowed rebuild for forward-only changes (Phase 2)
4. **Validation**: Dual-run testing comparing full vs scoped results
5. **Rollout**: Deploy with fallback to full rebuild if validation fails
6. **Monitor**: Track performance improvements and edge case frequency

---

## 13. Open Questions for Another AI Model

1. **Is there a safe way to checkpoint FIFO state?** Can we serialize pending purchases and resume FIFO from a specific date, or must we always start FIFO from the beginning?

2. **How to handle pair changes elegantly?** Currently suggests recalculating both old and new pairs fully - is there a smarter way?

3. **Checkpoint validation strategy?** What's the minimum check to ensure checkpoint is safe to use? Just check for NULL fields, or deeper validation?

4. **Backward date change handling?** Should we:
   - Always fallback to full rebuild (safe, defeats optimization)
   - Detect earliest affected date and start there (complex)
   - Use two-pass approach (rebuild affected range twice)

5. **Performance vs correctness tradeoff?** Where should we draw the line? Is 90% optimization with 100% correctness acceptable, or must we achieve 99% optimization?

6. **Edge case frequency?** In a typical 10,000-session database, how often do backward date changes, pair changes, and same-day time changes occur? Does optimization even matter if edge cases trigger full rebuild 50% of the time?

---

## Appendix: Sample Data Patterns

### Typical User Workflow:
- Records 20-50 sessions per month
- 2-5 purchases per month
- 1-2 redemptions per month
- Mostly appends (new sessions), rare edits

### Common Edit Patterns:
- Fix typos in notes (50%)
- Adjust ending balance slightly (30%)
- Change game_id (10%)
- Change date/time (5%)
- Change wager amount (5%)

**Insight**: 50% of edits are notes-only → field-specific skip logic yields big win.

---

## Appendix: Current Performance Baseline

**Test Environment**: MacOS, Python 3.11, SQLite

**Scenario**: Edit 1 session wager in 10,000-session pair

**Current Performance**: ~2-5 seconds (full rebuild)

**Target Performance**: <0.5 seconds (scoped rebuild)

**Measurement Code**:
```python
import time
start = time.time()
session_mgr.auto_recalculate_affected_sessions(site_id, user_id, ...)
elapsed = time.time() - start
print(f"Recalculation took {elapsed:.2f}s")
```

---

*Document compiled for external AI model review - January 12, 2026*
