# Casino Accounting Application - System Overview

## Application Purpose

A PySide6/Qt desktop application for tracking sweepstakes casino gameplay, managing cost basis using FIFO (First In, First Out) methodology, and calculating taxable profit/loss for IRS reporting purposes. The application handles multiple users across multiple casino sites with real-time tax calculations.

---

## Core Concepts

### Sweepstakes Casino Model
- **Sweeps Coins (SC)**: Virtual currency purchased with real money (1 SC ≈ $1)
- **Redeemable SC**: SC that can be cashed out for real money
- **Non-Redeemable SC (Locked)**: Promotional SC that must be played through before becoming redeemable
- **Freebies**: Bonus SC with no cost basis (not taxable when received, but winnings are taxable)

### Tax Accounting Philosophy
The application implements a **session-based FIFO tax accounting system**:
1. **Cost Basis Tracking**: Each purchase creates cost basis that gets consumed via FIFO when SC is redeemed
2. **Session P/L**: Calculate net taxable profit/loss per gaming session
3. **Redemption P/L**: Calculate realized gains/losses when cashing out
4. **Carryforward Basis**: Unused cost basis carries forward to future sessions

---

## Database Schema Overview

### Primary Tables

**Transactional Data:**
- `purchases` - Cash purchases of SC (creates cost basis)
- `redemptions` - SC cashed out for money (consumes cost basis via FIFO)
- `game_sessions` - Individual gameplay sessions with starting/ending balances
- `expenses` - Business expenses (not currently used in tax calculations)

**Derived/Calculated Data:**
- `tax_sessions` - Realized P/L from redemptions (one per redemption)
- `daily_tax_sessions` - Aggregated daily tax totals
- `redemption_allocations` - FIFO tracking: which purchases funded which redemptions
- `site_sessions` - Tracking container for grouping redemptions (legacy, minimal use)

**Reference Data:**
- `users` - Players being tracked
- `sites` - Casino websites
- `cards` - Payment cards used for purchases
- `redemption_methods` - Cash out methods (PayPal, Check, etc.)
- `game_types` / `game_names` - Catalog of games played

---

## Critical Algorithms & Data Flows

### 1. FIFO Cost Basis Allocation

**Purpose**: Determine how much cost basis (purchase money) is consumed when redeeming SC.

**Location**: `business_logic.py` - `FIFOCalculator.calculate_cost_basis()`

**Algorithm**:
```
INPUT: site_id, redemption_amount, user_id, redemption_date

1. Query all purchases for (site, user) with remaining_amount > 0
   ORDER BY purchase_date ASC, purchase_time ASC, id ASC

2. Initialize: needed = redemption_amount, allocations = []

3. For each purchase in FIFO order:
   a. If needed <= 0: break
   b. available = purchase.remaining_amount
   c. to_allocate = min(available, needed)
   d. Add (purchase_id, to_allocate) to allocations
   e. needed -= to_allocate

4. Return: (total_cost_basis, allocations)
```

**Key Rules**:
- Purchases are consumed in chronological order (FIFO)
- Only purchases on or before redemption date are eligible
- Each purchase tracks `remaining_amount` (amount - consumed)
- Allocations are stored in `redemption_allocations` table

---

### 2. Session Tax Field Calculation

**Purpose**: Calculate taxable P/L for each gaming session using session balances and FIFO basis.

**Location**: `business_logic.py` - `SessionManager._rebuild_session_tax_fields_for_pair()`

**Core Methodology**:

Sessions are processed in chronological order (by end_date, end_time). For each session:

#### A. Expected Starting Balances
```
expected_start_total = last_end_total - redemptions_between + purchases_between
expected_start_redeemable = last_end_redeem - redemptions_between
```
Where "between" means: after previous session end, up to current session start.

#### B. Inferred Deltas (Untracked Changes)
```
inferred_start_total_delta = actual_start_total - expected_start_total
inferred_start_redeemable_delta = actual_start_redeem - expected_start_redeem
```
These capture freebies, bonuses, or SC changes that occurred outside tracked transactions.

#### C. Session Basis (Cash Purchases)
```
session_basis = SUM(purchases.amount)
    WHERE purchase_datetime BETWEEN (last_session_end, current_session_end]
```

#### D. Pending Basis Pool
```
pending_basis_pool += session_basis
```
The pool accumulates cash basis from purchases and gets consumed only when redeemable SC increases (via locked SC converting to redeemable).

#### E. Basis Consumption
```
locked_start = starting_total_sc - starting_redeemable_sc
locked_end = ending_total_sc - ending_redeemable_sc
locked_processed_sc = max(locked_start - locked_end, 0)
locked_processed_value = locked_processed_sc * sc_rate  (typically 1.0)

basis_consumed = min(pending_basis_pool, locked_processed_value)
pending_basis_pool -= basis_consumed
```

**Critical Insight**: Basis is ONLY consumed when locked SC becomes redeemable. Playing with redeemable SC doesn't consume additional basis.

#### F. Net Taxable P/L
```
discoverable_sc = max(0, starting_redeemable - expected_start_redeemable)
delta_play_sc = ending_redeemable - starting_redeemable

net_taxable_pl = (discoverable_sc + delta_play_sc) - basis_consumed
```

**Components**:
- `discoverable_sc`: Unexpected redeemable SC at session start (freebies/bonuses discovered)
- `delta_play_sc`: Net change in redeemable SC during session (gameplay P/L)
- `basis_consumed`: Cost basis used up during this session

**Fields Written to game_sessions**:
- `session_basis`, `basis_consumed`
- `expected_start_total_sc`, `expected_start_redeemable_sc`
- `inferred_start_total_delta`, `inferred_start_redeemable_delta`
- `delta_total`, `delta_redeem`
- `net_taxable_pl`, `total_taxable` (same value, dual fields for compatibility)
- `sc_change`, `dollar_value` (simple calculations)

---

### 3. Rebuild All Derived Data

**Purpose**: Complete recalculation of all FIFO and tax data from scratch.

**Location**: `business_logic.py` - `SessionManager.rebuild_all_derived()`

**Process**:
```
For each (site_id, user_id) pair:
    1. _rebuild_fifo_for_pair(site_id, user_id)
       - Reset purchases.remaining_amount = amount
       - Delete all tax_sessions for (site, user)
       - Delete all redemption_allocations for (site, user)
       - Reset site_sessions totals to 0
       - Reprocess ALL redemptions in chronological order
         (calls process_redemption() for each)

    2. _rebuild_session_tax_fields_for_pair(site_id, user_id)
       - Recalculate all game_sessions tax fields
       - Update daily_tax_sessions for affected dates
```

**When Called**:
- User clicks "Recalculate Everything" button
- Inline edits (purchases, redemptions, sessions) via `auto_recalculate_affected_sessions()`
- After CSV imports
- After force-changing purchase site/user

---

### 4. Inline Recalculation (Auto-Recalculate)

**Purpose**: Efficiently recalculate only affected data after a single edit.

**Location**: `business_logic.py` - `SessionManager.auto_recalculate_affected_sessions()`

**Process**:
```
INPUT: site_id, user_id, changed_date, changed_time

1. Call _rebuild_fifo_for_pair(site_id, user_id)
   - Full FIFO rebuild for this (site, user) pair

2. Call _rebuild_session_tax_fields_for_pair(site_id, user_id)
   - Recalculate session tax fields

3. Update daily_tax_sessions for all affected dates

RETURNS: count of sessions recalculated
```

**Key Insight**: Even "inline" recalculation does a FULL rebuild for the (site, user) pair. This ensures consistency but only processes one pair instead of all pairs.

---

### 5. CSV Import with Validation

**Purpose**: Bulk import data from CSV files with comprehensive validation.

**Location**: `qt_app.py` - `_upload_table_dynamic()`

**Process**:

#### A. Schema Detection
```
1. Read CSV file
2. Detect column names and data types
3. Match to database schema (case-insensitive, flexible matching)
4. Identify missing required columns
5. Exclude calculated fields (configured per table)
```

#### B. Pre-Validation Defaults
```
Apply defaults BEFORE validation:
- game_sessions.start_time = '00:00:00' if blank
- game_sessions.status based on presence of end_date/end_time
```

#### C. Validation (Per Row)
```
1. Required field checks
2. Foreign key lookups (user_name → user_id, etc.)
3. Data type validation
4. Business logic validation:
   - No future dates
   - End date/time must be after start date/time
   - Session end != start (must be ≥1 second)
   - Balances cannot be negative
   - Purchase/expense amounts must be > 0
   - Redemption dates: receipt_date >= redemption_date
5. Duplicate detection (based on unique_column configuration)
```

#### D. Import Execution
```
1. Show preview with validation results
2. User confirms
3. Optional: Clear existing records
4. Insert/Update records in batch
5. Prompt to run "Recalculate Everything"
```

**Unique Column Configuration**:
- `purchases`: `(purchase_date, purchase_time, user_id, site_id, amount)`
- `redemptions`: `(redemption_date, redemption_time, user_id, site_id, amount)`
- `game_sessions`: `(session_date, start_time, user_id, site_id)`
- `cards`: `(name, user_id)` - Composite key allows same card name for different users

---

## Key UI Workflows

### Purchase Entry
1. User creates purchase record (date, site, amount, SC received)
2. Purchase creates cost basis: `remaining_amount = amount`
3. Auto-recalculate updates session tax fields

### Session Entry
1. User starts session: records starting balances
2. User ends session: records ending balances
3. Auto-recalculate computes net P/L using session tax algorithm

### Redemption Entry
1. User creates redemption record (date, site, amount)
2. FIFO calculates cost basis from purchases
3. Creates tax_session record: `net_pl = redemption_amount - cost_basis`
4. Updates `redemption_allocations` to track which purchases were used
5. Auto-recalculate updates affected sessions

### Close Position (Unrealized → Realized)
1. User selects position on Unrealized tab
2. System creates $0 redemption for remaining cost basis
3. Creates tax_session showing net loss
4. Marks purchases as 'dormant' status
5. Runs FIFO rebuild for (site, user)

---

## Recent Critical Updates

### 1. Fixed Redundant FIFO Processing (2025-01)
**Problem**: When editing redemptions, `process_redemption()` was called, then immediately overwritten by `auto_recalculate_affected_sessions()` which does a full rebuild.

**Solution**: Removed redundant `process_redemption()` calls before `auto_recalculate`. The rebuild handles everything.

**Files**: `qt_app.py` lines 6036-6037, 6081

### 2. Fixed Missing Recalculation for Active Sessions (2025-01)
**Problem**: Editing Active (not closed) sessions didn't trigger recalculation. Changes to starting balances didn't propagate to dependent calculations, causing "wonky results."

**Solution**: Added `auto_recalculate_affected_sessions()` call after Active session updates, recalculating both old and new (site, user) pairs if changed.

**Files**: `qt_app.py` lines 7753-7807

**Impact**: This was likely the root cause of inconsistent calculations.

### 3. Fixed site_sessions Double-Counting (2025-01)
**Problem**: `_rebuild_fifo_for_pair()` reprocessed redemptions without resetting `site_sessions.total_buyin` and `total_redeemed`, causing accumulation on repeated rebuilds.

**Solution**: Reset site_sessions totals and status before reprocessing redemptions.

**Files**: `business_logic.py` lines 265-271

**Note**: This bug didn't affect tax calculations (which use `tax_sessions`), only secondary tracking data.

### 4. Enhanced CSV Import Validation (2025-01)
**Added Validations**:
- Future date prevention (purchases, redemptions, sessions, expenses)
- Session end date/time validation (must be after start, ≥1 second difference)
- Negative balance prevention
- Receipt date >= redemption date for redemptions
- Amount validation (purchases/expenses > 0, redemptions can be 0)

**Files**: `qt_app.py` lines 14946-15023

### 5. Schema Improvements (2025-01)
- Made `game_sessions.game_type` nullable (Migration 11)
- Added composite unique key for cards: `(name, user_id)`
- Configured calculated fields exclusion for CSV import
- Added `purchases.status` for dormant balance tracking

---

## Data Integrity Rules

### Critical Invariants
1. **FIFO Consistency**: `SUM(purchases.remaining_amount)` must equal unallocated cost basis
2. **Allocation Consistency**: `SUM(redemption_allocations.allocated_amount) WHERE purchase_id=X` must equal `purchases.amount - purchases.remaining_amount`
3. **Session Ordering**: Sessions must be processed in chronological order (end_date, end_time, id)
4. **Temporal Validity**: No transactions can occur in the future; session end >= start

### Calculated vs User-Provided Fields

**Never in CSV (Auto-calculated)**:
- `purchases`: `remaining_amount`, `processed`, `status`
- `redemptions`: `site_session_id`
- `game_sessions`: `sc_change`, `dollar_value`, `status`, `processed`, `freebies_detected`, `rtp`, `total_taxable`, `session_basis`, `basis_consumed`, all expected/inferred/delta fields
- All fields in `tax_sessions`, `daily_tax_sessions`, `redemption_allocations`

**User-Providable (Can be in CSV)**:
- `redemptions`: `processed` flag (external tracking indicator)
- `game_sessions`: `starting_sc_balance`, `ending_sc_balance`, `starting_redeemable_sc`, `ending_redeemable_sc`, `notes`, `game_type`, `game_name`, `wager_amount`

---

## Performance Considerations

### When Full Rebuild is Triggered
- Manual "Recalculate Everything"
- After bulk CSV import
- Force-changing purchase site/user with allocations

### When Targeted Rebuild is Triggered (One Pair)
- Editing any purchase
- Editing any redemption
- Editing any session (now includes Active sessions)
- Closing position

### Optimization Strategy
- Targeted rebuilds only process one (site, user) pair
- Full rebuilds process all pairs sequentially
- Database indexes on (site_id, user_id, date, time) columns
- Use of composite keys for efficient lookups

---

## Common Troubleshooting Scenarios

### "Wonky Results" After Editing
**Cause**: Was due to Active session edits not recalculating (Fixed in Update #2)
**Solution**: Now automatically recalculates on all session edits

### Negative site_sessions Totals
**Cause**: Double-counting from repeated rebuilds (Fixed in Update #3)
**Solution**: Totals now reset before rebuild
**Note**: These totals don't affect tax calculations

### Import Shows Duplicates
**Check**: Unique column configuration matches your data
**Example**: Cards now use `(name, user_id)` to allow same card name for different users

### Session P/L Seems Wrong
**Check**:
1. Are there purchases before the session? (Need cost basis)
2. Are starting/ending balances accurate?
3. Run "Recalculate Everything" to ensure consistency
4. Verify session dates/times are correct (no end before start)

---

## Architecture Philosophy

### Why FIFO?
IRS requires cost basis tracking for gambling winnings. FIFO is the standard method: first money in is first money out.

### Why Session-Based?
Sessions represent discrete gambling activities. Tracking session-level P/L provides:
- Detailed activity history
- Better understanding of risk/reward
- Granular data for tax reporting

### Why Rebuild vs Incremental?
Rebuilding ensures consistency. The dependencies between purchases, sessions, and redemptions make incremental updates error-prone. Targeted rebuilds (per site/user pair) balance efficiency with correctness.

### Why site_sessions Exists
Originally intended for grouping redemptions and tracking session totals. Now primarily used for:
- Storing position notes (Unrealized tab)
- Linking redemptions to session groups
- Legacy compatibility

---

## Future Considerations

### Potential Enhancements
1. RTP (Return to Player) calculation integration
2. More sophisticated freebie detection
3. Multi-site tournament tracking
4. Tax form generation (W-2G, Schedule 1)
5. Audit trail improvements

### Known Limitations
1. Single currency (USD) assumption
2. Fixed SC:$ conversion rate per site
3. No support for partial year tax calculations
4. Manual session entry (no casino API integration)

---

## Development Notes

### Code Organization
- `qt_app.py` - Main UI, dialogs, tab implementations
- `business_logic.py` - FIFO calculator, session manager, tax calculations
- `database.py` - Schema, migrations, connection management
- `session2.py` - Alternative session management UI (legacy)

### Testing Recommendations
1. Always test with "Recalculate Everything" after bulk changes
2. Verify FIFO allocations in `redemption_allocations` table
3. Check `net_taxable_pl` matches manual calculations
4. Test edge cases: same-day transactions, midnight boundaries, zero-amount redemptions

### Migration Strategy
Schema changes use versioned migrations in `database.py`. Each migration is idempotent and checks current state before applying changes.

---

**Document Version**: 1.0
**Last Updated**: January 2026
**Application Version**: V28 (Multi-Session Testing 2)
