## Problem / motivation

The desktop game session service performs two accounting side effects that the web service does not yet implement:

1. **Dormant purchase reactivation on session creation**: When a new session is created, the desktop calls `UPDATE purchases SET status='active' WHERE status='dormant' AND user_id=? AND site_id=?` to reactivate purchases that were marked dormant (e.g., after a position close).

2. **PENDING_CANCEL redemption processing on session close**: When a session is closed, the desktop calls `redemption_service.process_pending_cancels()` to finalize any redemptions in PENDING_CANCEL state.

These are backend-only changes to `workspace_game_session_service.py`.

## Proposed solution

Add both side effects to the hosted game session service:
1. In `create_game_session`: after creating the session, query for dormant purchases matching (workspace_id, user_id, site_id) and update their status to active.
2. In `update_game_session`: when status changes to Closed, call the redemption service to process pending cancels for that user+site.

Desktop reference: `services/game_session_service.py` — `create_session()` and `update_session()`

## Scope

In-scope:
- Dormant purchase reactivation in `create_game_session`
- PENDING_CANCEL processing in `update_game_session` (on close)
- Tests for both side effects

Out-of-scope:
- UI changes (these are invisible backend side effects)
- Changes to purchase or redemption services themselves

## Acceptance criteria

- Creating a game session reactivates dormant purchases for that user+site
- Closing a game session processes PENDING_CANCEL redemptions
- Tests verify both side effects fire at the correct time
- Tests verify side effects don't fire on non-triggering operations (e.g., edit without status change)

## Test plan

Automated tests:
- Create session with dormant purchases present -> purchases become active
- Create session with no dormant purchases -> no error
- Close session with PENDING_CANCEL redemptions -> redemptions finalized
- Edit session without closing -> no side effects

Manual verification:
- None required (backend-only)
