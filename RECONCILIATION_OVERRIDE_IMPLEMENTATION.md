# Session Reconciliation Override Implementation

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

## Solution: Reconciliation Override System

Allow users to manually override basis calculations when they detect missing sessions, ensuring **total lifetime P/L is correct** even when intermediate sessions are unknown.

### User Workflow:

1. **Detection:** User starts a session and sees balance check warning
2. **Decision:** System offers "Reconcile with Full Basis" option
3. **Reconciliation:** User applies override to consume all available basis
4. **Result:** Correct total P/L ($40.43) recorded in this session
5. **Flexibility:** User can clear override later if needed

---

## Implementation Plan

### Phase 1: Database Schema

Add three columns to `game_sessions` table:
- `session_basis_override` (REAL): Manual override for session basis
- `basis_consumed_override` (REAL): Manual override for basis consumed  
- `is_reconciliation` (INTEGER): Flag indicating this session has overrides

### Phase 2: UI Changes

#### A. GameSessionStartDialog
- Enhance balance check warning to offer reconciliation
- Show dialog explaining full basis reconciliation
- Set override flags when user confirms

#### B. GameSessionEditDialog  
- Display reconciliation status if overrides are active
- Provide "Clear Overrides" button to revert to automatic calculation
- Trigger rebuild when overrides are cleared

#### C. GameSessionsTab
- Add visual indicator (icon/tag) for reconciliation sessions
- Include override info in session view dialog

### Phase 3: Business Logic Updates

#### A. Session Creation (qt_app.py)
- Store override values in database when reconciliation is applied
- Add notes documenting the reconciliation

#### B. Rebuild Algorithm (business_logic.py)
- Check for override flags during session processing
- Use override values instead of calculations when present
- Apply override effects to pending_basis_pool for downstream sessions
- **Preserve** override fields during rebuild (don't overwrite)

#### C. Cascade Behavior
- Overrides participate in chronological chain
- Downstream sessions see effects via pending_basis_pool
- Full rebuild respects overrides (sticky until explicitly cleared)

---

## Key Design Principles

1. **Overrides are sticky** - Survive rebuilds/recalculations
2. **Overrides cascade** - Affect downstream sessions via basis pool
3. **Overrides are auditable** - Clearly flagged and documented
4. **Overrides are reversible** - User can clear and recalculate
5. **Overrides are conservative** - Consume all basis = higher P/L (not hiding income)

---

## Test Scenarios

### Scenario 1: Apply Override to Current Session
```
Given: Session 1/25/26 with $60 available basis, ending at 100.43 redeemable
When: User applies reconciliation override
Then: 
  - session_basis_override = $60.00
  - basis_consumed_override = $60.00
  - net_taxable_pl = $40.43 ✓
  - is_reconciliation = 1
```

### Scenario 2: Backdate Session with Override
```
Given: Existing session on 1/25/26
When: User adds 1/21/26 session with reconciliation override
Then:
  - 1/21 session: Uses override values
  - 1/25 session: Recalculates based on 1/21's ending state
  - Pending basis pool flows correctly through chain
```

### Scenario 3: Edit Session with Override
```
Given: Session 1/25/26 with reconciliation override
When: User edits ending balance
Then:
  - Override flags/values preserved
  - P/L recalculates with new ending balance
  - Downstream sessions rebuild
```

### Scenario 4: Delete Session with Override
```
Given: Session 1/25/26 with reconciliation override
When: User deletes the session
Then:
  - Session removed from chain
  - Downstream sessions rebuild
  - Warning may reappear on next session (basis not consumed)
```

### Scenario 5: Clear Override
```
Given: Session 1/25/26 with reconciliation override
When: User clicks "Clear Overrides" 
Then:
  - Override fields set to NULL
  - is_reconciliation = 0
  - Session recalculates with automatic logic
  - P/L returns to $56.58 (incorrect, but calculated)
  - Balance warning reappears
```

---

## Files to Modify

### 1. database.py
- Add migration for new columns
- Ensure columns exist in schema

### 2. business_logic.py
- Update `_rebuild_session_tax_fields_for_pair()` to check/use overrides
- Update `_rebuild_session_tax_fields_for_pair_from()` to check/use overrides
- Preserve override fields in UPDATE statements

### 3. qt_app.py

#### GameSessionStartDialog
- Add reconciliation detection logic
- Create reconciliation dialog/flow
- Store override values on save

#### GameSessionEditDialog  
- Add reconciliation info display
- Add clear overrides button/handler
- Trigger rebuild after clear

#### GameSessionsTab
- Add visual indicator for reconciliation sessions
- Update view dialog to show override info

---

## Expected Outcome

After implementation, the Clubs Poker 1/25/26 session will:
1. Show balance check warning at start
2. Offer reconciliation option
3. When applied, report **$40.43 net taxable P/L** ✓
4. Be clearly flagged as reconciliation session
5. Allow user to clear override if needed

This ensures **mathematically correct lifetime P/L** even when intermediate sessions are missing.

---

## Migration Path for Existing Data

No automatic migration needed. Existing sessions without overrides continue to function as before. Users can manually apply reconciliation to any session that needs correction.

---

## Documentation Notes for Users

Add to user guide:
- **When to use reconciliation:** Missing/unrecorded sessions causing balance discrepancies
- **What it does:** Applies all available basis to ensure correct total P/L
- **Trade-off:** May shift P/L to different tax year (but total is correct)
- **Reversibility:** Can be cleared at any time to return to automatic calculation
