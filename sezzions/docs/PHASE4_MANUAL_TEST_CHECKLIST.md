# Phase 4 Manual Testing Checklist

**Date:** January 27, 2026  
**Tester:** _______________________  
**Application Version:** Sezzions OOP

---

## ✅ Backend Integration Tests (PASSED)

All backend components verified:
- ✅ RecalculationService accessible via facade
- ✅ All required methods present (rebuild_fifo_all, rebuild_fifo_for_pair, rebuild_after_import, get_stats)
- ✅ ImportResult DTO has affected_user_ids and affected_site_ids fields
- ✅ RecalculationWorker and WorkerSignals importable
- ✅ All dialog classes importable (Progress, Result, PostImportPrompt)
- ✅ ToolsTab has all required methods

---

## 🎯 Manual UI Testing (In Progress)

### Test Suite 1: Basic UI Verification

#### Test 1.1: Tools Tab Accessibility ⬜
- [X] Open the running application (python3 sezzions.py)
- [X] Locate the 🔧 Tools tab in the tab bar
- [X] Click on Tools tab
- [X] Verify Tools tab opens and displays content
- [X] **Expected:** Tab opens with 3 sections visible:
  - Recalculation section (with buttons)
  - CSV Import/Export section (placeholder)
  - Database Tools section (placeholder)

**Notes:**
________________________________________

---

#### Test 1.2: Recalculation Section Layout ⬜
- [X] In Tools tab, locate "Data Recalculation" section
- [X] Verify description text is visible and readable
- [X] Verify "Recalculate Everything" button is prominent (blue, large)
- [X] Verify scoped recalculation controls visible:
  - "Recalculate specific user/site:" label
  - User dropdown
  - Site dropdown
  - "Recalculate Pair" button
- [X] Why don't we have sessions included here?  Is that by design? - Verify statistics label shows: "Database: X pairs, Y purchases, Z redemptions, W allocations"

**Notes:**
________________________________________

---

#### Test 1.3: Empty Database Behavior ⬜
**Current State:** Database has 0 users, 0 sites, 0 purchases

- [X] Click "Recalculate Everything" button
- [X] Confirm dialog appears: "This will recalculate all FIFO allocations..."
- [X] Click "Yes"
- [X] It stalls with a 0% progress bar, and I have to close the app **Expected:** Progress dialog shows 0/0 pairs, completes immediately
- [X] **Expected:** Result dialog shows: "0 pairs processed, 0 redemptions"
- [X] **Expected:** No errors or crashes

**Notes:**
________________________________________

---

### Test Suite 2: Data Population

#### Test 2.1: Add Sample Data ⬜
Before testing with real data, add minimal sample data:

- [X] Go to Setup tab
- [X] Add 2 users (e.g., "Alice", "Bob")
- [X] Add 2 sites (e.g., "Stake", "Pulsz")
- [X] Go to Purchases tab
- [X] Add 3 purchases for Alice @ Stake
- [X] Add 2 purchases for Bob @ Pulsz
- [X] **Expected:** 2 user/site pairs with purchase data

**Notes:**
________________________________________

---

#### Test 2.2: Statistics Update ⬜
- [X] Return to Tools tab
- [X] Verify statistics updated:
  - "Database: 2 pairs, 5 purchases, 0 redemptions, 0 allocations"
- [X] User dropdown populated with Alice, Bob
- [X] Site dropdown populated with Stake, Pulsz

**Notes:**
________________________________________

---

### Test Suite 3: Recalculate Everything

#### Test 3.1: Full Recalculation (No Redemptions) ⬜
- [X] Click "Recalculate Everything"
- [X] Confirm dialog: Click "Yes"
- [X] **Progress Dialog Verification:**
  - [X] Dialog appears immediately
  - [X] Progress bar updates (0% → 100%)
  - [X] Status shows "Processing pair 1/2", "Processing pair 2/2"
  - [X] Details shows "Processing 1/2", "Processing 2/2"
  - [X] Cancel button present and enabled
  - [X] Dialog is modal (can't click main window)
- [X] **Result Dialog Verification:**
  - [X] Shows "Successfully recalculated 2 pairs"
  - [X] Shows "0 redemptions processed" (no redemptions yet)
  - [X] Shows purchases updated count
  - [X] Close button works

**Notes:**
________________________________________

---

#### Test 3.2: Add Redemptions and Recalculate ⬜
- [X] Go to Redemptions tab (if available) or Unrealized tab
- [X] Add 2 redemptions for Alice @ Stake
- [X] Add 1 redemption for Bob @ Pulsz
- [X] Return to Tools tab
- [X] Verify statistics show "3 redemptions"
- [X] Click "Recalculate Everything"
- [X] Confirm and observe progress
- [X] **Expected:** Result shows "3 redemptions processed", allocations written > 0

**Notes:**
________________________________________

---

### Test Suite 4: Scoped Recalculation

#### Test 4.1: Single Pair Recalculation ⬜
- [X] In Tools tab, select "Alice" from User dropdown
- [X] Select "Stake" from Site dropdown
- [X] Click "Recalculate Pair" button
- [X] **Confirmation Dialog:**
  - [X] Shows "Recalculate Alice @ Stake?"
  - [X] Click "Yes"
- [X] **Progress Dialog:**
  - [X] Shows "Recalculate Alice @ Stake - Progress"
  - [X] Faster than full recalculation
  - [X] Shows pair 1/1 (only one pair)
- [X] **Result Dialog:**
  - [X] Shows "1 pairs processed"
  - [X] Shows only Alice @ Stake redemptions processed

**Notes:**
________________________________________

---

### Test Suite 5: Progress and Cancellation

#### Test 5.1: UI Responsiveness During Recalculation ⬜
- [ ] Start "Recalculate Everything"
- [ ] While progress dialog is open:
  - [ ] Try to move progress dialog (should work)
  - [ ] Try to resize progress dialog (should work)
  - [ ] Try to click main window (should be blocked)
  - [ ] Try to switch tabs (should be blocked)
- [ ] Verify main window not frozen (no "Not Responding")

**Notes:**
________________________________________

---

#### Test 5.2: Cancellation Mid-Process ⬜
**Note:** This test needs larger dataset. If database too small, skip this test.

- [ ] Start "Recalculate Everything"
- [ ] Wait until progress shows ~50% (if possible)
- [ ] Click "Cancel" button
- [ ] **Expected:**
  - [ ] Cancellation warning appears: "Recalculation was cancelled..."
  - [ ] Warning recommends running recalculation again
  - [ ] Progress dialog closes
  - [ ] Can start new recalculation
  - [ ] No errors in console

**Notes:**
________________________________________

---

### Test Suite 6: Menu Integration

#### Test 6.1: Tools Menu Delegation ⬜
- [X] Switch to a different tab (e.g., Purchases)
- [X] Click Tools menu → "Recalculate Everything"
- [X] **Expected:**
  - [X] Tools tab automatically becomes active
  - [X] Confirmation dialog appears
  - [X] Full recalculation proceeds normally
  - [X] No duplicate dialogs

**Notes:**
________________________________________

---

### Test Suite 7: Post-Import Prompt (Future Test)

**Status:** CSV Import UI not yet built. This test will be relevant in Phase 5.

#### Test 7.1: Import Purchases → Prompt ⬜ (SKIP FOR NOW)
- [ ] Import purchases CSV
- [ ] Import result dialog shows
- [ ] Post-import prompt appears: "Recalculate FIFO allocations?"
- [ ] Shows affected users/sites count
- [ ] Click "Recalculate Now"
- [ ] Recalculation proceeds
- [ ] All tabs refresh

**Notes:** Will test in Phase 5 when CSV Import UI complete

---

## 📊 Test Summary

**Completed Tests:** ____ / 13  
**Passed:** ____  
**Failed:** ____  
**Skipped:** ____  

**Critical Issues Found:**
1. _____________________________________
2. _____________________________________
3. _____________________________________

**Non-Critical Issues:**
1. _____________________________________
2. _____________________________________

**Recommendations:**
- _____________________________________
- _____________________________________

---

## ✅ Sign-Off

**Backend Integration:** ✅ PASSED (All 6 tests)  
**UI Integration:** ⬜ IN PROGRESS  

**Tester Signature:** _____________________  
**Date:** _____________________  

**Ready for Phase 5?** YES / NO / WITH ISSUES

**Notes:**
________________________________________________________________
________________________________________________________________
________________________________________________________________
