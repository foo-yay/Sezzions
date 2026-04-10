## Problem / motivation

The `compute_expected_balances` endpoint (Issue #267) currently uses Priority 2 (last closed session) and Priority 3 (zero baseline) as anchors. Priority 1 — balance checkpoint anchors from the Adjustments system — is skipped because Adjustments CRUD is not yet ported to web. Additionally, the desktop "Adjusted" badge on game sessions (shows when adjustments fall within a session's basis period) requires adjustment timeline queries.

Adjustments are Phase 5 in the web port plan. The Supabase schema already has `HostedAccountAdjustmentRecord` in `services/hosted/persistence.py`, and `HostedRecalculationService` reads adjustments during recalc. What's missing is the CRUD layer (repo, service, API endpoints) and the frontend tab.

## Proposed solution

Port the Adjustments system to web:
1. **Repository**: `HostedAdjustmentRepository` — CRUD for adjustments (balance checkpoints, basis corrections)
2. **Service**: `HostedWorkspaceAdjustmentService` — business logic, validation
3. **API endpoints**: GET list, POST create, PATCH update, DELETE
4. **Frontend tab**: AdjustmentsTab in the Tools area (Phase 5)
5. **Integrate checkpoint anchors**: Update `compute_expected_balances` to query `get_latest_checkpoint_before()` as Priority 1
6. **Adjusted badge**: Add adjustment timeline query for game sessions table

Desktop reference: `services/adjustment_service.py`, `repositories/adjustment_repository.py`, `models/adjustment.py`

## Scope

In-scope:
- Hosted adjustment repository + service + API
- Adjustments frontend tab (Tools section)
- Checkpoint anchor integration in `compute_expected_balances`
- Adjusted badge on game sessions

Out-of-scope:
- Daily session sync (separate issue)
- Tax withholding recalc on adjustment (separate issue)

## Acceptance criteria

- Adjustments CRUD works via web UI
- Balance checkpoints serve as Priority 1 anchor in expected balance computation
- Adjusted badge appears on game sessions when adjustments fall in the basis period
- Backend tests for adjustment CRUD + checkpoint anchor integration

## Test plan

Automated tests:
- Adjustment CRUD repository + service tests
- `compute_expected_balances` with checkpoint anchor vs without
- Adjusted badge timeline logic

Manual verification:
- Create/edit/delete adjustments in web UI
- Verify expected balances use checkpoint when available
