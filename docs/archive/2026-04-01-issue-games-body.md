## Problem / Motivation

The Games entity has no web implementation yet. The desktop app has a fully functional Games tab (Setup > Games) with CRUD operations, FK dropdown for Game Type, and optional RTP fields. Games are referenced by Game Sessions (the core transaction entity) and Purchases.

## Proposal

Implement full-stack Games web support using the established EntityTable pattern:

### Backend
- Add `HostedGame` domain model to `services/hosted/models.py`
- Create `hosted_game_repository.py` (workspace-scoped CRUD with game_type JOIN for display name)
- Create `workspace_game_service.py`
- Add 5 API endpoints at `/v1/workspace/games` (list, create, update, delete, batch-delete)

### Frontend
- Create `GamesTab/` with EntityTable config, modal, constants, utils
- Fields: name (required), game_type_id (required, TypeaheadSelect), rtp (optional, 0-100), actual_rtp (read-only display), is_active, notes
- Use `extraLoaders` for game types FK data
- Enable the tab in AppShell

### Desktop parity
- Desktop UI requires: name, game_type_id (both required in UI)
- Desktop UI optional: rtp (float 0-100), notes, is_active
- actual_rtp is computed/read-only (displayed but not editable)
- Game Type dropdown uses editable autocomplete with inline completion
- Desktop has a "Recalculate RTP" button on edit — defer to follow-up

## Scope

- [x] Hosted domain model
- [x] Hosted repository (with game_type JOIN)
- [x] Hosted service
- [x] API endpoints (5)
- [x] Frontend tab (EntityTable pattern)
- [x] Frontend modal (view/create/edit with TypeaheadSelect for game type)
- [x] Enable tab in AppShell
- [x] Changelog entry

## Out of Scope (Follow-ups)
- Recalculate RTP button (requires game session data)
- Game view dialog with session history / date range filter

## Acceptance Criteria

- Games tab loads and displays existing games with game_type_name resolved
- Can create a new game with name (required), game_type (required), optional rtp/notes
- Can edit an existing game
- Can delete single and batch-delete games
- Name and Game Type are required (validation errors shown)
- RTP validates 0-100 range if provided
- actual_rtp is displayed read-only
- All existing tests still pass
- Frontend builds cleanly

## Test Plan

- Backend: model validation (name required, game_type_id required, rtp 0-100 range)
- Frontend: vite build passes
- Full pytest suite passes
