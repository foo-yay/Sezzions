## Problem / motivation

The desktop app has a Daily Sessions system that aggregates game sessions by date for tax reporting. After every session close/edit/delete, the desktop calls `_sync_daily_sessions_for_pair()` and `_sync_tax_for_affected_dates()` to keep daily aggregates and tax withholding calculations up to date. None of this is ported to web yet.

This is Phase 5+ in the web port plan and is the foundation for tax reporting.

## Proposed solution

Port the daily session sync + tax withholding system to web:
1. **Daily Sessions service**: Aggregate game sessions by (user, site, date) into daily summaries (total P/L, basis, etc.)
2. **Tax withholding service**: Compute running YTD P/L and determine when withholding thresholds are hit
3. **Integration hooks**: Call sync after session create/update/delete in `workspace_game_session_service.py`
4. **API endpoints**: GET daily sessions list, GET tax summary
5. **Frontend**: Daily Sessions tab / Tax withholding display columns in game sessions table

Desktop reference: `services/game_session_service.py` (`_sync_daily_sessions_for_pair`, `_sync_tax_for_affected_dates`)

## Scope

In-scope:
- Daily session aggregation service + repo
- Tax withholding calculation service
- Integration with game session mutations
- API endpoints for daily sessions + tax data
- Frontend display (daily sessions tab or section, tax columns in game sessions)

Out-of-scope:
- Tax filing / export (separate concern)
- W-2G generation

## Acceptance criteria

- Daily session aggregates are maintained automatically when game sessions change
- Tax withholding thresholds are computed correctly per YTD P/L
- Tax withholding column appears in game sessions table where applicable
- Daily sessions are viewable in the web UI

## Test plan

Automated tests:
- Daily session sync after session create/close/delete
- Tax withholding threshold computation
- Edge cases: multiple sessions same day, session deletion mid-year

Manual verification:
- Close several sessions across dates, verify daily aggregates update
- Verify tax withholding appears when threshold is exceeded
