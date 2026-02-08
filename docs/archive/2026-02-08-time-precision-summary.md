# Time Precision & Edge Case Handling - Implementation Summary

**GitHub Issue:** #90  
**Created:** 2026-02-08  
**Status:** Ready for implementation  
**Priority:** High

## Problem Discovered

During Issue #88 testing, Session 147 showed incorrect P/L ($170 instead of $20) due to:
- Time fields losing second-level precision
- Session showing start=13:16:00, end=13:16:00
- Purchases at 13:16:05 and 13:16:30 appearing AFTER session end
- No links created, no basis consumed, incorrect P/L

## Solution Overview

### Phase 1: Time Input Standardization
- Blank time → Current time with seconds (HH:MM:SS)
- User enters HH:MM → Append :00 (HH:MM:00)
- User enters HH:MM:SS → Keep as-is
- Apply to all entities: purchases, redemptions, sessions, adjustments

### Phase 2: Display Format + Edge Case Handling
- **Show HH:MM:SS everywhere** (tables, dialogs, forms, reports)
- Update boundary logic with clear rules
- Handle exact timestamp matches with ID-based tiebreaker

## Boundary Rules (FINALIZED)

### Session Windows

**Inclusive Start, Exclusive End:**
```python
def is_during_session(event_time, session_start, session_end):
    return event_time >= session_start and event_time < session_end
```

**Examples:**
| Event Time | Session Window | Classification | Reason |
|------------|----------------|----------------|---------|
| 16:00:00 | 16:00:00 - 17:00:00 | DURING | >= start (inclusive) |
| 17:00:00 | 16:00:00 - 17:00:00 | AFTER | NOT < end (exclusive) |
| 15:59:59 | 16:00:00 - 17:00:00 | BEFORE | NOT >= start |
| 16:30:00 | 16:00:00 - 17:00:00 | DURING | Within window |

### Checkpoint Windows

**Exclusive Checkpoint:**
```python
def in_next_window(purchase_time, checkpoint_end):
    return purchase_time > checkpoint_end  # Strictly greater
```

**Example:**
| Purchase | Checkpoint End | Session A End | Window |
|----------|----------------|---------------|---------|
| 16:59:59 | 16:00:00 | 17:00:00 | Current (> checkpoint) |
| 16:00:00 | 16:00:00 | 17:00:00 | Current (> checkpoint) |
| 15:59:59 | 16:00:00 | 17:00:00 | Previous (<= checkpoint) |

### Back-to-Back Sessions

**Clean Boundaries:**
```
Session A: 16:00:00 - 17:00:00 (end exclusive)
Session B: 17:00:00 - 18:00:00 (start inclusive)
Purchase: 17:00:00 → Belongs to Session B
```

No double-counting, no gaps.

### Zero-Duration Sessions

**Allowed and handled correctly:**
```
Session: 17:00:00 - 17:00:00 (start = end)
Purchase: 17:00:00
Check: 17:00:00 >= 17:00:00 AND 17:00:00 < 17:00:00 → FALSE
Result: AFTER (empty window, no events satisfy condition)
```

### Exact Timestamp Tiebreaker

When events have identical timestamps, use **ID-based secondary sort**:
```python
# For sorting purchases at 16:00:00
purchases.sort(key=lambda p: (p.time, p.id))

# Result: Lower ID processed first (deterministic)
```

## Implementation Checklist

### Phase 1: Input (Critical)
- [ ] Update purchase time input to capture/default HH:MM:SS
- [ ] Update redemption time input to capture/default HH:MM:SS
- [ ] Update session start/end time input to capture/default HH:MM:SS
- [ ] Update adjustment time input to capture/default HH:MM:SS
- [ ] Service-level validation for HH:MM:SS format
- [ ] Unit tests for time parsing logic

### Phase 2: Display + Logic (Critical)
- [ ] Update all table time columns to show HH:MM:SS
- [ ] Update all dialog time displays to show HH:MM:SS
- [ ] Update all form time displays to show HH:MM:SS
- [ ] Update report time displays to show HH:MM:SS
- [ ] Update link builder: `event >= start AND event < end`
- [ ] Update windowing: `purchase > checkpoint` (exclusive)
- [ ] Add ID-based tiebreaker for exact timestamps
- [ ] Document boundary rules in code comments
- [ ] Integration tests for edge cases

## Code Changes Required

### Link Builder Logic
```python
# services/game_session_event_link_service.py
# Current: uses <= for start (exclusive start)
# Change to: >= for start (inclusive start), < for end (exclusive end)

def classify_purchase_relation(purchase_dt, session_start, session_end):
    if purchase_dt < session_start:
        return 'BEFORE'
    elif purchase_dt >= session_start and purchase_dt < session_end:
        return 'DURING'
    else:
        return 'AFTER'
```

### Windowing Logic
```python
# services/game_session_service.py
# Current: uses exclusive start, inclusive end
def in_window(dt, start_exclusive, end_inclusive):
    if dt is None:
        return False
    if start_exclusive is not None and dt <= start_exclusive:
        return False
    return dt <= end_inclusive

# Change to: inclusive start, exclusive end for consistency
def in_session_window(dt, start_inclusive, end_exclusive):
    if dt is None:
        return False
    if start_inclusive is not None and dt < start_inclusive:
        return False
    if end_exclusive is not None and dt >= end_exclusive:
        return False
    return True
```

Note: Checkpoint logic should remain exclusive (purchase > checkpoint).

## Testing Strategy

### Unit Tests
- Time parsing: blank → HH:MM:SS with current seconds
- Time parsing: "16:30" → "16:30:00"
- Time parsing: "16:30:45" → "16:30:45"
- Boundary checks with exact timestamps

### Integration Tests
1. **Inclusive Start:** Purchase at 16:00:00, session starts 16:00:00 → link as DURING
2. **Exclusive End:** Purchase at 17:00:00, session ends 17:00:00 → link as AFTER
3. **Zero Duration:** Session 17:00:00-17:00:00, purchase 17:00:00 → link as AFTER
4. **Back-to-Back:** Session A ends 17:00:00, Session B starts 17:00:00, purchase 17:00:00 → link to B
5. **Multiple Same Time:** Purchases A, B, C at 16:00:00 → ordered by ID
6. **Basis Calculation:** Session with DURING purchases at exact boundaries → correct basis consumed

### Manual Testing
- Create purchase, leave time blank, verify seconds captured
- Create session with exact boundary times, verify links
- Check all table columns show HH:MM:SS
- Check all dialogs show HH:MM:SS

## Migration Notes

**Historical Data:** Leave as-is. Fixes apply to new data going forward.

**Session 147 Workaround:** Manually edit end_time to 13:16:45 or later in UI, then rebuild links and recalculate.

## Related Issues

- Issue #88 (PR #89): Purchase-to-session linking - time precision issue discovered during testing
- Current PR includes basis consumption fix that depends on proper linking
- Issue #90 must be completed before full accounting accuracy can be guaranteed

## Priority Rationale

**High Priority** because:
1. Directly impacts accounting accuracy (P/L calculations)
2. Breaks purchase-to-session linking
3. Creates incorrect basis consumption
4. Discovered in production testing (Session 147 real data)
5. Will affect all future sessions until fixed

**Recommendation:** Implement Phase 1-2 before merging PR #89, or immediately after as a follow-up PR.
