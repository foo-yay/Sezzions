## Problem / Motivation

The Game Types entity has no web implementation yet. The desktop app has a fully functional Game Types tab (Setup > Game Types) with CRUD operations, but the web app only has a disabled sidebar stub. Game Types are a prerequisite for the Games entity (FK dependency).

## Proposal

Implement full-stack Game Types web support using the established EntityTable pattern:

### Backend
- Add `HostedGameType` domain model to `services/hosted/models.py`
- Create `hosted_game_type_repository.py` (standard workspace-scoped CRUD)
- Create `workspace_game_type_service.py`
- Add 5 API endpoints at `/v1/workspace/game-types` (list, create, update, delete, batch-delete)

### Frontend
- Create `GameTypesTab/` with EntityTable config, modal, constants, utils
- Fields: name (required), is_active, notes
- Enable the tab in AppShell

### Desktop parity
- Desktop UI requires: name (required)
- Desktop UI optional: notes, is_active (default true)
- Desktop enforces unique name per workspace
- Notes section is collapsible in desktop

## Scope

- [x] Hosted domain model
- [x] Hosted repository
- [x] Hosted service
- [x] API endpoints (5)
- [x] Frontend tab (EntityTable pattern)
- [x] Frontend modal (view/create/edit)
- [x] Enable tab in AppShell
- [x] Changelog entry

## Acceptance Criteria

- Game Types tab loads and displays existing game types
- Can create a new game type with name (required) and optional notes
- Can edit an existing game type (name, is_active, notes)
- Can delete single and batch-delete game types
- Name is required (validation error shown if empty)
- All 1196+ existing tests still pass
- Frontend builds cleanly

## Test Plan

- Backend: model validation (name required, strip whitespace)
- Frontend: vite build passes
- Full pytest suite passes
