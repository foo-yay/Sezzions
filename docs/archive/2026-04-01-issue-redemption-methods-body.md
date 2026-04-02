## Problem / Motivation

The Redemption Methods entity tab is stubbed in the web app (disabled in AppShell) but has no backend API or frontend implementation yet. The desktop app has full Redemption Methods CRUD, and the web app needs functional parity.

Redemption Methods have two FK relationships (user_id -> Users, method_type_id -> Redemption Method Types), making this the first entity with two foreign-key joins.

## Proposed Solution

Full-stack implementation following the established EntityTable thin-config pattern:

### Backend
- Add `HostedRedemptionMethod` dataclass to `services/hosted/models.py` (fields: name, method_type_id, user_id, is_active, notes; display fields: user_name, method_type_name)
- Create `repositories/hosted_redemption_method_repository.py` with two outerjoin queries (users + method types) for display names
- Create `services/hosted/workspace_redemption_method_service.py` (list, create, update, delete, batch-delete)
- Add 5 API endpoints at `/v1/workspace/redemption-methods` in `api/app.py`

### Frontend
- Create `web/src/components/RedemptionMethodsTab/` with thin config (~120 lines)
- Constants: columns (Name, Method Type, User, Status, Notes), initial form, page size
- Utils: normalizeForm, getColumnValue
- Modal: two TypeaheadSelect dropdowns (users + method types) following CardModal pattern
- Tab: extraLoaders for both users and method types
- Enable tab in AppShell

## Scope / Boundaries

- In scope: Full CRUD for Redemption Methods, two-FK JOIN pattern, frontend tab with TypeaheadSelect dropdowns
- Out of scope: Redemptions entity, CSV export, advanced filters beyond what EntityTable provides

## Acceptance Criteria

- [ ] `GET /v1/workspace/redemption-methods` returns paginated list with user_name and method_type_name resolved
- [ ] `POST /v1/workspace/redemption-methods` creates with FK validation
- [ ] `PATCH /v1/workspace/redemption-methods/{id}` updates all fields
- [ ] `DELETE /v1/workspace/redemption-methods/{id}` deletes single record
- [ ] `POST /v1/workspace/redemption-methods/batch-delete` deletes multiple
- [ ] Frontend tab shows Name, Method Type, User, Status, Notes columns
- [ ] Modal has TypeaheadSelect for both User and Method Type
- [ ] Tab is enabled in AppShell navigation

## Test Plan

- Unit tests for HostedRedemptionMethod model validation
- Integration tests for repository CRUD with two-FK joins
- Service-level tests for workspace scoping
