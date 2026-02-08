# Session-Event Links Not Updated When Events Added

## Problem
When adding a new redemption or purchase, the session-event links are not automatically updated. This causes related events to not appear in session view dialogs until a manual rebuild is triggered.

## Steps to Reproduce
1. End a game session (e.g., session 140)
2. Add a redemption that occurs after the session (e.g., redemption 107 at 23:07)
3. View the session's "Related" tab
4. Observe: the redemption does NOT appear in "Redemptions Affecting This Session"
5. Close and reopen the app, view session again
6. Observe: the redemption NOW appears (because lazy rebuild was triggered)

## Root Cause
The `AppFacade.get_linked_events_for_session()` method has a flawed early-return logic:

```python
def get_linked_events_for_session(self, session_id: int):
    events = self.game_session_event_link_service.get_events_for_session(session_id)
    if events.get("purchases") or events.get("redemptions"):
        return events  # ← BUG: returns if ANY links exist, even if incomplete
    # ... rebuild only happens if NO links exist at all
```

If a session has ANY existing links (e.g., one purchase), the facade assumes all links are up-to-date and skips the rebuild. This means newly added events don't get linked.

## Expected Behavior
Session-event links should be automatically updated when:
- A new purchase is created
- A new redemption is created
- An existing purchase/redemption is edited (date/time changes)
- A session is ended

## Proposed Solution
1. Call `rebuild_links_for_pair_from()` in `_rebuild_or_mark_stale()` after FIFO rebuild
2. Or: Remove the early-return optimization in `get_linked_events_for_session()` and always check for staleness
3. Or: Track link freshness with timestamps and rebuild only if stale

## Impact
- User confusion: related events appear missing
- Data integrity: events exist but relationships not visible
- Workaround: manually run "Tools → Recalculate Everything"

## Test Case
See session 140 + redemption 107 in production database for concrete example.
