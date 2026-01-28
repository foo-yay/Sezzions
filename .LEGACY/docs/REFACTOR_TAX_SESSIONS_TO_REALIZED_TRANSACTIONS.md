# Refactor Plan: tax_sessions → realized_transactions

## Executive Summary
**Goal**: Rename `tax_sessions` table to `realized_transactions` and `session_date` column to `redemption_date` to clarify purpose and eliminate confusion.

**Scope**: Database schema + all Python code references

**Risk Level**: Medium (database schema change + widespread code updates)

**Estimated Changes**: ~50-70 lines across 4 files

---

## 1. Database Changes

### Table Rename
- **Old**: `tax_sessions`
- **New**: `realized_transactions`

### Column Rename
- **Old**: `tax_sessions.session_date`
- **New**: `realized_transactions.redemption_date`

### Schema (after migration)
```sql
CREATE TABLE realized_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redemption_date DATE NOT NULL,  -- RENAMED from session_date
    site_id INTEGER NOT NULL,
    redemption_id INTEGER NOT NULL,
    cost_basis REAL NOT NULL,
    payout REAL NOT NULL,
    net_pl REAL NOT NULL,
    user_id INTEGER NOT NULL,
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (redemption_id) REFERENCES redemptions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 2. Files to Update

### File: `database.py`
**Changes**: Add migration to rename table and column

**Migration SQL**:
```sql
-- Step 1: Create new table with correct schema
CREATE TABLE realized_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redemption_date DATE NOT NULL,
    site_id INTEGER NOT NULL,
    redemption_id INTEGER NOT NULL,
    cost_basis REAL NOT NULL,
    payout REAL NOT NULL,
    net_pl REAL NOT NULL,
    user_id INTEGER NOT NULL,
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (redemption_id) REFERENCES redemptions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Step 2: Copy all data (mapping session_date → redemption_date)
INSERT INTO realized_transactions 
    (id, redemption_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id, notes)
SELECT 
    id, session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id, notes
FROM tax_sessions;

-- Step 3: Drop old table
DROP TABLE tax_sessions;
```

### File: `business_logic.py`
**Estimated changes**: ~15-20 occurrences

**Pattern to find**: 
- `tax_sessions` (table name)
- `session_date` (when referring to this table's date column)

**Functions to update**:
1. `calculate_cost_basis()` - INSERT INTO tax_sessions
2. `apply_allocation()` - INSERT INTO tax_sessions
3. `reverse_cost_basis()` - DELETE FROM tax_sessions
4. `_rebuild_session_tax_fields_for_pair()` - multiple tax_sessions queries
5. `_update_daily_tax_summaries()` - SELECT from tax_sessions
6. Any other functions that query/modify tax_sessions

### File: `reporting.py`
**Estimated changes**: ~5-10 occurrences

**Sections to update**:
1. `_run_overall_dashboard()` - Redeemed P/L query (line ~640)
2. Any other reports that query tax_sessions

### File: `qt_app.py`
**Estimated changes**: Minimal (mostly indirect via business_logic calls)

**Potential areas**:
- Any UI code that directly queries tax_sessions (unlikely)
- Status messages that mention "tax sessions"

---

## 3. Search & Replace Strategy

### Phase 1: Find all occurrences
```bash
# In workspace root:
grep -r "tax_sessions" *.py
grep -r "session_date" business_logic.py reporting.py | grep -i "tax\|redemption"
```

### Phase 2: Replace pattern
1. **Table name**: `tax_sessions` → `realized_transactions`
2. **Column name**: `session_date` → `redemption_date` (ONLY when in context of this table)

### Phase 3: Careful review
- Verify each `session_date` replacement is for the right table
- Don't change `session_date` in `game_sessions` or `daily_sessions`

---

## 4. Pre-Migration Verification Queries

Run these BEFORE migration to capture baseline:

```sql
-- Count records
SELECT COUNT(*) as total_records FROM tax_sessions;

-- Sum of net_pl (should match after migration)
SELECT SUM(net_pl) as total_pl FROM tax_sessions;

-- Check for NULL session_dates
SELECT COUNT(*) FROM tax_sessions WHERE session_date IS NULL;

-- Verify all redemption_ids exist
SELECT COUNT(*) FROM tax_sessions ts
LEFT JOIN redemptions r ON r.id = ts.redemption_id
WHERE r.id IS NULL;
```

---

## 5. Post-Migration Verification Queries

Run these AFTER migration to verify integrity:

```sql
-- Count records (should match pre-migration)
SELECT COUNT(*) as total_records FROM realized_transactions;

-- Sum of net_pl (should match pre-migration)
SELECT SUM(net_pl) as total_pl FROM realized_transactions;

-- Check for NULL redemption_dates
SELECT COUNT(*) FROM realized_transactions WHERE redemption_date IS NULL;

-- Verify all redemption_ids still exist
SELECT COUNT(*) FROM realized_transactions rt
LEFT JOIN redemptions r ON r.id = rt.redemption_id
WHERE r.id IS NULL;

-- Spot check: compare first 5 records
SELECT * FROM realized_transactions ORDER BY id LIMIT 5;
```

---

## 6. Rollback Plan

If something goes wrong:

### Option A: Restore from backup
```bash
cp casino_accounting.db.backup casino_accounting.db
```

### Option B: Manual rollback (if caught mid-migration)
```sql
-- Recreate old table
CREATE TABLE tax_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date DATE NOT NULL,
    site_id INTEGER NOT NULL,
    redemption_id INTEGER NOT NULL,
    cost_basis REAL NOT NULL,
    payout REAL NOT NULL,
    net_pl REAL NOT NULL,
    user_id INTEGER NOT NULL,
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (redemption_id) REFERENCES redemptions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Copy data back
INSERT INTO tax_sessions 
    (id, session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id, notes)
SELECT 
    id, redemption_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id, notes
FROM realized_transactions;

-- Drop new table
DROP TABLE realized_transactions;
```

---

## 7. Function Names - NO CHANGES NEEDED

After review, all existing function names are accurate and should NOT be renamed:

- `update_daily_tax_session()` - Works with `daily_sessions` table (IRS tax reporting rollup of game_sessions) ✓
- `_rebuild_session_tax_fields_for_pair()` - Rebuilds tax fields ON game_sessions (net_taxable_pl, total_taxable, etc.) ✓
- `_rebuild_session_tax_fields_for_pair_from()` - Same as above, scoped version ✓

These functions deal with actual **tax calculations** (game session P/L), NOT the `tax_sessions` table we're renaming.

---

## 8. Execution Steps

### Before starting:
1. ✅ **BACKUP DATABASE**
   ```bash
   cp casino_accounting.db casino_accounting.db.backup_before_refactor_$(date +%Y%m%d_%H%M%S)
   ```

2. ✅ Run pre-migration verification queries (save results)

3. ✅ Close all running app instances

### Migration sequence:
1. Update `database.py` - add migration
2. Update `business_logic.py` - all tax_sessions references
3. Update `reporting.py` - all tax_sessions references
4. Update `qt_app.py` - any remaining references
5. Run app once to trigger migration
6. Run post-migration verification queries
7. Test key workflows:
   - View Realized tab
   - Create a redemption
   - View Overall Dashboard
   - Run Recalculate Everything

### If tests pass:
8. Commit changes
9. Update documentation

### If tests fail:
10. Restore from backup
11. Review errors
12. Fix and retry

---

## 8. Testing Checklist

After migration, verify these workflows work:

- [ ] App starts without errors
- [ ] View Realized tab (should display redemption records)
- [ ] View Overall Dashboard with date filters
- [ ] Create a new purchase
- [ ] Create a new redemption (triggers realized_transactions INSERT)
- [ ] Edit an existing redemption
- [ ] Delete a redemption (should clean up realized_transactions)
- [ ] Run "Recalculate Everything" for one site
- [ ] Verify totals match pre-migration
- [ ] Check game_sessions table still intact
- [ ] Check daily_sessions table still intact

---

## 9. Expected Occurrences by File

### business_logic.py
```
Line ~673: INSERT INTO tax_sessions → INSERT INTO realized_transactions
Line ~676: (session_date, site_id...) → (redemption_date, site_id...)
Line ~797: INSERT INTO tax_sessions → INSERT INTO realized_transactions  
Line ~800: (session_date, site_id...) → (redemption_date, site_id...)
Line ~534: DELETE FROM tax_sessions → DELETE FROM realized_transactions
Line ~1477: SELECT ... FROM tax_sessions → FROM realized_transactions
Line ~1481: ts.session_date → ts.redemption_date
Line ~1507: UPDATE tax_sessions → UPDATE realized_transactions
Line ~1561: DELETE FROM tax_sessions → DELETE FROM realized_transactions
Line ~1564: INSERT INTO tax_sessions → INSERT INTO realized_transactions
... (approximately 15-20 total)
```

### reporting.py
```
Line ~640: FROM tax_sessions ts → FROM realized_transactions rt
Line ~641: (any ts.session_date references → rt.redemption_date)
... (approximately 5-10 total)
```

### database.py
```
Add new migration function (new code)
```

---

## 10. Documentation Updates

After successful migration:

1. Update `SESSION_APP_ENGINE_HANDOFF.md` - replace tax_sessions terminology
2. Update `SYSTEM_OVERVIEW.md` - update table descriptions
3. Update `AGENTS.md` - update domain rules if mentioned
4. Update any code comments that reference "tax sessions"

---

## 11. Timeline Estimate

- **Preparation**: 15 minutes (backup, run verification queries)
- **Code changes**: 30-45 minutes (careful search & replace)
- **Testing**: 30 minutes (run through checklist)
- **Documentation**: 15 minutes
- **Total**: ~90-120 minutes

---

## 12. Success Criteria

✅ All tests pass
✅ No errors in terminal when running app
✅ Pre/post migration totals match exactly
✅ Can create/edit/delete redemptions successfully
✅ Reports display correct data
✅ Recalculate Everything completes without errors

---

## Notes

- The term "tax_sessions" appears to be a legacy naming artifact
- The table actually tracks realized profit from redemptions, not tax-related sessions
- `daily_sessions` is the actual tax reporting table (aggregates game_sessions)
- This refactor clarifies the distinction between:
  - **game_sessions**: Individual gameplay (generates taxable P/L)
  - **realized_transactions**: Redemption events (realizes the P/L)
    - **daily_sessions**: IRS reporting format (daily rollup)
