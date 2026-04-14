## Problem / Motivation

Phase 3c of the web port: the Game Sessions tab is the most complex entity and unblocks all downstream derived views (Daily Sessions, Realized Transactions), reports (Tax Report, P/L Report), and tools.

The backend (model, ORM, repo, service, API) is already complete. The frontend WIP (GameSessionsTab, GameSessionModal, constants, utils) was developed in prior sessions and needs to be committed and shipped.

## Proposed Solution

Commit and ship the existing Game Sessions implementation:

**Backend (already on develop):**
- HostedGameSession model (30+ fields, Active/Closed status)
- HostedGameSessionRepository (CRUD + active session guard + pagination)
- HostedWorkspaceGameSessionService (create/update/delete with FIFO rebuild, event links, expected-balances, deletion-impact)
- 7 API endpoints: list, create, update, batch-delete, single-delete, expected-balances, deletion-impact

**Frontend (WIP, uncommitted):**
- GameSessionsTab.jsx with Active Only filter and Active Sessions counter
- GameSessionModal.jsx with 4 modes: create (Start Session), edit (Edit Active/Closed), close (Close Session), view (View Session)
- Expected balance auto-fill on create
- Balance check (match/higher/lower) always-on
- P/L preview for closed sessions
- End & Start New flow
- Deletion impact check
- useEntityTable hook extended for "close" mode (PATCH with status=Closed)
- gameSessionsConstants.js (13 columns, initial form)
- gameSessionsUtils.js (formatters, normalizers)

## Scope

- [x] Backend model/repo/service/API (already shipped)
- [ ] Commit WIP frontend (3 modified files)
- [ ] Verify tests pass
- [ ] Open PR into develop

## Acceptance Criteria

- Game Sessions tab visible in web app navigation
- Start Session creates an Active session with auto-filled expected balances
- Close Session transitions Active to Closed with ending balances and P/L preview
- Edit works for both Active and Closed sessions
- View shows read-only detail with Edit/Close/Delete actions
- End & Start New closes current and opens pre-filled create
- Active Only filter and Active Sessions counter work
- Deletion impact check warns before destructive deletes
- All existing tests pass

## Test Plan

- Existing pytest suite passes (1342+ tests)
- Manual: Start Session, Close Session, Edit, View, Delete, End & Start New
