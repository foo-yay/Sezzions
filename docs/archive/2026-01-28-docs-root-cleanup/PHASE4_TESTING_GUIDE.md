# Phase 4 UI Integration - End-to-End Testing Guide

## Overview
This guide provides systematic test scenarios for validating the complete Phase 4 Tools integration, including background workers, progress dialogs, Tools tab UI, and post-import recalculation prompts.

---

## Test Environment Setup

### Prerequisites:
1. Python 3.14.2 installed
2. All dependencies installed: `pip install -r requirements.txt`
3. Fresh database with sample data (or backup to restore between tests)
4. Qt application running: `python sezzions.py`

### Backup Before Testing:
```bash
# Create backup before destructive tests
cp casino_accounting.db casino_accounting.db.test_backup
```

### Sample Data Requirements:
- At least 2 users (e.g., "Alice", "Bob")
- At least 2 sites (e.g., "Stake", "Pulsz")
- At least 5 purchases per user/site pair
- At least 3 redemptions per user/site pair
- At least 2 game sessions per user/site pair

---

## Test Suite 1: Basic Recalculation UI

### Test 1.1: Recalculate Everything Button
**Steps:**
1. Open Tools tab (click 🔧 Tools or Tools menu → Open Tools Tab)
2. Verify "Recalculate Everything" button is visible and prominent (blue, 40px height)
3. Click "Recalculate Everything"
4. Verify confirmation dialog appears: "This will recalculate all FIFO allocations..."
5. Click "Yes"

**Expected Results:**
- Progress dialog appears immediately
- Progress bar updates in real-time (0% → 100%)
- Status label shows "Processing pair X/Y"
- Details label shows "Processing X/Y"
- Dialog remains modal (can't interact with main window)
- Cancel button is enabled

**Pass Criteria:**
- ✅ Progress updates smoothly without freezing UI
- ✅ Progress reaches 100% completion
- ✅ Result dialog appears with statistics
- ✅ All tabs refresh automatically after completion

---

### Test 1.2: Scoped Recalculation
**Steps:**
1. Open Tools tab
2. Select user from dropdown (e.g., "Alice")
3. Select site from dropdown (e.g., "Stake")
4. Click "Recalculate Pair" button
5. Verify confirmation dialog: "Recalculate Alice @ Stake?"
6. Click "Yes"

**Expected Results:**
- Progress dialog shows: "Recalculate Alice @ Stake - Progress"
- Progress updates for single pair only
- Faster completion than "Recalculate Everything"
- Result dialog shows statistics for single pair

**Pass Criteria:**
- ✅ Only selected pair is recalculated
- ✅ Other pairs remain unchanged
- ✅ Statistics show correct counts for single pair
- ✅ All tabs refresh after completion

---

### Test 1.3: Statistics Display
**Steps:**
1. Open Tools tab
2. Note statistics: "Database: X pairs, Y purchases, Z redemptions, W allocations"
3. Run "Recalculate Everything"
4. After completion, verify statistics updated

**Expected Results:**
- Statistics accurate before recalculation
- Statistics update immediately after recalculation
- Numbers match database reality

**Pass Criteria:**
- ✅ Pair count matches (users × sites with data)
- ✅ Purchase count accurate
- ✅ Redemption count accurate
- ✅ Allocation count accurate

---

## Test Suite 2: Background Worker Functionality

### Test 2.1: UI Responsiveness During Recalculation
**Steps:**
1. Start "Recalculate Everything"
2. While progress dialog is open, try to:
   - Switch tabs (should be blocked by modal dialog)
   - Resize progress dialog window
   - Move progress dialog window
   - Click main window (should be blocked)

**Expected Results:**
- Progress dialog is modal (blocks main window)
- Progress dialog can be moved/resized
- Main window grayed out or blocked
- No UI freezing or lag

**Pass Criteria:**
- ✅ Main window remains responsive (not frozen)
- ✅ Progress updates continue smoothly
- ✅ Modal dialog prevents unwanted interactions
- ✅ No "Application Not Responding" warnings

---

### Test 2.2: Progress Update Accuracy
**Steps:**
1. Start "Recalculate Everything" with 10+ pairs
2. Watch progress updates closely
3. Note progress percentages and messages

**Expected Results:**
- Progress bar increases monotonically (never goes backward)
- Pair count increments correctly (1/10, 2/10, 3/10...)
- Status messages describe current operation
- Progress reaches exactly 100% at completion

**Pass Criteria:**
- ✅ Progress bar smooth and accurate
- ✅ Pair count sequential and correct
- ✅ Status messages meaningful
- ✅ No skipped or duplicate pair counts

---

### Test 2.3: Error Handling
**Steps:**
1. Close database file manually (simulate error)
2. Try "Recalculate Everything"
3. Observe error handling

**Expected Results:**
- Error dialog appears with clear message
- Progress dialog closes gracefully
- Main window remains functional
- No crash or data corruption

**Pass Criteria:**
- ✅ Error message describes problem clearly
- ✅ Application doesn't crash
- ✅ Database remains consistent
- ✅ User can retry after fixing issue

---

## Test Suite 3: Cancellation Behavior

### Test 3.1: Cancel During Recalculation
**Steps:**
1. Start "Recalculate Everything" (large dataset preferred)
2. Wait until progress shows 50% completion
3. Click "Cancel" button
4. Wait for cancellation to complete

**Expected Results:**
- Cancellation dialog appears: "Recalculation was cancelled. Database may be in incomplete state."
- Progress dialog closes
- Warning recommends running recalculation again
- Database left in consistent state (partial progress saved or rolled back)

**Pass Criteria:**
- ✅ Cancel button responsive (stops within 2 seconds)
- ✅ No data corruption after cancellation
- ✅ Warning dialog appears
- ✅ Can run recalculation again successfully

---

### Test 3.2: Cancel Immediately
**Steps:**
1. Click "Recalculate Everything"
2. Click "Cancel" immediately (before 1% progress)
3. Verify clean cancellation

**Expected Results:**
- Progress dialog closes quickly
- No partial data written
- Warning dialog appears
- Database remains consistent

**Pass Criteria:**
- ✅ Fast cancellation (< 1 second)
- ✅ No errors in console/logs
- ✅ Database state valid
- ✅ Can start new recalculation

---

### Test 3.3: Cancel Near Completion
**Steps:**
1. Start "Recalculate Everything"
2. Wait until 95%+ progress
3. Click "Cancel"
4. Observe behavior

**Expected Results:**
- May complete before cancellation takes effect
- OR cancels cleanly with warning
- No data corruption either way

**Pass Criteria:**
- ✅ No errors or crashes
- ✅ Either completes or cancels cleanly
- ✅ Database state valid
- ✅ Statistics accurate

---

## Test Suite 4: Post-Import Recalculation Prompts

### Test 4.1: Import Purchases with Prompt
**Steps:**
1. Prepare CSV with 5 purchase records (same user/site)
2. Import via CSV Import UI (when Phase 5 complete)
3. Observe ImportResultDialog
4. Observe PostImportPromptDialog

**Expected Results:**
- ImportResultDialog shows: "Successfully imported 5 Purchases"
- PostImportPromptDialog appears after closing import result
- Prompt shows: "Successfully imported 5 Purchases. Would you like to recalculate FIFO allocations?"
- Affected details: "Affected: 1 users, 1 sites"
- Recommendation: "⚠️ Recommended: Recalculating ensures accurate..."
- Two buttons: "Recalculate Now" (default), "Later"

**Pass Criteria:**
- ✅ Import result dialog appears first
- ✅ Post-import prompt appears second
- ✅ Affected counts accurate
- ✅ "Recalculate Now" is default (Enter key triggers it)

---

### Test 4.2: Accept Recalculation Prompt
**Steps:**
1. Import purchases (from Test 4.1)
2. Click "Recalculate Now" on prompt
3. Observe recalculation progress

**Expected Results:**
- Progress dialog appears immediately
- Progress shows "Recalculate - Progress"
- Only affected pairs are recalculated
- Result dialog shows updated statistics
- All tabs refresh after completion

**Pass Criteria:**
- ✅ Recalculation starts immediately
- ✅ Only imported user/site pair processed
- ✅ Purchase consumed amounts updated
- ✅ FIFO allocations accurate

---

### Test 4.3: Decline Recalculation Prompt
**Steps:**
1. Import purchases
2. Click "Later" on prompt
3. Verify no recalculation occurs

**Expected Results:**
- Prompt closes without recalculation
- User returned to main window
- Can manually recalculate later from Tools tab
- Imported data visible but derived fields not updated

**Pass Criteria:**
- ✅ No progress dialog appears
- ✅ No recalculation triggered
- ✅ Can recalculate manually later
- ✅ No errors or warnings

---

### Test 4.4: Multiple Imports Before Recalculation
**Steps:**
1. Import 5 purchases → Click "Later"
2. Import 3 redemptions → Click "Later"
3. Import 2 game sessions → Click "Later"
4. Manually click "Recalculate Everything"

**Expected Results:**
- Each import shows prompt, user declines
- Manual recalculation processes all changes
- All derived data updated correctly
- Statistics accurate after full recalculation

**Pass Criteria:**
- ✅ Can batch multiple imports
- ✅ Manual recalculation works after multiple imports
- ✅ All data consistent after recalculation
- ✅ No duplicate prompts

---

## Test Suite 5: Integration Testing

### Test 5.1: Menu Action → Tools Tab Flow
**Steps:**
1. Close Tools tab (switch to another tab)
2. Click Tools menu → "Recalculate Everything"
3. Verify delegation to Tools tab

**Expected Results:**
- Tools tab becomes active automatically
- "Recalculate Everything" button triggered
- Confirmation dialog appears
- Recalculation proceeds normally

**Pass Criteria:**
- ✅ Tools tab opens automatically
- ✅ Button click delegated correctly
- ✅ No duplicate confirmation dialogs
- ✅ Full recalculation works

---

### Test 5.2: Database Change Notifications
**Steps:**
1. Open Purchases tab
2. Run "Recalculate Everything" from Tools tab
3. After completion, switch to Purchases tab
4. Verify table data refreshed

**Expected Results:**
- Purchases tab refreshes automatically
- Consumed amounts updated
- Available balance updated
- No manual refresh needed

**Pass Criteria:**
- ✅ All tabs refresh after recalculation
- ✅ Data accurate across all tabs
- ✅ No stale data visible
- ✅ Refresh happens automatically

---

### Test 5.3: Multiple Simultaneous Operations
**Steps:**
1. Start "Recalculate Everything"
2. While running, try to start another recalculation
3. Observe queueing behavior

**Expected Results:**
- Second operation queues or is rejected
- First operation completes
- Second operation starts after first completes (if queued)
- No race conditions or data corruption

**Pass Criteria:**
- ✅ Thread pool handles queuing correctly
- ✅ No concurrent writes to same data
- ✅ Both operations complete successfully
- ✅ Database remains consistent

---

## Test Suite 6: Performance Testing

### Test 6.1: Large Database Performance
**Requirements:** Database with 1000+ purchases, 500+ redemptions, 10+ users, 5+ sites

**Steps:**
1. Run "Recalculate Everything"
2. Time the operation
3. Monitor system resources

**Expected Results:**
- Completes in reasonable time (< 5 minutes for 1000 purchases)
- CPU usage moderate (not 100% sustained)
- Memory usage stable (no leaks)
- UI remains responsive throughout

**Pass Criteria:**
- ✅ Reasonable completion time
- ✅ No memory leaks
- ✅ No UI freezing
- ✅ Progress updates smooth

---

### Test 6.2: Memory Leak Check
**Steps:**
1. Note initial memory usage
2. Run "Recalculate Everything" 10 times
3. Check memory usage after each run
4. Compare final memory to initial

**Expected Results:**
- Memory usage stable across runs
- No significant growth (< 50MB increase)
- Memory released between runs
- No warnings in logs

**Pass Criteria:**
- ✅ Memory usage stable
- ✅ No linear memory growth
- ✅ Python garbage collection working
- ✅ Qt objects properly destroyed

---

## Test Suite 7: Edge Cases

### Test 7.1: Empty Database
**Steps:**
1. Create new empty database
2. Open Tools tab
3. Click "Recalculate Everything"

**Expected Results:**
- Confirmation dialog appears
- Progress dialog shows 0/0 pairs
- Completes immediately
- Result dialog: "0 pairs processed"
- No errors

**Pass Criteria:**
- ✅ No crashes
- ✅ Graceful handling of empty data
- ✅ Clear result message
- ✅ Statistics show zeros

---

### Test 7.2: No Affected Pairs After Import
**Steps:**
1. Import CSV with invalid data (all skipped)
2. Observe import result
3. Verify no post-import prompt

**Expected Results:**
- Import result shows 0 added, N skipped
- No post-import recalculation prompt
- User returned to main window
- No errors

**Pass Criteria:**
- ✅ No prompt for failed import
- ✅ Clear error messages in import result
- ✅ No unnecessary recalculation
- ✅ User can correct and retry

---

### Test 7.3: Recalculation with Missing Foreign Keys
**Steps:**
1. Manually delete a user from database
2. Leave orphaned purchases for that user
3. Run "Recalculate Everything"

**Expected Results:**
- Recalculation detects orphaned records
- Error message or warning appears
- Database consistency maintained
- Clear guidance on fixing issue

**Pass Criteria:**
- ✅ Error handling prevents crash
- ✅ Clear error message
- ✅ Database not corrupted
- ✅ Can fix issue and retry

---

## Test Suite 8: Result Accuracy

### Test 8.1: Verify FIFO Allocations
**Steps:**
1. Note purchase amounts before recalculation
2. Note redemption amounts before recalculation
3. Run "Recalculate Everything"
4. Verify FIFO allocations in database

**Expected Results:**
- Allocations table populated correctly
- Basis allocated in chronological order
- No over-allocation (consumed ≤ amount)
- No under-allocation (all redemptions allocated)

**Pass Criteria:**
- ✅ FIFO order correct
- ✅ No allocation errors
- ✅ All redemptions fully allocated
- ✅ Purchases consumed correctly

---

### Test 8.2: Verify Cost Basis Calculations
**Steps:**
1. Create simple scenario:
   - Purchase 1: $100, 100 SC
   - Purchase 2: $200, 200 SC
   - Redemption 1: 150 SC → $140
2. Run recalculation
3. Check allocation details

**Expected Results:**
- Allocation 1: 100 SC from Purchase 1 (basis $100)
- Allocation 2: 50 SC from Purchase 2 (basis $50)
- Total basis: $150
- Profit: $140 - $150 = -$10 (loss)

**Pass Criteria:**
- ✅ FIFO order maintained
- ✅ Basis calculated correctly
- ✅ Profit/loss accurate
- ✅ Matches legacy app behavior

---

## Test Suite 9: Regression Testing

### Test 9.1: Legacy Parity Check
**Steps:**
1. Use same dataset in legacy app (session2.py)
2. Run legacy recalculation
3. Export legacy results
4. Run new app recalculation
5. Compare results

**Expected Results:**
- FIFO allocations identical
- Cost basis identical
- Profit/loss identical
- Consumed amounts identical

**Pass Criteria:**
- ✅ 100% parity with legacy
- ✅ No regressions
- ✅ Same accounting logic
- ✅ Same edge case handling

---

## Test Completion Checklist

### Functional Tests:
- [ ] All Suite 1 tests passing (Basic UI)
- [ ] All Suite 2 tests passing (Background Workers)
- [ ] All Suite 3 tests passing (Cancellation)
- [ ] All Suite 4 tests passing (Post-Import Prompts)
- [ ] All Suite 5 tests passing (Integration)

### Non-Functional Tests:
- [ ] All Suite 6 tests passing (Performance)
- [ ] All Suite 7 tests passing (Edge Cases)
- [ ] All Suite 8 tests passing (Result Accuracy)
- [ ] All Suite 9 tests passing (Regression)

### Documentation:
- [ ] All tests documented with results
- [ ] Bugs logged in todo.md
- [ ] Performance metrics recorded
- [ ] Edge cases documented

### Sign-Off:
- [ ] Developer tested all scenarios
- [ ] User acceptance testing complete
- [ ] No critical bugs remaining
- [ ] Ready for Phase 5 (Notifications)

---

## Reporting Template

### Test Run Summary:
**Date:** YYYY-MM-DD  
**Tester:** [Name]  
**Environment:** macOS/Windows/Linux, Python 3.X.X  
**Database Size:** X users, Y sites, Z purchases, W redemptions

### Results:
| Test Suite | Tests Run | Passed | Failed | Skipped | Notes |
|-----------|-----------|--------|--------|---------|-------|
| Suite 1   |           |        |        |         |       |
| Suite 2   |           |        |        |         |       |
| Suite 3   |           |        |        |         |       |
| Suite 4   |           |        |        |         |       |
| Suite 5   |           |        |        |         |       |
| Suite 6   |           |        |        |         |       |
| Suite 7   |           |        |        |         |       |
| Suite 8   |           |        |        |         |       |
| Suite 9   |           |        |        |         |       |
| **Total** |           |        |        |         |       |

### Issues Found:
1. **Issue ID:** TOOLS-001  
   **Severity:** Critical/High/Medium/Low  
   **Description:** [Brief description]  
   **Steps to Reproduce:** [Steps]  
   **Expected:** [Expected behavior]  
   **Actual:** [Actual behavior]  
   **Status:** Open/Fixed/Won't Fix

### Performance Metrics:
- **1000 purchases recalculation time:** X seconds
- **Peak memory usage:** X MB
- **UI freeze events:** X occurrences
- **Progress update latency:** X ms average

### Recommendations:
- [Recommendation 1]
- [Recommendation 2]
- [Recommendation 3]

### Conclusion:
**PASS** / **FAIL** / **PASS WITH ISSUES**

[Summary statement]

---

## Next Steps After Testing

### If All Tests Pass:
1. Mark Task 6 as complete
2. Update TOOLS_IMPLEMENTATION_PLAN.md status
3. Proceed to Phase 5 (Notification System)
4. Archive test results for reference

### If Tests Fail:
1. Log all failures in todo.md
2. Prioritize critical bugs
3. Fix bugs and re-test
4. Repeat until all tests pass

### Before Phase 5:
1. Review all Phase 4 documentation
2. Confirm no regressions vs legacy app
3. Performance acceptable for production
4. User feedback incorporated
