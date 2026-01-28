# Dormant SC Implementation - Test Plan

## Changes Implemented

### 1. **Fixed Reactivation Bug** ✅
- **File:** `sezzions/services/game_session_service.py`
- **Change:** Added dormant purchase reactivation in `create_session()` method
- **Code:**
  ```python
  # IMPORTANT: Reactivate any dormant purchases for this site/user
  # When starting a new session, dormant SC becomes active again (matches legacy behavior)
  db.execute(
      """
      UPDATE purchases
      SET status = 'active', updated_at = CURRENT_TIMESTAMP
      WHERE site_id = ? AND user_id = ? AND status = 'dormant'
      """,
      (site_id, user_id),
  )
  ```

### 2. **Added Dormant SC Display** ✅
- **File:** `sezzions/ui/tabs/game_sessions_tab.py`
- **Changes:**
  - Added `dormant_sc_display` QLabel widget to StartSessionDialog
  - Added `_update_dormant_sc_display()` method
  - Connected to site/user combo changes
  - Displays: "ℹ️ X.XX SC (will reactivate)" or "None"
  - Shows in Balance Details section, right below Balance Check

---

## Test Scenarios

### **Test 1: Full Redemption with Fractional SC**

**Setup:**
1. Create a purchase: $100.45 SC
2. Create a game session with this balance
3. End the session with 100.45 SC remaining

**Test Steps:**
1. Go to Redemptions tab
2. Create a $100 redemption (Full Redemption)
3. Verify the redemption is processed
4. Go to Unrealized tab → Click "View Details" on the position
5. Verify: "Dormant SC balance: 0.45 SC"
6. Go back to Unrealized tab main view
7. Verify: Position is GONE (dormant = hidden)

**Expected Results:**
- ✅ Position removed from Unrealized tab
- ✅ Purchase status = 'dormant' in database
- ✅ remaining_amount still = 0.45 (basis preserved)

---

### **Test 2: Manual Close Balance**

**Setup:**
1. Have an unrealized position with remaining basis
2. Example: $50.00 remaining basis, 35.25 SC balance

**Test Steps:**
1. Go to Unrealized tab
2. Select the position
3. Click "Close Balance" button
4. Verify confirmation dialog shows:
   - Current SC balance
   - Cost basis
   - Net loss calculation
5. Confirm the close
6. Go to Realized tab
7. Verify: Entry shows "-$X.XX" net cash flow loss
8. Check the redemption note

**Expected Results:**
- ✅ $0 redemption created with note: "Balance Closed - Net Loss: $X.XX ($Y.YY SC marked dormant)"
- ✅ All active purchases for that site/user marked 'dormant'
- ✅ Position removed from Unrealized tab
- ✅ realized_transactions entry shows net loss

---

### **Test 3: Dormant SC Display in Start Session Dialog**

**Setup:**
1. Complete Test 1 or Test 2 to have dormant SC
2. Close all sessions for that site/user

**Test Steps:**
1. Go to Game Sessions tab
2. Click "➕ Start Session"
3. Select the User and Site that have dormant SC
4. Watch the "Dormant SC:" field in Balance Details section

**Expected Results:**
- ✅ Dormant SC field updates automatically when user/site selected
- ✅ Shows: "ℹ️ 0.45 SC (will reactivate)" (or appropriate amount)
- ✅ Tooltip explains: "Leftover SC from prior sessions that couldn't be redeemed. Will be reactivated when this session starts."
- ✅ If no dormant SC: Shows "None"

---

### **Test 4: Dormant SC Reactivation on Session Start** ⚠️ CRITICAL

**Prerequisites:**
- Complete Test 3 to see dormant SC display

**Test Steps:**
1. In Start Session dialog (with dormant SC shown)
2. Fill in all required fields:
   - Date/Time
   - User/Site (with dormant SC)
   - Game Type/Game
   - Starting Total SC: 100.00
   - Starting Redeemable: 100.00
3. Click "💾 Save"
4. Go to Unrealized tab
5. Verify: Position now appears again (reactivated!)
6. Check database directly:
   ```sql
   SELECT status, remaining_amount 
   FROM purchases 
   WHERE site_id = X AND user_id = Y;
   ```

**Expected Results:**
- ✅ Session created successfully
- ✅ Purchases status changed from 'dormant' to 'active'
- ✅ Position reappears in Unrealized tab
- ✅ remaining_amount unchanged (basis still there)
- ✅ Dormant SC can now be used for future redemptions

---

### **Test 5: Delete "Balance Closed" Redemption**

**Prerequisites:**
- Complete Test 2 (manual close balance)

**Test Steps:**
1. Go to Redemptions tab
2. Find the $0 redemption with "Balance Closed" in notes
3. Select it and click "Delete"
4. Confirm deletion
5. Go to Unrealized tab

**Expected Results:**
- ✅ Purchases automatically reactivated (status → 'active')
- ✅ Position reappears in Unrealized tab
- ✅ realized_transactions entry removed
- ✅ Cash flow loss reversed

---

### **Test 6: Multiple Partial Redemptions + Close Balance**

**Setup:**
1. Purchase: $100.00
2. Partial redemption: $25.00
3. Partial redemption: $30.00
4. Close balance manually

**Test Steps:**
1. Create the purchase and redemptions as above
2. Go to Unrealized tab
3. Close the remaining balance
4. Verify dormant SC = remaining basis
5. Start a new session for that site/user
6. Verify all purchases reactivated

**Expected Results:**
- ✅ Dormant SC = $100 - $25 - $30 = $45.00 basis
- ✅ All three purchase allocations preserved
- ✅ Reactivation brings back full remaining basis

---

## Verification Checklist

### UI Checks:
- [ ] Dormant SC field appears in Start Session dialog
- [ ] Dormant SC field appears in Edit Active Session dialog (if applicable)
- [ ] Field updates when user/site changed
- [ ] Shows "ℹ️ X.XX SC (will reactivate)" format
- [ ] Shows "None" when no dormant SC
- [ ] Tooltip text is helpful and accurate

### Database Checks:
- [ ] `purchases.status` correctly set to 'dormant' on close
- [ ] `purchases.status` correctly set to 'active' on reactivation
- [ ] `purchases.remaining_amount` unchanged during dormant/reactivate cycle
- [ ] $0 redemption created with proper notes on close balance
- [ ] realized_transactions entry created on close balance

### Behavior Checks:
- [ ] Positions hidden from Unrealized tab when dormant
- [ ] Positions reappear in Unrealized tab after reactivation
- [ ] FIFO excludes dormant purchases (they're not available for allocation)
- [ ] FIFO includes reactivated purchases after session start
- [ ] Deleting "Balance Closed" redemption reverses everything

### Legacy Parity:
- [ ] Behavior matches `business_logic.py` lines 1536-1559
- [ ] Matches `session2.py` close_unrealized_balance() method
- [ ] UI messages consistent with legacy "will reactivate" promise

---

## Edge Cases to Test

1. **Multiple users on same site:**
   - User A has dormant SC
   - User B starts session on same site
   - Verify: Only User A's dormant SC should reactivate when User A starts a session

2. **Same user on multiple sites:**
   - User has dormant SC on Site A and Site B
   - User starts session on Site A
   - Verify: Only Site A dormant SC reactivates

3. **Zero dormant SC:**
   - Site/user with no prior activity
   - Verify: Shows "None" cleanly

4. **Very small fractional amounts:**
   - 0.01 SC dormant
   - Verify: Displays and reactivates correctly

5. **Large dormant amounts:**
   - $999.99 dormant
   - Verify: No display issues, reactivates fully

---

## Rollback Plan

If issues are found:

1. **Remove UI changes:**
   - Comment out `dormant_sc_display` widget and method
   - Remove signal connections

2. **Revert reactivation logic:**
   - Comment out the `UPDATE purchases SET status = 'active'` block in `game_session_service.py`

3. **Database is safe:**
   - No schema changes were made
   - Status column already exists
   - No data corruption risk

---

## Success Criteria

✅ **Implementation Complete When:**
1. All 6 test scenarios pass
2. No errors in console during testing
3. Dormant SC displays correctly for all edge cases
