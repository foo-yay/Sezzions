# Session Reconciliation Override Implementation

## Executive Summary

This document describes the complete implementation of the **Session Reconciliation Override System** - a feature that allows users to manually force full basis consumption in sessions where prior unrecorded play has created balance discrepancies. This ensures mathematically correct lifetime P/L even when intermediate sessions are missing from the historical record.

**Status:** ✅ **FULLY IMPLEMENTED** (January 2026)

---

## Problem Statement

When a user has unrecorded gaming sessions, the current algorithm produces **incorrect taxable P/L** by:
1. Treating all prior redeemable balance as "discoverable" (newly won) in the first recorded session
2. Only consuming basis based on locked→redeemable conversion observed in the current session
3. Failing to account for basis already consumed in unrecorded play

### Real Example (Clubs Poker 1/25/26):

**Actual Economic Reality:**
- Total purchases: $60.00 ($20 on 12/22/25 + $40 on 1/25/26)
- Current redeemable balance: 100.43 SC
- **True net gain: $40.43**

**What Algorithm Calculates (WRONG):**
- Discoverable: 57.08 SC (treats prior balance as new winnings)
- Delta redeemable: 43.35 SC
- Total gain: 100.43 SC
- Basis consumed: $43.85 (only from this session's locked conversion)
- **Net taxable P/L: $56.58** ❌

**The Error:** $16.15 of basis ($60.00 - $43.85) is "lost" because it was consumed in the unrecorded 2025 session.

---

## Solution Overview: Reconciliation Override System

A manual intervention system that allows users to force consumption of all available cost basis in a session when they detect missing prior gameplay. This ensures **total lifetime P/L is correct** even when intermediate sessions are unknown.

### Key Principles:
1. **Overrides are sticky** - Survive rebuilds/recalculations
2. **Overrides cascade** - Affect downstream sessions via basis pool
3. **Overrides are auditable** - Clearly flagged and documented
4. **Overrides are reversible** - User can clear and recalculate
5. **Overrides are conservative** - Consume all basis = higher P/L (not hiding income)

### When to Use Reconciliation:
✅ **Appropriate:**
- Extra redeemable SC from **unrecorded gameplay**
- You know basis should have been consumed but wasn't tracked
- Example: Played sessions between purchases but forgot to record them

❌ **Inappropriate:**
- Gifts/bonuses (no basis involved - these are pure profit)
- Data entry errors (fix the actual data instead)
- Missing purchase records (add the purchase record)

---

## Implementation Details

### Phase 1: Database Schema Changes

**File:** `database.py`

Added three columns to `game_sessions` table:

```python
# In Database.__init__() migration section (~line 893)
# Check and add reconciliation override columns
columns = [row[1] for row in c.execute("PRAGMA table_info(game_sessions)").fetchall()]

if 'session_basis_override' not in columns:
    c.execute("ALTER TABLE game_sessions ADD COLUMN session_basis_override REAL")
    
if 'basis_consumed_override' not in columns:
    c.execute("ALTER TABLE game_sessions ADD COLUMN basis_consumed_override REAL")
    
if 'is_reconciliation' not in columns:
    c.execute("ALTER TABLE game_sessions ADD COLUMN is_reconciliation INTEGER DEFAULT 0")
```

**Column Definitions:**
- `session_basis_override` (REAL): Manual override value for total basis available in this session
- `basis_consumed_override` (REAL): Manual override value for basis consumed during this session
- `is_reconciliation` (INTEGER): Flag (0/1) indicating this session has reconciliation overrides applied

**Migration Pattern:**
- Additive migration (ALTER TABLE ADD COLUMN)
- Guarded by PRAGMA table_info check (idempotent)
- Safe to run multiple times
- NULL/0 defaults preserve existing sessions' behavior

---

### Phase 2: Business Logic Updates

**File:** `business_logic.py`

#### A. Override Detection in `_rebuild_session_tax_fields_for_pair()` (lines ~1137-1165)

The rebuild function checks for override flags and uses override values instead of calculating:

```python
# Check for reconciliation overrides
has_override = bool(s['is_reconciliation'] if 'is_reconciliation' in s.keys() else 0)

# Session basis calculation
if has_override and 'session_basis_override' in s.keys() and s['session_basis_override'] is not None:
    session_basis = float(s['session_basis_override'])
else:
    session_basis = float(pur_cash_to_end or 0)

# Pending basis pool management
pending_basis_pool += session_basis
if pending_basis_pool < 0:
    pending_basis_pool = 0.0

discoverable_sc = max(0.0, start_red - expected_start_redeem)
delta_play_sc = delta_redeem

# Basis consumed calculation
if has_override and 'basis_consumed_override' in s.keys() and s['basis_consumed_override'] is not None:
    basis_consumed = float(s['basis_consumed_override'])
else:
    locked_start = max(0.0, start_total - start_red)
    locked_end = max(0.0, end_total - end_red)
    locked_processed_sc = max(locked_start - locked_end, 0.0)
    locked_processed_value = locked_processed_sc * sc_rate
    basis_consumed = min(pending_basis_pool, locked_processed_value)

pending_basis_pool = max(0.0, pending_basis_pool - basis_consumed)
```

**Critical Note:** The override columns are accessed using `s['column_name']` with key existence checks because `s` is a `sqlite3.Row` object (NOT a dict). The pattern `'key' in s.keys()` must be used - `.get()` method doesn't exist on Row objects.

#### B. Override Detection in `_rebuild_session_tax_fields_for_pair_from()` (lines ~1362-1387)

Identical logic duplicated in the "from timestamp" variant:

```python
has_override = bool(s['is_reconciliation'] if 'is_reconciliation' in s.keys() else 0)

if has_override and 'session_basis_override' in s.keys() and s['session_basis_override'] is not None:
    session_basis = float(s['session_basis_override'])
else:
    session_basis = float(pur_cash_to_end or 0)

# ... (same pattern for basis_consumed)
```

#### C. Override Preservation During UPDATE (lines ~1175-1195)

**CRITICAL:** The UPDATE statement in rebuild functions writes to `session_basis` and `basis_consumed` (calculated fields), NOT to the override columns:

```python
c.execute("""
    UPDATE game_sessions
    SET
        session_basis=?,
        basis_consumed=?,
        expected_start_total_sc=?,
        expected_start_redeemable_sc=?,
        inferred_start_total_delta=?,
        inferred_start_redeemable_delta=?,
        delta_total=?,
        delta_redeem=?,
        net_taxable_pl=?,
        total_taxable=?,
        sc_change=?,
        rtp=?,
        basis_bonus=NULL,
        gameplay_pnl=NULL
    WHERE id=?
""", (session_basis, basis_consumed, ...))
```

**Why This Works:**
- Override columns (`*_override`, `is_reconciliation`) are SEPARATE from calculated columns
- Rebuild writes calculated values but doesn't touch override columns
- Override columns persist across rebuilds (sticky behavior)
- When overrides exist, calculated values reflect the override-adjusted basis

---

### Phase 3: UI Implementation

**File:** `qt_app.py`

#### A. GameSessionStartDialog (Active Sessions)

**Location:** Lines ~3020-3650

##### 1. Redeemable Balance Check Display (lines ~3100-3120)

Added row 2 in the balance check section:

```python
balance_grid.addWidget(QtWidgets.QLabel("Redeemable Check:"), 2, 0)
self.redeem_check_value = QtWidgets.QLabel("—")
self.redeem_check_value.setObjectName("InfoField")
self.redeem_check_value.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
self.redeem_check_value.setProperty("status", "neutral")
balance_grid.addWidget(self.redeem_check_value, 2, 1, 1, 3)
```

**Purpose:** Shows comparison of actual starting redeemable SC vs. expected, alerting user to potential missing sessions.

**Display States:**
- `"+50.47 SC (expected 0.00)"` - More SC than expected (warning status)
- `"OK (0.00 SC)"` - Matches expected (neutral status)
- `"-10.00 SC (expected 50.00)"` - Less SC than expected (negative status)
- `"✓ Reconciliation applied"` - Override is active (neutral status)

##### 2. Reconciliation Buttons (lines ~3122-3140)

Added two buttons on row 2 next to the redeemable check:

```python
self.reconcile_btn = QtWidgets.QPushButton("Reconcile with Full Basis")
self.reconcile_btn.setObjectName("ActionButton")
self.reconcile_btn.setToolTip("Apply all available basis to this session")
self.reconcile_btn.hide()  # Only show when discrepancy detected
balance_grid.addWidget(self.reconcile_btn, 2, 4)

self.clear_reconcile_btn = QtWidgets.QPushButton("Clear Reconciliation")
self.clear_reconcile_btn.setObjectName("DangerButton")
self.clear_reconcile_btn.hide()  # Only show when override is active
balance_grid.addWidget(self.clear_reconcile_btn, 2, 5)
```

**Button Visibility Logic:**
- `reconcile_btn`: Shows when redeemable check detects `delta_redeem > 0.5 SC` AND no override is active
- `clear_reconcile_btn`: Shows when `reconciliation_override` is set (override is active)

##### 3. Update Logic in `_update_freebie_label()` (lines ~3395-3415)

Called whenever balance fields change to update the redeemable check:

```python
# Get starting redeemable and compare to expected
start_redeem_text = self.start_redeem_edit.text().strip()
if start_redeem_text:
    valid_redeem, start_redeem = validate_currency(start_redeem_text)
    if valid_redeem:
        delta_redeem = start_redeem - expected_redeem
        
        # If reconciliation already applied, show that instead of warning
        if self.reconciliation_override:
            self.redeem_check_value.setProperty("status", "neutral")
            self.redeem_check_value.setText("✓ Reconciliation applied")
            self.reconcile_btn.setVisible(False)
        elif delta_redeem > 0.5:  # Threshold to avoid noise
            self.redeem_check_value.setProperty("status", "warning")
            self.redeem_check_value.setText(f"+{delta_redeem:.2f} SC (expected {expected_redeem:.2f})")
            self.reconcile_btn.setVisible(True)
        # ... other cases
```

**Order of Operations Critical:** When loading existing session with override, must set `self.reconciliation_override` BEFORE calling `_update_freebie_label()` so the check text displays correctly.

##### 4. Reconciliation Dialog (`_show_reconciliation_dialog()`, lines ~3446-3560)

Displayed when user clicks "Reconcile with Full Basis":

```python
def _show_reconciliation_dialog(self):
    # Calculate available basis
    site_id, user_id = self._lookup_ids(site_name, user_name)
    info = self.session_mgr.detect_freebies(site_id, user_id, ...)
    total_basis = float(info.get('pending_basis_pool', 0.0))
    
    # Show dialog explaining reconciliation
    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle("Reconcile Session with Full Basis")
    
    # Header explaining what reconciliation does
    header = QtWidgets.QLabel(
        "This will consume ALL available cost basis in this session.\n\n"
        "Use this when you have unrecorded gameplay between purchases. "
        "Reconciliation will consume all $60.00 of basis to minimize taxable income."
    )
    
    # Basis summary showing amount to consume
    summary_group = QtWidgets.QGroupBox("Basis Summary")
    summary_layout.addWidget(QtWidgets.QLabel("Available Basis:"), 0, 0)
    summary_layout.addWidget(QtWidgets.QLabel(f"${total_basis:.2f}"), 0, 1)
    
    # Warning about tax year implications
    warning_label = QtWidgets.QLabel(
        "Applying reconciliation will:\n"
        "• Consume all $60.00 of available basis in this session\n"
        "• Flag this session as 'Reconciliation' for audit purposes\n"
        "• Report the full net P/L in this session's tax year\n\n"
        "The total lifetime P/L will be correct, even if some gains occurred in prior years."
    )
    
    # Accept = Apply reconciliation
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        self.reconciliation_override = {
            'session_basis': total_basis,
            'basis_consumed': total_basis,
            'is_reconciliation': 1
        }
        
        # Add note to session
        current_notes = self.notes_edit.toPlainText().strip()
        reconcile_note = f"Reconciliation applied: ${total_basis:.2f} basis consumed."
        if current_notes:
            self.notes_edit.setPlainText(f"{current_notes}\n\n{reconcile_note}")
        else:
            self.notes_edit.setPlainText(reconcile_note)
        
        # Update button visibility
        self.reconcile_btn.hide()
        self.clear_reconcile_btn.show()
        
        # Update redeemable check to show reconciliation applied
        self._update_freebie_label()
```

**Dialog Flow:**
1. Calculate total available basis from `pending_basis_pool`
2. Show explanation of what reconciliation does
3. Display basis amount that will be consumed
4. Warn about tax year implications
5. On accept: Store override dict, add note, update UI

##### 5. Clear Reconciliation (`_clear_reconciliation()`, lines ~3571-3577)

Removes override and reverts to automatic calculation:

```python
def _clear_reconciliation(self):
    self.reconciliation_override = None
    self.reconcile_btn.show()
    self.clear_reconcile_btn.hide()
    
    # Remove reconciliation note from notes field
    current_notes = self.notes_edit.toPlainText()
    # (Note removal logic)
    
    self._update_freebie_label()  # Refresh to show warning again
```

##### 6. Loading Existing Session with Override (`_load_session()`, lines ~3608-3650)

When editing an active session that already has reconciliation applied:

```python
def _load_session(self):
    # Load form fields first
    self.start_total_edit.setText(str(self.session["starting_sc_balance"]))
    # ... other fields
    
    # Check for reconciliation overrides BEFORE updating labels
    is_reconciliation = (self.session.get("is_reconciliation") 
                        if isinstance(self.session, dict) 
                        else (self.session["is_reconciliation"] 
                              if "is_reconciliation" in self.session.keys() else 0))
    
    if is_reconciliation:
        # Load override values from database
        session_basis = (self.session.get("session_basis_override") 
                        if isinstance(self.session, dict) 
                        else (self.session["session_basis_override"] 
                              if "session_basis_override" in self.session.keys() else None))
        basis_consumed = ...  # Same pattern
        
        if session_basis is not None and basis_consumed is not None:
            self.reconciliation_override = {
                "session_basis": session_basis,
                "basis_consumed": basis_consumed,
                "is_reconciliation": 1
            }
            # Update button visibility
            self.reconcile_btn.hide()
            self.clear_reconcile_btn.show()
    
    # Update labels AFTER setting reconciliation_override
    self._update_freebie_label()
    self._update_rtp_tooltip()
```

**Critical Order:** Must set `reconciliation_override` BEFORE calling `_update_freebie_label()` so the redeemable check displays "✓ Reconciliation applied" instead of the warning.

##### 7. Saving Active Session with Override (`_save_start_session()`, lines ~9411-9614)

When saving an active session (new or editing existing):

```python
def _save_start_session(self, dialog, session_id):
    data, error = dialog.collect_data()
    
    if session_id:
        # Editing existing active session
        # Extract reconciliation overrides if present
        session_basis_override = data.get("session_basis")
        basis_consumed_override = data.get("basis_consumed")
        is_reconciliation = data.get("is_reconciliation", 0)
        
        c.execute("""
            UPDATE game_sessions
            SET session_date=?, start_time=?, site_id=?, user_id=?,
                game_type=?, game_name=?, wager_amount=?,
                starting_sc_balance=?, starting_redeemable_sc=?, notes=?,
                session_basis_override=?, basis_consumed_override=?, is_reconciliation=?
            WHERE id=?
        """, (..., session_basis_override, basis_consumed_override, is_reconciliation, session_id))
    else:
        # Creating new session - start_game_session() first, then UPDATE overrides
        session_id = self.session_mgr.start_game_session(...)
        
        session_basis_override = data.get("session_basis")
        basis_consumed_override = data.get("basis_consumed")
        is_reconciliation = data.get("is_reconciliation", 0)
        
        c.execute("""
            UPDATE game_sessions
            SET game_name=?, wager_amount=?,
                session_basis_override=?, basis_consumed_override=?, is_reconciliation=?
            WHERE id=?
        """, (game_name, wager_amount, session_basis_override, basis_consumed_override, 
              is_reconciliation, session_id))
```

**Two Paths:**
- **Editing existing:** Override columns included in main UPDATE statement
- **Creating new:** Session created first, then UPDATE adds overrides

**Data Collection:** The `dialog.collect_data()` method includes reconciliation override if set:

```python
# In GameSessionStartDialog.collect_data() (line ~3654)
data = {
    "session_date": ...,
    "start_time": ...,
    # ... other fields
}

# Include reconciliation overrides if set
if self.reconciliation_override:
    data.update(self.reconciliation_override)

return data, None
```

#### B. GameSessionEditDialog (Closed Sessions)

**Location:** Lines ~4025-4980

##### 1. Similar UI Structure

Closed session editing has parallel implementation:
- Redeemable check display (not needed - balances are fixed)
- Balance check shows both Total SC and Redeemable SC discrepancies
- Reconciliation buttons (same as active sessions)
- Reconciliation dialog (nearly identical)

##### 2. Key Difference: Balance Check Display (lines ~4340-4380)

For closed sessions, shows discrepancy in BOTH total and redeemable:

```python
def _update_balance_label(self):
    # ... calculate expected values
    
    delta_total = start_total - expected_total
    delta_redeem = start_redeem - expected_redeem
    
    # Show reconcile button if redeemable is higher than expected
    if delta_redeem > 0.5 and not self.reconciliation_override:
        self.apply_reconciliation_btn.show()
    else:
        self.apply_reconciliation_btn.hide()
    
    # Display both checks
    if abs(delta_total) < 0.5:
        total_status = "OK"
    elif delta_total > 0:
        total_status = f"+{delta_total:.2f} SC"
    else:
        total_status = f"-{abs(delta_total):.2f} SC"
    
    # Same for redeemable
    self.balance_value.setText(f"Total: {total_status}, Redeemable: {redeem_status}")
```

##### 3. Loading Existing Closed Session with Override (`_load_session()`, lines ~4810-4860)

Same pattern as active sessions - loads override values and sets button visibility:

```python
def _load_session(self):
    # Debug output
    print(f"DEBUG _load_session (GameSessionEditDialog):")
    print(f"  is_reconciliation: {self.session.get('is_reconciliation')}")
    
    # Load form fields
    # ...
    
    # Check for reconciliation (same pattern as active sessions)
    is_reconciliation = ...
    if is_reconciliation:
        # Load overrides
        self.reconciliation_override = {
            "session_basis": session_basis,
            "basis_consumed": basis_consumed,
            "is_reconciliation": 1
        }
        self.reconciliation_label.setText("⚠️ This session has reconciliation overrides applied")
        self.reconciliation_label.show()
        self.clear_reconciliation_btn.show()
        self.apply_reconciliation_btn.hide()
    else:
        self.reconciliation_label.hide()
        self.clear_reconciliation_btn.hide()
```

##### 4. Clear Reconciliation Handler (`_handle_clear_reconciliation()`, lines ~4493-4545)

For closed sessions, clearing reconciliation requires database update and rebuild:

```python
def _handle_clear_reconciliation(self):
    reply = QtWidgets.QMessageBox.question(...)
    if reply != QtWidgets.QMessageBox.Yes:
        return
    
    conn = self.db.get_connection()
    c = conn.cursor()
    
    # Clear the override fields in database
    c.execute("""
        UPDATE game_sessions
        SET session_basis_override = NULL,
            basis_consumed_override = NULL,
            is_reconciliation = 0
        WHERE id = ?
    """, (self.session["id"],))
    
    conn.commit()
    conn.close()
    
    # Trigger recalculation
    site_id = self.session["site_id"]
    user_id = self.session["user_id"]
    self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id)
    
    QtWidgets.QMessageBox.information(self, "Success", "Reconciliation cleared. Session recalculated.")
    self.accept()  # Close dialog
    
    # Refresh parent view
    parent = self.parent()
    if hasattr(parent, 'load_data'):
        parent.load_data()
```

**Why Close Dialog:** Clearing reconciliation triggers a rebuild that changes the session's P/L. Rather than try to reload the dialog state, it's cleaner to close and let the user reopen if needed.

##### 5. Saving Closed Session with Override (`_save_closed_session()`, lines ~9695-10000)

**Most Complex Part** - Multiple code paths with optimization logic that must be bypassed when reconciliation is applied.

###### Step 1: Detect Reconciliation Application (lines ~9800-9803)

```python
# Detect if reconciliation is being applied
applying_reconciliation = data.get("is_reconciliation", 0) == 1
```

###### Step 2: Bypass Fast Paths (lines ~9806-9872)

The save function has optimizations for notes-only and RTP-only changes. These must be bypassed when reconciliation is applied:

```python
# Notes-only change - skip recomputation (UNLESS reconciliation is being applied)
if changed_fields == {'notes'} and not applying_reconciliation:
    c.execute("UPDATE game_sessions SET notes=? WHERE id=?", ...)
    # ... early return

# RTP-only change - update RTP directly (UNLESS reconciliation is being applied)
rtp_only_fields = {'wager_amount', 'game_id'}
if changed_fields and changed_fields <= rtp_only_fields and not applying_reconciliation:
    c.execute("UPDATE game_sessions SET wager_amount=?, game_id=?, ...", ...)
    # ... early return
```

**Why Bypass:** The fast paths don't include override columns in their UPDATE statements. We must force the full path that includes all columns.

###### Step 3: Full UPDATE with Override Columns (lines ~9880-9925)

```python
c.execute("""
    UPDATE game_sessions
    SET session_date=?, end_date=?, start_time=?, end_time=?,
        site_id=?, user_id=?, game_type=?, game_name=?, wager_amount=?,
        starting_sc_balance=?, starting_redeemable_sc=?,
        ending_sc_balance=?, ending_redeemable_sc=?,
        notes=?,
        session_basis_override=?,
        basis_consumed_override=?,
        is_reconciliation=?
    WHERE id=?
""", (
    data["session_date"], data["end_date"], data["start_time"], data["end_time"],
    new_site_id, new_user_id, data["game_type"], data["game_name"], data["wager_amount"],
    data["starting_total_sc"], data["starting_redeemable_sc"],
    data["ending_total_sc"], data["ending_redeemable_sc"],
    data["notes"],
    data.get("session_basis") if isinstance(data, dict) else None,
    data.get("basis_consumed") if isinstance(data, dict) else None,
    data.get("is_reconciliation", 0) if isinstance(data, dict) else 0,
    old_session["id"],
))
conn.commit()
conn.close()
```

**Debug Checkpoint:** After commit, verify override columns were saved:

```python
if data.get("is_reconciliation"):
    c2 = conn.cursor()
    c2.execute("SELECT session_basis_override, basis_consumed_override, is_reconciliation 
                FROM game_sessions WHERE id = ?", (old_session["id"],))
    check = c2.fetchone()
    print(f"DEBUG: After UPDATE, before rebuild - DB values:")
    print(f"  session_basis_override: {check['session_basis_override']}")
    print(f"  basis_consumed_override: {check['basis_consumed_override']}")
    print(f"  is_reconciliation: {check['is_reconciliation']}")
```

###### Step 4: Force Rebuild of This Session (lines ~9927-9943)

```python
# If reconciliation was applied, force rebuild of this specific session
if data.get("is_reconciliation"):
    self.session_mgr._rebuild_session_tax_fields_for_pair_from(
        new_site_id, new_user_id, data["session_date"], data["start_time"]
    )
    
    # Debug: Verify overrides still exist after rebuild
    conn2 = self.db.get_connection()
    c3 = conn2.cursor()
    c3.execute("SELECT session_basis_override, basis_consumed_override, is_reconciliation 
                FROM game_sessions WHERE id = ?", (old_session["id"],))
    check2 = c3.fetchone()
    conn2.close()
    print(f"DEBUG: After rebuild - DB values:")
    print(f"  session_basis_override: {check2['session_basis_override']}")
```

**Why Force Rebuild:** The UPDATE saves the override columns, but the session's calculated fields (net_taxable_pl, etc.) haven't been recalculated yet. The rebuild reads the override columns and applies them to the calculation.

###### Step 5: Skip Auto-Recalculate to Preserve Overrides (lines ~9959-9999)

```python
# Skip auto_recalculate if reconciliation was applied - we already did the rebuild above
# and don't want to clear the overrides
if not data.get("is_reconciliation"):
    # Scoped recalculation using new API
    if (new_site_id, new_user_id) != (old_site_id, old_user_id):
        # Old pair: remove old timestamp
        total_recalc = self.session_mgr.auto_recalculate_affected_sessions(...)
        # New pair: add new timestamp
        total_recalc += self.session_mgr.auto_recalculate_affected_sessions(...)
    else:
        # Same pair: use both timestamps
        total_recalc = self.session_mgr.auto_recalculate_affected_sessions(...)
else:
    # Reconciliation was applied - skip auto_recalculate to preserve overrides
    total_recalc = 0
```

**CRITICAL:** The `auto_recalculate_affected_sessions` function would rebuild from the edited session forward, which would **overwrite the override columns** back to NULL. By skipping this when reconciliation is applied, we preserve the overrides.

**Why This Works:**
1. We already did a targeted rebuild of the specific session (step 4)
2. Downstream sessions don't need recalculation because the override affects them via `pending_basis_pool` cascade
3. The override columns remain intact in the database

---

### Phase 4: User Workflow Examples

#### Scenario 1: Apply Reconciliation to New Active Session

**Steps:**
1. User starts new session: $100 purchase, starting balance 150 SC, starting redeemable 50 SC
2. Redeemable check shows: "+50.00 SC (expected 0.00)" in warning status
3. "Reconcile with Full Basis" button appears
4. User clicks button → Dialog shows "$100.00 available basis"
5. User confirms → Override set, note added, button changes to "Clear Reconciliation"
6. Redeemable check updates to "✓ Reconciliation applied"
7. User saves session

**Database State:**
- `session_basis_override` = 100.00
- `basis_consumed_override` = 100.00
- `is_reconciliation` = 1
- Note: "Reconciliation applied: $100.00 basis consumed."

**Calculation Result:**
- Discoverable: 50.00 SC ($50)
- Delta play: (end_redeem - start_redeem)
- Basis consumed: $100.00 (override)
- Net taxable P/L = ($50 + delta_play) - $100 = correct P/L

#### Scenario 2: Edit Closed Session and Apply Reconciliation

**Steps:**
1. User opens edit dialog for closed session from 1/25/26
2. Balance check shows discrepancy
3. User clicks "Apply Reconciliation" → Dialog appears
4. User confirms → Warning label appears: "⚠️ Reconciliation will be applied when you save"
5. Reconciliation note added to notes field
6. "Clear Reconciliation" button appears
7. User clicks Save

**Behind the Scenes:**
1. `collect_data()` includes override dict
2. Fast paths bypassed (applying_reconciliation = True)
3. UPDATE statement includes override columns
4. Commit to database (overrides saved)
5. Force rebuild of this session (applies overrides to calculation)
6. Skip auto_recalculate (preserves overrides)
7. Dialog closes, table refreshes

**Result:**
- Session shows corrected taxable P/L
- Flagged as reconciliation session (visual indicator could be added)
- Can be reopened and cleared if needed

#### Scenario 3: Clear Reconciliation from Closed Session

**Steps:**
1. User opens edit dialog for session with reconciliation
2. Debug output shows: `is_reconciliation: 1`, override values loaded
3. "Clear Reconciliation" button visible, "Apply Reconciliation" hidden
4. Redeemable check (if applicable) shows "✓ Reconciliation applied"
5. User clicks "Clear Reconciliation"
6. Confirmation dialog: "This will remove the reconciliation overrides..."
7. User confirms

**Behind the Scenes:**
1. UPDATE sets override columns to NULL, is_reconciliation to 0
2. auto_recalculate_affected_sessions() rebuilds from this session forward
3. Rebuild uses automatic calculation (no overrides)
4. Dialog closes, parent table refreshes

**Result:**
- Session reverts to calculated P/L (may be incorrect again)
- Reconciliation warning may reappear when session is reopened
- Override can be reapplied if needed

#### Scenario 4: Load Existing Session with Reconciliation

**Steps:**
1. User clicks edit on a session that already has reconciliation
2. `_load_session()` called
3. Debug output: "Keys in session: [..., 'session_basis_override', 'basis_consumed_override', 'is_reconciliation', ...]"
4. Check shows: `is_reconciliation: 1`, override values: 60.0, 60.0

**Loading Process:**
1. Load form fields with session data
2. Check `is_reconciliation` flag
3. If flag is 1, load override values into `reconciliation_override` dict
4. Set button visibility: hide apply, show clear
5. Call `_update_freebie_label()` (for active) or `_update_balance_label()` (for closed)
6. Label shows "✓ Reconciliation applied"

**Result:**
- Dialog displays correctly showing reconciliation is active
- User can clear if desired
- If saved without changes, overrides are preserved

---

## Implementation Challenges & Solutions

### Challenge 1: sqlite3.Row Access Pattern

**Problem:** Database queries return `sqlite3.Row` objects which don't support `.get()` method.

**Solution:** Use bracket notation with key existence checks:
```python
# WRONG:
value = row.get('column_name', default)

# CORRECT:
value = row['column_name'] if 'column_name' in row.keys() else default
```

**Locations:** business_logic.py lines 1137, 1152, 1362, 1373

### Challenge 2: Fast Path Optimization Bypass

**Problem:** `_save_closed_session()` has optimized fast paths for notes-only and RTP-only changes that don't include override columns.

**Solution:** Detect when reconciliation is being applied and bypass fast paths:
```python
applying_reconciliation = data.get("is_reconciliation", 0) == 1

if changed_fields == {'notes'} and not applying_reconciliation:
    # notes-only fast path
```

**Locations:** qt_app.py lines 9800-9872

### Challenge 3: Override Preservation During Rebuild

**Problem:** After saving override columns, `auto_recalculate_affected_sessions()` would rebuild from that session forward and clear the overrides.

**Solution:** Skip auto_recalculate when reconciliation is applied:
```python
if not data.get("is_reconciliation"):
    # Do auto_recalculate
else:
    # Skip - we already did targeted rebuild
    total_recalc = 0
```

**Locations:** qt_app.py lines 9959-9999

### Challenge 4: Update Order in _load_session()

**Problem:** Calling `_update_freebie_label()` before setting `reconciliation_override` caused the redeemable check to show the warning instead of "✓ Reconciliation applied".

**Solution:** Load override values first, THEN update labels:
```python
# 1. Load form fields
# 2. Check and load reconciliation_override
# 3. Update labels (which now see the override)
```

**Locations:** qt_app.py lines 3608-3650 (active), 4810-4860 (closed)

### Challenge 5: Separate Override Columns vs Calculated Columns

**Problem:** Initially unclear whether override columns should replace calculated columns or be separate.

**Solution:** Keep them separate:
- Override columns: `*_override`, `is_reconciliation` - User input, sticky
- Calculated columns: `session_basis`, `basis_consumed` - Always reflect current calculation
- Rebuild reads overrides, writes calculated values
- Override columns never touched by rebuild

**Design Rationale:** Separation allows viewing both the override value and what the calculated value would have been, aids debugging, and prevents accidental override loss.

---

## Testing & Validation

### Debug Output Added

Throughout development, strategic debug output was added to trace the flow:

```python
# In _save_closed_session()
if data.get("is_reconciliation"):
    print(f"DEBUG: Reconciliation override detected in data:")
    print(f"  session_basis: {data.get('session_basis')}")
    print(f"  basis_consumed: {data.get('basis_consumed')}")
    print(f"  is_reconciliation: {data.get('is_reconciliation')}")

# In _load_session() GameSessionEditDialog
print(f"DEBUG _load_session (GameSessionEditDialog):")
print(f"  Keys in session: {list(self.session.keys())}")
print(f"  is_reconciliation: {self.session.get('is_reconciliation')}")
print(f"  session_basis_override: {self.session.get('session_basis_override')}")

# After UPDATE
print(f"DEBUG: After UPDATE, before rebuild - DB values:")
print(f"  session_basis_override: {check['session_basis_override']}")

# After rebuild
print(f"DEBUG: After rebuild - DB values:")
print(f"  session_basis_override: {check2['session_basis_override']}")
```

**Purpose:** These debug statements helped identify:
1. Fast path bypass issue (no debug output = wrong path taken)
2. Override persistence issue (values correct after UPDATE but NULL after recalculate)
3. Load order issue (override NULL in _load_session despite being in database)

**Recommendation:** Remove or comment out debug statements in production, but keep them in comments for future debugging.

### Test Scenarios Validated

✅ **Scenario 1:** Apply reconciliation to new active session → Save → Reopen → Verify override persists
✅ **Scenario 2:** Apply reconciliation to closed session → Save → Verify P/L changes → Reopen → Verify "Clear" button shows
✅ **Scenario 3:** Clear reconciliation from closed session → Verify revert to calculated values
✅ **Scenario 4:** Edit session with reconciliation without changing override → Save → Verify override preserved
✅ **Scenario 5:** Apply reconciliation, then edit ending balance → Save → Verify override preserved, P/L recalculated with new balance

---

## Port to Sezzions OOP Architecture

### Overview of Sezzions Structure

Based on the attached folder, Sezzions uses a clean OOP architecture with:
- **Models:** Data classes (game_session.py, purchase.py, etc.)
- **Repositories:** Database access layer (game_session_repository.py, etc.)
- **Services:** Business logic layer (game_session_service.py, fifo_service.py, etc.)
- **UI:** Separate UI layer (not yet implemented in attached folder)

### Step-by-Step Port Guide

#### Step 1: Extend GameSession Model

**File:** `sezzions/models/game_session.py`

Add three fields to the GameSession dataclass:

```python
@dataclass
class GameSession:
    # ... existing fields ...
    
    # Reconciliation override fields
    session_basis_override: Optional[Decimal] = None
    basis_consumed_override: Optional[Decimal] = None
    is_reconciliation: bool = False
```

**Notes:**
- Use `Decimal` type for monetary values (consistent with Sezzions pattern)
- Default to None/False (existing sessions have no overrides)
- Add to `__post_init__` validation if needed

#### Step 2: Update GameSessionRepository

**File:** `sezzions/repositories/game_session_repository.py`

##### A. Add Columns to CREATE TABLE Statement

```python
def _create_table(self):
    self.db.execute("""
        CREATE TABLE IF NOT EXISTS game_sessions (
            -- ... existing columns ...
            session_basis_override REAL,
            basis_consumed_override REAL,
            is_reconciliation INTEGER DEFAULT 0
        )
    """)
```

##### B. Update SELECT Queries

Add new columns to all SELECT statements:

```python
def get_by_id(self, session_id: int) -> Optional[GameSession]:
    row = self.db.fetch_one("""
        SELECT id, session_date, start_time, ...,
               session_basis_override, basis_consumed_override, is_reconciliation
        FROM game_sessions
        WHERE id = ?
    """, (session_id,))
    
    if row:
        return self._row_to_model(row)
    return None
```

##### C. Update INSERT/UPDATE Statements

```python
def create(self, session: GameSession) -> GameSession:
    cursor = self.db.execute("""
        INSERT INTO game_sessions (
            session_date, start_time, ...,
            session_basis_override, basis_consumed_override, is_reconciliation
        ) VALUES (?, ?, ..., ?, ?, ?)
    """, (
        session.session_date, session.start_time, ...,
        float(session.session_basis_override) if session.session_basis_override else None,
        float(session.basis_consumed_override) if session.basis_consumed_override else None,
        1 if session.is_reconciliation else 0
    ))
    # ...

def update(self, session: GameSession) -> GameSession:
    self.db.execute("""
        UPDATE game_sessions
        SET session_date=?, start_time=?, ...,
            session_basis_override=?, basis_consumed_override=?, is_reconciliation=?
        WHERE id=?
    """, (
        session.session_date, session.start_time, ...,
        float(session.session_basis_override) if session.session_basis_override else None,
        float(session.basis_consumed_override) if session.basis_consumed_override else None,
        1 if session.is_reconciliation else 0,
        session.id
    ))
    return session
```

##### D. Update _row_to_model()

```python
def _row_to_model(self, row: sqlite3.Row) -> GameSession:
    return GameSession(
        id=row['id'],
        session_date=...,
        # ... existing fields ...
        session_basis_override=Decimal(str(row['session_basis_override'])) if row['session_basis_override'] else None,
        basis_consumed_override=Decimal(str(row['basis_consumed_override'])) if row['basis_consumed_override'] else None,
        is_reconciliation=bool(row['is_reconciliation']) if 'is_reconciliation' in row.keys() else False
    )
```

#### Step 3: Update FIFOService

**File:** `sezzions/services/fifo_service.py`

This is the equivalent of `business_logic.py`'s rebuild functions.

##### A. Add Override Check in Rebuild Logic

```python
def rebuild_sessions_for_pair(
    self,
    site_id: int,
    user_id: int,
    from_date: Optional[date] = None
) -> List[GameSession]:
    """
    Rebuild all session calculations for a site/user pair.
    Respects reconciliation overrides when present.
    """
    sessions = self.session_repo.get_by_site_user(site_id, user_id, from_date)
    
    pending_basis_pool = Decimal('0')
    last_end_total = Decimal('0')
    last_end_redeem = Decimal('0')
    
    for session in sessions:
        # Get purchases between last session end and this session start
        purchases = self.purchase_repo.get_between_dates(...)
        
        # Calculate expected starting balances
        expected_start_total = ...
        expected_start_redeem = ...
        
        # Check for reconciliation override
        if session.is_reconciliation and session.session_basis_override is not None:
            session_basis = session.session_basis_override
        else:
            # Calculate from purchases
            session_basis = sum(p.amount for p in purchases_in_session)
        
        pending_basis_pool += session_basis
        
        # Calculate basis consumed
        if session.is_reconciliation and session.basis_consumed_override is not None:
            basis_consumed = session.basis_consumed_override
        else:
            # Calculate from locked SC conversion
            locked_start = max(Decimal('0'), session.starting_sc_balance - session.starting_redeemable_sc)
            locked_end = max(Decimal('0'), session.ending_sc_balance - session.ending_redeemable_sc)
            locked_processed = max(locked_start - locked_end, Decimal('0'))
            basis_consumed = min(pending_basis_pool, locked_processed)
        
        pending_basis_pool = max(Decimal('0'), pending_basis_pool - basis_consumed)
        
        # Calculate net P/L
        discoverable_sc = max(Decimal('0'), session.starting_redeemable_sc - expected_start_redeem)
        delta_play_sc = session.ending_redeemable_sc - session.starting_redeemable_sc
        net_taxable_pl = (discoverable_sc + delta_play_sc) - basis_consumed
        
        # Update session with calculated values (preserve override columns)
        session.session_basis = session_basis  # Calculated, not override
        session.basis_consumed = basis_consumed  # Calculated, not override
        session.net_taxable_pl = net_taxable_pl
        session.expected_start_total_sc = expected_start_total
        session.expected_start_redeemable_sc = expected_start_redeem
        # ... other calculated fields
        
        # Save updated session
        self.session_repo.update(session)
        
        # Update last_end values for next iteration
        last_end_total = session.ending_sc_balance
        last_end_redeem = session.ending_redeemable_sc
    
    return sessions
```

**Key Points:**
- Check `session.is_reconciliation` flag
- If true and override values exist, use them
- Otherwise calculate normally
- Update statement preserves override columns (they're already in the model)
- Sezzions pattern: modify the model object, then call `repo.update(session)`

##### B. Add Method to Detect Redeemable Discrepancy

```python
def detect_redeemable_discrepancy(
    self,
    site_id: int,
    user_id: int,
    starting_redeemable: Decimal,
    session_date: date,
    session_time: Optional[time] = None
) -> Tuple[Decimal, Decimal, bool]:
    """
    Compare actual starting redeemable SC to expected based on history.
    Returns: (expected_redeem, delta_redeem, should_show_reconcile_button)
    """
    # Get last session end values
    last_session = self.session_repo.get_last_before_datetime(
        site_id, user_id, session_date, session_time
    )
    
    if last_session:
        last_end_redeem = last_session.ending_redeemable_sc or Decimal('0')
    else:
        last_end_redeem = Decimal('0')
    
    # Get redemptions between last session and this session
    redemptions = self.redemption_repo.get_between_dates(...)
    total_redeemed = sum(r.amount for r in redemptions)
    
    expected_redeem = max(Decimal('0'), last_end_redeem - total_redeemed)
    delta_redeem = starting_redeemable - expected_redeem
    
    # Show reconcile button if delta > 0.5 SC
    should_reconcile = delta_redeem > Decimal('0.5')
    
    return (expected_redeem, delta_redeem, should_reconcile)
```

##### C. Add Method to Calculate Available Basis

```python
def get_available_basis_for_session(
    self,
    site_id: int,
    user_id: int,
    session_date: date,
    session_time: Optional[time] = None
) -> Decimal:
    """
    Calculate total available cost basis at session start.
    This is the pending_basis_pool value.
    """
    sessions = self.session_repo.get_by_site_user_before_datetime(
        site_id, user_id, session_date, session_time
    )
    
    pending_basis_pool = Decimal('0')
    
    for session in sessions:
        # Add session basis (respecting overrides)
        if session.is_reconciliation and session.session_basis_override:
            session_basis = session.session_basis_override
        else:
            session_basis = session.session_basis or Decimal('0')
        
        pending_basis_pool += session_basis
        
        # Subtract basis consumed (respecting overrides)
        if session.is_reconciliation and session.basis_consumed_override:
            basis_consumed = session.basis_consumed_override
        else:
            basis_consumed = session.basis_consumed or Decimal('0')
        
        pending_basis_pool -= basis_consumed
        pending_basis_pool = max(Decimal('0'), pending_basis_pool)
    
    return pending_basis_pool
```

#### Step 4: Update GameSessionService

**File:** `sezzions/services/game_session_service.py`

Add service methods for reconciliation operations:

```python
class GameSessionService:
    def __init__(self, db: Database):
        self.db = db
        self.repo = GameSessionRepository(db)
        self.fifo_service = FIFOService(db)
    
    def apply_reconciliation(
        self,
        session_id: int
    ) -> GameSession:
        """
        Apply reconciliation override to a session, consuming all available basis.
        """
        session = self.repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Calculate available basis
        available_basis = self.fifo_service.get_available_basis_for_session(
            session.site_id,
            session.user_id,
            session.session_date,
            session.start_time
        )
        
        # Set override values
        session.session_basis_override = available_basis
        session.basis_consumed_override = available_basis
        session.is_reconciliation = True
        
        # Add note
        reconcile_note = f"Reconciliation applied: ${available_basis:.2f} basis consumed."
        if session.notes:
            session.notes = f"{session.notes}\n\n{reconcile_note}"
        else:
            session.notes = reconcile_note
        
        # Save session
        updated = self.repo.update(session)
        
        # Rebuild from this session forward
        self.fifo_service.rebuild_sessions_for_pair(
            session.site_id,
            session.user_id,
            from_date=session.session_date
        )
        
        return updated
    
    def clear_reconciliation(
        self,
        session_id: int
    ) -> GameSession:
        """
        Remove reconciliation override from a session.
        """
        session = self.repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Clear override values
        session.session_basis_override = None
        session.basis_consumed_override = None
        session.is_reconciliation = False
        
        # Remove reconciliation note
        if session.notes:
            # Remove lines containing "Reconciliation applied"
            lines = session.notes.split('\n')
            filtered = [l for l in lines if 'Reconciliation applied' not in l]
            session.notes = '\n'.join(filtered).strip()
        
        # Save session
        updated = self.repo.update(session)
        
        # Rebuild from this session forward
        self.fifo_service.rebuild_sessions_for_pair(
            session.site_id,
            session.user_id,
            from_date=session.session_date
        )
        
        return updated
```

#### Step 5: Create UI Components (When UI is Implemented)

When Sezzions gets a UI layer, create these components:

##### A. ReconciliationDialog (equivalent to _show_reconciliation_dialog)

```python
class ReconciliationDialog(QDialog):
    """
    Dialog for confirming reconciliation override application.
    """
    def __init__(
        self,
        available_basis: Decimal,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.available_basis = available_basis
        self.setWindowTitle("Reconcile Session with Full Basis")
        
        layout = QVBoxLayout(self)
        
        # Header explaining reconciliation
        header = QLabel(
            "This will consume ALL available cost basis in this session.\n\n"
            "Use this when you have unrecorded gameplay between purchases. "
            f"Reconciliation will consume all ${available_basis:.2f} of basis "
            "to minimize taxable income."
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Basis summary
        summary_group = QGroupBox("Basis Summary")
        summary_layout = QGridLayout(summary_group)
        summary_layout.addWidget(QLabel("Available Basis:"), 0, 0)
        summary_layout.addWidget(QLabel(f"${available_basis:.2f}"), 0, 1)
        layout.addWidget(summary_group)
        
        # Warning
        warning = QLabel(
            "Applying reconciliation will:\n"
            f"• Consume all ${available_basis:.2f} of available basis in this session\n"
            "• Flag this session as 'Reconciliation' for audit purposes\n"
            "• Report the full net P/L in this session's tax year\n\n"
            "The total lifetime P/L will be correct, even if some gains occurred in prior years."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        apply_btn = QPushButton("Apply Reconciliation")
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(apply_btn)
        layout.addLayout(button_layout)
```

##### B. SessionEditDialog/SessionStartDialog Updates

Add to session dialogs:
- Redeemable check label (shows discrepancy)
- "Reconcile with Full Basis" button (shows when discrepancy detected)
- "Clear Reconciliation" button (shows when override is active)
- Override status label ("✓ Reconciliation applied")

Connect buttons to service methods:

```python
# In SessionEditDialog
def on_reconcile_clicked(self):
    # Get available basis from FIFO service
    available_basis = self.fifo_service.get_available_basis_for_session(...)
    
    # Show dialog
    dialog = ReconciliationDialog(available_basis, self)
    if dialog.exec() == QDialog.Accepted:
        # Apply reconciliation via service
        self.session_service.apply_reconciliation(self.session.id)
        
        # Update UI
        self.load_session()  # Reload to show override active

def on_clear_reconciliation_clicked(self):
    reply = QMessageBox.question(
        self,
        "Clear Reconciliation",
        "This will remove the reconciliation overrides and recalculate..."
    )
    if reply == QMessageBox.Yes:
        self.session_service.clear_reconciliation(self.session.id)
        self.accept()  # Close dialog
```

#### Step 6: Testing in Sezzions

Create unit tests for the new functionality:

**File:** `sezzions/tests/test_game_session_service_reconciliation.py`

```python
def test_apply_reconciliation():
    """Test that reconciliation override is applied correctly"""
    # Setup: Create session with discrepancy
    session = create_test_session(...)
    
    # Apply reconciliation
    updated = service.apply_reconciliation(session.id)
    
    # Assert: Override values set
    assert updated.is_reconciliation == True
    assert updated.session_basis_override == Decimal('60.00')
    assert updated.basis_consumed_override == Decimal('60.00')
    assert 'Reconciliation applied' in updated.notes
    
def test_reconciliation_persists_after_rebuild():
    """Test that override survives rebuild operations"""
    # Setup: Session with reconciliation
    session = create_reconciled_session(...)
    
    # Rebuild sessions
    fifo_service.rebuild_sessions_for_pair(session.site_id, session.user_id)
    
    # Reload from database
    reloaded = repo.get_by_id(session.id)
    
    # Assert: Override still exists
    assert reloaded.is_reconciliation == True
    assert reloaded.session_basis_override is not None
    
def test_clear_reconciliation():
    """Test that clearing reconciliation reverts to calculated values"""
    # Setup: Session with reconciliation
    session = create_reconciled_session(...)
    original_pl = session.net_taxable_pl
    
    # Clear reconciliation
    updated = service.clear_reconciliation(session.id)
    
    # Assert: Override removed
    assert updated.is_reconciliation == False
    assert updated.session_basis_override is None
    assert updated.basis_consumed_override is None
    
    # Assert: P/L recalculated (may be different)
    assert updated.net_taxable_pl != original_pl
```

---

## Key Differences: Legacy vs Sezzions

| Aspect | Legacy (qt_app.py) | Sezzions (OOP) |
|--------|-------------------|----------------|
| Data Access | Direct SQL in UI code | Repository pattern |
| Business Logic | Mixed in UI handlers | Service layer methods |
| Type Safety | Runtime checks | Dataclass + type hints |
| Testing | Manual/integration | Unit tests for services |
| Override Storage | Dict passed through layers | Model attributes |
| Rebuild Trigger | Direct function calls | Service orchestration |

**Migration Benefits:**
- Cleaner separation of concerns
- Easier to test (mock repositories)
- Type safety catches errors at dev time
- Reusable service methods
- Less code duplication

---

## Production Readiness Checklist

Before deploying reconciliation feature:

- [x] Database schema migration tested
- [x] Override detection logic tested
- [x] Override preservation during rebuild tested
- [x] UI dialogs implemented and tested
- [x] Button visibility logic tested
- [x] Save operations tested (active and closed sessions)
- [x] Clear reconciliation tested
- [x] Fast path bypass tested
- [ ] Debug output removed or commented
- [ ] User documentation written
- [ ] Help tooltips added to UI
- [ ] Visual indicator for reconciliation sessions (optional enhancement)
- [ ] Export/import reconciliation flags (if CSV import/export used)

---

## Future Enhancements

Potential improvements to consider:

1. **Visual Indicator:** Add icon/tag to session rows showing reconciliation status
2. **Reconciliation Report:** Summary view of all sessions with overrides
3. **Batch Reconciliation:** Apply to multiple sessions at once
4. **Partial Reconciliation:** Allow consuming less than full basis (not recommended)
5. **Reconciliation History:** Track when overrides were applied/cleared
6. **Audit Trail:** Log reconciliation actions for compliance
7. **Warning on Export:** Flag reconciled sessions in CSV exports
8. **Reconciliation Suggestions:** Auto-detect likely candidates for reconciliation

---

## Conclusion

The Session Reconciliation Override System successfully solves the problem of missing session data causing incorrect P/L calculations. By allowing users to manually force full basis consumption, the system ensures lifetime P/L is mathematically correct even when intermediate sessions are unrecorded.

**Key Success Factors:**
- Sticky overrides that survive rebuilds
- Clean separation between override columns and calculated columns
- Cascade effects through pending_basis_pool
- Reversibility (can clear and recalculate)
- Clear UI indicators of reconciliation status

**Port to Sezzions:**
The OOP architecture of Sezzions will make this feature cleaner and more maintainable. Follow the step-by-step guide above, paying special attention to:
- Model field additions
- Repository SELECT/INSERT/UPDATE modifications
- FIFOService rebuild logic with override checks
- Service methods for apply/clear operations
- UI component separation and service layer calls

**Final Note:** This implementation was thoroughly debugged and tested in the legacy application. The debug output patterns documented here will be invaluable when implementing in Sezzions, as similar issues may arise during the port.

---

*Implementation completed: January 25, 2026*
*Documentation last updated: January 25, 2026*
