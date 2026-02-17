# Bug: Multi-day session indicator always shows (+1d) regardless of actual day span

## Problem

When a game session spans multiple days (e.g., 2 or 3 days), the Game Sessions tab always displays `(+1d)` regardless of how many days the session actually spans. For a session that runs from Feb 1 to Feb 3, it should show `(+2d)` but instead shows `(+1d)`.

## Current Behavior

The code in `ui/tabs/game_sessions_tab.py` (line 395) only checks if the end date is different from the start date:

```python
if session.end_date and session.end_date != session.session_date:
    date_time += " (+1d)"
```

This results in:
- 1-day span (Feb 1 → Feb 2): Shows `(+1d)` ✅ CORRECT
- 2-day span (Feb 1 → Feb 3): Shows `(+1d)` ❌ WRONG (should be +2d)
- 3-day span (Feb 1 → Feb 4): Shows `(+1d)` ❌ WRONG (should be +3d)

## Expected Behavior

The indicator should calculate the actual number of days between session_date and end_date and display the correct value:
- 1-day span: `(+1d)`
- 2-day span: `(+2d)`
- 3-day span: `(+3d)`
- etc.

## Proposed Solution

Calculate the day difference using date arithmetic:

```python
if session.end_date and session.end_date != session.session_date:
    start = datetime.strptime(session.session_date, "%Y-%m-%d")
    end = datetime.strptime(session.end_date, "%Y-%m-%d")
    day_diff = (end - start).days
    if day_diff > 0:
        date_time += f" (+{day_diff}d)"
```

## Scope

**Primary location:**
- `ui/tabs/game_sessions_tab.py` (line ~395) - Game Sessions tab display

**Verify not needed:**
- `ui/tabs/daily_sessions_tab.py` - Uses full date display (e.g., "2026-02-01 10:00 → 2026-02-03 14:00"), no day indicator
- `ui/tabs/realized_tab.py` - Uses separate start/end date columns, no day indicator

## Acceptance Criteria

- [ ] Multi-day sessions correctly display the number of days spanned (e.g., `+2d`, `+3d`)
- [ ] Single-day overnight sessions still show `(+1d)`
- [ ] Sessions that don't span days show no indicator
- [ ] Existing tests pass
- [ ] Manual verification with 2-day and 3-day test sessions

## Test Plan

1. Create test session spanning 1 day (overnight) - verify shows `(+1d)`
2. Create test session spanning 2 days - verify shows `(+2d)`
3. Create test session spanning 3 days - verify shows `(+3d)`
4. Verify same-day session shows no indicator
5. Run full pytest suite

## Related

- Daily Sessions tab handles multi-day sessions differently (full date ranges)
- Realized tab shows separate start/end columns
