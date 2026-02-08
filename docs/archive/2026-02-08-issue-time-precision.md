# Issue: Improve Time Field Precision and Edge Case Handling

## Problem

Currently, time fields across the app default to `HH:MM:00` when left blank or when only `HH:MM` is entered. This causes loss of precision and creates ambiguity when events happen within the same minute.

**Real-world example from testing:**
- Session 147 shows: start `13:16:00`, end `13:16:00`
- Purchase 255: `13:16:05` (5 seconds after session start)
- Purchase 256: `13:16:30` (30 seconds after session start)
- Result: Purchases appear to be AFTER session end because session end time lost its seconds precision

This breaks:
- Purchase-to-session linking (BEFORE/DURING/AFTER classification)
- Basis consumption calculations
- Session P/L accuracy
- Event timeline reconstruction

## Proposed Solution

### Part 1: Time Input Handling (All CRUD Operations)

Standardize time field handling across all entities (purchases, redemptions, sessions, adjustments):

**Rules:**
1. **Blank time field** → Default to **current time with seconds** (`HH:MM:SS`)
2. **User enters `HH:MM`** → Append `:00` to get `HH:MM:00`
3. **User enters `HH:MM:SS`** → Keep as-is
4. **Validation:** Ensure all stored times are in `HH:MM:SS` format

**Affected Entities:**
- `purchases` (purchase_time)
- `redemptions` (redemption_time)
- `game_sessions` (session_time, end_time)
- `adjustments` (adjustment_time)
- Any other time fields

**Implementation Areas:**
- UI time input widgets/validators
- Repository save/update methods
- Service layer validation
- CSV import/export

### Part 2: Edge Case Handling - Exact Time Matches

When events have identical timestamps, we need deterministic ordering rules.

#### Purchase Edge Cases

**Scenario 1: Purchase at exact session start time**
```
Purchase: 2026-02-08 13:16:05
Session:  2026-02-08 13:16:05 - 13:16:45
```
- **Question:** Is this BEFORE or DURING?
- **Proposal:** Use event sequence (purchase ID < session ID) as tiebreaker?
- **Or:** Require purchase to be strictly < start_time to be BEFORE?

**Scenario 2: Purchase at exact session end time**
```
Purchase: 2026-02-08 13:16:45
Session:  2026-02-08 13:16:05 - 13:16:45
```
- **Question:** Is this DURING or AFTER?
- **Proposal:** Inclusive end (purchase <= end_time is DURING)?

**Scenario 3: Multiple purchases with identical timestamps**
```
Purchase A: 2026-02-08 13:16:30
Purchase B: 2026-02-08 13:16:30
Session:    2026-02-08 13:16:05 - 13:16:45
```
- **Question:** Does ordering matter for basis calculation?
- **Proposal:** Use purchase ID as secondary sort key (deterministic)

#### Session Edge Cases

**Scenario 1: Back-to-back sessions (end = next start)**
```
Session A: 13:16:05 - 13:16:45
Session B: 13:16:45 - 13:17:30
```
- **Question:** Which session "owns" the checkpoint at 13:16:45?
- **Current:** checkpoint_end_dt is exclusive (purchase must be > checkpoint)
- **Proposal:** Keep exclusive boundary (session A ends at :45, session B starts at :45, purchases at exactly :45 belong to session B's window)

**Scenario 2: Zero-duration sessions (start = end)**
```
Session: 13:16:00 - 13:16:00
```
- **Question:** Is this valid? Should it be allowed?
- **Proposal:** Warn user or auto-increment end_time by 1 second?

#### Redemption Edge Cases

**Scenario 1: Redemption between sessions**
```
Session A ends:   13:16:45
Redemption:       13:16:50
Session B starts: 13:17:00
```
- **Question:** How does this affect expected_start_redeemable for Session B?
- **Current behavior:** Deducted in windowing calculation
- **Proposal:** Keep current behavior, ensure timestamp precision

**Scenario 2: Redemption at exact session boundary**
```
Session:    13:16:05 - 13:16:45
Redemption: 13:16:45
```
- **Question:** Is this DURING or AFTER the session?
- **Proposal:** Match purchase logic (inclusive end = DURING)

### Part 3: Testing Requirements

**Scenario-based tests needed:**
1. Purchase exactly at session start time
2. Purchase exactly at session end time
3. Multiple purchases with identical timestamps during session
4. Zero-duration session (start = end)
5. Back-to-back sessions with shared boundary timestamp
6. Redemption at session boundary
7. Events with sub-second timing (if supported)

## Acceptance Criteria

- [ ] All time fields store `HH:MM:SS` format consistently
- [ ] Blank time input defaults to actual current time with seconds
- [ ] `HH:MM` input expands to `HH:MM:00`
- [ ] `HH:MM:SS` input preserved as-is
- [ ] Edge case rules documented and tested
- [ ] Existing sessions/purchases/redemptions migrated or validated
- [ ] Link builder handles exact timestamp matches correctly
- [ ] Basis consumption calculation handles exact matches correctly
- [ ] UI provides feedback when times are identical (warning?)

## Test Plan

1. **Unit tests:**
   - Time parsing and defaulting logic
   - Edge case timestamp comparison functions
   
2. **Integration tests:**
   - Create session, save purchase at exact start time, verify link relation
   - Create session, save purchase at exact end time, verify link relation
   - Create two back-to-back sessions, verify checkpoint handling
   
3. **Manual testing:**
   - Leave time blank, verify it captures seconds
   - Enter HH:MM, verify :00 appended
   - Enter HH:MM:SS, verify preserved
   - Test across all entity types (purchase, redemption, session, adjustment)

## Discussion Points

### 1. Boundary Inclusiveness

Current implementation uses exclusive start, inclusive end for windowing:
```python
def in_window(dt, start_exclusive, end_inclusive):
    if start_exclusive is not None and dt <= start_exclusive:
        return False
    return dt <= end_inclusive
```

**Questions:**
- Should session start_time be inclusive or exclusive?
- Should session end_time be inclusive or exclusive?
- Should this be consistent across all time windowing operations?

### 2. Tiebreaker Strategy

When timestamps are identical, what determines order?

**Options:**
1. **ID-based:** Use entity ID as secondary sort (lower ID = earlier)
   - Pro: Deterministic, matches database creation order
   - Con: IDs might not reflect user intent
   
2. **User-prompted:** Force user to adjust time by at least 1 second
   - Pro: Explicit intent, no ambiguity
   - Con: UX friction, might be overly strict
   
3. **Millisecond precision:** Store subsecond timestamps
   - Pro: Most accurate
   - Con: Requires schema changes, SQLite datetime handling complexity

### 3. Migration Strategy

Existing data has time precision issues. Options:

**Option A: Leave as-is**
- Pro: No data changes, no risk
- Con: Historical sessions may show incorrect P/L

**Option B: Rebuild all links**
- Pro: Fixes link relationships
- Con: Doesn't fix underlying timestamp precision loss

**Option C: Add seconds based on heuristics**
- Pro: Retroactive precision improvement
- Con: Invents data, potentially wrong

**Recommendation:** Option A (leave historical data), apply fixes going forward only.

## Implementation Notes

### Files Likely Affected

**UI Layer:**
- `ui/tabs/purchases_tab.py` - purchase time input
- `ui/tabs/redemptions_tab.py` - redemption time input
- `ui/tabs/game_sessions_tab.py` - session start/end time input
- `ui/tabs/adjustments_tab.py` - adjustment time input

**Service Layer:**
- `services/purchase_service.py` - time validation/defaulting
- `services/redemption_service.py` - time validation/defaulting
- `services/game_session_service.py` - time validation/defaulting, windowing logic
- `services/game_session_event_link_service.py` - boundary logic for BEFORE/DURING/AFTER

**Repository Layer:**
- Validate time format before INSERT/UPDATE

**Utilities:**
- Create shared `time_utils.py` for consistent time parsing/defaulting?

## Related Issues

- Issue #88: Purchase-to-session linking (current PR)
  - This time precision issue was discovered during #88 testing
  - Session 147 accounting bug is caused by time precision loss

## Priority

**High** - Directly impacts accounting accuracy and event relationship correctness.

Should be implemented before merging PR #89 or immediately after.

---

**Created:** 2026-02-08  
**Discovered During:** Issue #88 testing (PR #89)  
**Status:** Draft - needs owner review and decision on edge case handling
