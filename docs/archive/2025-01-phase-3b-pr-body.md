## Summary

Full-stack implementation of the Redemptions tab (Phase 3b of the web port plan). Follows the same patterns established in Phase 3a (Purchases).

## Backend

- **HostedRedemption** dataclass in `services/hosted/models.py` with validation and `as_dict()`
- **HostedRedemptionRepository** with LEFT JOINs to users, sites, redemption methods, and realized transactions for joined display names and accounting fields (cost_basis, net_pl)
- **HostedWorkspaceRedemptionService** — full CRUD plus cancel/uncancel workflow, with FIFO rebuild on every write operation
- **8 API endpoints**: paginated list, create, update, delete, batch-delete, cancel, uncancel

## Frontend

- **RedemptionsTab** using the shared `useEntityTable` + `EntityTable` pattern
- **RedemptionModal** with view mode (detail grid) and edit mode (form with TypeaheadSelect for user/site/method, Full/Partial radio, Free SC checkbox, receipt date, processed checkbox)
- Status chips (PENDING = active, CANCELED = inactive), net P/L color coding (green/red)
- Wired into AppShell nav between Purchases and Tools

## Cancel/Uncancel Workflow

- Cancel: PENDING -> CANCELED with timestamp and optional reason; rebuilds FIFO to release cost basis
- Uncancel: CANCELED -> PENDING; clears cancel fields and rebuilds FIFO to re-allocate

## Tests

- 17 new tests covering: basic CRUD, cancel/uncancel, FIFO integration, partial/free SC handling, pair isolation, error cases
- Full suite: 1294 passed (no regressions), 1 pre-existing failure (expenses UI test), 1 skipped
- Frontend build: clean (140 modules)

## Files Changed

| Area | Files |
|------|-------|
| Model | `services/hosted/models.py` |
| Repository | `repositories/hosted_redemption_repository.py` (new) |
| Service | `services/hosted/workspace_redemption_service.py` (new) |
| API | `api/app.py` |
| Frontend | `web/src/components/RedemptionsTab/` (4 new files) |
| Frontend | `web/src/components/AppShell.jsx`, `Icon.jsx`, `forms.css` |
| Tests | `tests/services/hosted/test_workspace_redemption_service.py` (new) |

## Pitfalls / Follow-ups

- **API endpoint tests**: Backend tests cover the service layer; dedicated API/integration tests for the redemption endpoints could be added in a follow-up.
- **Redemption method filtering**: The modal filters methods by selected user (matching desktop behavior). If method assignment changes, the filter logic may need updating.
- **Status transitions**: Currently only PENDING <-> CANCELED. If additional statuses are needed (e.g., COMPLETED, PROCESSING), the state machine will need expansion.
- **Batch cancel**: Only batch delete is implemented; batch cancel could be a future enhancement if needed.
