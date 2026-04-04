## Problem / Goal

Phase 3a of the web port plan: implement the Purchases full-stack entity. Purchases are the first transaction entity and create FIFO cost-basis lots. This sets the pattern for Redemptions and Game Sessions.

## Proposal

Full-stack implementation following the established EntityTable pattern (same as Games, Sites, Cards, etc.):

**Backend:**
- `HostedPurchase` domain model in `services/hosted/models.py`
- `HostedPurchaseRepository` in `repositories/hosted_purchase_repository.py` (with JOINs on users, sites, cards)
- `HostedWorkspacePurchaseService` in `services/hosted/workspace_purchase_service.py`
- API endpoints: `GET/POST /v1/workspace/purchases`, `PATCH/DELETE /v1/workspace/purchases/{id}`, `POST /v1/workspace/purchases/batch-delete`
- Timestamp service integration on create/update
- `remaining_amount` initialized to `amount` on create

**Frontend:**
- `PurchasesTab/` component directory with EntityTable config
- `PurchaseModal` with form fields: Date (required), Time, User (required FK), Site (required FK), Amount (required, > 0), SC Received, Post-Purchase SC (starting_sc_balance), Card (optional FK), Cashback, Notes
- TypeaheadSelect for User, Site, Card dropdowns
- Currency/decimal formatting for monetary fields

**Scope for this Issue (MVP):**
- Core CRUD: create, list, view, edit, soft-delete, batch-delete
- Timestamp uniqueness enforcement via HostedTimestampService
- remaining_amount = amount on create
- FK joins for user_name, site_name, card_name display
- Table columns: Date/Time, User, Site, Amount, SC Received, Starting SC, Card, Cashback, Remaining, Status, Notes

**Deferred to follow-up Issues:**
- Cashback auto-calculation from card rate
- Balance check display (expected vs actual)
- Consumed protection (immutable amount/date when FIFO-consumed)
- Active session warning
- FIFO reprocessing triggers on edit/delete
- Dormant status lifecycle
- Starting redeemable balance auto-computation
- Row color coding by consumption status

## Scope

- [x] Backend model, repository, service, API
- [x] Frontend tab, modal, constants, utils
- [x] Timestamp service integration
- [x] AppShell routing for purchases tab
- [x] Tests for repository and service

## Acceptance Criteria

- Can create a purchase with date, user, site, amount (required) + optional fields
- Can list all purchases with FK names resolved (user, site, card)
- Can view, edit, and soft-delete purchases
- Can batch-delete purchases
- Timestamp conflicts auto-resolve (increment by 1 second)
- remaining_amount equals amount on create
- Table displays all columns with sorting and filtering
- All new tests pass; no regressions

## Test Plan

- Unit tests for HostedPurchase model validation
- Integration tests for HostedPurchaseRepository CRUD + FK joins
- Integration tests for workspace_purchase_service
- Full pytest suite passes with no regressions
