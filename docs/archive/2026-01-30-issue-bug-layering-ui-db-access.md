# Bug: UI directly accesses database in tabs (layering violation)

Sezzions rule: UI must call services; UI must not talk to repositories/DB connections directly.

## Problem

Some UI tab code directly executes SQL / uses repository DB cursors. This violates the layering rule and risks:
- Threading/lifetime issues in UI
- Tests flaking during widget cleanup
- Hidden coupling between UI and schema

## Evidence (current code)

1) Realized date notes are persisted directly from UI:
- `ui/tabs/realized_tab.py`
  - Reads: `self.db.fetch_one("SELECT notes FROM realized_daily_notes ...")`
  - Writes: `self.db.execute("INSERT OR REPLACE INTO realized_daily_notes ...")`
  - Deletes: `self.db.execute("DELETE FROM realized_daily_notes ...")`

2) UI queries repository DB cursor directly for deletion-impact messaging:
- `ui/tabs/redemptions_tab.py` → `_check_redemption_deletion_impact()`
  - Uses `self.facade.redemption_repo.db` and `db._connection.cursor().execute(...)`
- `ui/tabs/game_sessions_tab.py` → `_check_deletion_impact()`
  - Uses `self.facade.game_session_repo.db` and `db._connection.cursor().execute(...)`

## Proposed fix

- Move these operations behind service methods (reachable via AppFacade), e.g.:
  - `RealizedNotesService.get_date_note(date)` / `set_date_note(date, text)` / `delete_date_note(date)`
  - `RedemptionsService.get_deletion_impact(redemption_id)` (or by providing the object)
  - `GameSessionService.get_deletion_impact(session_id)`
- UI becomes purely orchestration: call service, show message.

## Acceptance criteria

- No SQL execution or repository DB cursor access from UI tabs for the above flows.
- All functionality remains the same (same messages/notes behavior).
- Tests no longer emit UI/Qt cleanup database warnings attributable to these flows.

## Test plan

- Unit tests for the new service methods.
- Integration tests for:
  - Realized date notes read/write/delete through facade/service
  - Deletion impact message generation through service (spot-check output contains key facts)

## Notes

- [X] This change likely requires updating `docs/PROJECT_SPEC.md` if new service APIs are added.
- [X] This change likely requires adding/updating tests.
- [ ] This change likely touches the database schema or migrations.
