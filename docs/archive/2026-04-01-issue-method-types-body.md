## Problem / Motivation

The "Method Types" tab exists in AppShell but is disabled. Redemption Method Types (e.g., Bank, Crypto, Check, PayPal) are a lookup entity that categorizes Redemption Methods. The backend domain model, desktop repo/service, and hosted ORM record already exist, but there is no hosted API endpoint or web UI for managing them.

## Proposed Solution

Full-stack implementation of the Redemption Method Types entity for the web app:

**Backend (API layer)**
- Add `HostedRedemptionMethodType` dataclass to `services/hosted/models.py`
- Add `HostedRedemptionMethodTypeRepository` in `repositories/hosted_redemption_method_type_repository.py`
- Add `HostedWorkspaceRedemptionMethodTypeService` in `services/hosted/workspace_redemption_method_type_service.py`
- Add CRUD + batch-delete endpoints to `api/app.py` at `/v1/workspace/redemption-method-types`

**Frontend (web tab)**
- Create `web/src/components/MethodTypesTab/` with:
  - `MethodTypesTab.jsx` — thin config layer using `useEntityTable` + `EntityTable`
  - `methodTypesConstants.js` — columns, initial form, initial filters
  - `methodTypesUtils.js` — normalizeForm, getColumnValue
  - `MethodTypeModal.jsx` — view/edit/create modal
- Enable the "method-types" tab in `AppShell.jsx`

## Scope

- Entity fields: name (required), is_active, notes (optional)
- Standard CRUD: list (paginated), create, update, delete, batch-delete
- Follows the EntityTable shared infrastructure pattern (Issue #248)
- No changes to other entities

## Acceptance Criteria

- [ ] API endpoints return correct paginated data for redemption method types
- [ ] Method Types tab is enabled and navigable in the web app
- [ ] Users can create, view, edit, and delete method types
- [ ] Batch delete works
- [ ] Tab uses shared EntityTable infrastructure (not duplicated)
- [ ] Build passes with no warnings

## Test Plan

- Backend: unit tests for hosted service CRUD + batch delete
- Frontend: Vite build passes, manual smoke test of tab
