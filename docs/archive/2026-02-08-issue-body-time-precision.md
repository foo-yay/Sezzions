## Problem

Time fields lose second-level precision, causing incorrect event relationships and accounting errors.

**Example:** Session 147 shows start=13:16:00, end=13:16:00 but purchases happened at 13:16:05 and 13:16:30. Purchases appear AFTER session end, breaking linking and P/L calculation.

## Solution Part 1: Time Input Standardization

Apply to ALL time fields (purchases, redemptions, sessions, adjustments):

1. **Blank time** → Current time with seconds (HH:MM:SS)
2. **User enters HH:MM** → Append :00 (HH:MM:00)
3. **User enters HH:MM:SS** → Keep as-is

## Solution Part 2: Edge Case Handling - DECISIONS MADE

### Boundary Inclusiveness Rules

**Session Boundaries:**
- **Start:** Inclusive (event >= start_time is DURING)
- **End:** Exclusive (event < end_time is DURING)
- **Logic:** `event_time >= session_start AND event_time < session_end`

**Checkpoint Boundaries:**
- **Checkpoint:** Inclusive (purchase >= checkpoint_end is in next window)

**Examples:**
```
Purchase at 16:00:00, Session starts 16:00:00 → DURING (start inclusive)
Purchase at 17:00:00, Session ends 17:00:00 → AFTER (end exclusive)
Session A ends 17:00:00, Session B starts 17:00:00 → No overlap (clean boundary)
```

### Zero-Duration Sessions

**Allowed:** Yes, they handle correctly with inclusive start / exclusive end.

**Example:**
```
Session: 17:00:00 - 17:00:00 (zero duration)
Purchase: 17:00:00
Result: AFTER (because >= 17:00:00 but NOT < 17:00:00)
```

**Rationale:** Empty window (no events can satisfy >= start AND < end when start == end).

### Tiebreaker for Exact Timestamps

When timestamps match exactly, use **ID-based secondary sort**:
- Lower ID = earlier in sequence
- Provides deterministic ordering
- Matches database creation order

**Example:**
```python
# Purchase at 16:00:00, Session starts 16:00:00
if purchase_time >= session_start_time and purchase_time < session_end_time:
    relation = 'DURING'  # Start is inclusive
# If ambiguous, use ID as tiebreaker for ordering
```

## Affected Areas

**UI Layer - Time Input:**
- All CRUD time input fields (purchases_tab, redemptions_tab, game_sessions_tab, adjustments_tab)
- Time field validation and defaulting

**UI Layer - Time Display:**
- **All time displays must show HH:MM:SS format** (not HH:MM)
- Table columns showing times (purchases, redemptions, sessions, adjustments)
- Detail dialogs and forms
- Reports and summaries
- Session-related event lists

**Service Layer:**
- Time validation/defaulting in all services
- Link builder: BEFORE/DURING/AFTER classification
- Windowing: basis calculation, checkpoint logic

**Repository Layer:**
- Validate time format before INSERT/UPDATE

## Implementation Phases

### Phase 1: Time Input Standardization (Critical)

**Scope:**
- Update all time input fields to capture/default HH:MM:SS
- Blank time → current time with seconds
- HH:MM input → append :00
- HH:MM:SS input → preserve

**Files:**
- `ui/tabs/purchases_tab.py`
- `ui/tabs/redemptions_tab.py`
- `ui/tabs/game_sessions_tab.py`
- `ui/tabs/adjustments_tab.py`
- Services: validation methods

**Tests:**
- Unit tests for time parsing logic
- Integration tests for CRUD operations with various time inputs

### Phase 2: Display Format + Edge Case Handling (Critical)

**Scope:**
- **Update ALL time displays to show HH:MM:SS** (tables, dialogs, forms, reports)
- Update link builder boundary logic (inclusive start, exclusive end)
- Update windowing functions (checkpoint handling)
- Document boundary rules in code comments

**Files:**
- All UI table models/columns showing times
- `services/game_session_event_link_service.py` - boundary logic
- `services/game_session_service.py` - windowing functions (in_window)
- Dialogs showing session/purchase/redemption details

**Tests:**
- Exact timestamp match scenarios
- Zero-duration sessions
- Back-to-back sessions
- Purchase at session start/end boundaries

## Acceptance Criteria

**Phase 1 - Time Input:**
- [ ] All time fields store HH:MM:SS format in database
- [ ] Blank time input defaults to actual current time with seconds
- [ ] HH:MM input auto-expands to HH:MM:00
- [ ] HH:MM:SS input preserved as-is
- [ ] Applied to all entities (purchases, redemptions, sessions, adjustments)

**Phase 2 - Display + Edge Cases:**
- [ ] **All time displays show HH:MM:SS format** (tables, dialogs, forms, reports)
- [ ] Boundary logic: event >= start_time AND event < end_time = DURING
- [ ] Checkpoint logic: purchase > checkpoint_end (exclusive)
- [ ] ID-based tiebreaker for exact timestamp matches
- [ ] Zero-duration sessions handle correctly (empty window)
- [ ] Link builder updated with new boundary rules
- [ ] Windowing functions updated with new boundary rules
- [ ] Code comments document boundary inclusiveness rules

**Testing:**
- [ ] Unit tests for time parsing and defaulting
- [ ] Integration tests for exact timestamp scenarios
- [ ] Manual testing across all entity types

## Test Cases

**Phase 1 - Input:**
1. Blank time field → captures current HH:MM:SS
2. Enter "16:30" → stores as "16:30:00"
3. Enter "16:30:45" → stores as "16:30:45"
4. Test across all entity types

**Phase 2 - Edge Cases:**
1. Purchase at 16:00:00, Session starts 16:00:00 → DURING (start inclusive)
2. Purchase at 17:00:00, Session ends 17:00:00 → AFTER (end exclusive)
3. Multiple purchases at 16:00:00 → Ordered by ID
4. Zero-duration session (17:00:00 - 17:00:00) with purchase at 17:00:00 → AFTER
5. Back-to-back sessions (A ends 17:00:00, B starts 17:00:00) → Clean boundary, no overlap
6. Redemption at session start/end boundaries → Same rules as purchases

**Phase 2 - Display:**
1. Verify all table columns show HH:MM:SS (not HH:MM)
2. Verify detail dialogs show HH:MM:SS
3. Verify session-related event lists show HH:MM:SS
4. Verify reports show HH:MM:SS

## Discussion Needed

~~1. **Boundary inclusiveness:** Should session start/end be inclusive or exclusive?~~  
**DECIDED:** Start inclusive (>=), End exclusive (<)

~~2. **Tiebreaker:** Use ID-based sorting when timestamps match?~~  
**DECIDED:** Yes, use ID-based secondary sort

~~3. **Migration:** Leave historical data as-is or attempt retroactive fixes?~~  
**DECIDED:** Leave historical data as-is, fixes apply going forward only

~~4. **Zero-duration sessions:** Allow or warn?~~  
**DECIDED:** Allow - they handle correctly as empty windows with the inclusive/exclusive boundary rules

## Priority

**High** - Directly impacts accounting accuracy. Discovered during Issue #88 testing (session 147 shows +$170 P/L instead of +$20 due to missing purchase links caused by time precision loss).

Related: Issue #88 (PR #89)
