# Sezzions — Changelog (Human + AI Parsable)

Purpose: a chronological log of noteworthy changes.

Rules:
- One entry per meaningful change set.
- Prefer adding here over creating a new markdown file.
- Entries must include the metadata block.

---

## 2026-04-03

```yaml
id: 2026-04-03-02
type: feature
areas: [api, web, services, repositories, models]
issue: "#260"
summary: "Phase 3a — Purchases Tab (full-stack CRUD)"
details: >
  Full-stack Purchases entity: HostedPurchase model with Decimal validation,
  HostedPurchaseRepository with FK joins (users, sites, cards),
  HostedWorkspacePurchaseService, 5 API endpoints at /v1/workspace/purchases,
  PurchasesTab + PurchaseModal frontend with TypeaheadSelect for FKs,
  Activity nav group in AppShell with /activity/:tabKey routing,
  purchases icon in Icon component. 22 new tests (model + service + edge cases).
```

## 2026-04-03

```yaml
id: 2026-04-03-01
type: feature
areas: [services]
issue: "#258"
summary: "Phase 2 — Accounting Engine Core (hosted services + tests)"
details: >
  Ported the four core accounting services from the desktop layer to the hosted
  (SQLAlchemy / web) layer: HostedTimestampService (timestamp uniqueness enforcement),
  HostedFIFOService (FIFO cost-basis calculation), HostedRecalculationService
  (bulk FIFO + realized-transaction rebuilds with full/scoped/all-pairs modes),
  and HostedEventLinkService (temporal BEFORE/DURING/AFTER classification of
  purchases and redemptions relative to game sessions). Includes 53 tests covering
  happy paths, edge cases (deleted records, canceled redemptions, free SC, close-
  balance Net Loss, synthetic BASIS_USD_CORRECTION adjustments), failure injection,
  and idempotency invariants.

files_changed:
  - services/hosted/hosted_timestamp_service.py (new)
  - services/hosted/hosted_fifo_service.py (new)
  - services/hosted/hosted_recalculation_service.py (new)
  - services/hosted/hosted_event_link_service.py (new)
  - tests/services/hosted/test_hosted_timestamp_service.py (new — 11 tests)
  - tests/services/hosted/test_hosted_fifo_service.py (new — 11 tests)
  - tests/services/hosted/test_hosted_recalculation_service.py (new — 15 tests)
  - tests/services/hosted/test_hosted_event_link_service.py (new — 16 tests)
```

## 2026-04-02

```yaml
id: 2026-04-02-01
type: feature
areas: [web, api]
issue: "#255"
summary: "Games — full-stack web implementation"
details: >
  Full-stack Games entity (name, game_type_id FK, rtp, actual_rtp, is_active, notes)
  following EntityTable + FK pattern (same as Redemption Methods).
  Backend: HostedGame model, hosted_game_repository with game_types JOIN,
  workspace_game_service, 5 API endpoints at /v1/workspace/games.
  Frontend: thin EntityTable config with GameModal (TypeaheadSelect for game type,
  optional RTP numeric field, read-only Actual RTP display). Tab enabled in AppShell.
  Persistence record (HostedGameRecord) already existed.

files_changed:
  - services/hosted/models.py (add HostedGame)
  - repositories/hosted_game_repository.py (new)
  - services/hosted/workspace_game_service.py (new)
  - api/app.py (request models + dependency + 5 endpoints)
  - web/src/components/GamesTab/ (new — 4 files)
  - web/src/components/AppShell.jsx (enable games tab)
```

## 2026-04-01

```yaml
id: 2026-04-01-03
type: feature
areas: [web, api]
issue: "#254"
summary: "Game Types — full-stack web implementation"
details: >
  Full-stack Game Types entity (name, is_active, notes) following EntityTable pattern.
  Backend: HostedGameType model, hosted_game_type_repository, workspace_game_type_service,
  5 API endpoints at /v1/workspace/game-types. Frontend: thin EntityTable config with
  GameTypeModal (view/create/edit). Tab enabled in AppShell.
  Persistence record (HostedGameTypeRecord) already existed.

files_changed:
  - services/hosted/models.py (add HostedGameType)
  - repositories/hosted_game_type_repository.py (new)
  - services/hosted/workspace_game_type_service.py (new)
  - api/app.py (request models + dependency + 5 endpoints)
  - web/src/components/GameTypesTab/ (new — 4 files)
  - web/src/components/AppShell.jsx (enable game-types tab)
```

```yaml
id: 2026-04-01-02
type: feature
areas: [web, api]
issue: "#252"
summary: "Redemption Methods — full-stack web implementation"
details: >
  Full-stack Redemption Methods entity with two FK relationships (user_id, method_type_id).
  Backend: HostedRedemptionMethod model, repository with two-FK outerjoin pattern (users +
  method types), workspace service, 5 API endpoints at /v1/workspace/redemption-methods.
  Frontend: thin EntityTable config with extraLoaders for both users and method types,
  RedemptionMethodModal with two TypeaheadSelect dropdowns. Tab enabled in AppShell.

files_changed:
  - services/hosted/models.py (add HostedRedemptionMethod)
  - repositories/hosted_redemption_method_repository.py (new)
  - services/hosted/workspace_redemption_method_service.py (new)
  - api/app.py (add endpoints + request models + dependency)
  - web/src/components/RedemptionMethodsTab/RedemptionMethodsTab.jsx (new)
  - web/src/components/RedemptionMethodsTab/RedemptionMethodModal.jsx (new)
  - web/src/components/RedemptionMethodsTab/redemptionMethodsConstants.js (new)
  - web/src/components/RedemptionMethodsTab/redemptionMethodsUtils.js (new)
  - web/src/components/AppShell.jsx (enable tab + import)
```

---

## 2026-04-01

```yaml
id: 2026-04-01-01
type: refactor
areas: [web]
issue: "#248"
pr: "#249"
summary: "Extract shared EntityTable hook + component from duplicated tab code"
details: >
  Three entity tabs (Users, Sites, Cards) shared ~73% identical code across
  ~4,195 lines. Extracted shared useEntityTable hook (~600 lines), EntityTable
  component (~300 lines), tableUtils (~175 lines), and 4 shared components
  into common/. Each tab reduced to ~120-145 line thin config layer.
  Net: -2,528 lines, bundle 520.66→464.10 kB (10.8% smaller).

files_changed:
  - web/src/hooks/useEntityTable.js (new)
  - web/src/components/common/EntityTable.jsx (new)
  - web/src/utils/tableUtils.js (new)
  - web/src/components/common/ExportModal.jsx (moved)
  - web/src/components/common/FilterTreeNode.jsx (moved)
  - web/src/components/common/TableContextMenu.jsx (moved)
  - web/src/components/common/TableHeaderFilterMenu.jsx (moved+renamed)
  - web/src/components/UsersTab/UsersTab.jsx (rewritten)
  - web/src/components/SitesTab/SitesTab.jsx (rewritten)
  - web/src/components/CardsTab/CardsTab.jsx (rewritten)
  - web/src/components/UsersTab/usersUtils.js (slimmed)
  - web/src/components/SitesTab/sitesUtils.js (slimmed)
  - web/src/components/CardsTab/cardsUtils.js (slimmed)
```

---

## 2026-03-31

```yaml
id: 2026-03-31-03
type: feature
areas: [web]
issue: "#244"
summary: "Add URL-based routing with React Router for Setup tabs"
details: >
  Replaced hash-based routing (/#/migration, manual hashchange listeners)
  with React Router v6 (BrowserRouter, Routes, useParams, useNavigate, Link).
  Setup tabs are now at /setup/:tabKey, migration at /migration. useAuth uses
  React Router's useLocation() for OAuth return route persistence instead of
  reading window.location directly. Vite dev server configured with SPA
  historyApiFallback. All 19 tests updated to use MemoryRouter wrapper.

files_changed:
  - web/src/main.jsx
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/components/AppShell.jsx
  - web/src/components/MarketingShell.jsx
  - web/src/components/MigrationShell.jsx
  - web/src/hooks/useAuth.js
  - web/src/services/routing.js
  - web/vite.config.js
  - web/package.json
```

```yaml
id: 2026-03-31-02
type: bugfix
areas: [backend, database]
issue: "#242"
summary: "Fix FK cascade migration silently nulling redemption_method_id"
details: >
  _migrate_user_fk_cascade() and _migrate_redemption_methods_table() ran
  DROP TABLE with PRAGMA foreign_keys=ON, which triggered ON DELETE SET NULL
  on redemptions.redemption_method_id, silently nulling 288 method assignments.
  Added PRAGMA foreign_keys=OFF/ON around all table-rebuild migrations.
  Restored affected data from the 3/30 auto-backup.

files_changed:
  - repositories/database.py
```

```yaml
id: 2026-03-31-01
type: feature
areas: [web, api, backend]
issue: "#242"
pr: "#243"
summary: "Port Setup > Sites CRUD to hosted web app"
details: >
  Full Sites management tab for the hosted web app: list/create/edit/delete
  with inline editing, status toggles, and confirmation dialogs matching the
  Users tab pattern. Backend: HostedSite SQLAlchemy model, hosted_site_repository,
  workspace_site_service, 5 API endpoints. Frontend: SitesTab, SiteModal,
  sitesConstants, sitesUtils. Added DRY/reusability design principles to
  PROJECT_SPEC.md, copilot-instructions.md, and AGENTS.md.

files_changed:
  - api/app.py
  - models/hosted_site.py
  - repositories/hosted_site_repository.py
  - services/hosted/workspace_site_service.py
  - web/src/components/SitesTab/ (new)
  - web/src/components/AppShell.jsx
  - docs/PROJECT_SPEC.md
  - .github/copilot-instructions.md
  - AGENTS.md
```

## 2026-03-30

```yaml
id: 2026-03-30-02
type: chore
areas: [repo, docs]
issue: "#238"
summary: "Reorganize repo: move desktop-only code to desktop/ subdirectory"
details: >
  Moved all desktop-specific files (PyQt UI, entrypoint, resources, build spec)
  into a desktop/ subdirectory. Shared backend code (models, repositories,
  services, app_facade) remains at root. Updated all import paths from
  'from ui.*' to 'from desktop.ui.*' across ~70 files. Updated AGENTS.md,
  copilot-instructions.md, and PROJECT_SPEC.md to reflect active web
  development vs deprecated desktop.

  Desktop app remains runnable via: python3 desktop/sezzions.py

files_changed:
  - desktop/ (new — ui/, sezzions.py, resources/, __init__.py)
  - ~70 .py files (import path updates)
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-30-01
type: feat
areas: [hosted, persistence, tests]
issue: "#236"
summary: "Hosted DB schema parity with desktop: timestamps, missing columns, missing tables, auto-migration"
details: >
  Brought the hosted Postgres schema into full parity with the desktop SQLite schema.

  Implemented:
  - Added created_at and updated_at columns to all 18 domain ORM tables
  - Added created_at to 4 link/transaction tables (event_links, allocations, realized_transactions, tz_history)
  - Added starting_redeemable_balance column to hosted_purchases
  - Added 3 missing tables: hosted_audit_log, hosted_settings, hosted_accounting_time_zone_history
  - Added generic _migrate_missing_columns() auto-migration that introspects ORM metadata vs live schema and ALTERs any missing columns with correct types/defaults
  - 12 new tests covering timestamp presence, new tables, migration idempotency, and column default SQL generation

  Validation:
  - python3 -m pytest (1170 passed, 1 known flaky skipped)
files_changed:
  - services/hosted/persistence.py
  - tests/services/hosted/test_hosted_schema_parity.py
  - tests/services/hosted/test_business_schema_foundation.py
  - docs/status/CHANGELOG.md
```

## 2026-03-29

```yaml
id: 2026-03-29-19
type: feat
areas: [web, docs, tests]
issue: none
summary: "Reframe hosted Users into a contained scrolling data grid"
details: >
  Reworked the hosted Users experience into a single framed data-grid surface.
  The Setup/Users intro now lives inside the framed surface so it scrolls away
  under the rounded top edge before the action/search controls pin in place.
  The row area then continues beneath sticky table headers, and the bottom
  stats rail acts as an integrated opaque footer without extra nested chrome
  or translucent corners.

  Implemented:
  - contained hosted Users frame with rounded outer borders
  - scoped scroll viewport that lets the Setup/Users intro scroll away first
  - internal row viewport with sticky hosted Users headers
  - simplified integrated footer rail with shown/total/selected stats and load-more action
  - removed the extra footer status copy from the hosted Users surface
  - updated frontend tests for viewport-based paging and the single summary rail

  Validation:
  - cd web && npm test -- --run
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/styles.css
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-18
type: feat
areas: [web, docs, tests]
issue: none
summary: "Lock hosted Users controls while table rows scroll"
details: >
  Finalized the hosted Users panel around a fixed-controls data-grid pattern.
  Action buttons, search, summary chips, and footer stats now stay outside the
  scrollable row viewport so the interface behaves more like a desktop table.
  Infinite loading is driven by the table viewport rather than the page, which
  keeps the controls stable while the row area scrolls independently.

  Implemented:
  - internal scrolling viewport for hosted Users rows
  - opaque sticky table headers inside the row viewport
  - fixed top controls and top/bottom summary rails outside the row scroll area
  - updated frontend tests for viewport-based paging behavior

  Validation:
  - cd web && npm test
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/styles.css
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-17
type: feat
areas: [web, docs]
issue: none
summary: "Add sticky Users controls and bottom stats rail"
details: >
  Continued the hosted Users UI polish by turning the actions and search area
  into a sticky control block and moving the summary chips into dedicated top
  and bottom rails. The framed internal-scroll table experiment was then backed
  out in favor of preserving the original page-scroll loading behavior while
  keeping the sticky bottom stats treatment.

  Implemented:
  - sticky hosted Users action/search control block
  - top and bottom summary rails for shown, total, selection, and filtered-state chips
  - search input switched to a plain text control and corrected left padding so the custom search icon no longer collides with the text
  - restored page-scroll-based auto loading instead of an internal table scroll frame

  Validation:
  - cd web && npm test
files_changed:
  - web/src/App.jsx
  - web/src/styles.css
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-16
type: fix
areas: [web, docs]
issue: none
summary: "Polish hosted Users search spacing and viewport fit"
details: >
  Tightened the hosted Users page after live validation. The search field now
  clears the browser-native search decoration so the custom magnifying-glass
  icon no longer overlaps the placeholder text, and the Users page/table shell
  no longer impose oversized viewport-based minimum heights when only a small
  number of rows are present.

  Implemented:
  - removed native WebKit search adornments from the hosted Users search field
  - increased the left text inset so the custom search icon has clear spacing
  - removed hard minimum heights that forced the Users table below the visible window when few rows exist

  Validation:
  - cd web && npm test
files_changed:
  - web/src/styles.css
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-15
type: feat
areas: [web, docs, tests]
issue: 233
summary: "Compact the hosted header into desktop-style utility controls"
details: >
  Reworked the hosted signed-in header again to reduce the oversized title and
  chrome introduced in the prior shell pass. The header now uses a compact
  product title and desktop-inspired utility controls for notifications,
  status, account, and settings so the Setup content keeps visual priority.
  Account details and other actions now live behind modal-style utility entry
  points instead of always-visible header blocks.

  Implemented:
  - compact header title using the product name instead of a large workspace banner
  - utility-icon pattern for notifications, status, account, and settings
  - account/settings modal access in place of the prior prominent header summary
  - updated frontend coverage for the compact header utilities

  Validation:
  - cd web && npm test
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/styles.css
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-14
type: feat
areas: [web, docs, tests]
issue: 225
summary: "Reshape the hosted shell around desktop-style tabs and compact status"
details: >
  Reworked the signed-in hosted web shell to better match the original desktop
  app structure. The hosted experience now uses top-level primary tabs with
  Setup sub-tabs beneath them, moves account ownership and sign-out actions into
  a dedicated Account section, and collapses the hosted operational checks into
  a small status affordance that opens a modal with green/orange/red health
  feedback. The Users view dialog now also restores direct Edit access from the
  view state to match the desktop workflow more closely.

  Implemented:
  - top-tab hosted shell with separate Setup and Account primary sections
  - compact hosted status indicator and modal-based detailed health view
  - desktop-style View User actions including Edit from the view dialog
  - updated frontend coverage for the new shell structure and view-dialog flow

  Validation:
  - cd web && npm test
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/styles.css
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-13
type: fix
areas: [api, database, tests]
issue: 225
summary: "Repair legacy hosted bootstrap tables before account bootstrap runs"
details: >
  Hardened the hosted persistence bootstrap so older hosted databases created
  before the account role/status columns existed are upgraded in place before
  the account bootstrap service queries them. This prevents `/v1/account/bootstrap`
  from failing with a raw 500 on long-lived hosted environments that still have
  the original bootstrap-era schema.

  Implemented:
  - compatibility upgrade for legacy `hosted_accounts` bootstrap tables
  - regression coverage for bootstrapping against a pre-role/pre-status schema

  Validation:
  - pytest -q tests/services/hosted/test_account_bootstrap_service.py tests/api/test_app.py
files_changed:
  - services/hosted/persistence.py
  - tests/services/hosted/test_account_bootstrap_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-12
type: fix
areas: [web, docs, tests]
issue: 225
summary: "Keep the hosted shell visible when bootstrap cannot be reached"
details: >
  Adjusted the hosted web entry flow so a signed-in user still lands in the
  hosted workspace shell even if the protected API handshake or hosted
  bootstrap cannot currently reach the backend. The Users slice now remains
  visible with retryable hosted-status messaging instead of leaving the user on
  the marketing shell with a generic fetch failure.

  Implemented:
  - signed-in hosted shell visibility even when bootstrap is unavailable
  - clearer network failure text for API/bootstrap/users flows
  - retry action for hosted connection recovery
  - frontend coverage for the signed-in bootstrap-failure path

  Validation:
  - cd web && npm test -- --run src/App.test.jsx
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-11
type: feat
areas: [web, api, docs, tests]
issue: 225
summary: "Port the first real hosted Setup Users slice"
details: >
  Replaced the signed-in hosted web control tower with the first real app shell
  and ported the Setup Users workflow onto the hosted backend. The browser app
  now boots into a dark hosted workspace shell after bootstrap, loads real
  workspace-owned users, and supports add/edit flows through the hosted users
  API instead of fake client-side CRUD state.

  Implemented:
  - dark hosted app shell with Setup navigation and a real Users surface
  - desktop-inspired Users tools: search, refresh, CSV export, and modal-based
    add/view/edit/delete workflows with required-field validation
  - hosted `PATCH /v1/workspace/users/{user_id}` support for editing and
    active-status changes within the authenticated workspace
  - hosted `DELETE /v1/workspace/users/{user_id}` support and an allowlist-safe
    Google OAuth redirect flow that preserves the hash-route return target locally
  - focused frontend tests for signed-in shell rendering, create/edit flows,
    and preserved migration upload behavior

  Validation:
  - pytest -q tests/services/hosted/test_workspace_user_service.py tests/api/test_workspace_users.py
  - cd web && npm test -- --run
files_changed:
  - api/app.py
  - repositories/hosted_user_repository.py
  - services/hosted/workspace_user_service.py
  - tests/api/test_workspace_users.py
  - tests/services/hosted/test_workspace_user_service.py
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/styles.css
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-10
type: feat
areas: [api, database, docs, tests]
issue: 224
summary: "Add hosted account roles and lifecycle status foundation"
details: >
  Extended the hosted account model with explicit role and lifecycle status
  fields so future Sezzions admin capabilities can be built on a real account
  authorization foundation instead of inferred behavior. Self-serve hosted
  sign-ups now default to the normal customer `owner` role and `active`
  status, while the spec now documents the intended distinction between normal
  workspace ownership and Sezzions-controlled elevated administrators.

  Implemented:
  - `role` and `status` fields on hosted account persistence/model records
  - hosted account bootstrap summaries now include role and lifecycle status
  - focused bootstrap/API tests for the new defaults and summary fields
  - spec updates documenting future admin dashboard and bug-reporting direction

  Validation:
  - pytest -q tests/services/hosted/test_account_bootstrap_service.py tests/api/test_app.py
files_changed:
  - repositories/hosted_account_repository.py
  - services/hosted/account_bootstrap_service.py
  - services/hosted/models.py
  - services/hosted/persistence.py
  - tests/api/test_app.py
  - tests/services/hosted/test_account_bootstrap_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-09
type: feat
areas: [database, services, docs, tests]
issue: 222
summary: "Define the hosted workspace-owned business schema foundation"
details: >
  Added the structural hosted business schema needed before real web UI porting
  begins. The hosted metadata now defines the core Sezzions business tables as
  workspace-owned records so future UI, import, and desktop-compatibility work
  can target the real long-term data contract rather than temporary CRUD-only
  scaffolding.

  Implemented:
  - workspace-owned hosted table definitions for core master and transactional data
  - scoped uniqueness for key workspace master tables such as users, sites,
    game types, and redemption method types
  - targeted schema tests covering table presence, explicit workspace ownership,
    and core transactional foreign-key structure

  Validation:
  - pytest -q tests/services/hosted/test_business_schema_foundation.py
files_changed:
  - services/hosted/persistence.py
  - tests/services/hosted/test_business_schema_foundation.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-08
type: feat
areas: [api, database, services, docs, tests]
issue: 220
summary: "Add a hosted workspace-managed users foundation"
details: >
  Added the first hosted business-domain data slice after account/workspace
  bootstrap: workspace-owned managed users. This preserves the product model
  where an authenticated account owner is separate from the players they manage
  inside a workspace, giving the hosted path a stable parent entity for later
  cards, transactions, and import work.

  Implemented:
  - `hosted_users` hosted persistence table keyed by `workspace_id`
  - workspace-scoped hosted user repository and service for create/list flows
  - protected `GET /v1/workspace/users` and `POST /v1/workspace/users` endpoints
  - focused service and API tests covering workspace isolation and validation

  Validation:
  - pytest -q tests/services/hosted/test_workspace_user_service.py tests/api/test_workspace_users.py
files_changed:
  - api/app.py
  - repositories/hosted_user_repository.py
  - services/hosted/__init__.py
  - services/hosted/models.py
  - services/hosted/persistence.py
  - services/hosted/workspace_user_service.py
  - tests/api/test_workspace_users.py
  - tests/services/hosted/test_workspace_user_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-07
type: fix
areas: [web, auth, docs, tests]
issue: 216
summary: "Preserve the migration hash route across navigation and sign-in"
details: >
  Fixed the staged migration upload page failing to stay visible during normal
  navigation and after Google sign-in. The web shell now reacts to hash-route
  changes client-side and preserves the full current URL as the Supabase OAuth
  redirect target so `/#/migration` survives the auth round-trip.

  Implemented:
  - reactive hash-route page selection in the staged web shell
  - Google OAuth redirect now preserves the full current URL
  - focused web test updates for the route/auth behavior

  Validation:
  - cd web && npm test -- --run src/App.test.jsx
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-06
type: fix
areas: [web, docs, tests]
issue: 216
summary: "Use a hash route for the temporary migration page on static hosting"
details: >
  Fixed the staged migration upload page returning a server-side 404 on the
  cPanel static host. The temporary migration surface now uses a hash route
  instead of a direct `/migration` path so the server only has to serve the
  root web bundle and React can select the migration view client-side.

  Implemented:
  - switched migration links/page detection to `/#/migration`
  - updated the web tests for hash-based routing
  - clarified the static-host routing constraint in the project spec

  Validation:
  - cd web && npm test -- --run src/App.test.jsx
files_changed:
  - web/src/App.jsx
  - web/src/App.test.jsx
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-05
type: feat
areas: [api, web, docs, tests]
issue: 216
summary: "Add a temporary hosted SQLite upload planning page"
details: >
  Added a pragmatic one-user migration bridge for the hosted rollout: an
  authenticated web migration page and protected API endpoint that accept a
  SQLite upload, inspect it read-only through the existing inventory service,
  and return planning data without performing any hosted business-data import.

  Implemented:
  - `POST /v1/workspace/import-upload-plan` multipart upload inspection endpoint
  - temporary uploaded-SQLite inspection service with temp-file cleanup
  - staged `/migration` page for authenticated SQLite upload planning
  - focused service, API, and web tests for the upload bridge

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/services/hosted/test_uploaded_sqlite_inspection_service.py tests/api/test_workspace_import_upload.py
  - cd web && npm test -- --run src/App.test.jsx
files_changed:
  - api/app.py
  - services/hosted/uploaded_sqlite_inspection_service.py
  - services/hosted/__init__.py
  - requirements.txt
  - web/src/App.jsx
  - web/src/App.test.jsx
  - tests/services/hosted/test_uploaded_sqlite_inspection_service.py
  - tests/api/test_workspace_import_upload.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-04
type: feat
areas: [api, web, docs, tests]
issue: 214
summary: "Add authenticated hosted workspace import planning"
details: >
  Added the next hosted product slice after workspace bootstrap: a protected
  read-only import-planning endpoint and staged web UI that report whether the
  hosted workspace has an inspectable SQLite migration source. The implemented
  contract reflects the real deployment boundary: the hosted API can only
  inspect a source SQLite path when that path is actually accessible to the API
  process.

  Implemented:
  - `GET /v1/workspace/import-plan` protected hosted planning endpoint
  - hosted planning service with safe statuses for missing paths, inaccessible
    paths, and inspection failures
  - staged web-shell import planning status/inventory rendering after bootstrap
  - focused service, API, and web tests for the new hosted slice

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/services/hosted/test_workspace_import_planning_service.py tests/api/test_workspace_import_plan.py
  - cd web && npm test -- --run src/App.test.jsx
files_changed:
  - api/app.py
  - services/hosted/workspace_import_planning_service.py
  - services/hosted/__init__.py
  - web/src/App.jsx
  - web/src/App.test.jsx
  - tests/services/hosted/test_workspace_import_planning_service.py
  - tests/api/test_workspace_import_plan.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-03
type: fix
areas: [api, database, docs, tests]
issue: 210
summary: "Allow hosted Postgres URL overrides for IPv4-safe deployments"
details: >
  Followed up on the staged hosted bootstrap 500 after Render logs showed the
  API was attempting to reach the direct Supabase database host over IPv6,
  which was unreachable from the deployed service. The hosted backend now
  accepts `SUPABASE_SQLALCHEMY_URL` or `DATABASE_URL` so deployments can use a
  Supabase pooler or other platform-safe Postgres connection string directly.

  Implemented:
  - direct SQLAlchemy URL override support for hosted database access
  - focused config coverage for the override path
  - README guidance for using a pooler/IPv4-safe connection string on hosted platforms

  Validation:
  - pending deploy verification on Render using a Supabase pooler URL override
files_changed:
  - api/config.py
  - tests/services/hosted/test_config.py
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-02
type: fix
areas: [api, database, docs, tests]
issue: 210
summary: "Require SSL on hosted Supabase Postgres connections"
details: >
  Fixed a live staged regression where authenticated hosted account bootstrap
  reached the backend but failed with a server-side error while opening the
  hosted Supabase Postgres connection. The hosted SQLAlchemy URL now includes
  `sslmode=require` by default, with an env override for deployments that need
  a different libpq SSL mode.

  Implemented:
  - default Supabase SQLAlchemy URLs now append `?sslmode=require`
  - optional `SUPABASE_DB_SSLMODE` override for hosted deployments
  - focused config tests covering the default and override cases

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/services/hosted/test_config.py tests/api/test_app.py
files_changed:
  - api/config.py
  - tests/services/hosted/test_config.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-29-01
type: feat
areas: [api, auth, database, web, docs, tests]
issue: 210
summary: "Bootstrap a hosted account and workspace after authenticated sign-in"
details: >
  Added the first persisted hosted product state after the protected Supabase
  session handshake. The hosted API now exposes `POST /v1/account/bootstrap`,
  which idempotently creates or returns the hosted account/workspace for the
  authenticated Supabase user. The web shell now calls that endpoint after the
  protected session handshake succeeds and renders the hosted owner/workspace
  summary in the UI.

  Implemented:
  - SQLAlchemy-backed hosted account/workspace persistence records
  - idempotent hosted account bootstrap service and protected API endpoint
  - web-shell bootstrap request and hosted summary rendering after sign-in
  - focused service, API, and web tests for the new authenticated slice

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/services/hosted/test_account_bootstrap_service.py tests/api/test_app.py
  - cd web && npm test -- --run App.test.jsx
files_changed:
  - api/app.py
  - repositories/hosted_account_repository.py
  - repositories/hosted_workspace_repository.py
  - services/hosted/__init__.py
  - services/hosted/account_bootstrap_service.py
  - services/hosted/persistence.py
  - web/src/App.jsx
  - web/src/App.test.jsx
  - tests/api/test_app.py
  - tests/services/hosted/test_account_bootstrap_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

## 2026-03-28

```yaml
id: 2026-03-28-10
type: fix
areas: [api, auth, tests]
issue: 203
summary: "Prefer the browser apikey during staged Supabase user fallback"
details: >
  Followed up on the still-live staged `401` after confirming the current web
  bundle was deployed. The hosted auth fallback was still preferring any
  backend-configured Supabase publishable key over the fresh `apikey` already
  being sent by the browser, which left room for stale Render env values to
  keep breaking `/auth/v1/user` validation.

  Implemented:
  - auth fallback now tries request-supplied Supabase API keys before backend
    config values
  - fallback now retries available key candidates in order instead of failing on
    the first rejected key
  - focused auth tests covering request-key precedence and ordered retries

  Validation:
  - /usr/local/bin/python3 -m pytest tests/api/test_auth.py -q
files_changed:
  - api/auth.py
  - tests/api/test_auth.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-28-09
type: fix
areas: [api, auth, web, docs, tests]
issue: 203
summary: "Provide the Supabase public key on the protected session fallback path"
details: >
  Followed up on the staged `401` issue after adding the `/auth/v1/user`
  fallback. Supabase's server-side user validation path requires both the bearer
  token and a publishable/anon API key. Added support for the hosted API to read
  that public key from backend configuration or from the web client's protected
  handshake request, and updated the web shell to forward the key alongside the
  bearer token.

  Implemented:
  - hosted config support for `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY`
  - `apikey` forwarding on the protected web handshake
  - auth tests covering the forwarded-key fallback path

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/api/test_auth.py tests/api/test_app.py tests/services/hosted/test_config.py
files_changed:
  - api/config.py
  - api/auth.py
  - web/src/App.jsx
  - tests/api/test_auth.py
  - tests/services/hosted/test_config.py
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-28-08
type: fix
areas: [api, auth, docs, tests]
issue: 203
summary: "Fallback to Supabase user validation when direct JWT decoding rejects a live session"
details: >
  Fixed the staged Google sign-in handshake returning `401` after the CORS
  issue was resolved. The browser was now reaching the Render API, but the API
  was rejecting the live Supabase access token during direct JWT/JWKS decoding.
  Added a fallback path that validates the bearer token through Supabase's
  `/auth/v1/user` endpoint before rejecting the request. This keeps the direct
  JWT path in place while making the live hosted session handshake compatible
  with the current Supabase token behavior.

  Implemented:
  - Supabase `/auth/v1/user` fallback in the hosted auth layer
  - focused auth tests covering successful fallback and unauthorized failure

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/api/test_auth.py tests/api/test_app.py tests/services/hosted/test_config.py
files_changed:
  - api/auth.py
  - tests/api/test_auth.py
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-28-07
type: fix
areas: [api, auth, deployment, docs, tests]
issue: 203
summary: "Allow staged web-to-Render auth requests through API CORS handling"
details: >
  Fixed the immediate production blocker for the protected API handshake after
  Google sign-in. The browser app on `dev.sezzions.com` was failing with
  "failed to fetch" because the Render-hosted FastAPI service rejected CORS
  preflight requests. Added CORS middleware to the hosted API, introduced
  configurable allowed origins, and added focused tests to verify that the
  staged web origin can preflight `GET /v1/session` successfully.

  Implemented:
  - FastAPI CORS middleware for staged web + local Vite origins
  - configurable `CORS_ALLOWED_ORIGINS` parsing in hosted config
  - API preflight coverage for the protected session endpoint

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/api/test_app.py tests/services/hosted/test_config.py
files_changed:
  - api/app.py
  - api/config.py
  - tests/api/test_app.py
  - tests/services/hosted/test_config.py
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-28-06
type: feat
areas: [api, auth, frontend, docs, tests]
issue: 203
summary: "Add the first protected Supabase-to-Render API handshake"
details: >
  Extended the hosted foundation with the first authenticated API slice.
  The FastAPI service now exposes `GET /v1/session`, which requires a bearer
  token and verifies the Supabase access token against Supabase JWKS before
  returning the authenticated identity summary. The web shell now uses the
  signed-in Supabase session token to call that protected endpoint and displays
  the Render handshake status in the UI.

  Implemented:
  - JWT/JWKS verification for Supabase access tokens in the API layer
  - protected `GET /v1/session` endpoint
  - web-side protected API call after Google sign-in
  - focused tests for the protected endpoint and frontend handshake behavior

  Validation:
  - PYTHONPATH=$PWD /usr/local/bin/python3 -m pytest -q tests/api/test_app.py tests/services/hosted/test_config.py
  - cd web && npm test
files_changed:
  - requirements.txt
  - api/auth.py
  - api/app.py
  - api/config.py
  - tests/api/test_app.py
  - tests/services/hosted/test_config.py
  - web/src/App.jsx
  - web/src/App.test.jsx
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-28-04
type: feat
areas: [api, auth, database, migration, docs, tests, tools]
issue: 203
summary: "Scaffold the hosted backend foundation around Supabase and FastAPI"
details: >
  Added the first concrete shared desktop/web backend foundation. The repository
  now includes a minimal FastAPI package for hosted API work, environment-based
  Supabase configuration helpers, explicit hosted account/workspace model stubs,
  and a read-only SQLite migration inventory service and CLI to inspect the
  current local database before import work begins. Documented the chosen stack
  and ownership boundary: Supabase Auth with Google first, Supabase PostgreSQL
  as the hosted system of record, FastAPI for the API layer, and `sezzions.db`
  as the initial migration source.

  Implemented:
  - FastAPI scaffold under `api/` with health and foundation endpoints
  - Supabase environment configuration loader with derived PostgreSQL host/URL
  - hosted account/workspace model stubs separate from business-domain users
  - read-only SQLite migration inventory service and CLI
  - targeted tests for hosted config, API scaffold, and migration inventory

  Validation:
  - pytest -q tests/api/test_app.py tests/services/hosted/test_config.py tests/services/hosted/test_sqlite_migration_inventory_service.py
files_changed:
  - requirements.txt
  - .gitignore
  - api/__init__.py
  - api/app.py
  - api/config.py
  - api/.env.example
  - services/hosted/__init__.py
  - services/hosted/models.py
  - services/hosted/sqlite_migration_inventory_service.py
  - tools/inspect_sqlite_for_hosted_import.py
  - tools/README.md
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
  - docs/adr/2026-03-28-hosted-foundation-stack.md
  - tests/api/test_app.py
  - tests/services/hosted/test_config.py
  - tests/services/hosted/test_sqlite_migration_inventory_service.py
```

```yaml
id: 2026-03-28-05
type: feat
areas: [web, auth, frontend, docs, tests]
issue: 203
summary: "Wire the web shell for Supabase Google sign-in"
details: >
  Replaced the static web shell call-to-action with the first real hosted auth
  state machine. The web app now initializes a Supabase browser client from
  environment variables, displays signed-in vs signed-out state, starts Google
  OAuth through Supabase, and supports sign-out from the shell. Added example
  frontend environment variables and updated docs to define the required web
  auth configuration.

  Implemented:
  - Supabase browser client module for Vite environment variables
  - Google sign-in and sign-out actions in the web shell
  - current session email display in the web UI
  - focused frontend tests for signed-out, sign-in trigger, and signed-in states

  Validation:
  - cd web && npm test
  - cd web && npm run build
files_changed:
  - web/.env.example
  - web/src/lib/supabaseClient.js
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/styles.css
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-28-03
type: feat
areas: [web, frontend, deployment, ci, docs]
issue: 201
summary: "Scaffold the actual Vite and React web frontend"
details: >
  Replaced the static tracked placeholder-only approach with a real Vite + React
  frontend scaffold under `web/`. Added a landing shell, responsive styling,
  frontend test coverage, and a working production build. Updated CI so the web
  frontend is installed, tested, and built when present, and switched the
  deployment defaults/documentation to use built output from `web/dist` with a
  canonical build command.

  Implemented:
  - Vite + React app scaffold with an initial Sezzions web landing shell
  - Vitest + Testing Library smoke coverage for the app shell
  - CI steps for frontend dependency install, test, and build
  - deploy helper/default documentation changes from tracked placeholder output
    to built frontend output

  Validation:
  - cd web && npm test
  - cd web && npm run build
files_changed:
  - .github/workflows/ci.yml
  - .gitignore
  - README.md
  - tools/README.md
  - tools/deploy_cpanel_static.sh
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
  - docs/archive/2026-03-28-issue-web-frontend-scaffold.md
  - web/package.json
  - web/package-lock.json
  - web/index.html
  - web/src/App.jsx
  - web/src/App.test.jsx
  - web/src/main.jsx
  - web/src/styles.css
  - web/src/test/setup.js
```

```yaml
id: 2026-03-28-02
type: feat
areas: [workflow, deployment, docs, tools]
issue: 199
summary: "Add staged cPanel-compatible static deployment scaffold"
details: >
  Added a GitHub Actions deployment scaffold for future static web rollout.
  Pushes to `develop` target the `development` environment and pushes to
  `main` target `production`. Deployment uses SSH + rsync through a new helper
  script and expects all hostnames, target paths, build commands, and SSH
  credentials to come from GitHub environment variables/secrets. Deployment is
  further gated by `DEPLOY_ENABLED=true` so environment values can be staged in
  GitHub before secrets are added. The workflow skips cleanly until cPanel
  deployment config is actually enabled.

  Documented:
  - required GitHub environment variables and secrets
  - required cPanel setup steps for subdomains, SSH access, authorized keys,
    and dedicated target paths
  - static-only scope of the scaffold pending a real web build/API hosting plan
  - added a minimal placeholder page under `web/static` so the development lane
    can be verified end-to-end before the real frontend exists

  Validation:
  - bash -n tools/deploy_cpanel_static.sh
  - YAML/workflow validation via editor diagnostics
files_changed:
  - .github/workflows/deploy-static-web.yml
  - tools/deploy_cpanel_static.sh
  - README.md
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
  - docs/archive/2026-03-28-issue-cpanel-deployment-workflow.md
  - web/static/index.html
```

```yaml
id: 2026-03-28-01
type: chore
areas: [workflow, ci, release, docs]
issue: null
summary: "Adopt develop-to-main workflow and guard production release publishing"
details: >
  Established `develop` as the integration/staging branch and `main` as the
  production branch. CI now runs on pushes and pull requests for both branches,
  and the release publishing workflow now refuses to run unless dispatched from
  `main`. Updated the repository instructions, PR template, README, and project
  spec so future human and AI work defaults to feature branches into `develop`
  with explicit promotion to `main` only for approved releases or hotfixes.

  Validation:
  - YAML/workflow validation via editor diagnostics
files_changed:
  - .github/workflows/ci.yml
  - .github/workflows/release-binaries.yml
  - .github/copilot-instructions.md
  - AGENTS.md
  - README.md
  - docs/PROJECT_SPEC.md
  - .github/pull_request_template.md
  - docs/status/CHANGELOG.md
```

## 2026-03-26

```yaml
id: 2026-03-26-02
type: fix
areas: [sessions, purchases, accounting, tests, docs]
issue: 196
summary: "Block closing sessions whose stored start already includes a later DURING purchase"
details: >
  Narrowed and fixed the Stake/Punt chronology bug without breaking legitimate
  mid-session purchase workflows. Verified that true `DURING` purchases still
  close correctly, then added a close-time consistency guard in
  `GameSessionService`: when a session has linked purchases during the session,
  the recorded starting total/redeemable balances must still match the
  expected-balance calculation at the session start timestamp. If they do not,
  close is rejected with a validation error instead of writing impossible
  `session_basis`, `basis_consumed`, and `net_taxable_pl` values.

  Implemented:
  - added an integration regression proving a valid mid-session purchase can
    still close normally
  - added an integration regression proving close is blocked when the stored
    session start already includes a later `DURING` purchase
  - added a narrow service-layer close guard so inconsistent chronology is
    rejected before the close transaction commits

  Validation:
  - pytest -q tests/ui/test_end_session_auto_redeemable.py tests/integration/test_issue_196_session_start_consistency.py tests/integration/test_purchase_active_session_link.py
files_changed:
  - services/game_session_service.py
  - tests/integration/test_issue_196_session_start_consistency.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-26-01
type: fix
areas: [redemptions, fifo, unrealized, timezone, tests, docs]
issue: 195
summary: "Fix same-day full closeouts dropping basis because of local-vs-UTC cutoff drift"
details: >
  Fixed a data-correctness bug in basis-bearing `Balance Closed` / full-redemption
  flows where the pre-FIFO "total remaining basis" query used the raw local
  redemption date/time while purchases had already been stored in UTC. On
  same-day entries from non-UTC entry timezones, that mismatch could exclude
  purchases that really occurred before the close in local time, causing the
  close marker to record too little `cost_basis`, leave stale
  `purchases.remaining_amount`, and keep the position highlighted in Unrealized
  after the user had explicitly closed it.

  Implemented:
  - centralized full-redemption remaining-basis lookup inside
    `RedemptionService` so both initial creation and reprocess paths reuse the
    same timezone-aware purchase windowing as FIFO allocation
  - added a unit regression proving a same-day full redemption at `09:30` local
    consumes a `09:00` local purchase but not a later `10:00` local purchase
  - added an integration regression proving `close_unrealized_position()` now
    fully consumes same-day local basis and writes the expected realized loss

  Motivation / intent:
  - explicit close markers must be trustworthy bookkeeping anchors
  - a full closeout cannot leave stale orange basis merely because local clock
    time was compared directly against UTC-stored purchase timestamps
  - pre-calculation and allocation must share one timestamp semantics rule to
    avoid path-dependent accounting drift

  Validation:
  - pytest -q tests/integration/test_issue_195_close_marker_timezone.py tests/unit/test_issue_195_full_redemption_timezone.py
  - pytest -q (full suite hit one unrelated flaky failure in `tests/ui/test_expenses_autocomplete.py`; rerunning that file alone passed)
files_changed:
  - services/redemption_service.py
  - tests/integration/test_issue_195_close_marker_timezone.py
  - tests/unit/test_issue_195_full_redemption_timezone.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

## 2026-03-25

```yaml
id: 2026-03-25-01
type: feat
areas: [sessions, unrealized, redemptions, ui, tests, docs]
issue: 193
summary: "Prompt to close low-balance positions after ending a session"
details: >
  Added a post-close prompt to the normal End Session flow when the saved ending
  balance is worth less than $1.00 at the site's SC conversion rate. The prompt
  uses dollar-equivalent value (`ending_total_sc × sc_rate`) so non-1:1 sites
  behave consistently, and it reuses the existing Unrealized close semantics:
  basis-bearing positions create the usual FIFO-backed realized loss while
  zero-basis positions create only a dormant `Balance Closed` marker with no
  FIFO change and no realized loss row. Declining the prompt leaves the session
  closed and the position open, while `End & Start New` intentionally skips the
  prompt to preserve the fast chained-session workflow.

  Validation:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/integration/test_issue_193_low_balance_close_prompt.py tests/integration/test_issue_191_zero_basis_unrealized_close.py tests/ui/test_issue_191_unrealized_zero_basis_close_ui.py
  - QT_QPA_PLATFORM=offscreen pytest -q
files_changed:
  - app_facade.py
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_issue_193_low_balance_close_prompt.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
  - docs/archive/2026-03-25-issue-low-balance-close-prompt.md
```

## 2026-03-23

```yaml
id: 2026-03-23-03
type: fix
areas: [redemptions, unrealized, ui, tests, docs]
issue: 191
summary: "Label all close markers as closed in Redemptions"
details: >
  Polished the Redemptions tab so synthetic `Balance Closed` rows display as
  `Closed` consistently, regardless of whether the underlying marker uses
  `more_remaining = 0` or `more_remaining = 1`. These rows still use the
  existing close-marker mechanism for Unrealized suppression and accounting,
  but the UI now presents both the Type and Method columns as `Closed` instead
  of mixing `Full`, `Partial`, or `Loss` labels for dormant-position markers.

  Validation:
  - pytest -q tests/ui/test_issue_191_redemptions_close_marker_label.py tests/ui/test_issue_191_unrealized_zero_basis_close_ui.py tests/integration/test_issue_191_zero_basis_unrealized_close.py
files_changed:
  - ui/tabs/redemptions_tab.py
  - tests/ui/test_issue_191_redemptions_close_marker_label.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-23-02
type: feat
areas: [unrealized, redemptions, ui, tests, docs]
issue: 191
summary: "Allow closing zero-basis Unrealized positions without changing basis logic"
details: >
  Added a dedicated zero-basis Unrealized close path for profit-only balances
  that are still visible on the site. When `Remaining Basis = $0.00`, closing
  the position now writes only an explicit `Balance Closed` marker so the row
  disappears from Unrealized until later activity resumes, without consuming
  FIFO basis, mutating historical purchases, or creating a realized cashflow
  loss. Existing basis-bearing close behavior remains unchanged.

  Validation:
  - pytest -q tests/integration/test_issue_191_zero_basis_unrealized_close.py tests/ui/test_issue_191_unrealized_zero_basis_close_ui.py tests/ui/test_issue_92_ui_smoke.py
files_changed:
  - app_facade.py
  - ui/tabs/unrealized_tab.py
  - tests/integration/test_issue_191_zero_basis_unrealized_close.py
  - tests/ui/test_issue_191_unrealized_zero_basis_close_ui.py
  - tests/ui/test_issue_92_ui_smoke.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
  - docs/archive/2026-03-23-issue-zero-basis-unrealized-close.md
```

```yaml
id: 2026-03-23-01
type: fix
areas: [ui, maintenance, cleanup, tests]
issue: null
summary: "Remove the stale Validate Data menu action"
details: >
  Removed the legacy `Tools -> Validate Data` action, which still called an old
  facade wrapper with a mismatched result shape and could crash with
  `KeyError: 'total_checks'`. Current integrity protection already runs through
  startup maintenance-mode checks, so the broken manual menu entry was retired
  instead of being kept as a misleading duplicate path.

  Validation:
  - pytest -q tests/ui/test_issue_92_ui_smoke.py
files_changed:
  - ui/main_window.py
  - app_facade.py
  - tests/ui/test_issue_92_ui_smoke.py
  - docs/status/CHANGELOG.md
```

## 2026-03-22

```yaml
id: 2026-03-22-01
type: fix
areas: [notifications, redemptions, tools, ui, tests, docs]
issue: 189
summary: "Clear stale update alerts, exclude balance-close losses, and refresh backup alerts"
details: >
  Fixed the three notification false positives reported in Issue #189.

  Implemented:
  - periodic/manual update checks now prune older persisted `app_update_available`
    rows so stale version alerts do not linger after the app is already current
  - overdue pending-receipt rules now exclude zero-dollar loss / "Balance Closed"
    redemptions so synthetic close-balance markers do not create payout-receipt
    reminders
  - backup success handling now routes through a shared Tools-tab completion path
    that clears backup notifications and refreshes the visible bell state
    immediately for both manual and automatic backups
  - added integration coverage for excluding balance-close rows and a headless UI
    regression proving backup completion clears the bell badge

  Validation:
  - pytest -q tests/ui/test_update_ui.py tests/integration/test_notification_rules_balance_closed.py tests/ui/test_backup_notification_ui.py
  - pytest -q
files_changed:
  - services/notification_service.py
  - services/notification_rules_service.py
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_notification_rules_balance_closed.py
  - tests/ui/test_backup_notification_ui.py
  - tests/ui/test_update_ui.py
  - docs/archive/2026-03-22-issue-notification-fixes.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

## 2026-03-14

```yaml
id: 2026-03-14-02
type: fix
areas: [undo-redo, purchases, redemptions, tests]
issue: 187
summary: "Close red-team gaps in purchase undo reconstruction and queued cancel cleanup"
details: >
  Follow-up adversarial replay uncovered two more integrity holes in chained
  undo/cancel flows. Undoing a deleted purchase could fail while reconstructing
  the audited snapshot because `starting_redeemable_balance` was not coerced
  back to `Decimal`. Separately, queued cancel completion could leave a stale
  `realized_transactions` row behind for zero-basis/full redemptions that never
  had FIFO allocation rows.

  Implemented:
  - undo/redo snapshot preparation now restores the missing purchase decimal
    field (and normalizes common boolean flags) before rebuilding models
  - queued and immediate cancel completion now always delete the realized row,
    even when no FIFO allocation rows exist
  - added regression coverage for purchase delete undo/redo round-trips and the
    historical queued-cancel stale-realized-row scenario

  Validation:
  - /usr/local/bin/python3 -m pytest tests/integration/test_purchase_undo_redo.py -q
  - /usr/local/bin/python3 -m pytest tests/integration/test_redemption_cancel_uncancel.py -q -k 'queued_historical_zero_basis_cancel_clears_realized_row_on_close'
files_changed:
  - services/undo_redo_service.py
  - services/redemption_service.py
  - tests/integration/test_purchase_undo_redo.py
  - tests/integration/test_redemption_cancel_uncancel.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-14-01
type: fix
areas: [redemptions, undo-redo, audit, tests]
issue: 187
summary: "Audit and undo full redemption reprocess edits"
details: >
  Fixed an accounting integrity gap where `update_redemption_reprocess()` wrote
  direct redemption updates without creating an audit snapshot or undoable
  operation. That allowed full accounting edits to change redemption amounts in
  the database with no matching row-level audit trail, and undo could not
  restore the prior value.

  Implemented:
  - full redemption reprocess updates now log an audited `UPDATE` snapshot
  - the same operation now pushes a dedicated undo/redo entry
  - added regression coverage proving the reprocess path records the old/new
    amount and undo restores the original amount

  Validation:
  - /usr/local/bin/python3 -m pytest tests/integration/test_issue_40_redemption_receipt_date.py -q
files_changed:
  - app_facade.py
  - tests/integration/test_issue_40_redemption_receipt_date.py
  - docs/status/CHANGELOG.md
```

## 2026-03-13

```yaml
id: 2026-03-13-05
type: fix
areas: [redemptions, sessions, undo-redo, tests, docs]
issue: 187
summary: "Close recursive cancel-pipeline drift found by deep war-game replay"
details: >
  Follow-up red-team simulation for Issue #187 compared live cancel/uncancel
  state against canonical `recalculate_everything()` output under nested
  purchase/redemption/cancel/delete/session/undo/redo chains.

  Implemented:
  - FIFO rebuilds now ignore soft-deleted purchases and clear stale derived rows
    for deleted/canceled redemptions within the affected pair scope.
  - Scoped FIFO seeding now ignores deleted/canceled predecessor redemptions so
    undo/delete chains cannot leak orphan allocation history forward.
  - Queued `PENDING_CANCEL` transitions now rebuild immediately so prior closed
    sessions stop counting the redemption in links and `redemptions_during`.
  - Post-change session links and closed-session totals now rebuild for the
    whole pair after scoped FIFO correction, eliminating suffix-only drift from
    nested cancel/delete/undo sequences.
  - Added regression coverage for queued-cancel deletion keeping closed-session
    totals clean alongside the new artifact-cleanup tests.

  Validation:
  - python3 tools/issue_187_wargame.py
    - Result: NO_FINDINGS
files_changed:
  - services/recalculation_service.py
  - app_facade.py
  - tests/integration/test_redemption_cancel_uncancel.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-13-04
type: fix
areas: [redemptions, sessions, undo-redo, ui, tests, docs]
issue: 187
summary: "Align redemption cancel semantics across session recalculation, event links, undo/redo, and UI gating"
details: >
  Fixed Issue #187 where redemption cancellation updated the row lifecycle and
  expected-balance timeline, but left downstream accounting and UI behavior out
  of sync.

  Implemented:
  - Closed-session recalculation now uses cancellation-aware redemption balance
    events, including canceled credit events and SC-rate conversion parity.
  - Session-event link rebuilds now exclude canceled redemptions so
    `redemptions_during` and related session views do not keep counting canceled
    rows.
  - Cancel / uncancel flows now apply FIFO, realized-transaction, and status
    changes atomically.
  - Uncancel now restores row lifecycle first and rebuilds FIFO from the
    original redemption timestamp, preventing later redemptions from keeping
    stale post-cancel allocations.
  - FIFO rebuilds now keep `PENDING_CANCEL` rows in allocation / realized
    rebuilds until queued cancellation completes, preventing rebuilds from
    corrupting queued state or breaking later session close.
  - Session close now commits queued-cancel completion atomically with the
    session status update, preventing partial close / partial cancel outcomes
    when one queued cancellation fails mid-batch.
  - The full `recalculate_everything()` path now uses the current rebuild API
    and re-syncs links/session fields in the correct order.
  - Undo/redo now reconciles redemption physical state after snapshot restore so
    cancellation-related statuses do not leave missing allocations or other
    impossible states.
  - Added delete/undo regression coverage for queued and canceled redemption
    lifecycle restoration.
  - Redemptions tab action gating now hides Cancel for received rows and locks
    `PENDING_CANCEL` rows from editing.

  Validation:
  - pytest -q tests/integration/test_redemption_cancel_uncancel.py -k "uncancel_rebuilds_fifo_chronologically_when_later_redemption_exists or nested_cancel_uncancel_sequence_stays_rebuild_stable or recalculate_everything_preserves_pending_cancel_accounting_state"
  - pytest -q tests/integration/test_redemption_cancel_uncancel.py -k "pending_cancel_batch_failure_rolls_back_all_and_session_close or undo_delete_pending_cancel_restores_queued_state_with_fifo or undo_delete_canceled_redemption_restores_canceled_without_fifo"
  - pytest -q tests/integration/test_redemption_cancel_uncancel.py tests/ui/test_redemption_cancel_visibility.py tests/integration/test_issue_40_redemption_receipt_date.py tests/unit/test_redemption_service.py
  - pytest -q tests/integration/test_redemption_cancel_uncancel.py tests/ui/test_redemption_cancel_visibility.py
  - pytest -q
files_changed:
  - services/game_session_service.py
  - services/game_session_event_link_service.py
  - services/redemption_service.py
  - repositories/game_session_repository.py
  - services/recalculation_service.py
  - app_facade.py
  - ui/tabs/redemptions_tab.py
  - tests/integration/test_redemption_cancel_uncancel.py
  - tests/ui/test_redemption_cancel_visibility.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-13-03
type: fix
areas: [release, macos, packaging, signing, tests, versioning]
issue: null
summary: "Fix macOS damaged-app gatekeeper failures after menu-name metadata update and release v1.0.13"
details: >
  Fixed a regression where macOS app bundles were reported as damaged because
  `Info.plist` metadata edits were applied after bundle signing, invalidating
  the signature.

  Implemented:
  - Re-sign macOS app bundle (`codesign --force --deep --sign -`) after
    setting `CFBundleName`/`CFBundleDisplayName`.
  - Applied the same re-sign step in local release tooling and GitHub Actions
    release workflow.
  - Updated release tool unit test expectations.
  - Bumped application version to `1.0.13`.

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - .github/workflows/release-binaries.yml
  - tests/unit/test_release_update_tool.py
  - __init__.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-13-02
type: fix
areas: [release, macos, packaging, tests, versioning]
issue: null
summary: "Set macOS app menu-bar name to Sezzions and release v1.0.12"
details: >
  Fixed packaged macOS runtime branding where the system menu bar showed the
  binary build name (`sezzions-macos-arm64`) instead of the product name.

  Implemented:
  - Release packaging now sets `CFBundleName=Sezzions` and
    `CFBundleDisplayName=Sezzions` in the macOS app bundle Info.plist.
  - Applied the same behavior in both local release tooling and GitHub Actions
    release workflow.
  - Updated unit tests for release build command expectations.
  - Bumped application version to `1.0.12`.

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - tests/unit/test_release_update_tool.py
  - .github/workflows/release-binaries.yml
  - __init__.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-13-01
type: fix
areas: [updater, macos, tests, versioning]
issue: null
summary: "Repair macOS app-bundle launch permissions during auto-update and release v1.0.11"
details: >
  Fixed a macOS auto-update failure where the updated app bundle could not be
  opened because the binary under `Contents/MacOS/` lost executable permissions,
  causing relaunch to fail with launchd spawn errors.

  Implemented:
  - Updater now enforces execute permissions on extracted app binaries before apply.
  - Apply script now also repairs `Contents/MacOS` permissions on the staged app
    before swapping into the target path.
  - Added regression assertions to ensure the script includes permission repair
    and extracted candidate binaries are executable.
  - Bumped application version to `1.0.11`.

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/ui/test_update_ui.py -k "translocated or script_clears_quarantine or ditto_extraction"
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - __init__.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

## 2026-03-12

```yaml
id: 2026-03-12-31
type: fix
areas: [updater, macos, tests, versioning]
issue: null
summary: "Use metadata-safe archive extraction for macOS auto-update and release v1.0.10"
details: >
  Fixed macOS auto-update installs producing non-launchable app bundles by
  switching updater extraction from Python `zipfile` to `ditto -x -k` on macOS,
  which preserves required app bundle metadata and executable permissions.

  Implemented:
  - Auto-updater extraction now uses `ditto` on macOS with fallback to `zipfile`
    on non-macOS environments.
  - Added UI regression test asserting `ditto` extraction path is used.
  - Bumped application version to `1.0.10`.

  Validation:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/ui/test_update_ui.py -k "translocated or script_clears_quarantine or ditto_extraction"
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - __init__.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-30
type: fix
areas: [updater, ui, macos, tests, versioning]
issue: null
summary: "Harden auto-update relaunch flow and release v1.0.9"
details: >
  Fixed macOS auto-update cases where install completed but relaunch failed with
  launchd spawn errors after app quit.

  Implemented:
  - Auto-installer now performs staged swap via temporary app path before replacing target.
  - Clears quarantine xattr on staged app bundle before relaunch attempt.
  - Adds relaunch retry (`open` then `open -n`) and richer installer log breadcrumbs.
  - Added UI regression test validating generated updater script includes quarantine
    cleanup and retry logic.
  - Bumped application version to `1.0.9`.

  Validation:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/ui/test_update_ui.py -k "translocated or script_clears_quarantine"
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - __init__.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-29
type: release
areas: [release, versioning, updater]
issue: null
summary: "Release v1.0.8 with packaged theme resource bundling fix"
details: >
  Bumped application version to `1.0.8` and published cross-platform updater
  assets so packaged runtimes include `resources/theme.qss` and related SVG
  assets, restoring full UI styling in installed binaries.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - __init__.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-28
type: fix
areas: [ui, themes, packaging, release, ci, tests]
issue: null
summary: "Include theme resources in packaged binaries to restore full UI styling"
details: >
  Fixed packaged-app styling regression where buttons/hover/rounded controls
  appeared plain because `resources/theme.qss` and related SVG assets were not
  included in PyInstaller release builds.

  Implemented:
  - Added PyInstaller data inclusion for `resources/` in local release tooling.
  - Added same inclusion in GitHub Actions macOS and Windows release builds.
  - Added unit test asserting the release tool emits `--add-data resources:resources`.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - .github/workflows/release-binaries.yml
  - tests/unit/test_release_update_tool.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-27
type: fix
areas: [updater, ui, macos, tests, versioning]
issue: null
summary: "Make auto-update install translocation-safe and bump version to 1.0.7"
details: >
  Fixed macOS packaged auto-install failures when Sezzions runs from Gatekeeper
  App Translocation paths (`/private/var/.../AppTranslocation/...`).

  Implemented:
  - Auto-installer now resolves install target via stable application locations
    when runtime bundle is translocated:
    - `/Applications/<App>.app`
    - fallback `~/Applications/<App>.app`
  - Added regression tests for translocated runtime destination selection and
    user-Applications fallback.
  - Bumped application version to `1.0.7`.

  Validation:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/ui/test_update_ui.py -k translocated
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - __init__.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-26
type: fix
areas: [settings, notifications, ui, startup, tests]
issue: null
summary: "Unify settings persistence path to prevent split-state config saves"
details: >
  Fixed inconsistent settings persistence where some components wrote to
  working-directory `settings.json` while others wrote to a different path,
  causing theme and related preferences to appear non-persistent.

  Implemented:
  - `ui/settings.py` now resolves defaults via `services.db_location_service.settings_file_path()`.
  - `app_facade.py` notification repository now uses the same canonical settings path.
  - Updated unit tests and spec documentation to reflect the canonical path behavior.

  Validation:
  - pytest -q tests/unit/test_settings_paths.py tests/unit/test_update_service.py tests/unit/test_release_update_tool.py
files_changed:
  - ui/settings.py
  - app_facade.py
  - tests/unit/test_settings_paths.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-25
type: release
areas: [release, versioning, updater]
issue: null
summary: "Release v1.0.5 with split updates channel policy restored"
details: >
  Bumped source/dev version to `1.0.5` after merging split-repo updater
  channel restoration. Development/source remains in `foo-yay/Sezzions` while
  updater manifest and binaries are published to `foo-yay/sezzions-updates`.

  Validation:
  - pytest -q
files_changed:
  - __init__.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-24
type: fix
areas: [updater, release, docs, ci, tests]
issue: null
summary: "Reinstate split-repo updater channel and enforce release guardrails"
details: >
  Reverted updater/release defaults back to the dedicated public updates repo
  (`foo-yay/sezzions-updates`) so source development remains in private
  `foo-yay/Sezzions` while binaries/manifests publish to the public updates channel.

  Implemented:
  - Restored default manifest URL to `sezzions-updates`.
  - Restored release automation default updates repo to `sezzions-updates`.
  - Added tooling guardrail: `tools/release_update.py` now fails when updates
    repo equals source repo.
  - Restored workflow publishing via `SEZZIONS_UPDATES_TOKEN` for cross-repo release writes.
  - Updated README/tools/spec docs with canonical split-repo policy.
  - Updated/added unit tests for defaults and repo-separation guard.

  Validation:
  - pytest -q tests/unit/test_update_service.py tests/unit/test_release_update_tool.py
files_changed:
  - services/update_service.py
  - tools/release_update.py
  - .github/workflows/release-binaries.yml
  - README.md
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - tests/unit/test_update_service.py
  - tests/unit/test_release_update_tool.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-23
type: release
areas: [release, versioning, updater]
issue: null
summary: "Release v1.0.4 after updater channel consolidation to Sezzions"
details: >
  Bumped application version to `1.0.4` after merging updater/release channel
  consolidation so default manifests and release automation target
  `foo-yay/Sezzions`.

  Validation:
  - pytest -q
files_changed:
  - __init__.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-22
type: fix
areas: [updater, release, docs, ci, tests]
issue: null
summary: "Consolidate updater and release automation defaults to Sezzions repository"
details: >
  Moved update manifest/release defaults from `foo-yay/sezzions-updates` to
  `foo-yay/Sezzions` to simplify release operations and avoid cross-repo publish
  confusion.

  Implemented:
  - `services/update_service.py` default manifest URL now points to Sezzions releases.
  - `tools/release_update.py` default updates repo now points to `foo-yay/Sezzions`.
  - Release workflow now uses repository `GITHUB_TOKEN` with `contents: write`
    (no separate `SEZZIONS_UPDATES_TOKEN` requirement).
  - Updated README/tools/spec docs and added regression tests for new defaults.

  Validation:
  - pytest -q tests/unit/test_update_service.py tests/unit/test_release_update_tool.py
files_changed:
  - services/update_service.py
  - tools/release_update.py
  - .github/workflows/release-binaries.yml
  - README.md
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - tests/unit/test_update_service.py
  - tests/unit/test_release_update_tool.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-21
type: release
areas: [release, versioning]
issue: 182
summary: "Release v1.0.3 with local working-directory settings persistence"
details: >
  Bumped application version to `1.0.3` after merging Issue #182 changes.
  This release includes local `settings.json` default persistence behavior
  (colocated with working directory) and associated tests/docs updates.

  Validation:
  - pytest -q
files_changed:
  - __init__.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-20
type: fix
areas: [settings, startup, tests, docs]
issue: 182
summary: "Consolidate default settings path to local working-directory settings.json"
details: >
  Updated default settings storage to always use local `settings.json` in the
  current working directory, matching DB locality and local-run expectations.

  Implemented:
  - `ui/settings.py` now resolves default settings path to local
    working-directory `settings.json` for all runtimes.
  - `Settings.save()` now ensures the parent directory exists before writing.
  - Added/updated unit tests to validate local default path behavior and
    default-path save path creation.

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/unit/test_settings_paths.py tests/unit/test_backup_notification_settings.py
files_changed:
  - ui/settings.py
  - tests/unit/test_settings_paths.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-19
type: fix
areas: [updater, ui, tests, docs]
issue: 179
summary: "Improve packaged auto-update fallback diagnostics and installer logging"
details: >
  Hardened packaged auto-update install flow so failures are diagnosable and
  manual fallback is more actionable.

  Implemented:
  - `ui/main_window.py` now records auto-install failure reasons for fallback UI.
  - Added installer log path helper: `~/Library/Application Support/Sezzions/update-installer.log`.
  - Background apply script now appends output to installer log file.
  - Manual fallback dialog now includes:
    - auto-install failure reason,
    - installer log location,
    - existing downloaded file/folder guidance.
  - Added preflight diagnostic checks for common failure causes (e.g., non-zip,
    missing app bundle, destination write permission).

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/ui/test_update_ui.py
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-18
type: fix
areas: [startup, settings, tools, release, tests, docs]
issue: 178
summary: "Consolidate DB path persistence into settings.json and add release version-sync validation"
details: >
  Follow-up to Issue #176 to reduce config sprawl and provide a testable guard
  against local source version drift behind published updater releases.

  Implemented:
  - `services/db_location_service.py` now persists `db_path` in `settings.json`
    instead of a separate `runtime_config.json` file.
  - Added legacy migration fallback: if old `runtime_config.json` contains
    `db_path`, the value is imported into `settings.json` on read.
  - Added `tools/release_update.py --check-version-sync` to validate local
    `__version__` is not behind latest published updates release.
  - Added explicit version guard helper so older explicit release versions fail
    with actionable messaging.
  - Added/updated unit tests for both behaviors.

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/unit/test_db_location_service.py tests/unit/test_release_update_tool.py
files_changed:
  - services/db_location_service.py
  - tools/release_update.py
  - tests/unit/test_db_location_service.py
  - tests/unit/test_release_update_tool.py
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-17
type: feature
areas: [startup, settings, data, tests, docs]
issue: 176
summary: "Add first-run DB location chooser and Settings-based safe DB relocation"
details: >
  Implemented Issue #176 to give users explicit control over database location
  at startup and from Settings.

  Implemented:
  - Added `services/db_location_service.py` for runtime DB path persistence and
    relocation helpers.
  - Startup now resolves DB path as:
    env override -> persisted runtime config -> runtime default.
  - Added first-run modal chooser before app initialization when no path is
    configured yet.
  - Added Settings -> Data "Database Location" UI with current path display and
    `Change Database Location...` action.
  - Added guided relocation modes:
    - Copy and Switch (recommended/default)
    - Move and Switch
  - Added overwrite confirmation for existing destination files.
  - Added controlled app restart after successful relocation so next launch uses
    the new DB immediately.

  Safety semantics:
  - DB path persistence only updates after successful relocation.
  - Copy failures leave source DB/path unchanged.
  - Move mode deletes source only after successful copy + verification.

  Validation:
  - /usr/local/bin/python3 -m pytest -q tests/unit/test_db_location_service.py tests/unit/test_sezzions_runtime_paths.py tests/ui/test_settings_undo_retention_ui.py
files_changed:
  - services/db_location_service.py
  - sezzions.py
  - ui/settings_dialog.py
  - ui/main_window.py
  - tests/unit/test_db_location_service.py
  - tests/unit/test_sezzions_runtime_paths.py
  - tests/ui/test_settings_undo_retention_ui.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-16
type: fix
areas: [tools, release, ci, tests, docs]
issue: 174
summary: "Fix next-patch release flow to increment beyond latest published tag"
details: >
  Corrected `tools/release_update.py --next-patch` behavior so repeated release
  runs do not overwrite the same tag when local `__version__` is behind already
  published updates.

  Implemented:
  - Added latest published updates-release tag lookup via GitHub CLI.
  - `--next-patch` now uses the higher of:
    - local `__version__` from `--version-file`, and
    - latest published `foo-yay/sezzions-updates` release version,
    then increments patch from that base.
  - Added unit tests for highest-version selection and release-tag parsing.
  - Updated docs to clarify next-patch semantics.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - tests/unit/test_release_update_tool.py
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-15
type: fix
areas: [packaging, startup, docs, tests]
issue: null
summary: "Fix packaged macOS app immediate exit by moving default DB path to writable user directory"
details: >
  Fixed a packaged-runtime startup failure where Sezzions attempted to use a
  default database path inside the `.app` bundle location. On downloaded builds,
  this could fail with `sqlite3.OperationalError: unable to open database file`,
  causing the app to appear to open and then immediately close.

  Implemented:
  - Added runtime DB path resolver in `sezzions.py`.
  - Source runtime keeps existing default (`./sezzions.db`).
  - Frozen/packaged runtime now defaults to:
    `~/Library/Application Support/Sezzions/sezzions.db`.
  - Ensured parent directory is created before opening the DB.
  - Added unit tests covering env override, frozen-path resolution, and parent
    directory creation.

  Validation:
  - pytest -q tests/unit/test_sezzions_runtime_paths.py
files_changed:
  - sezzions.py
  - tests/unit/test_sezzions_runtime_paths.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-14
type: feature
areas: [tools, release, ci, docs, tests]
issue: 174
summary: "Add next-patch version bump and CI workflow for macOS+Windows release assets"
details: >
  Expanded release automation to support patch-version auto-increment and
  cross-platform binary publishing from a macOS-only development setup.

  Implemented:
  - `tools/release_update.py --next-patch` to read `__version__`, increment patch,
    and write updated version back to `__init__.py` (or `--version-file`).
  - Added helpers and tests for reading/updating version file semantics.
  - Added GitHub Actions workflow `.github/workflows/release-binaries.yml` to:
    build macOS + Windows artifacts on hosted runners and publish both assets in
    one updater release flow.

  Operational note:
  - Workflow uses `SEZZIONS_UPDATES_TOKEN` secret for write access to
    `foo-yay/sezzions-updates` releases.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - tests/unit/test_release_update_tool.py
  - .github/workflows/release-binaries.yml
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-13
type: feature
areas: [tools, updater, docs, tests, release]
issue: 174
summary: "Support multi-platform binary asset publishing in one release run"
details: >
  Extended `tools/release_update.py` to publish multiple updater assets in one
  release by adding repeatable `--extra-asset PLATFORM=/path/to/asset.zip`.

  Behavior:
  - `latest.json` now includes all provided platform assets (for example,
    `macos-arm64` + `windows-x64`) so each runtime selects its exact binary.
  - Release upload now includes all staged assets plus `latest.json`.
  - Added validation for malformed extra-asset inputs and duplicate platform
    keys.
  - Updated default `notes_url` to point to the public updates release page.

  Policy/docs:
  - Documented that GitHub auto-generated source archives cannot be removed.
  - Documented binary-first distribution via direct asset links and in-app updater.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - tests/unit/test_release_update_tool.py
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-12
type: feature
areas: [tools, tests, docs, workflow]
issue: 174
summary: "Add optional local branch sync after release automation publish"
details: >
  Extended `tools/release_update.py` with optional post-publish local branch sync
  so development environments can be aligned immediately after release.

  Implemented:
  - `--sync-local-main` to fetch/switch/pull the local checkout after publish.
  - `--sync-branch <name>` to target a branch other than `main`.
  - dirty-worktree safety guard that aborts sync when uncommitted changes exist.

  Added unit tests for dirty-worktree rejection and command sequencing
  (with and without branch checkout), and updated release tool docs/spec.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - tests/unit/test_release_update_tool.py
  - tools/README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-11
type: fix
areas: [ui, updater, tests, docs]
issue: null
summary: "Disable Update Now while running from source/development runtime"
details: >
  Added a development-runtime guard so accidental auto-update from local source
  execution is prevented.

  Behavior:
  - When Sezzions runs from source (`python3 sezzions.py`), update checks still
    report availability, but `Update Now` auto-install is not offered.
  - Dialog explains that developers should sync via git or install from release
    artifacts manually.
  - Packaged app runtime keeps existing auto-install behavior.

  Validation:
  - pytest -q tests/ui/test_update_ui.py tests/unit/test_app_update_facade.py tests/unit/test_update_service.py
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-10
type: feature
areas: [ui, updater, tests, docs]
issue: null
summary: "Add Update Now action with auto-install for packaged macOS app"
details: >
  Added `Update Now` flow to manual update checks.

  Behavior:
  - Manual update check now prompts with `Update Now` when a newer version exists.
  - Update asset is downloaded and checksum-verified before install logic.
  - If running from packaged `.app` and update asset is zip containing app bundle,
    Sezzions can auto-apply update by quitting, replacing app bundle, and relaunching.
  - If running from source/dev mode, updater falls back to manual install guidance
    and opens the downloaded file location.

  Validation:
  - pytest -q tests/ui/test_update_ui.py tests/unit/test_app_update_facade.py tests/unit/test_update_service.py
files_changed:
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-09
type: fix
areas: [ui, facade, tests]
issue: null
summary: "Prevent stale/fake app-update notifications from persisting across contexts"
details: >
  Fixed a mismatch where notification center could show a stale
  `app_update_available` item (for example `9.9.9`) while manual check reported
  "Up to Date".

  Root causes and fixes:
  - Notification persistence was global (`settings.json`) and UI tests using
    temporary databases could leak fake update rows into real local settings.
  - `AppFacade` now scopes `NotificationRepository` settings file to the active
    database directory (`<db_dir>/settings.json`) so test runs stay isolated.
  - Up-to-date path now clears update notifications by deleting stale
    `app_update_available` records rather than only dismissing.
  - Added UI regression test ensuring a previously-created update notification is
    cleared when a subsequent check returns no update.

  Validation:
  - pytest -q tests/ui/test_update_ui.py tests/unit/test_app_update_facade.py tests/unit/test_update_service.py
files_changed:
  - app_facade.py
  - ui/main_window.py
  - tests/ui/test_update_ui.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-08
type: feature
areas: [tools, tests, docs, release]
issue: 174
summary: "Add one-command release automation tool for updater publishing"
details: >
  Added `tools/release_update.py` to make updater publishing a single-command flow.

  Implemented:
  - semantic version validation (`X.Y.Z`),
  - optional `v` prefix normalization,
  - automated build path for macOS arm64 via PyInstaller,
  - app-bundle zip packaging,
  - SHA-256 generation,
  - `latest.json` manifest generation,
  - release create/upload automation for `foo-yay/sezzions-updates`,
  - optional source release creation in `foo-yay/Sezzions`,
  - `--dry-run` and `--asset-path` support.

  Added unit tests for release helper semantics and updated docs.

  Validation:
  - pytest -q tests/unit/test_release_update_tool.py
files_changed:
  - tools/release_update.py
  - tests/unit/test_release_update_tool.py
  - tools/README.md
  - .gitignore
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-07
type: feature
areas: [distribution, services, docs]
issue: 171
summary: "Move updater default manifest to public sezzions-updates release channel"
details: >
  Completed a public update-distribution path so update checks work while the
  primary Sezzions source repository remains private.

  Changes:
  - Created public companion repository `foo-yay/sezzions-updates`.
  - Published `v1.0.0` release assets there:
    - `sezzions-macos-arm64.zip`
    - `latest.json`
  - Updated `DEFAULT_UPDATE_MANIFEST_URL` to point at the public release manifest.
  - Updated project spec to document private-source/public-update hosting model.

  Validation:
  - `curl -sSfL https://github.com/foo-yay/sezzions-updates/releases/latest/download/latest.json`
  - `gh release view v1.0.0 --repo foo-yay/sezzions-updates`
files_changed:
  - services/update_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-06
type: release
areas: [versioning, distribution, docs]
issue: 171
summary: "Prepare and publish Sezzions v1.0.0 release"
details: >
  Promoted the app version to `1.0.0` and published the first release-oriented
  updater distribution contract.

  Release packaging includes:
  - version bump in application metadata,
  - macOS arm64 artifact upload,
  - `latest.json` release manifest with SHA-256 integrity metadata.

  Outcome:
  - In-app update checks now resolve against a published release artifact path
    rather than returning 404 for missing manifest.

  Validation:
  - pytest -q tests/unit/test_update_service.py tests/unit/test_app_update_facade.py tests/ui/test_update_ui.py
files_changed:
  - __init__.py
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-05
type: fix
areas: [services, tests, docs]
issue: 171
summary: "Show actionable updater error when release manifest is missing (HTTP 404)"
details: >
  Improved update-check error handling for repositories without published releases.

  Changes:
  - `UpdateService` now converts manifest HTTP 404 responses into a clear message:
    publish a GitHub Release with `latest.json` asset.
  - Added unit regression test for the 404 error path.

  Validation:
  - pytest -q tests/unit/test_update_service.py tests/unit/test_app_update_facade.py tests/ui/test_update_ui.py
files_changed:
  - services/update_service.py
  - tests/unit/test_update_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-04
type: fix
areas: [services, tests, dependencies, docs]
issue: 171
summary: "Harden updater HTTPS checks on macOS cert-store failures using certifi fallback"
details: >
  Fixed update-check failures caused by Python SSL trust-store issues
  (`CERTIFICATE_VERIFY_FAILED`) on some macOS environments.

  Changes:
  - `UpdateService._default_fetcher` now detects certificate-verification errors
    and retries the HTTPS request using a `certifi` CA bundle SSL context.
  - If no trusted context can be established, updater returns a clear, actionable
    certificate error without disabling TLS verification.
  - Added unit tests for cert-failure retry path and no-cert-store fallback path.
  - Added `certifi` to runtime dependencies.

  Validation:
  - pytest -q tests/unit/test_update_service.py tests/unit/test_app_update_facade.py
  - pytest -q tests/ui/test_update_ui.py
files_changed:
  - services/update_service.py
  - tests/unit/test_update_service.py
  - requirements.txt
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-03
type: feature
areas: [ui, services, tests, docs]
issue: 171
summary: "Add desktop update UX: Help action, Settings controls, and periodic bell notifications"
details: >
  Completed the user-facing integration for the updater MVP by wiring update
  checks into the desktop shell.

  Implemented:
  - Help menu action: `Check for Updates...`.
  - Settings dialog additions:
    - software version display,
    - `Check for Updates Now` action,
    - persisted update-check settings (`enabled`, interval hours).
  - Main-window periodic update check flow using persisted settings and
    `update_last_checked_at` gating.
  - Notification bell integration:
    - create `app_update_available` notification when new version is detected,
    - route notification action `open_updates` to manual check flow,
    - dismiss stale update notifications when app is up to date.

  Test coverage:
  - Added UI tests validating menu action presence, settings controls, and
    update-notification creation path.

  Validation:
  - pytest -q tests/ui/test_update_ui.py tests/unit/test_update_service.py tests/unit/test_app_update_facade.py
  - pytest -q tests/ui/test_issue_92_ui_smoke.py tests/ui/test_settings_undo_retention_ui.py tests/integration/test_notification_cooldown.py
files_changed:
  - ui/main_window.py
  - ui/settings.py
  - ui/settings_dialog.py
  - ui/notification_widgets.py
  - tests/ui/test_update_ui.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-02
type: feature
areas: [services, facade, tests, docs]
issue: 171
summary: "Add updater service MVP for GitHub-release manifest checks and verified downloads"
details: >
  Added MVP auto-update backend primitives to support release-based updates
  without using git operations on end-user installs.

  Implemented:
  - `UpdateService` (`services/update_service.py`) with:
    - manifest fetch/parse (`latest.json` contract),
    - semantic version comparison,
    - platform-specific asset selection,
    - artifact download + SHA-256 verification.
  - `AppFacade` wiring:
    - `check_for_app_updates(...)`
    - `download_app_update(...)`

  MVP boundaries:
  - Includes update discovery, download, and integrity verification.
  - Does not yet implement installer handoff or automatic restart/install flow.

  Test-first evidence:
  - Added new unit suites covering:
    - update available/up-to-date outcomes,
    - invalid manifest handling,
    - checksum pass/fail behavior,
    - facade integration path for check + download.

  Validation:
  - pytest -q tests/unit/test_update_service.py tests/unit/test_app_update_facade.py
files_changed:
  - services/update_service.py
  - app_facade.py
  - tests/unit/test_update_service.py
  - tests/unit/test_app_update_facade.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-12-01
type: fix
areas: [services, tests, docs]
issue: 169
summary: "Apply expected balances from a single chronological event timeline"
details: >
  Fixed expected-balance chronology drift in `GameSessionService.compute_expected_balances`
  where redemptions were applied in a separate pass and then purchase snapshot assignment
  could overwrite their effect.

  Root cause:
  - Historical logic applied all redemption deltas first.
  - Purchase application then reassigned expected totals from purchase snapshots.
  - In timelines where a redemption occurred after a purchase but before cutoff,
    expected balances could incorrectly reflect pre-redemption values.

  Fix behavior:
  - Build one merged, deterministic timeline of events after anchor and before cutoff.
  - Apply purchase snapshot events and redemption debit/credit events in chronological order.
  - Preserve existing semantics:
    - purchase exclusion during edit (`exclude_purchase_id`)
    - redemption unit conversion (`$ -> SC` via `sc_rate`)
    - canceled redemption two-event model (debit + credit)

  Repro scenario now covered:
  - Anchor: 1000 total / 1000 redeemable
  - Purchase snapshot: 1300
  - Redemption after purchase before cutoff: $5.00 at sc_rate=0.01 (=500 SC)
  - Correct expected balances at cutoff: total=800, redeemable=500

  Validation:
  - pytest -q tests/integration/test_compute_expected_balances_cancel.py
  - pytest -q tests/integration/test_issue_49_purchase_exclusion.py tests/integration/test_expected_balance_entry_timezone_ordering.py tests/integration/test_expected_redeemable_not_from_purchases.py
files_changed:
  - services/game_session_service.py
  - tests/integration/test_compute_expected_balances_cancel.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

## 2026-03-10

```yaml
id: 2026-03-10-05
type: fix
areas: [services, tests, docs]
issue: null
summary: "Convert redemption dollars to SC in expected-balance timeline math"
details: >
  Fixed unit mismatch in `GameSessionService.compute_expected_balances` where
  redemption amounts (stored in dollars) were being applied as SC deltas.

  Updated logic now converts redemption dollars to SC using site `sc_rate`
  (`amount_sc = amount_usd / sc_rate`) before applying debit/credit events
  for both pending and canceled redemption timeline events.

  This resolves large false balance-check mismatches on non-unit-rate sites
  (for example, `sc_rate=0.01` where `$64.97` equals `6497 SC`).

  Validation:
  - pytest -q tests/integration/test_compute_expected_balances_cancel.py
files_changed:
  - services/game_session_service.py
  - tests/integration/test_compute_expected_balances_cancel.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-10-04
type: fix
areas: [ui, tests, docs]
issue: 162
summary: "Auto-calc redeemable now returns full end balance when normalized wager covers ending SC"
details: >
  Updated End Session and Edit Closed Session auto-calc redeemable logic to
  handle full-playthrough gain scenarios (e.g., ending balance fully redeemable
  on site after sufficient wager).

  Logic update:
  - Added a hard-capped full-unlock branch:
    if `(wager / playthrough_requirement) >= ending_total_sc`,
    auto-calc sets `ending_redeemable_sc = ending_total_sc`.
  - Existing conservative path remains for all other scenarios.

  Tests:
  - Added End Session regression test for full-unlock scenario.
  - Added Edit Closed Session regression test for full-unlock scenario.

  Validation:
  - pytest -q tests/ui/test_end_session_auto_redeemable.py
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/ui/test_end_session_auto_redeemable.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-10-03
type: feature
areas: [ui, tests, docs]
issue: 162
summary: "Refine session dialog balance guidance and redeemable auto-fill behavior"
details: >
  Updated Start Session, Edit Session, End Session, and Edit Closed Session
  dialog UX for clearer redeemable workflows and expected-balance visibility.

  Dialog updates:
  - End Session and Edit Closed Session auto checkbox now uses concise text:
    `Auto-Calc Redeemable SC` (no separate row label).
  - End Session and Edit Closed Session balance sections now render Auto-Calc as
    a dedicated label + inline checkbox row beneath Ending Redeemable, with Wager
    aligned in the paired left column row for a consistent 4x4 field grid.
  - Start/Edit/Edit Closed `Balance Check` now shows two real-time expected lines:
    `Starting SC: ...` and `Starting Redeemable: ...`.

  Starting Redeemable behavior updates:
  - `Starting Total SC` now follows the same auto-pop/manual-override lifecycle
    as `Starting Redeemable` in Start/Edit/Edit Closed dialogs.
  - Auto-populated Starting SC/Starting Redeemable values now render in muted
    gray text until manually edited; manual input restores normal field styling.
  - Start/Edit/Edit Closed dialogs now auto-populate Starting Redeemable from
    expected balances when User/Site context resolves and no manual override exists.
  - Manual entry (including zero) disables auto-refresh on User/Site changes.
  - Clearing the field returns it to auto mode for subsequent User/Site changes.

  Tests:
  - Added UI regression coverage for checkbox text/label cleanup.
  - Added UI regression coverage for two-line Balance Check display.
  - Added UI regression coverage for Starting Redeemable auto-fill/manual override/clear-to-repopulate behavior.

  Validation:
  - pytest -q tests/ui/test_end_session_auto_redeemable.py
  - pytest -q
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/ui/test_end_session_auto_redeemable.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-03-10-02
type: feature
areas: [ui, models, repositories, services, tests, docs]
issue: 160
summary: "Add site playthrough requirement + session auto-calculate redeemable toggle"
details: >
  Added a site-level `playthrough_requirement` setting and wired it into
  End Session and Edit Closed Session workflows via a new
  `Auto-Calculate End Redeemable SC` toggle.

  Site changes:
  - Added `playthrough_requirement` to Site model with positive-value validation.
  - Extended sites schema and migration path (`_migrate_sites_table`) with
    default `1.0` for existing/new records.
  - Updated site repository/service/facade and Setup → Sites UI (table, add/edit,
    and view dialogs) to persist/display the field.

  Session dialog changes:
  - Added `Auto-Calculate End Redeemable SC` toggle to End Session and
    Edit Closed Session dialogs.
  - Default state is OFF to preserve prior manual behavior.
  - When ON, Ending Redeemable is locked and auto-calculated in real time from:
      Start SC, Start Redeemable, Wager, End SC, and site playthrough requirement.
  - Auto mode now requires Wager input; manual mode keeps Wager optional.
  - Auto mode now applies net losses against provisional redeemable so losing
    sessions do not overstate ending redeemable.
  - When OFF, Ending Redeemable remains manually editable/validated.

  Tests:
  - Added UI regression test for auto-calc lock/unlock + live update behavior.
  - Extended site model/repository/service tests for new field semantics.
  - Extended schema alignment tests for fresh schema + migration path.

  Validation:
  - pytest -q tests/unit/test_site_model.py tests/unit/test_site_repository.py
    tests/unit/test_site_service.py tests/integration/test_schema_alignment.py
    tests/ui/test_end_session_auto_redeemable.py
  - pytest -q tests/integration/test_switch_game_flow.py tests/ui/test_end_session_auto_redeemable.py
  - pytest -q
files_changed:
  - models/site.py
  - repositories/database.py
  - repositories/site_repository.py
  - services/site_service.py
  - app_facade.py
  - ui/tabs/sites_tab.py
  - ui/tabs/game_sessions_tab.py
  - tests/unit/test_site_model.py
  - tests/unit/test_site_repository.py
  - tests/unit/test_site_service.py
  - tests/integration/test_schema_alignment.py
  - tests/ui/test_end_session_auto_redeemable.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

---

## 2026-03-10

```yaml
id: 2026-03-10-01
type: fix
areas: [services, tests, docs]
issue: 158
summary: "Fix scoped FIFO rebuild to consume close-marker basis (parity with full rebuild)"
details: >
  Fixed a path-dependent accounting bug in RecalculationService where scoped
  FIFO rebuild (`rebuild_fifo_for_pair_from`) handled close-marker redemptions
  (`amount=0` + parsable `Net Loss`) differently from full rebuild.

  Root cause:
  - Full rebuild path had Issue #156 close-marker allocation logic.
  - Scoped rebuild path still used legacy realized-only handling for close
    markers, writing realized loss rows without consuming basis or writing
    redemption_allocations.

  User-visible symptom:
  - Remaining basis was overstated after close markers when scoped rebuild was
    triggered by normal edit flows, causing Unrealized P/L to be materially wrong.

  Fix behavior:
  - Scoped rebuild now mirrors full rebuild for close markers:
    - consume FIFO basis up to parsed close-loss amount,
    - cap at available basis at/before close timestamp,
    - write `redemption_allocations`,
    - update `purchases.remaining_amount`,
    - keep realized synchronized (`net_pl = payout - consumed_basis`).

  Regression coverage:
  - Added scoped-path tests in tests/unit/test_recalculation_service.py:
    - close-marker basis consumption + allocation writes
    - timestamp boundary guard (no future purchase allocation)

  Validation:
  - pytest -q tests/unit/test_recalculation_service.py -k scoped_rebuild_close_marker
  - pytest -q tests/unit/test_recalculation_service.py
  - pytest -q tests/integration/test_recalculation_integration.py
  - pytest -q  (1 unrelated pre-existing failure in tests/ui/test_expenses_autocomplete.py)
files_changed:
  - services/recalculation_service.py
  - tests/unit/test_recalculation_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

---

## 2026-03-09

```yaml
id: 2026-03-09-02
type: fix
areas: [services, tests, docs]
issue: ~
summary: "Fix startup maintenance false-positive when purchase amounts are stored as TEXT"
details: >
  DataIntegrityService previously checked invalid purchase remaining amounts
  using `remaining_amount > amount` without numeric casting. Because SQLite can
  store monetary values as TEXT, lexical comparison could incorrectly flag valid
  rows (example: '8.51' > '149.97'). This triggered maintenance-mode prompts on
  startup even when the data was numerically valid.

  Changes:
  - Updated purchase remaining checks in services/data_integrity_service.py to
    use numeric comparison: CAST(remaining_amount AS REAL) > CAST(amount AS REAL)
  - Updated the auto-fix query in the same service to use the same numeric CAST
    predicate.
  - Added regression tests in tests/unit/test_data_integrity_service.py for:
    - valid text-stored values that must NOT violate
    - true numeric violations that must still be detected

  Validation:
  - pytest -q tests/unit/test_data_integrity_service.py
  - pytest -q tests/unit/test_validation_service.py
files_changed:
  - services/data_integrity_service.py
  - tests/unit/test_data_integrity_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

---

## 2026-03-09

```yaml
id: 2026-03-09-01
type: fix
areas: [services, tests, docs]
issue: 156
summary: "Fix Balance Closed FIFO rebuild to consume basis and prevent realized/unrealized double-counting"
details: >
  Fixed a data-correctness bug in RecalculationService FIFO rebuild where
  close-marker redemptions (`amount=0` with parsable `Net Loss: $X.XX` notes)
  recreated realized loss rows but skipped FIFO allocations and purchase basis
  consumption.

  Root cause:
  - services/recalculation_service.py had a special close-marker branch that
    wrote `realized_transactions` and `continue`d before allocation logic.

  Fix behavior:
  - Close-marker rebuild now performs timestamp-bounded FIFO consumption from
    purchases at or before the close timestamp.
  - Writes corresponding `redemption_allocations` rows for real purchase IDs.
  - Updates `purchases.remaining_amount` so pre-close lots cannot reappear as
    unrealized basis after reopen.
  - Synchronizes realized values to consumed basis:
      `cost_basis=consumed_basis`, `payout=0`, `net_pl=-consumed_basis`.
  - Caps consumed basis at available pre-close basis when parsed note loss is
    larger than available lots.

  Regression coverage (tests/unit/test_recalculation_service.py):
  - Added close-marker happy-path test asserting allocations + remaining basis
    updates + realized synchronization.
  - Added timestamp-boundary test ensuring no allocation from future purchases.
  - Updated existing zero-payout Net Loss test to assert basis consumption.

  Validation:
  - pytest -q tests/unit/test_recalculation_service.py
  - pytest -q tests/integration/test_recalculation_integration.py
  - pytest -q
  All passed at implementation time.
files_changed:
  - services/recalculation_service.py
  - tests/unit/test_recalculation_service.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

---

## 2026-03-05

```yaml
id: 2026-03-05-01
type: feature
areas: [ui, services, app_facade, tests]
issue: 154
summary: "View Game dialog: add user/date filters and filtered Actual RTP + Total Wager"
details: >
  Setup -> Games -> View Game now supports scoped stat analysis for the selected
  game via user and date filters.

  UI changes (ui/tabs/games_tab.py):
  - Added an editable User filter combo with Add Purchase-style inline autocomplete.
    Default behavior is All Users via placeholder text.
  - Added compact Date Filter controls on one line under the User filter:
    From + calendar, To + calendar, quick-range combo (Today, Last 30,
    This Month, This Year, All Time), and Clear.
  - Clear now resets all filters (user + date), restoring User=All Users
    behavior and Date=All Time.
  - Increased View Game dialog minimum size to accommodate the new controls.
  - Added "Total Wager" line item under Actual RTP.

  Stat semantics:
  - RTP (%) in View Game remains the configured game RTP (setup value).
  - Actual RTP now recalculates against the active filters:
      ((total_wager + total_delta) / total_wager) * 100, else 0.0 when wager is 0.
  - Total Wager sums wager_amount for filtered sessions; null/missing wager values
    are treated as 0.

  Service + facade:
  - Added GameSessionService.get_game_filtered_stats(game_id, user_id, start_date, end_date)
    returning session_count, total_wager, total_delta, actual_rtp, and average rtp.
  - Added AppFacade.get_game_filtered_stats(...) passthrough for UI-layer access.

  Tests:
  - Added service tests for happy path + user/date filtering + missing wager edge
    handling + failure injection in tests/unit/test_game_session_service.py.
  - Added headless UI coverage in tests/ui/test_view_game_dialog_filters.py for:
    - View Game filter controls presence/defaults
    - MainWindow startup smoke (QApplication + MainWindow instantiation)

  Validation executed during implementation:
  - Targeted tests: pytest -q tests/unit/test_game_session_service.py tests/ui/test_view_game_dialog_filters.py
    -> passed.
  - Full suite: pytest -q
    -> one unrelated pre-existing failure observed in tests/ui/test_expenses_autocomplete.py
       (autocomplete assertion), while issue-154 tests passed.
files_changed:
  - ui/tabs/games_tab.py
  - services/game_session_service.py
  - app_facade.py
  - tests/unit/test_game_session_service.py
  - tests/ui/test_view_game_dialog_filters.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

---

## 2026-02-25

```yaml
id: 2026-02-25-03
type: improvement
areas: [ui]
issue: ~
summary: "Polish 'Purchases in Basis Period' table in View Purchase → Related tab"
details: >
  Three improvements to the basis-period purchases section shown in the Related
  tab of the View Purchase dialog (ui/tabs/purchases_tab.py).

  1. Grayed-out consumed rows: Any purchase whose remaining_amount == 0 (fully
  consumed by FIFO redemption allocations) and is not the current purchase is
  now rendered in gray text. Active/partial purchases and the current purchase
  display normally. Current purchase remains bold as before.

  2. Remaining Basis column: A new "Remaining Basis" column was added (position
  5, before View Purchase) showing $X.XX for purchases with remaining basis or
  an em-dash for fully consumed ones.

  3. Plain-English header: The group box title was rewritten from the confusing
  "Basis Period (Checkpoint Window) — Purchases ((no prior checkpoint) → (no
  next checkpoint))" to human-readable labels such as:
    - "Purchases in Basis Period — since 2026-02-20 14:31 (period still open)"
    - "Purchases in Basis Period — since 2026-02-20 14:31 → until 2026-02-25 09:00"
    - "Purchases in Basis Period — all history → until 2026-02-25 09:00"
    - "Purchases in Basis Period — no full redemptions on record"
  The header now uses the full-redemption window (nearest prev/next
  more_remaining=0 redemption) as primary boundaries, falling back to balance
  checkpoint effective dates when no full redemptions exist.
  The (no prior checkpoint) and (no next checkpoint) fallback text was removed
  entirely — when no boundary exists the label describes the situation in plain
  language rather than showing internal field names.
```

---

```yaml
id: 2026-02-25-02
type: fix
areas: [services, app_facade]
issue: 152
summary: "Fix scoped link rebuild timezone mixing — BEFORE purchase links silently dropped"
details: >
  Bug A (app_facade.py — _rebuild_or_mark_stale): The boundary returned by
  _containing_boundary was in local time, but rebuild_links_for_pair_from
  compared it against UTC-stored session end_time/session_time/purchase_time
  columns via direct string comparison. For America/New_York (UTC-5), a
  local boundary of e.g. 07:16:23 would be compared against UTC end_time
  12:15:45 — numerically 07:16:23 < 12:15:45 — so the just-closed session was
  incorrectly pulled into the suffix window. The scoped rebuild then DELETEd
  the BEFORE purchase link that was correctly created by the session-close
  rebuild, without re-inserting it. FIX: convert boundary to UTC via
  local_date_time_to_utc before passing to rebuild_fifo_for_pair_from and
  rebuild_links_for_pair_from inside _rebuild_or_mark_stale.

  Bug B (app_facade.py — get_linked_events_for_session): The early-return
  guard used `if events.get("purchases") or events.get("redemptions")`, which
  returned immediately when a lone AFTER redemption link existed — preventing
  the self-healing full rebuild from running even when purchase BEFORE links
  were missing. FIX: changed to `if events.get("purchases")` so the heal only
  short-circuits when purchase links are already present.

  Bug C (_containing_boundary gap): When a new event lands in the AFTER gap
  of the most-recently-closed session (no containing session found), the
  boundary was set to the raw event time. This caused the just-ended session
  to fall out of the suffix window (its UTC end_time < UTC boundary). FIX:
  extended _containing_boundary to walk back to the closest prior closed
  session's start when no containing session is found, so the session's
  AFTER gap events get a correct boundary.

  Data impact: Session 274 (user_id=2, site_id=31, Stake) had purchase #453
  (BEFORE, 19s before session start) silently absent. Run "Rebuild All" from
  Tools after deploying this fix to restore the missing link in the live DB.
```

---

```yaml
id: 2026-02-25-01
type: fix
areas: [ui]
issue: ~
summary: "Fix black text in View Game Session Balances/Outcomes table"
details: >
  All data cells in the Balances/Outcomes grid had hardcoded color: black,
  making them unreadable on dark backgrounds. Removed explicit color: black
  from all Start/End/Basis cell stylesheets so they inherit the theme text
  color. Changed the 'black' fallback in delta_color, delta_redeem_color, and
  net_color (shown for null/dash values) to 'inherit'. Also softened the cell
  border from rgba(0,0,0,0.2) to rgba(128,128,128,0.3) so it is visible on
  both light and dark themes.
```

---

## 2026-02-23

```yaml
id: 2026-02-23-01
type: cleanup
areas: [ui, notifications]
issue: ~
summary: "Remove user-facing Dismiss button from Notification Center"
details: >
  The Dismiss button in NotificationItemWidget was non-functional: calling
  notification_service.dismiss() sets dismissed_at, but create_or_update()
  immediately resets dismissed_at to None on the next rule evaluation, so
  the notification reappeared instantly. The button provided no lasting effect.
  Removed: Dismiss button, dismissed Signal on NotificationItemWidget,
  item_widget.dismissed.connect() wiring, _dismiss_notification() handler.
  System-side dismiss() and dismiss_by_type() remain (used by notification
  rules to auto-clear resolved conditions such as backup completed or
  redemption received). Spec updated: §6.6 per-item actions and service
  user-actions list updated to remove Dismiss; system-only note added.
```

---

## 2026-02-21

```yaml
id: 2026-02-21-01
type: feature
areas: [ui, redemptions, services, accounting]
issue: 148
summary: "Redemption Cancel / Uncancel"
details: >
  Implements full cancel/uncancel lifecycle for PENDING redemptions.

  Schema: Added `status` (PENDING|CANCELED|PENDING_CANCEL), `canceled_at` (UTC),
  and `cancel_reason` columns to the `redemptions` table via migration.

  Accounting:
  - Cancel: deletes FIFO allocations and triggers rebuild_or_mark_stale.
    If an Active session exists for the same (user, site) pair, sets
    PENDING_CANCEL (deferred) instead of CANCELED immediately.
  - process_pending_cancels fires when a session transitions Active → Closed
    (moved outside the recalculate_pl guard so it fires even with
    recalculate_pl=False).
  - Uncancel: re-applies FIFO and triggers rebuild.
  - Two-event delta model in compute_expected_balances: CANCELED redemption
    contributes a debit at redemption_date and a credit at canceled_at.
  - RecalculationService excludes CANCELED/PENDING_CANCEL rows from all rebuild
    FIFO queries (WHERE COALESCE(status,'PENDING') NOT IN ('CANCELED','PENDING_CANCEL')).
  - NotificationRulesService.evaluate_redemption_pending_rules already filtered
    by status='PENDING'; added settings=None guard for test/API usage.
  - bulk_update_redemption_metadata skips CANCELED rows.

  UI:
  - Redemptions tab: Cancel toolbar button (single PENDING selection),
    Uncancel toolbar button (single CANCELED selection).
  - Cancel dialog: active-session deferred warning + reason input.
  - Table rendering: CANCELED rows gray (#95a5a6), PENDING_CANCEL rows purple (#8e44ad).
  - Pending quick filter excludes CANCELED and PENDING_CANCEL rows.

  Tests: 15 integration tests (test_redemption_cancel_uncancel.py,
  test_compute_expected_balances_cancel.py) covering H1-H4, E1-E6, F1, B1-B4.
  940 total tests pass (1 skipped, 0 failures).
```

---



```yaml
id: 2026-02-18-02
type: feature
areas: [ui, redemptions, services]
issue: 141
summary: "Bulk Mark Received / Mark Processed actions for Redemptions"
details: >
  Redemptions tab now shows two context-sensitive toolbar buttons (Mark Received,
  Mark Processed) whenever one or more rows are selected. Mark Received opens a
  themed dialog with a date-picker, Today shortcut, and Cancel/Clear/Save options
  so the user can stamp or clear receipt_date on all selected redemptions at once.
  Mark Processed sets the processed flag to True on all selected rows in a single
  transaction. A new AppFacade method (bulk_update_redemption_metadata) performs
  a direct SQL UPDATE with an IN clause, skipping all FIFO/session recalculation
  and link-rebuild work. Pending-receipt notification dismissal is preserved:
  on_redemption_received() is still called per ID when receipt_date is set.
  Undo/redo supported: one audit UPDATE entry per row shares a group_id, and one
  UndoRedoService.push_operation is pushed so Ctrl+Z reverts all rows atomically.
  After save the table selection is cleared and buttons are hidden immediately.
  15 integration tests cover happy-path, field isolation, edge cases (empty list
  no-op), failure injection (no rebuild called), notification behavior, undo stack
  presence, and full undo revert for both receipt_date and processed.
files_changed:
  - app_facade.py
  - ui/tabs/redemptions_tab.py
  - tests/integration/test_issue_141_bulk_metadata.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
pr: 142
```

```yaml
id: 2026-02-18-01
type: enhancement
areas: [ui, expenses]
issue: 139
summary: "Add autocomplete suggestions for Expense Vendor and Notes fields"
details: >
  Expense Add/Edit dialogs now provide case-insensitive autocomplete for Vendor and
  Notes based on distinct existing expense values, with inline real-time prediction
  and Tab-to-accept behavior to match existing editable-field completion patterns.
  Accepted completions preserve canonical casing from suggestions and users can
  continue normal editing (including Backspace/Delete) after a prediction appears.
  This remains UX-only help (no new validation rules; free text still allowed).
files_changed:
  - ui/tabs/expenses_tab.py
  - tests/ui/test_expenses_autocomplete.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
pr: 140
```

## 2026-02-17

```yaml
id: 2026-02-17-10
type: docs
areas: [docs]
summary: "Add Web Porting Contract to PROJECT_SPEC"
details: >
  Added a doctrinal portability section describing which invariants must remain true for a
  faithful recreation or web port (accounting semantics, derived rebuildability, atomicity,
  timezone/timestamp handling, audit/undo, and layering boundaries).
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
pr: 138
```

```yaml
id: 2026-02-17-09
type: docs
areas: [docs]
summary: "Doc sweep: inline dialog UX standards and post-import recalculation prompt; clarify SQLite-only dependencies"
details: >
  Consolidated requirements-bearing content from archived design docs into PROJECT_SPEC.md,
  including dialog UI conventions and the post-import recalculation prompt behavior.
  Also inlined the QTableView migration rejection rationale into the Spreadsheet UX section so the spec remains self-contained.
  Marked the historical “critical session P/L” incident writeup as resolved to avoid stale warnings.
  Also clarified that older archived PostgreSQL/ORM/pydantic dependency plans are deprecated;
  the current product is SQLite-only and governed by requirements.txt.
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/incidents/CRITICAL_P&L_ISSUE.md
  - docs/status/CHANGELOG.md
pr: 138
```

```yaml
id: 2026-02-17-08
type: docs
areas: [docs]
summary: "Clarify reconstruction contract and remove external doc dependency from PROJECT_SPEC"
details: >
  PROJECT_SPEC.md now explicitly treats repo file-path references as informational only and
  inlines ADR-0002 justification instead of linking to docs/adr, keeping the spec self-contained.
files_changed:
  - docs/PROJECT_SPEC.md
pr: 138
```


```yaml
id: 2026-02-17-07
type: fix
areas: [database, schema, tests]
issue: 136
summary: "Schema/spec alignment — add missing canonical columns to fresh DB schema and Appendix A"
details: >
  Three tables were missing columns in the CREATE TABLE statements (fresh DB path), causing
  divergence between upgraded real databases and freshly-created databases.
  - daily_sessions: added `notes TEXT` to CREATE TABLE; updated _migrate_daily_sessions_table
    to ALTER TABLE existing DBs.
  - game_sessions: added `tax_withholding_rate_pct REAL`, `tax_withholding_is_custom INTEGER DEFAULT 0`,
    `tax_withholding_amount REAL` to CREATE TABLE and to the ALTER TABLE migrations list.
  - expenses migration rebuild: fixed `expenses_new` CREATE TABLE and INSERT…SELECT to preserve
    `expense_entry_time_zone` (data-loss bug when DEFAULT constraint migration ran).
  Appendix A DDL in PROJECT_SPEC.md updated to match corrected fresh schema.
  11 integration tests added covering happy path, edge cases, and failure injection.
files_changed:
  - repositories/database.py
  - docs/PROJECT_SPEC.md
  - tests/integration/test_schema_alignment.py
pr: 138
```


```yaml
id: 2026-02-17-06
type: docs
areas: [docs, repo, tools]
summary: "Make PROJECT_SPEC + CHANGELOG the canonical docs; embed authoritative schema DDL"
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/archive/2026-02-17-docs-root-cleanup/sezzions_schema.sql
  - docs/archive/2026-02-17-docs-root-cleanup/GETTING_STARTED.md
  - docs/archive/2026-02-17-docs-root-cleanup/INDEX.md
  - docs/archive/2026-02-17-docs-root-cleanup/STATUS.md
  - docs/archive/2026-02-17-docs-root-cleanup/TODO.md
  - docs/archive/2026-02-17-docs-root-cleanup/0001-docs-governance.md
  - docs/archive/2026-02-17-docs-root-cleanup/TOOLS_DATABASE_PHASE_3_STATUS.md
  - docs/archive/2026-02-17-docs-root-cleanup/TOOLS_RECALCULATION_PHASE_4_STATUS.md
  - README.md
  - .github/copilot-instructions.md
  - AGENTS.md
  - tools/validate_schema.py
issue: null
pr: null
```

**Docs: consolidate to spec + changelog (self-contained)**

- Embedded the authoritative SQLite schema DDL (generated from the live schema builder) into `docs/PROJECT_SPEC.md` as Appendix A, so the spec is self-contained.
- Archived redundant/rolling docs (Getting Started, docs index, status, TODO mirror, docs governance ADR, and Tools phase snapshots) into `docs/archive/2026-02-17-docs-root-cleanup/`.
- Updated repo entrypoints (`README.md`, `AGENTS.md`, and `.github/copilot-instructions.md`) to point at `docs/PROJECT_SPEC.md` + `docs/status/CHANGELOG.md` as the canonical sources of truth.
- Updated `tools/validate_schema.py` to validate against the Appendix A DDL instead of a hard-coded table list.

---

```yaml
id: 2026-02-17-05
type: docs
areas: [docs]
summary: "Remove deprecated HTML operator guide"
files_changed:
  - docs/INDEX.md
  - docs/Readme/
issue: null
pr: null
```

**Docs: remove legacy operator guide**

- Removed `docs/Readme/` (HTML operator guide) per current docs cleanup direction.
- Updated `docs/INDEX.md` to stop linking to the removed guide.

---

```yaml
id: 2026-02-17-04
type: docs
areas: [docs, repo]
summary: "Remove obsolete root artifacts and refresh Getting Started"
files_changed:
  - GETTING_STARTED.md
  - demo.py
  - demo.db
  - =4.2.0
  - data.db
issue: null
pr: null
```

**Docs/Repo: root cleanup + current onboarding**

- Updated `GETTING_STARTED.md` to reflect current usage (`python3 sezzions.py`, `SEZZIONS_DB_PATH`, tests) and removed the old Phase-1 demo/phase tracking.
- Removed obsolete root artifacts (`demo.py`, `demo.db`, and a stray `=4.2.0` pip log) that are not part of the current app.
- Deleted `data.db` from repo root (obsolete local artifact).

---

```yaml
id: 2026-02-17-03
type: docs
areas: [docs]
summary: "Archive obsolete root docs and normalize TODO filename"
files_changed:
  - docs/TODO.md
  - docs/archive/2026-02-17-docs-root-cleanup/DATABASE_DESIGN.md
  - docs/BULK_TOOLS_REPOSITORY_COMPLETE.md
  - docs/DATABASE_IMPLEMENTATION_CHECKLIST.md
  - docs/DEPENDENCIES.md
  - docs/GAME_SESSION_IMPLEMENTATION_SUMMARY.md
  - docs/GAME_SESSION_PL_FIX_CHANGELOG.md
  - docs/PHASE4_SESSION_SUMMARY.md
  - docs/TESTING_STRATEGY.md
issue: null
pr: null
```

**Docs: archive + prune old top-level markdown**

- Removed several obsolete top-level `docs/*.md` writeups that reference the old `sezzions/` package layout and already have archived copies.
- Moved `docs/DATABASE_DESIGN.md` into the archive (`docs/archive/2026-02-17-docs-root-cleanup/`) to reduce top-level clutter and avoid stale guidance.
- Normalized `docs/TODO.md` filename casing to match the canonical link in `docs/INDEX.md`.

---

```yaml
id: 2026-02-17-02
type: enhancement
areas: [notifications, backup, ui]
summary: "Add automatic backup enablement reminder notification"
files_changed:
  - services/notification_rules_service.py
  - ui/notification_widgets.py
issue: 134
pr: null
```

**Enhancement: Automatic backup enablement reminder**

- **Problem**: Users may not realize they should enable automatic backups, especially on first use or after settings reset. The existing `backup_directory_missing` notification only appears when automatic backups are already enabled but directory is missing.
- **Solution**: Added new `backup_not_enabled` notification that appears for all users when automatic backups are disabled.
- **Behavior**:
  - Fires when automatic backups are disabled (`automatic_backup.enabled = False`)
  - Severity: INFO (gentle reminder, not urgent)
  - Action: Opens Tools → Database Tools
  - Cooldown: 7 days when user deletes or marks as read
  - Resurfaces indefinitely until automatic backups are enabled
- **Distinction**: INFO notification when auto-backup disabled vs WARNING `backup_directory_missing` which fires when auto-backup is enabled but directory is missing
- **User control**: Delete, dismiss, snooze, or mark read all apply 7-day cooldown before resurfacing
- **Auto-dismissal**: Notification auto-dismisses when user enables automatic backups

---

```yaml
id: 2026-02-17-01
type: bugfix
areas: [ui, game-sessions]
summary: "Fix multi-day session indicator to show actual day span"
files_changed:
  - ui/tabs/game_sessions_tab.py
issue: 132
pr: 133
```

**Bugfix: Multi-day session indicator now shows actual day span**

- **Problem**: Game Sessions tab displayed `(+1d)` for all multi-day sessions regardless of actual duration. A 3-day session (Feb 1 → Feb 4) incorrectly showed `(+1d)` instead of `(+3d)`.
- **Root cause**: Code only checked if `end_date != session_date` (boolean), not the actual day difference.
- **Fix**: Calculate day difference using `(end_date - session_date).days` and display the correct value (e.g., `+2d`, `+3d`). Handle both date objects and strings to avoid strptime errors.
- **Critical fix**: Initial implementation caused crash on launch ("strptime() argument 1 must be str, not datetime.date") because session dates are date objects, not strings. Fixed by checking instance type before parsing.
- **Scope**: Only affects Game Sessions tab. Daily Sessions and Realized tabs already display full date ranges and don't use day indicators.
- **Testing**: All 897 tests passing.

---

## 2026-02-16

```yaml
id: 2026-02-16-06
type: bugfix
areas: [data-model, accounting, unrealized, purchases]
summary: "Fix purchase checkpoints to preserve redeemable balance"
files_changed:
  - models/purchase.py
  - repositories/database.py
  - repositories/purchase_repository.py
  - services/purchase_service.py
  - app_facade.py
  - tools/backfill_purchase_redeemable.py
  - tests/integration/test_issue_130_purchase_redeemable_checkpoint.py
issue: 130
pr: null
```

**Bugfix: Purchase checkpoints now preserve redeemable balance**

- **Problem**: When making a purchase after playing sessions, the Unrealized tab showed redeemable balance reset to $0.00 instead of preserving the redeemable earned from play.
- **Root cause**: Purchase checkpoint snapshots (`starting_sc_balance`) tracked total SC but not redeemable SC. The `unrealized_position_repository` hardcoded `redeemable_sc = 0` for purchase checkpoints.
- **Fix**: Added `starting_redeemable_balance` field to purchases table (with migration), auto-populated at purchase creation time using `compute_expected_balances()` to capture the redeemable balance at that moment. Purchase checkpoints now use this stored value instead of hardcoded 0.
- **Semantics clarification**: `starting_sc_balance` is the POST-purchase SC balance (the balance after the purchase completes, including dailies/bonuses). Similarly, `starting_redeemable_balance` is the redeemable balance at that same point in time. Purchases don't generate redeemable SC, so this preserves the pre-purchase redeemable value.
- **Backfill tool**: `tools/backfill_purchase_redeemable.py` migrates existing data (with `--dry-run` support).
- **Testing**: 5 new integration tests covering purchase-after-session, redemptions between purchases, first purchase (baseline), multiple sequential purchases, and balance checkpoint priority scenarios.
- **Result**: Unrealized positions now correctly show redeemable balance when purchases occur after play sessions, instead of incorrectly resetting to $0.

---

```yaml
id: 2026-02-16-05
type: enhancement
areas: [ui, timezone, travel-mode, sessions, purchases, redemptions, expenses, adjustments]
summary: "Complete travel mode badge implementation with fixes"
files_changed:
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/expenses_tab.py
  - ui/adjustment_dialogs.py
  - tests/integration/test_travel_mode_badges_comprehensive.py
issue: 128
pr: 129
```

**Enhancement: Complete Travel Mode Badge Implementation**

- **Comprehensive badge coverage**: Added 🌐 globe badges + tooltips to all locations where dates/times are displayed when entry timezone differs from accounting timezone.
- **Session dialogs**: ViewSessionDialog (start/end badges), EditClosedSessionDialog (inline badges), StartSessionDialog, EndSessionDialog.
- **Transaction view dialogs**: PurchaseViewDialog, RedemptionViewDialog, ExpenseViewDialog.
- **Edit dialogs**: Added badges to PurchaseDialog, RedemptionDialog, ExpenseDialog (after NOW button).
- **Adjustment dialogs**: Added badges to BasisAdjustmentDialog and CheckpointDialog (after NOW button).
- **Linked event tables**: Session-linked purchases/redemptions tables, purchase/redemption-linked sessions tables.
- **Main tables**: Game Sessions (date/time column), Purchases, Redemptions, Expenses.
- **Session table optimization**: Consolidated globe display to date/time column only (removed from End SC column); shows badge if either start OR end time was entered in travel mode; enhanced tooltip shows which timezone(s) differ.
- **Bugfix: Edit session timezone validation**: Fixed logic to ask about timezone update BEFORE calculating UTC times for validation, preventing false "end time earlier than start time" errors when updating timezone from travel mode to current timezone.
- **Testing**: 7 comprehensive integration tests covering all badge display locations; all 892 tests passing.

---

```yaml
id: 2026-02-16-04
type: bugfix
areas: [services, timestamp, timezone]
summary: "Fix timestamp uniqueness to use entry timezone instead of accounting timezone"
files_changed:
  - services/timestamp_service.py
  - tests/unit/test_timestamp_service.py
pr: 127
```

**Bugfix: Timestamp Uniqueness Timezone Mismatch**

- **Problem**: `TimestampService` was using accounting timezone for UTC conversion when checking for conflicts, but all repositories use entry timezone when storing. This mismatch caused the uniqueness check to happen in the wrong timezone, allowing duplicate timestamps when entry and accounting timezones differed (e.g., in travel mode).
- **Example failure**: User in EST (entry TZ) with PST (accounting TZ) could create purchase at 23:30 EST and session at 23:30 EST because service checked for conflicts using PST conversion (wrong UTC time).
- **Fix**: Changed `TimestampService.ensure_unique_timestamp()` to use `get_entry_timezone_name()` instead of `get_configured_timezone_name()`, ensuring conflict checks use the same timezone as storage.
- **Impact**: Critical fix for cross-event timestamp uniqueness feature; prevents duplicate timestamps that could break event linking and data integrity.

---

```yaml
id: 2026-02-16-03
type: enhancement
areas: [ui, purchases, redemptions, sessions]
summary: "Add persistent quick filter toggles on primary tabs"
files_changed:
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_issue_121_quick_filters.py
  - docs/PROJECT_SPEC.md
```

**Enhancement: Quick Filters on Purchases / Redemptions / Sessions**

- Added persistent quick toggles near Export buttons:
  - Purchases: `Basis Remaining`
  - Redemptions: `Pending`, `Unprocessed`
  - Game Sessions: `Active Only`
- Toggled states now persist across app restarts and are cleared by existing per-tab “Clear All Filters” actions.

---

```yaml
id: 2026-02-16-01
type: bugfix
areas: [ui, redemptions, balances]
summary: "Treat 'full cashout' as total balance (not redeemable)"
files_changed:
  - ui/tabs/redemptions_tab.py
  - tests/unit/test_redemption_confirmation_classification.py
```

**Bugfix: Partial Redemptions vs Redeemable-Only Balance**

- The full/partial confirmation prompt now compares against expected TOTAL balance, so redeeming all currently redeemable can still be treated as a Partial redemption when additional non-redeemable balance remains.

---

```yaml
id: 2026-02-16-02
type: bugfix
areas: [sessions, ui, redemptions]
summary: "Ignore soft-deleted redemptions in session delete impact"
files_changed:
  - services/game_session_service.py
  - tests/unit/test_game_session_deletion_impact.py
```

**Bugfix: Session Delete Impact vs Soft-Deleted Redemptions**

- The session deletion impact warning now ignores soft-deleted redemptions, so deleting a redemption won’t keep triggering “future redemption(s) after this session” warnings.

---

## 2026-02-15

```yaml
id: 2026-02-15-13
type: bugfix
areas: [redemptions, sessions, balances]
summary: "Do not boost redeemable from purchases"
files_changed:
  - services/game_session_service.py
  - tests/integration/test_expected_redeemable_not_from_purchases.py
```

**Bugfix: Redeemable Balance Expectations**

- Purchases no longer increase expected redeemable balances; redeemable is anchored to sessions/checkpoints.

---

```yaml
id: 2026-02-15-12
type: bugfix
areas: [redemptions, realized, fifo]
summary: "Exclude deleted redemptions from realized rebuilds"
files_changed:
  - services/recalculation_service.py
  - repositories/realized_transaction_repository.py
  - tests/integration/test_deleted_redemption_excluded_from_realized.py
```

**Bugfix: Deleted Redemptions & Realized Basis**

- Soft-deleted redemptions are now excluded from FIFO rebuilds and realized lists.

---

```yaml
id: 2026-02-15-11
type: bugfix
areas: [ui, expenses]
summary: "Confirm + close on expense delete"
files_changed:
  - ui/tabs/expenses_tab.py
```

**Bugfix: Expense View Delete Flow**

- Deleting from the expense view dialog now closes the dialog and shows a confirmation prompt.

---

```yaml
id: 2026-02-15-10
type: bugfix
areas: [sessions, time]
summary: "Block session end before start in UTC"
files_changed:
  - ui/tabs/game_sessions_tab.py
```

**Bugfix: Session End Validation Across Time Zones**

- Closing a session now blocks saving when the end time is earlier than the start time after UTC conversion.

---

```yaml
id: 2026-02-15-09
type: bugfix
areas: [sessions, purchases, time]
summary: "Expected balances compare UTC instants"
files_changed:
  - services/game_session_service.py
  - app_facade.py
  - tests/integration/test_expected_balance_entry_timezone_ordering.py
```

**Bugfix: Cross-TZ Expected Balance Ordering**

- Expected balance calculations now compare UTC instants so purchases in other entry time zones don’t apply before they occur.

---

```yaml
id: 2026-02-15-08
type: enhancement
areas: [ui, purchases, redemptions, sessions, time]
summary: "Allow entry TZ re-stamp on edit"
files_changed:
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - repositories/game_session_repository.py
  - docs/PROJECT_SPEC.md
```

**Edit Entry Time Zone Prompt**

- Edit/save now prompts to re-stamp entry time zones to the current mode when they differ.

---

```yaml
id: 2026-02-15-07
type: bugfix
areas: [purchases, redemptions, adjustments, time]
summary: "Default missing entry TZ to accounting"
files_changed:
  - repositories/purchase_repository.py
  - repositories/redemption_repository.py
  - repositories/adjustment_repository.py
```

**Bugfix: Stable Entry TZ Fallback**

- Records with missing entry time zones now default to the accounting TZ, preventing travel-mode toggles from retroactively adding globe badges.

---

```yaml
id: 2026-02-15-06
type: bugfix
areas: [time, settings]
summary: "Use active settings for entry time zone"
files_changed:
  - tools/timezone_utils.py
  - ui/main_window.py
```

**Bugfix: Live Travel-Mode Settings**

- Timezone helpers now honor the active settings instance so entry TZ selection reflects the latest travel-mode changes.

---

```yaml
id: 2026-02-15-04
type: enhancement
areas: [ui, purchases, redemptions, sessions, time]
summary: "Show travel-mode badge on entry timestamps"
files_changed:
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/unrealized_tab.py
  - ui/tabs/realized_tab.py
```

**UI: Travel-Mode Timestamp Badge**

- Entries recorded in a non-accounting time zone now show a globe badge with a tooltip indicating the entry TZ.

---

```yaml
id: 2026-02-15-01
type: bugfix
areas: [unrealized, time, repositories]
summary: "Keep Unrealized positions visible after partial redemptions (local date filtering)"
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
  - docs/PROJECT_SPEC.md
```

**Bugfix: Unrealized Partial Redemptions**

- Unrealized positions now convert UTC timestamps to local dates for start/last-activity filtering.
- Prevents positions from disappearing when partial redemptions fall on a different UTC date.
- Fixed a helper method indentation issue that could trigger maintenance mode at startup.

---

```yaml
id: 2026-02-15-02
type: bugfix
areas: [daily-sessions, tax]
summary: "Fix Daily Sessions tax set-aside display"
files_changed:
  - services/daily_sessions_service.py
  - tests/integration/test_daily_sessions_tax_withholding.py
```

**Bugfix: Daily Sessions Tax Set-Aside**

- Daily tax withholding rows now align with session dates so the Tax Set-Aside column renders values.

---

```yaml
id: 2026-02-15-03
type: bugfix
areas: [daily-sessions, tax, time]
summary: "Align tax set-aside rollups to local session dates"
files_changed:
  - services/game_session_service.py
  - services/tax_withholding_service.py
  - tests/unit/test_tax_withholding_service.py
  - docs/PROJECT_SPEC.md
```

**Bugfix: Local-Date Tax Rollups**

- Tax withholding now computes net daily P/L using local end dates so set-aside matches Daily Sessions rollups.
- Deleted sessions no longer affect daily tax rollups.

---

```yaml
id: 2026-02-15-04
type: bugfix
areas: [reports, sessions, time]
summary: "Report filters and session boundaries use local day rules"
files_changed:
  - services/report_service.py
  - repositories/realized_transaction_repository.py
  - tests/unit/test_report_service.py
  - tests/unit/test_realized_transaction_repository.py
  - services/game_session_service.py
  - tests/unit/test_game_session_service.py
  - docs/PROJECT_SPEC.md
```

**Bugfix: Local-Date Report Filtering**

- Tax/realized transaction filters and session P/L reports now convert local date ranges to UTC bounds.
- Prevents late-night sessions/redemptions from being dropped when UTC dates roll over.
- Containing-session recalculation now converts local timestamps to UTC for boundary queries.

---

```yaml
id: 2026-02-15-05
type: bugfix
areas: [ui, realized, time]
summary: "Realized tab groups by local day; view-position dialogs show local times"
files_changed:
  - ui/tabs/realized_tab.py
  - ui/tabs/unrealized_tab.py
  - tests/ui/test_realized_tab_local_timezone.py
```

**Bugfix: Local-Time Realized Grouping & View Dialogs**

- Realized tab now groups and filters transactions by the configured local day using redemption timestamps.
- View Position dialogs (Unrealized/Realized) now display related purchase/session times in local time.

---

```yaml
id: 2026-02-15-06
type: feature
areas: [ui, settings, time]
summary: "Add Time Zones settings and Travel Mode indicator"
files_changed:
  - repositories/database.py
  - repositories/game_session_repository.py
  - repositories/purchase_repository.py
  - repositories/redemption_repository.py
  - services/accounting_time_zone_service.py
  - services/daily_sessions_service.py
  - services/game_session_service.py
  - services/redemption_service.py
  - services/tax_withholding_service.py
  - ui/settings_dialog.py
  - ui/main_window.py
  - tests/integration/test_accounting_timezone_change_rollback.py
  - tests/integration/test_daily_sessions_accounting_timezone.py
  - tests/integration/test_dual_timezone_entry_display.py
  - tests/integration/test_timezone_storage.py
  - tests/ui/test_settings_undo_retention_ui.py
  - tests/unit/test_game_session_service.py
  - tests/unit/test_realized_transaction_repository.py
  - tests/unit/test_report_service.py
  - tests/unit/test_tax_withholding_service.py
  - docs/PROJECT_SPEC.md
```

**Feature: Time Zones Settings + Travel Mode Banner**

- Settings now include a Time Zones section with Accounting TZ, Entry TZ (Travel Mode), and effective-dated change flow.
- Accounting TZ changes prompt for an effective timestamp and recommend backup before rebucketing daily totals.
- Main window shows a Travel Mode banner; new redemptions persist the entry time zone.

---

## 2026-02-14

```yaml
id: 2026-02-14-01
type: bugfix
areas: [ui, services, time]
summary: "Fix redemption edit validation when sessions exist (UTC-aware checks)"
files_changed:
  - services/timestamp_service.py
  - ui/tabs/redemptions_tab.py
  - tests/unit/test_timestamp_service.py
  - tests/integration/test_settings_dialog_smoke.py
```

**Bugfix: Redemption Edit Session Validation**

- Timestamp uniqueness checks now compare against UTC storage and return local-adjusted values.
- Redemption session validation now converts adjusted local timestamps to UTC before querying closed sessions.
- Added unit coverage for timezone-aware timestamp adjustment and extended UI smoke coverage.

---

## 2026-02-13

```yaml
id: 2026-02-13-05
type: feature
areas: [settings, time, repositories, services, ui]
summary: "Add time zone setting with UTC storage + local display"
files_changed:
  - tools/timezone_utils.py
  - ui/settings.py
  - ui/settings_dialog.py
  - ui/main_window.py
  - app_facade.py
  - services/timezone_migration_service.py
  - services/audit_service.py
  - services/daily_sessions_service.py
  - services/notification_rules_service.py
  - repositories/purchase_repository.py
  - repositories/redemption_repository.py
  - repositories/game_session_repository.py
  - repositories/adjustment_repository.py
  - repositories/expense_repository.py
  - ui/audit_log_viewer_dialog.py
  - tests/unit/test_timezone_utils.py
  - tests/integration/test_timezone_storage.py
  - docs/PROJECT_SPEC.md
```

**Feature: Time Zone + UTC Storage**

- Added a Settings time zone selector and persisted `time_zone`/`timezone_storage_migrated`.
- User-entered timestamps now store in UTC with local display conversion across UI/views.
- Audit log filtering/CSV export use local date ranges mapped to UTC bounds.
- One-time migration converts existing local timestamps to UTC using the current time zone.

---

```yaml
id: 2026-02-13-01
type: bugfix
areas: [repositories, accounting]
summary: "Unrealized uses balance checkpoints (account_adjustments) as checkpoint anchors"
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
  - docs/PROJECT_SPEC.md
```

**Bugfix: Unrealized Ignored Balance Checkpoints**

- Unrealized checkpoint selection now considers `account_adjustments` rows of type `BALANCE_CHECKPOINT_CORRECTION`.
- This allows Setup → Tools → “New Balance Checkpoint” to immediately update Unrealized “Total SC (Est.)” / “Redeemable SC (Position)”.
- Added an integration regression test covering the checkpoint override behavior.

---

```yaml
id: 2026-02-13-02
type: bugfix
areas: [ui]
summary: "Fix Unrealized 'View Position' dialog crash"
files_changed:
  - ui/tabs/unrealized_tab.py
  - tests/ui/test_unrealized_position_dialog_smoke.py
```

**Bugfix: Unrealized "View Position" Crash**

- Fixed an `AttributeError` when opening the Unrealized Position details dialog.
- Added a headless UI regression test that instantiates the dialog.

---

```yaml
id: 2026-02-13-03
type: bugfix
areas: [ui]
summary: "Unrealized 'View Position' related tab is scoped to the current position"
files_changed:
  - app_facade.py
  - ui/tabs/unrealized_tab.py
  - tests/unit/test_unrealized_position_dialog_related_data.py
```

**Bugfix: Unrealized Related Tab Filtering**

- Related Purchases/Sessions in the "View Position" dialog now filter to the position's `start_date`.
- Excludes soft-deleted sessions and inactive/deleted purchases.

---

```yaml
id: 2026-02-13-04
type: bugfix
areas: [ui, repositories]
summary: "Unrealized Related tab anchors profit-only positions to latest checkpoint"
files_changed:
  - repositories/unrealized_position_repository.py
  - app_facade.py
  - ui/tabs/unrealized_tab.py
  - tests/unit/test_unrealized_position_dialog_related_data.py
  - docs/PROJECT_SPEC.md
```

**Bugfix: Unrealized Related Tab for Profit-Only Positions**

- When `Remaining Basis = $0.00`, Unrealized positions can still exist (profit-only SC). In this case, using the earliest-ever purchase date as a Related filter is too broad.
- The “View Position” Related tab now anchors to the latest non-adjustment checkpoint (purchase/session) for profit-only positions.
- Session filtering now uses `end_date` when present so sessions spanning midnight still appear when anchored to a checkpoint date.

---

```yaml
id: 2026-02-13-05
type: bugfix
areas: [ui, repositories, accounting]
summary: "Unrealized Related Purchases shows contributing purchases for profit-only positions"
files_changed:
  - repositories/unrealized_position_repository.py
  - app_facade.py
  - ui/tabs/unrealized_tab.py
  - tests/unit/test_unrealized_position_dialog_related_data.py
  - docs/PROJECT_SPEC.md
```

**Bugfix: Unrealized Related Purchases for Profit-Only Positions**

- Renamed the dialog section from “Open Purchases” to “Related Purchases”.
- For profit-only positions (basis = $0), Related Purchases now prefers FIFO-attributed purchases from `redemption_allocations` so the dialog can still explain *which purchases contributed* even when `remaining_amount` is $0.
- Profit-only position `start_date` now prefers a FIFO-allocation-derived start (instead of the earliest-ever purchase) when available.

---

```yaml
id: 2026-02-13-06
type: feature
areas: [ui]
summary: "Unrealized positions surface adjustment/checkpoint presence and deep-link to View Adjustments"
files_changed:
  - app_facade.py
  - repositories/adjustment_repository.py
  - services/adjustment_service.py
  - ui/adjustment_dialogs.py
  - ui/tabs/unrealized_tab.py
```

**Feature: Adjustment/Checkpoint Visibility for Unrealized**

- Unrealized rows now show a small “Adjusted” indicator when that site/user has any active adjustments/checkpoints.
- “View Position” includes a brief “Adjustments & Checkpoints” section in Details and a conditional “Adjustments” tab listing applicable adjustments.
- Each listed adjustment can open Tools → “View Adjustments” pre-filtered and pre-selected to the matching record.

---

```yaml
id: 2026-02-13-07
type: feature
areas: [ui, services, repositories]
summary: "Warn before soft-deleting adjustments with downstream activity; add Adjustments tabs to view dialogs"
files_changed:
  - repositories/adjustment_repository.py
  - services/adjustment_service.py
  - ui/adjustment_dialogs.py
  - ui/tabs/purchases_tab_modern.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/realized_tab.py
  - tests/unit/test_adjustment_service.py
  - tests/ui/test_adjustments_rollout_dialogs_smoke.py
```

**Feature: Safer Adjustment/Checkpoint Deletion + Rollout of Reconciliation UI**

- “View Adjustments” soft-delete now warns when there is later site/user activity (purchases, sessions, redemptions, or later adjustments).
- Purchase / Redemption / Game Session / Realized position view dialogs now show a brief “Adjustments & Checkpoints” section and an “Adjustments” tab when linked adjustments exist.
- Added unit coverage for the downstream warning summary and a headless dialog smoke test for the rollout.

---

```yaml
id: 2026-02-13-08
type: feature
areas: [ui, services, repositories]
summary: "Purchase/Redemption/Session view dialogs show checkpoint-window adjustments/checkpoints"
files_changed:
  - repositories/adjustment_repository.py
  - services/adjustment_service.py
  - ui/tabs/purchases_tab_modern.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - tests/unit/test_adjustment_repository.py
  - tests/unit/test_adjustment_service.py
```

**Feature: Checkpoint-Window Adjustments/Checkpoints in View Dialogs**

- Purchase / Redemption / Game Session view dialogs can show adjustments/checkpoints that fall in the record’s checkpoint window (basis period), not only those explicitly linked.

---

```yaml
id: 2026-02-13-09
type: bugfix
areas: [ui, accounting]
summary: "Fix Purchase basis-period scoping; reduce noisy adjustment sections; add Adjusted badges"
files_changed:
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
```

**Bugfix: Basis-Period Scoping + Adjusted Badges**

- Purchase “Basis Period” related list is now bounded by the next checkpoint (no longer open-ended).
- View dialogs no longer show the Adjustments/Checkpoints section just because a boundary checkpoint exists.
- Purchases / Redemptions / Game Sessions tables now show an “Adjusted” info icon when adjustments/checkpoints exist inside the row’s checkpoint window.

---

```yaml
id: 2026-02-13-10
type: bugfix
areas: [ui]
summary: "Adjustment/checkpoint dialogs resolve typed User/Site selections"
files_changed:
  - ui/adjustment_dialogs.py
  - tests/ui/test_checkpoint_dialog_autocomplete.py
```

**Bugfix: Adjustment/Checkpoint Dialog Autocomplete**

- The “New Balance Checkpoint” and “New Basis Adjustment” dialogs now resolve typed User/Site values to their underlying IDs and validate correctly.
- Autocomplete behavior now mirrors the Add Purchase dialog for editable combo boxes.
- Time inputs now accept HH:MM or HH:MM:SS and store as HH:MM:SS (defaulting seconds to :00).

---

```yaml
id: 2026-02-13-11
type: feature
areas: [services, audit]
summary: "Add audit logging + undo/redo support for adjustments and checkpoints"
files_changed:
  - app_facade.py
  - repositories/adjustment_repository.py
  - services/adjustment_service.py
  - services/undo_redo_service.py
  - tests/unit/test_adjustment_service.py
  - tests/integration/test_adjustment_audit_undo_redo.py
  - docs/PROJECT_SPEC.md
```

**Feature: Audit + Undo/Redo for Adjustments/Checkpoints**

- Basis adjustments and balance checkpoints now emit audit log entries for CREATE/DELETE/RESTORE.
- Adjustment operations now push undo/redo stack entries and participate in undo/redo flows.
- Undo/redo recalculation logic now recognizes `account_adjustments` timestamps.

## 2026-02-10

```yaml
id: 2026-02-10-05
type: feature
areas: [ui]
summary: "Cmd+F/Ctrl+F shortcut focuses search bars across all tabs (Issue #99)"
files_changed:
  - ui/main_window.py
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/daily_sessions_tab.py
  - ui/tabs/unrealized_tab.py
  - ui/tabs/realized_tab.py
  - ui/tabs/expenses_tab.py
  - ui/tabs/users_tab.py
  - ui/tabs/sites_tab.py
  - ui/tabs/cards_tab.py
  - ui/tabs/redemption_method_types_tab.py
  - ui/tabs/redemption_methods_tab.py
  - ui/tabs/game_types_tab.py
  - ui/tabs/games_tab.py
  - tests/ui/test_issue_99_search_shortcut.py
```

**Feature: Global Search Shortcut (Issue #99)**

- Added Cmd+F (macOS) / Ctrl+F (Windows/Linux) keyboard shortcut to focus the search bar on the current tab.
- Works on all main tabs (Purchases, Redemptions, Game Sessions, Daily Sessions, Unrealized, Realized, Expenses).
- Works on all Setup sub-tabs (Users, Sites, Cards, Method Types, Redemption Methods, Game Types, Games).
- Added `QShortcut` with `QKeySequence.Find` in `MainWindow` that routes to the active tab's `focus_search()` method.
- Each tab now implements `focus_search()` which sets focus and selects all text in `search_edit`.
- Setup sub-tabs are correctly unwrapped from their scroll area container before routing.
- Added 7 headless UI tests verifying shortcut registration, method presence, and handler routing.

---

```yaml
id: 2026-02-10-04
type: bugfix
areas: [repositories, ui]
summary: "Unrealized tab excludes soft-deleted activity"
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
```

**Bugfix: Unrealized Tab Showing Deleted Data**

- Unrealized candidate site/user pairs now ignore rows where `deleted_at` is set for purchases, redemptions, and game sessions.
- Added a regression integration test that creates then soft-deletes Funrize activity and asserts no unrealized position is returned.

---

```yaml
id: 2026-02-10-03
type: bugfix
areas: [services]
summary: "Fix undo/redo recalculation for game sessions (Issue #97)"
files_changed:
  - app_facade.py
issue: 97
```

**Bugfix: Undo/Redo Calculated Fields Restoration**

**Problem:**
- After undo/redo on game sessions, calculated fields (delta_total, net_taxable_pl, etc.) would revert to zero
- Session status changes worked correctly, but P/L calculations were not being triggered

**Root Cause:**
- `_handle_undo_redo_recalculation()` callback was attempting to parse `old_data`/`new_data` from audit entries using `json.loads()`
- However, data retrieved from the database was already a dict, not a JSON string
- This caused silent parsing failures, resulting in 0 affected (user_id, site_id) pairs being found
- With no affected pairs, P/L recalculation was never triggered

**Solution:**
- Changed audit entry parsing to handle both JSON strings and dicts:
  ```python
  data = json.loads(data_json) if isinstance(data_json, str) else data_json
  ```
- Now recalculation callback properly identifies affected user/site pairs and triggers P/L recalculation
- Calculated fields are correctly excluded from snapshot restoration (already implemented) AND properly recomputed after undo/redo

**Testing:**
- Manual verification: Start Session → End Session → Undo → Redo
- Calculated fields now properly maintained through entire flow
- All 825 tests passing

---

```yaml
id: 2026-02-10-02
type: cleanup
areas: [ui]
summary: "Remove debug print statements from purchase balance check"
files_changed:
  - ui/tabs/purchases_tab.py
```

**Cleanup: Remove Purchase Balance Debug Output**

Removed debug print statements that were outputting purchase balance check details to console during ADD operations. These were leftover from earlier troubleshooting and are no longer needed.

---

```yaml
id: 2026-02-10-01
type: feature
areas: [services, ui, database]
summary: "Two-tier audit retention with summaries, CSV export, and viewer improvements (Issue #97)"
files_changed:
  - repositories/database.py
  - services/audit_service.py
  - ui/settings_dialog.py
  - ui/audit_log_viewer_dialog.py
  - tests/unit/test_audit_summary.py
  - tests/unit/test_audit_retention.py
  - tests/unit/test_audit_csv_export.py
issue: 97
```

**Feature: Two-Tier Audit Retention + CSV Export + Viewer Enhancements**

**Problem:**
- Full audit snapshots (`old_data`/`new_data`) grow unbounded, consuming storage indefinitely
- Needed balance between long-term audit trail and pragmatic storage limits
- Lacked CSV export for audit compliance workflows
- Audit viewer needed better filtering/sorting for large datasets

**Solution:**
- **Summary Data**: Added `audit_log.summary_data` column (TEXT NULL) to capture compact JSON summaries of critical fields:
  - Purchases: `{amount, user_id, site_id, starting_sc}`
  - Redemptions: `{amount, user_id, site_id}`
  - Game sessions: `{start_datetime, end_datetime, starting_sc, ending_sc, user_id, site_id}`
  - Summaries retained permanently even when full snapshots are pruned
- **Configurable Retention**: `max_audit_log_rows` setting (default: 10,000, 0 = unlimited)
  - Prunes oldest rows atomically when limit exceeded
  - Exposed in Settings → Data → "Audit Log Retention" spinbox
  - Auto-prunes on save when limit changes
- **CSV Export**: `AuditService.export_audit_log_csv(output_path, start_date=None, end_date=None)`
  - Exports all columns including `summary_data`
  - Optional date range filtering (inclusive)
  - Accessible via "📊 Export to CSV" button in Audit Log Viewer
- **Viewer Improvements**:
  - Date range presets: Today, Last 7 Days, Last 30 Days, This Month, This Year, Custom
  - Sortable table columns (click headers to sort by ID, Timestamp, Action, etc.)
  - CSV export button with date filtering

**Implementation:**
- `AuditService.build_summary(table_name, data)`: Static method generating compact summaries (never crashes)
- `AuditService.get/set_max_audit_log_rows()`: Settings persistence
- `AuditService.prune_audit_log()`: Atomic pruning with rollback on failure
- `AuditService.export_audit_log_csv()`: CSV export with csv.DictWriter pattern
- All audit log methods (`log_create`, `log_update`, `log_delete`) now call `build_summary()` and pass result to database
- Settings dialog matches existing undo retention UX pattern

**Testing:**
- 10 tests for summary generation (all tables + edge cases)
- 9 tests for retention settings and pruning (atomicity, unlimited mode, pruning logic)
- 5 tests for CSV export (date filtering, empty results, summary_data inclusion)
- All 825 tests passing (no regressions)

**Rationale:**
- Summaries preserve essential audit trail for long-term compliance
- Pruning prevents unbounded growth while keeping recent full details
- Date presets + CSV export match typical compliance/audit workflows
- Sortable columns improve usability for large datasets

---

## 2026-02-09

```yaml
id: 2026-02-09-02
type: feature
areas: [services]
summary: "Configurable undo/redo depth + audit snapshot retention (Issue #95)"
files_changed:
  - services/undo_redo_service.py
  - tests/unit/test_undo_retention.py
issue: 95
```

**Feature: Configurable Undo/Redo Depth with Audit Snapshot Pruning**

**Implementation:**
- Added `max_undo_operations` setting (default: 100) to limit undo history depth.
- Pruning removes JSON snapshots (`old_data`, `new_data`) from `audit_log` for operations beyond the retention window, but preserves audit metadata (action, table, record_id, timestamp, user, group_id).
- Setting to 0 disables undo/redo and prunes all snapshots.
- Auto-pruning triggers when pushing new operations and exceeding the limit.
- Manual pruning via `set_max_undo_operations(N)` takes effect immediately.
- Pruning is transactional (atomic): if pruning fails, stacks and snapshots roll back to previous state.

**Methods:**
- `get_max_undo_operations()`: Returns current limit.
- `set_max_undo_operations(N)`: Sets limit and prunes immediately if needed.
- `_prune_to_limit(N)`: Internal pruning logic (removes old stack entries + nulls JSON snapshots).

**Testing:**
- 8 new unit tests covering:
  - Stack depth limiting (max=3, perform 5 operations → only last 3 undoable)
  - JSON snapshot pruning (nulls `old_data`/`new_data`, keeps metadata rows)
  - Disabling undo (max=0 → no undo/redo, all snapshots pruned)
  - Atomicity (transaction rollback on failure)
  - Invariants (stacks never reference missing snapshots)
  - Bulk operations pruned as a unit (same `group_id`)
  - Default value (100)
  - Increasing limit does not restore pruned snapshots (pruning is permanent)

**Rationale:**
- Prevents unbounded database growth from undo history.
- Balances compliance (audit trail) with storage (undo capability).
- User can trade undo depth for disk space.

All tests pass: 795/795 (787 existing + 8 new).

---

```yaml
id: 2026-02-09-01
type: fix
areas: [ui, services]
summary: "Fix undo/redo persistence across app restarts (Issue #92)"
files_changed:
  - ui/main_window.py
```

**Problem:** Undo/redo stacks persisted correctly in database but UI actions remained disabled after app restart due to indentation bug in MainWindow.__init__() that prevented _update_undo_redo_states() from executing.

**Root Cause:** During previous edit, the entire undo/redo initialization section (lines ~220-350) was accidentally indented into the `_on_setup_subtab_changed()` method, causing __init__() to terminate prematurely.

**Fix:** Restored correct method structure - moved undo/redo state update and remaining init code back into __init__() at proper indentation level.

**Verification:** Added extensive checkpoint logging to trace execution flow, identified exact location where init terminated, fixed indentation, confirmed undo/redo actions now enable correctly on restart with persisted stacks (43 undo, 1 redo operations verified).

---

## 2026-02-08

```yaml
id: 2026-02-08-06
type: feature
areas: [database, services, ui, testing]
summary: "Audit Log + Undo/Redo + Soft Delete (Issue #92)"
files_changed:
  - repositories/database.py
  - repositories/purchase_repository.py
  - repositories/redemption_repository.py
  - repositories/game_session_repository.py
  - services/audit_service.py
  - services/undo_redo_service.py
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - ui/audit_log_viewer_dialog.py
  - tests/unit/test_soft_delete.py
  - tests/unit/test_audit_service.py
  - tests/ui/test_issue_92_ui_smoke.py
  - docs/archive/2026-02-17-docs-root-cleanup/DATABASE_DESIGN.md
issue: 92
branch: feature/issue-92-audit-undo-soft-delete
```

**Feature: Audit Log + Undo/Redo + Soft Delete**

**Schema Changes:**
- **audit_log table expansion**: Added `old_data` (JSON TEXT), `new_data` (JSON TEXT), `group_id` (TEXT UUID) columns + `idx_audit_group` index.
- **Soft delete columns**: Added `deleted_at` (TIMESTAMP NULL) + `idx_*_deleted` indexes to `purchases`, `redemptions`, `game_sessions`.
- **Migration pattern**: Idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS` guarded by `PRAGMA table_info()`.

**Services:**
- **AuditService** (`services/audit_service.py`): Structured audit logging with JSON snapshots (`old_data`, `new_data`), `group_id` for operation grouping, `auto_commit` flag for transactional logging. Methods: `log_create/update/delete/restore/undo/redo`, `get_audit_log(filters)`, `generate_group_id()`.
- **UndoRedoService** (`services/undo_redo_service.py`): Persistent undo/redo stacks (stored in `settings` table as JSON). `undo()` reverses audit entries in LIFO order; `redo()` replays in FIFO order. Excel-like behavior: new operations clear redo stack. Atomic rollback via `_reverse_audit_entry()` and `_replay_audit_entry()`.
- **Service-layer audit integration**: All CRUD methods in `PurchaseService`, `RedemptionService`, and `GameSessionService` call `audit_service.log_create/update/delete()` directly. Audit logging happens at service layer (not AppFacade) to ensure atomicity with data mutations. See ADR-0002 for architectural rationale.
- **CRUD audit coverage**: CREATE/UPDATE/DELETE operations for purchases, redemptions, and game_sessions all log structured audit entries with before/after snapshots using `dataclasses.asdict()` for serialization.

**Repository Layer:**
- **Soft delete pattern**: All `delete()` methods converted to `UPDATE SET deleted_at = CURRENT_TIMESTAMP`. Added `restore()` methods to clear `deleted_at`.
- **Query filters**: All `get_*()` queries automatically filter `WHERE deleted_at IS NULL`.
- **FIFO integrity**: `get_available_for_fifo()` excludes soft-deleted purchases to maintain accurate basis tracking.

**UI:**
- **Menu actions**: "Edit → Undo (Ctrl+Z)", "Edit → Redo (Ctrl+Shift+Z)", "Tools → View Audit Log…"
- **Action state updates**: `_update_undo_redo_states()` updates menu action text with operation descriptions (e.g., "Undo CREATE purchase #123").
- **Tools tab section**: Collapsible "📋 Audit Log" section with helper text and "Open Audit Log…" button.
- **Audit Log Viewer Dialog**: Full-featured browser with filters (table/action/limit), split view (table + JSON details panel), color-coded actions (green=CREATE, red=DELETE, orange=UPDATE/RESTORE).

**Testing:**
- **Unit tests**: 15 tests across `test_soft_delete.py` (7 tests) and `test_audit_service.py` (8 tests). Coverage: soft delete behavior, restore, FIFO exclusion, JSON snapshots, group_id linking, filters, auto_commit flag.
- **Headless UI smoke tests**: 8 tests in `test_issue_92_ui_smoke.py` verifying menu actions exist, handlers are wired, and MainWindow instantiates cleanly without displaying GUI.

**Documentation:**
- **DATABASE_DESIGN.md (archived)**: Updated `audit_log` schema docs, added soft delete behavior notes to `purchases`, `redemptions`, `game_sessions`.

**Commits:**
1. `59b2502`: Schema layer (deleted_at + indexes)
2. `5b50b1f`: Repository soft delete + restore methods
3. `2d36227`: Audit schema expansion (old_data/new_data/group_id)
4. `658b5a6`: AuditService implementation
5. `8062abb`: UndoRedoService implementation
6. `2dbcf1e`: UI menu actions (Undo/Redo/Audit Log)
7. `0971198`: Tools tab Audit Log section
8. `1723415`: Audit Log Viewer dialog
9. `1fde0ff`: Comprehensive tests (soft delete + audit)
10. `40cf5a0`: Headless UI smoke tests
11. `5817a81`: Wire audit_service CREATE operations into services
12. `35a4562`: Wire UPDATE/DELETE audit logging + fix repo create() return type bug
13. `1e8b2f4`: Fix missing imports and return statement - all 787 tests passing

**Implementation Notes:**
- **Architectural Decision (ADR-0002)**: Audit logging implemented at service layer rather than centralized in AppFacade. Rationale: atomicity (services own transactions), simplicity (services know what changed), type safety (no reflection needed). Trade-off: distributed code requires discipline when adding CRUD methods.
- **Bug fixes during implementation**: Repository `create()` methods return model objects (not int IDs), but services were treating them as IDs. Fixed by using `entity = repo.create(entity)` pattern and accessing `entity.id`.
- **Snapshot serialization**: Uses `dataclasses.asdict()` since models don't have `to_dict()` methods.

All tests pass (764 existing + 23 new = 787 total).

---

```yaml
id: 2026-02-08-05
type: enhancement
areas: [ui, services]
summary: "Add timestamp conflict banners to all dialogs (Issue #90)"
files_changed:
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
issue: 90
pr: 91
```

Notes:
- **Enhancement**: Added real-time timestamp conflict warning banners to RedemptionDialog, EditClosedSessionDialog, and EndSessionDialog.
- **User Experience**: All transaction/event dialogs now show an informational banner when the user-entered timestamp conflicts with existing events (purchases, redemptions, session starts, session ends).
- **Banner behavior**: Shows "ℹ️ Time will be adjusted to HH:MM:SS (original already in use)" when conflicts detected; auto-hides when timestamp is unique.
- **Cross-event uniqueness**: Enforces uniqueness across ALL event types using `timestamp_service.ensure_unique_timestamp()`.
- **Bug fixes**:
  - Fixed RedemptionDialog lookup bug (user_id/site_id are integers, not objects with .id attributes)
  - Fixed EndSessionDialog to use `self.session.user_id/site_id` instead of non-existent combo boxes
  - Fixed EndSessionDialog to use correct event_type ("session_end" instead of "session_start")
  - Fixed redemption validation to use ADJUSTED timestamps (prevents false "No game sessions" errors)
- **Layout improvements**: Removed excessive height adjustment; Qt's `updateGeometry()` now handles dialog resizing automatically.
- All 764 tests pass.

---

```yaml
id: 2026-02-08-04
type: bug-fix
areas: [services]
summary: "Fix basis consumption calculation for purchases during active session"
files_changed:
  - services/game_session_service.py
issue: 88
pr: 89
```

Notes:
- **Bug Fix**: Corrected `locked_processed_sc` calculation to account for locked SC added by purchases during an active session.
- Previous logic: `locked_processed_sc = locked_start - locked_end` (only counted SC at session start).
- Fixed logic: `locked_processed_sc = locked_start + purchases_during_sc - locked_end` (includes SC from DURING purchases).
- Impact: Basis consumption now correctly matches the actual amount of locked SC processed during the session.
- Example: $100 BEFORE + $50 DURING purchases, 100→150→0 locked processing now correctly consumes $150 basis (was $100).
- All 734 tests pass.

---

```yaml
id: 2026-02-08-03
type: enhancement
areas: [ui, services, facade]
summary: "Warn and link purchases when active session exists (Issue #88)"
files_changed:
  - services/game_session_event_link_service.py
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - tests/integration/test_purchase_active_session_link.py
issue: 88
pr: 89
```

Notes:
- **Enhancement**: When saving a purchase for a user+site pair with an active gaming session, the UI now shows a blocking warning dialog with session details.
- User must confirm before proceeding to save the purchase.
- If confirmed, the purchase is explicitly linked to the active session with a DURING relation.
- Success message includes a "View Session" button to navigate directly to the linked session in the Game Sessions tab.
- **Link Builder Fix**: Updated link builder logic to support DURING classification for active sessions:
  - Previously, purchases could only be DURING if the session had an `end_dt` (closed sessions).
  - Now, purchases with timestamps >= session start are classified as DURING for active sessions (when no next session exists).
- **New Facade Method**: `link_purchase_to_session(purchase_id, session_id, relation)` for explicit manual linking.
- All existing tests pass + new integration tests for active session linking behavior.

```yaml
id: 2026-02-08-02
type: enhancement
areas: [ui]
summary: "Allow main window resize below minimum width with scroll bars (Issue #86)"
files_changed:
  - ui/main_window.py
issue: 86
pr: 87
```

Notes:
- **Enhancement**: Main window can now be resized below the natural content width.
- Added QScrollArea wrapper around central widget with horizontal/vertical scroll bars as needed.
- Set minimum window size to 400x300 (previously constrained by content).
- Useful for smaller screens or side-by-side window viewing.
- All tabs and functionality remain accessible when scrolled.
- All 729 tests pass.

```yaml
id: 2026-02-08-01
type: fix
areas: [services, facade]
summary: "Fix session-event links not updated when events added/edited (Issue #84)"
files_changed:
  - app_facade.py
issue: 84
pr: 85
```

Notes:
- **Bug**: Adding or editing a purchase/redemption did not trigger session-event link rebuild.
- Result: Related events would not appear in session view dialogs until app restart or manual "Recalculate Everything".
- Root cause: `_rebuild_or_mark_stale()` only rebuilt FIFO allocations, not session-event links.
- Lazy rebuild in `get_linked_events_for_session()` had flawed early-return: it skipped rebuild if ANY links existed, even if incomplete.
- **Fix**: Added `rebuild_links_for_pair_from()` call in `_rebuild_or_mark_stale()` after FIFO rebuild (normal mode only).
- This ensures session-event links are kept in sync whenever purchases/redemptions are created or edited.
- All 729 tests pass after fix.

## 2026-02-07

```yaml
id: 2026-02-07-01
type: fix
areas: [services, ui]
summary: "Fix game_id/game_type updates not persisting for active sessions; add game_type_id field (Issue #82)"
files_changed:
  - models/game_session.py
  - repositories/database.py
  - repositories/game_session_repository.py
  - services/game_session_service.py
  - app_facade.py
  - ui/tabs/game_sessions_tab.py
  - services/tools/schemas.py
  - tests/integration/test_issue_82_edit_active_session_game_type.py
issue: 82
pr: 83
```

Notes:
- Root cause: `update_session()` kwargs handler skipped `None` values with `if value is not None`.
- This prevented clearing game_id (setting it to None) when user removes game from active session.
- Fix: Special-case `game_id` and `game_type_id` in kwargs to allow None values (game removal).
- **Database schema change**: Added `game_type_id` column to `game_sessions` table to support storing Game Type without a specific Game.
- Workflow change: Users can now select Game Type alone without selecting a specific Game.
  - Game Type is required IF there is a Game
  - Game Type is optional and can be stored by itself
- Migration automatically adds `game_type_id` column to existing databases.
- **Downstream coverage**: EditClosedSessionDialog now extracts and persists game_type_id (critical for edit closed session flow).
- **CSV support**: Added game_type_id field to GAME_SESSION_SCHEMA for CSV import/export with Game Type column.
- Recalculation services unaffected (P/L calculation does not depend on game_id or game_type_id).
- All 729 tests pass after changes.

## 2026-02-06

```yaml
id: 2026-02-06-13
type: docs
areas: [docs]
summary: "Add navigable HTML operator Readme (tabs, tools, recalculation)"
files_changed:
  - docs/INDEX.md
  - docs/Readme/index.html
  - docs/Readme/workflow.html
  - docs/Readme/architecture.html
  - docs/Readme/recalculation.html
  - docs/Readme/tools.html
  - docs/Readme/tab_purchases.html
  - docs/Readme/tab_redemptions.html
  - docs/Readme/tab_game_sessions.html
  - docs/Readme/tab_daily_sessions.html
  - docs/Readme/tab_unrealized.html
  - docs/Readme/tab_realized.html
  - docs/Readme/tab_expenses.html
  - docs/Readme/tab_setup.html
  - docs/Readme/dialogs.html
  - docs/Readme/glossary.html
  - docs/Readme/assets/style.css
```

Notes:
- New multi-page static HTML guide intended for operators, with special emphasis on recalculation scope and Tools safety/procedures.
- Linked from docs/INDEX.md so it’s discoverable.

```yaml
id: 2026-02-06-11
type: refactor
areas: [ui]
summary: "Load theme stylesheet from resources/theme.qss and refresh theme palettes"
files_changed:
  - ui/themes.py
  - docs/PROJECT_SPEC.md
```

Notes:
- Theme stylesheet is now maintained in `resources/theme.qss` with variables substituted at runtime.
- Updated Dark/Blue palettes and added a Custom theme option.

```yaml
id: 2026-02-06-10
type: feature
areas: [ui]
summary: "Redemptions table shows Cost Basis and Unbased columns"
files_changed:
  - ui/tabs/redemptions_tab.py
  - repositories/redemption_repository.py
```

Notes:
- Added Cost Basis and Unbased columns in the Redemptions table.
- Order is Cost Basis before Amount, and Unbased after Amount.
- Values are now populated from FIFO allocation totals and realized transaction cost basis.

```yaml
id: 2026-02-06-09
type: bugfix
areas: [ui]
summary: "Dark theme dialog labels now use theme-muted styling for readability"
issue: "#76"
files_changed:
  - ui/themes.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/purchases_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/realized_tab.py
  - ui/tabs/users_tab.py
  - ui/tabs/sites_tab.py
  - ui/tabs/cards_tab.py
  - ui/tabs/games_tab.py
  - ui/tabs/game_types_tab.py
  - ui/tabs/redemption_methods_tab.py
  - ui/tabs/redemption_method_types_tab.py
  - ui/tabs/expenses_tab.py
  - ui/tabs/unrealized_tab.py
  - ui/tabs/purchases_tab_modern.py
```

Notes:
- **Problem:** Dialog field labels were using `palette(mid)` and became unreadable in Dark theme.
- **Solution:** Introduced `MutedLabel` theme styling and applied it across dialog view layouts.
- **Impact:** Consistent, readable secondary labels in Dark theme without changing dialog layout.

```yaml
id: 2026-02-06-08
type: bugfix
areas: [ui]
summary: "Tools tab theming alignment + scroll area background fixes (Issue #76 follow-up)"
issue: "#76"
files_changed:
  - ui/themes.py
  - ui/tabs/tools_tab.py
```

Notes:
- **Problem:** Tools tab background diverged from Setup pane and collapsible header styling felt inconsistent after scroll-area changes.
- **Root Cause:** Scroll area + local widget styles interfered with global theme propagation.
- **Solution:**
  - Theme the Setup sub-tab scroll area and viewport to match the global surface
  - Tag Tools tab and collapsible headers with theme-managed object names
  - Remove hover style on collapsible headers to match standard patterns
- **Impact:** Tools tab and section headers now match global theme backgrounds, inputs, and button patterns.

```yaml
id: 2026-02-06-07
type: bugfix
areas: [ui]
summary: "Window resize constraints: prevent expansion beyond screen boundaries (resolves Issue #76)"
issue: "#76"
files_changed:
  - ui/tabs/setup_tab.py
  - ui/main_window.py
```

Notes:
- **Problem:** Expanding all Tools sub-sections caused window to resize beyond screen boundaries, becoming stuck off-screen and unresizable
- **Root Cause:** Tools tab content directly triggered window resize without boundary constraints
- **Solution:**
  - Wrapped ToolsTab in QScrollArea within Setup sub-tabs (content now scrolls instead of expanding window)
  - Added maximum window size constraint (90% of screen dimensions) in MainWindow initialization
  - Used screen.availableGeometry() to respect taskbar/dock areas
  - Set scroll area to widgetResizable with no frame for seamless integration
- **Impact:** Window now stays within screen bounds; Tools sections can all be expanded simultaneously with scrolling as needed
- **UX:** Collapsible sections work as expected; scroll bars appear automatically when content exceeds visible area

```yaml
id: 2026-02-06-06
type: bugfix
areas: [ui, services]
summary: "Repair Mode QA fixes: UI persistence, name resolution, stale pair updates, and architectural cleanup"
pr: "#75"
files_changed:
  - ui/repair_mode_dialog.py
  - ui/tabs/tools_tab.py
  - ui/main_window.py
  - ui/tabs/setup_tab.py
  - services/repair_mode_service.py
  - services/game_session_service.py
  - app_facade.py
```

Notes:
- **Manual QA Phase:** Comprehensive hands-on testing revealed 15 bugs not caught by automated tests (726 tests passing)
- **Signal Handling:** Fixed checkbox not enabling button (stateChanged → toggled signal in RepairModeConfirmDialog)
- **Method Names:** Fixed AttributeErrors (get_maintenance_mode → is_maintenance_mode, QTabBar.clear() → removeTab loop)
- **Widget Lifecycle:** Fixed RuntimeError from deleted widget by changing message box parent to main_window instead of self (after tab refresh)
- **Name Resolution:** Fixed "Unknown User/Site" in stale pair dialogs:
  - Updated RepairModeService to accept db_manager for name lookups
  - Fixed User model attribute (username → name)
  - Fixed Site model attribute (site_name → name)
- **Stale Pair Updates:** Fixed stale pair count not updating after purchase edits by adding tools_tab to refresh_all_tabs list
- **Rebuild Stale Pairs:** Fixed AttributeError (_run_recalculation didn't exist) by rewriting _on_rebuild_stale_pairs to properly create RecalculationWorker instances
- **Tax Withholding:** Removed invalid apply_to_session_model() call (tax withholding is calculated at date level, not per-session)
- **UI Button Visibility:** Changed repair mode buttons to hide() when disabled (not just setEnabled(False)) for cleaner UX
- **Stale Pair Clearing:** Added automatic clearing of stale pairs after "Recalculate Everything" completes
- **View Persistence:** Added Setup sub-tab index persistence (saves/restores which Setup sub-tab is active across app restarts and repair mode toggles)
- **Section State Persistence:** Added expand/collapse state persistence for all Tools sections (Repair Mode, Recalculation, CSV, Adjustments, Database)
- **Settings Propagation:** Passed settings object through MainWindow → SetupTab → ToolsTab for reliable persistence
- **Default Collapsed:** Changed all Tools sections to start collapsed by default for cleaner initial view
- **Known Issue (Follow-up):** Window can expand beyond screen boundaries when all Tools sections expanded; needs scroll area implementation (tracked in new Issue)

```yaml
id: 2026-02-06-05
type: feature
areas: [services, ui, app_facade]
summary: "Repair Mode: manual derived data rebuild control for troubleshooting (implements Issue #55)"
issue: "#55"
files_changed:
  - services/repair_mode_service.py (new)
  - app_facade.py
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - ui/repair_mode_dialog.py (new)
  - ui/settings.py
  - docs/archive/2026-02-06-issue-55-proposed-body.md (new)
```

Notes:
- **Purpose:** Provides controlled environment for troubleshooting derived data corruption by disabling automatic rebuilds and tracking affected (user, site) pairs.
- **Problem:** When derived data (FIFO allocations, cost basis, P/L) becomes corrupted, automatic rebuilds after every edit make it difficult to isolate the root cause or perform systematic repairs.
- **Solution:** Repair Mode (manual toggle in Tools tab):
  - **When enabled:** All CRUD operations (create/update/delete purchases, redemptions, sessions, adjustments) mark the affected (user, site) pair as "stale" instead of immediately rebuilding derived data
  - **Stale pair tracking:** Persisted in settings.json with boundary date/time, timestamp, and reasons for staleness
  - **Manual rebuild:** Tools tab provides "Rebuild Stale Pairs" and "Clear Stale List" actions
  - **UI indicators:** Red banner at top of window, window title suffix " - REPAIR MODE", status indicator in Tools tab
  - **Safety:** Cannot enable while Maintenance Mode is active; requires explicit confirmation with acknowledgment checkbox
- **Backend Architecture:**
  - `RepairModeService`: Manages enabled state and stale pair list (settings.json persistence)
  - `AppFacade._rebuild_or_mark_stale()`: Conditional helper method used by all CRUD operations
  - Refactored 10+ CRUD methods to use helper instead of direct rebuild calls
  - Cross-pair moves (e.g., reassigning purchase to different site) mark both old and new pairs stale
- **UI Components:**
  - `RepairModeConfirmDialog`: Blocking confirmation with warning bullets, required acknowledgment checkbox
  - Tools tab section: Status indicator, toggle button, stale pairs count, rebuild/clear actions
  - MainWindow: Red banner (mirrors Maintenance Mode pattern), window title suffix, `refresh_repair_mode_ui()` method
- **Workflow:**
  1. Enable Repair Mode via Tools tab (confirmation required)
  2. Perform troubleshooting edits/imports/corrections
  3. Review stale pairs list (shows which (user, site) pairs are affected)
  4. Rebuild selected/all stale pairs when ready
  5. Disable Repair Mode to resume normal auto-rebuild behavior
- **Testing:** Backend and CRUD refactoring complete; UI testing and comprehensive test suite pending.

```yaml
id: 2026-02-06-04
type: bugfix
areas: [models, services, repositories, ui, tests]
summary: "Notification lifecycle cooldown delays prevent delete/read nag loops (resolves Issue #73)"
issue: "#73"
files_changed:
  - models/notification.py
  - services/notification_service.py
  - repositories/notification_repository.py
  - ui/notification_widgets.py
  - tests/integration/test_notification_cooldown.py (new)
```

Notes:
- **Problem:** Deleting or marking notifications as read caused immediate reappearance when notification rules re-evaluated (on dialog close, hourly timer). This created a "nag loop" UX issue.
- **Root Cause:** `NotificationService.create_or_update()` recreated deleted notifications because it only checked `if existing and not existing.is_deleted`, treating deleted notifications as if they never existed.
- **Solution:** Added cooldown suppression mechanism:
  - New `suppressed_until` field in `Notification` model tracks cooldown period
  - New `is_suppressed` property checks if `datetime.now() < suppressed_until`
  - Updated `is_active` to exclude suppressed notifications
  - `delete()` and `mark_read()` methods now accept `cooldown_days` parameter
  - `create_or_update()` respects suppression: returns existing notification without recreation if suppressed
  - When cooldown expires + condition still true → notification resurfaces as new/unread
- **Cooldown Duration:** Based on notification type's configured threshold:
  - Redemption pending: `redemption_pending_receipt_threshold_days` (default 7 days)
  - Backup notifications: backup `interval_days` (default 1 day)
  - Other notifications: 1 day default
- **UI Integration:** `NotificationCenterDialog` determines cooldown_days from notification type and passes to service methods
- **Tests:** 7 comprehensive integration tests validating:
  - Delete with cooldown prevents immediate recreation
  - Mark read with cooldown prevents immediate recreation
  - Cooldown expiration allows resurfacing as unread
  - Past suppression timestamps don't suppress
  - Redemption rules respect suppression during evaluation
  - Condition resolution during cooldown
  - Multiple notifications with independent cooldowns

```yaml
id: 2026-02-06-03
type: bugfix
areas: [ui, tests]
summary: "Game Sessions tab search now filters by user/site/game names (resolves Issue #71)"
issue: "#71"
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_game_sessions_search.py (new)
```

Notes:
- Fixed Game Sessions search to resolve user/site/game names using lookup dictionaries (same as table display logic).
- Previously searched non-existent model attributes (`user_name`, `site_name`, `game_name`), causing empty results.
- Search now matches displayed text: searching "Alice" finds sessions by that user, "CasinoX" finds sessions at that site, etc.
- Added comprehensive integration tests (7 test cases): search by user/site/game name, numeric values, case-insensitive, clear search, no results.
- Tests set date filter to "All Time" to ensure visibility of test data.

```yaml
id: 2026-02-06-02
type: bugfix
areas: [services, ui, app_facade, tests]
summary: "Repair/rebuild robustness: adjustment-aware tools rebuilds, event-link rebuild coverage, and safer tax recompute"
issue: "#55"
files_changed:
  - app_facade.py
  - services/game_session_service.py
  - services/recalculation_service.py
  - services/tax_withholding_service.py
  - ui/tools_workers.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_issue_49_purchase_exclusion.py
  - tests/unit/test_recalculation_service.py
  - tests/unit/test_tax_withholding_service.py
```

Notes:
- Tools rebuild pipeline is now fully adjustment/checkpoint-aware and rebuilds `game_session_event_links` after scoped/all rebuilds.
- Redemption delete cascades now rebuild event links consistently (single + bulk paths).
- Expected-balance computation is deterministic for same-timestamp purchase edits (prevents drift/regressions).
- Tax withholding recompute (`apply_to_date`) preserves an existing custom rate when no override is provided.
- Pair discovery for rebuild (`iter_pairs`) now includes non-deleted account adjustments.

```yaml
id: 2026-02-06-01
type: bugfix
areas: [ui, app_facade]
summary: "Purchase balance check now respects balance checkpoints and adjustments"
issue: "#54"
files_changed:
  - app_facade.py (adjustment_service initialization order)
  - ui/tabs/purchases_tab.py (balance check logic)
  - ui/adjustment_dialogs.py (date/time field patterns)
```

Notes:
- **Bug Fix:** Purchase dialog balance check was using legacy logic that bypassed checkpoint calculations
  - Previously: When period_purchases existed, used prev_purchase.starting_sc_balance as expected value
  - Now: Always calls facade.compute_expected_balances() which respects checkpoints and adjustments
  - Fixed in: ADD purchase flow, EDIT purchase flow, and live balance check (_update_balance_check)

- **Bug Fix:** adjustment_service was initialized after game_session_service in AppFacade
  - Moved adjustment_service initialization before game_session_service
  - Now properly passed to game_session_service constructor
  - Enables checkpoint logic in compute_expected_balances()

- **UI Fix:** Adjustment dialogs now use correct date/time field pattern
  - Changed from QDateEdit/QTimeEdit to QLineEdit with placeholders (MM/DD/YY, HH:MM)
  - Added calendar picker button (📅) and "Today"/"Now" quick-fill buttons
  - Matches global UI patterns (Purchase dialog, etc.)
  - Fixed method names: get_user_by_id → get_user, get_site_by_id → get_site

---

## 2026-02-05

```yaml
id: 2026-02-05-06
type: feature
areas: [models, repositories, services, ui, database]
summary: "Adjustments & Corrections (Basis Adjustments + Balance Checkpoints)"
issue: "#54"
files_changed:
  - models/adjustment.py (new)
  - repositories/adjustment_repository.py (new)
  - repositories/database.py (account_adjustments table)
  - services/adjustment_service.py (new)
  - services/game_session_service.py (checkpoint integration)
  - services/recalculation_service.py (basis adjustment integration)
  - ui/tabs/tools_tab.py (adjustments section)
  - ui/adjustment_dialogs.py (new)
  - tests/unit/test_adjustment_model.py (12 tests)
  - tests/unit/test_adjustment_repository.py (10 tests)
  - tests/unit/test_adjustment_service.py (15 tests)
```

Notes:
- **Feature:** Two types of manual adjustments for correcting accounting issues:
  1. **Basis Corrections** (BASIS_USD_CORRECTION): Delta adjustments to cost basis (e.g., missed fees, refunds)
     - Integrated into FIFO pipeline as synthetic purchases with negative IDs
     - Ordered by effective datetime for correct FIFO sequencing
  2. **Balance Checkpoints** (BALANCE_CHECKPOINT_CORRECTION): Known balance anchors at specific timestamps
     - Override closed sessions in expected balance calculations
     - Used for reconciliation or importing external data

- **Data Layer:**
  - New `account_adjustments` table with soft delete support
  - Indexes on (user_id, site_id, effective_date, effective_time) and (type, deleted_at)
  - Fields: type, delta_basis_usd, checkpoint_total_sc, checkpoint_redeemable_sc, reason (required), notes, related_table/id

- **Service Layer:**
  - AdjustmentService with validation (delta != 0, checkpoints have non-zero balances)
  - GameSessionService.compute_expected_balances() uses latest checkpoint before cutoff
  - RecalculationService injects basis adjustments as synthetic lots in FIFO rebuild

- **UI (Tools Tab):**
  - New Adjustments section with three buttons: New Basis Adjustment, New Balance Checkpoint, View Adjustments
  - BasisAdjustmentDialog: form for delta, user/site, date/time, reason
  - CheckpointDialog: form for total/redeemable SC, user/site, date/time, reason
  - ViewAdjustmentsDialog: table view with filters, soft delete, restore

- **Test Coverage:** 37 new unit tests (100% coverage on new models/repos/services), 685 total tests passing

```yaml
id: 2026-02-05-05
type: feature
areas: [ui]
summary: "Game Sessions: End & Start New convenience flow"
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_switch_game_flow.py
```

Notes:
- Adds a fast workflow to end an Active session and immediately start a new session with carried-forward starting balances.
- End Session dialog now includes **"🎮 End & Start New"**.
- The Start Session dialog is prefilled with same User/Site and starting balances equal to the ended session’s ending balances; game selection is intentionally left blank.
- Validation: scenario-based pytest-qt integration tests cover happy path, cancel, and failure injection.

```yaml
id: 2026-02-05-04
type: feature
areas: [ui, facades, services]
summary: "Purchase dialogs: balance chain warnings + full basis-period display"
issue: "#66"
files_changed:
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - tests/integration/test_purchase_edit_balance_check.py
```

Notes:
- **Problem:** Purchase dialogs didn't track balance chains correctly, leading to misleading warnings and lack of context for multi-purchase basis periods.
- **Solution:** 
  1. Implemented proper balance chain tracking: expected balance uses previous purchase's actual `starting_sc_balance` (not just sum of SC received)
  2. Added "Full Basis Period" section to Purchase View dialog showing ALL purchases (past, current, future) in the basis period
  3. Added View Purchase buttons for easy navigation through purchase chains
  4. Simplified warnings: warn on ANY non-zero mismatch (no tolerance, no confusing delta display)

- **Basis Period Rules (Clarified):**
  - Period starts after most recent FULL redemption (`more_remaining=0`)
  - Partial redemptions (`more_remaining>0`) do NOT start new period
  - Example: Redeem 2500 SC but leave 200 SC → NOT full → period continues
  - Subsequent purchases continue same basis period until next FULL redemption

- **Balance Chain Logic (Critical Fix):**
  - If previous purchase exists in basis period: `expected_pre = prev_purchase.starting_sc_balance`
  - If first purchase in period: `expected_pre = compute_expected_balances()`
  - This creates proper balance chain accounting for actual entered balances
  - `total_extra = (actual_pre - expected_pre).quantize(Decimal("0.01"))`

- **Warning Logic (Simplified):**
  - Warn if `total_extra != 0` (any mismatch, no tolerance)
  - Real-time label shows: "✓ Balance Check: OK" or "✗ Balance Check: X.XX SC HIGHER/LOWER than expected (Y.YY SC)"
  - Submission warning dialog explains if mismatch indicates tracked loss or untracked wins

- **Bug Fixes During Implementation:**
  1. Fixed `exclude_purchase_id` not being passed when computing previous purchase's total_extra
  2. Fixed expected balance using `compute_expected_balances` instead of actual balance chain
  3. Fixed real-time label using old 0.50 tolerance logic instead of matching submission check
  4. Removed confusing delta display per user feedback ("just show if balance matches or not")

- **UI Enhancements:**
  - Current purchase shown in **bold** in basis period table
  - Table fills available space (min 3 rows visible, scales with content)
  - View Purchase buttons styled like View Session buttons
  - Clicking button highlights purchase in main table and opens its dialog

- **Facade Methods Added:**
  - `get_basis_period_start_for_purchase()`: finds most recent FULL redemption datetime
  - `get_basis_period_purchases()`: returns ALL purchases in basis period (past, current, future), ordered by (date, time, id)
  - `compute_purchase_total_extra()`: computes total_extra given entered balance values

- **Validation:** All 645 tests pass. Updated `test_purchase_edit_balance_check_excludes_edited_purchase` to expect new balance chain logic.

```yaml
id: 2026-02-05-01
type: fix
areas: [repositories, tests]
summary: "FULL redemptions (more_remaining=0) now close Unrealized positions"
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
```

Notes:
- **Problem:** When users cash out everything they want to (FULL redemption: `more_remaining=0`), the position would remain visible in the Unrealized tab even though they consider it dormant/closed. This clutters the Unrealized view with negligible balances (e.g., 0.43 SC left after $100 redemption).
- **Fix:** Expanded `_get_close_balance_dt()` to check both "Balance Closed" markers AND FULL redemptions (`more_remaining IS NOT NULL AND more_remaining = 0`). Returns the most recent closure datetime. Positions are excluded from Unrealized tab when closure datetime >= last activity datetime.
- **Semantics:** `more_remaining=0` means "I'm cashing out everything I want to/can right now; treat remaining balance as dormant." `more_remaining=1` means "partial redemption, balance remains active." Position reopens automatically when new activity (purchases, sessions) occurs after closure.
- **Validation:** Added 4 regression tests covering: (1) FULL redemption closes position, (2) partial redemption keeps position visible, (3) FULL redemption followed by later activity reopens position, (4) newest closure wins when both "Balance Closed" and FULL redemption exist. Updated 3 existing tests to use `more_remaining=1` to maintain position visibility for their test scenarios.

```yaml
id: 2026-02-05-02
type: fix
areas: [ui]
summary: "Fix Unrealized Close Position crash (current_sc -> total_sc)"
files_changed:
  - ui/tabs/unrealized_tab.py
```

Notes:
- **Problem:** Clicking "Close Position" could raise an `AttributeError` because the UI referenced `pos.current_sc` but the model uses `total_sc`.
- **Fix:** Use `pos.total_sc` for the close-balance confirmation and close call.

```yaml
id: 2026-02-05-03
type: fix
areas: [services, ui, tests]
summary: "Fix redemption deletion impact check on DBs without fifo_allocations"
files_changed:
  - services/redemption_service.py
  - tests/unit/test_redemption_deletion_impact.py
```

Notes:
- **Problem:** Deleting a redemption could log `no such table: fifo_allocations` while checking deletion impact.
- **Fix:** `RedemptionService.get_deletion_impact()` now queries `redemption_allocations` (the real FIFO allocation table).

---

## 2026-02-04

```yaml
id: 2026-02-04-08
type: feature
areas: [repositories, tests, docs]
summary: "Unrealized Total SC estimation now uses purchase snapshots and session starts as checkpoints (Issue #61)."
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
  - docs/PROJECT_SPEC.md
issue: 61
```

Notes:
- **Problem:** Total SC (Est.) only used last closed session ending balance as checkpoint, ignoring dailies/bonuses added before first session start or between sessions. Purchases with `starting_sc_balance` (snapshots) and Active session starting balances were not recognized as valid checkpoints. Additionally, Redeemable SC (Position) was incorrectly showing checkpoint value without subtracting redemptions that occurred after the checkpoint.
- **Fix:** Expanded checkpoint sources to three types: (1) purchase snapshots (WHERE `starting_sc_balance > 0.001`), (2) session starts (`starting_balance` from any session), (3) session ends (`ending_balance` from Closed sessions only). Checkpoint selection: most recent by datetime. Formula: `Total SC = checkpoint_total_sc + purchases_since_checkpoint - redemptions_since_checkpoint`. Redeemable SC now correctly subtracts non-free-SC redemptions after checkpoint: `Redeemable SC = checkpoint_redeemable_sc - redeemable_redemptions_since_checkpoint`.
- **No-double-counting:** When checkpoint is a purchase snapshot, that purchase's `sc_received` is excluded from "purchases since checkpoint" delta to prevent adding the same SC twice.
- **Validation:** Added 9 regression tests (7 for checkpoint expansion + 2 for redeemable SC after redemptions) covering purchase snapshot precedence, session start checkpoints, session end checkpoints, checkpoint source ordering, no-double-counting invariant, multiple purchases with snapshots, redemptions after snapshots, and redeemable SC estimation. Updated 3 existing test expectations to reflect new checkpoint behavior.

```yaml
id: 2026-02-04-07
type: feature
areas: [repositories, tests, docs]
summary: "Unrealized positions remain visible when SC remains but basis is fully allocated (Issue #58)."
files_changed:
  - repositories/unrealized_position_repository.py
  - tests/integration/test_issue_44_unrealized_live_balances.py
  - docs/PROJECT_SPEC.md
issue: 58
```

Notes:
- **Problem:** Partial redemptions could consume all remaining basis (via FIFO allocation) but leave SC on the site (e.g., Moonspin 2500 SC cap scenario left ~175 SC remaining). The position would disappear from Unrealized even though it wasn't fully closed.
- **Fix:** Unrealized now includes positions where `Total SC (Est.) > 0` even if `Remaining Basis = $0.00`, reflecting that the position is still open with profit-only SC.
- **Removal criteria:** Position removed when (a) estimated SC < 0.01, or (b) explicit "Balance Closed" marker exists.
- **Validation:** Added 3 regression tests (basis=0 + SC>0 shows, basis=0 + SC<threshold doesn't show, Balance Closed marker still suppresses).

```yaml
id: 2026-02-04-06
type: fix
areas: [ui, tests]
summary: "End Session dialog notes start collapsed; dialog resizes on expand/collapse."
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_edit_session_dialog_notes_layout.py
  - tests/integration/test_end_session_dialog_notes_layout.py
issue: null
```

Notes:
- **Problem:** Ending a session with pre-existing notes could open the dialog in a cramped state (especially when notes were visible), compressing the "Session Details" section.
- **Fix:** Start with notes collapsed (even if notes exist) and compute tight/expanded dialog heights from Qt size hints so expand/collapse resizes cleanly.
- **Validation:** Added headless regression tests for End Session + Edit Session + Edit Closed Session collapsed → expanded → collapsed behavior.

```yaml
id: 2026-02-04-05
type: fix
areas: [ui, tests]
summary: "End Session dialog now shows Game Type correctly."
files_changed:
  - ui/tabs/game_sessions_tab.py
  - tests/integration/test_end_session_dialog_game_type.py
issue: null
```

Notes:
- **Problem:** `EndSessionDialog` attempted to load game/game-type via repo attributes that are not part of `AppFacade`, causing the Game Type chip to render as blank/"—".
- **Fix:** Fetch game + game type via `AppFacade.get_game()` / `AppFacade.get_game_type()`.
- **Validation:** Added a headless regression test.

```yaml
id: 2026-02-04-04
type: fix
areas: [ui]
summary: "Fix purchase add/edit crash after removing _balance_check_cutoff helper."
files_changed:
  - ui/tabs/purchases_tab.py
issue: null
```

Notes:
- **Problem:** Purchase add/edit flows still referenced `_balance_check_cutoff()`, causing `NameError` when editing purchase timestamps.
- **Fix:** Remove the stale helper calls and use `compute_expected_balances()` directly (edit flow passes `exclude_purchase_id`).
- **Validation:** Full pytest suite passes.

```yaml
id: 2026-02-04-03
type: docs
areas: [docs, accounting]
summary: "Clarify 'redeemable' vs 'recognized/earned' SC and when taxable gameplay P/L is recognized."
files_changed:
  - docs/PROJECT_SPEC.md
issue: null
```

Notes:
- Documented the intentional semantics: Sezzions does not try to recognize taxable gains at the moment redeemable SC appears on a site; gains are recognized only when a session is closed.
- Clarified how `discoverable_sc` works and why off-session freebies net out if they are lost during play.

```yaml
id: 2026-02-04-02
type: fix
areas: [services, ui, tests]
summary: "Exclude edited purchase by ID in balance checks (replaces 1-second time epsilon)."
files_changed:
  - services/game_session_service.py
  - app_facade.py
  - ui/tabs/purchases_tab.py
  - tests/integration/test_issue_49_purchase_exclusion.py
issue: "#49"
```

Notes:
- **Problem:** Purchase balance checks used a "1 second before purchase" cutoff to avoid including the edited purchase itself. This broke when two purchases shared the same timestamp.
- **Solution:** Added `exclude_purchase_id` parameter throughout the balance check call chain:
  - `GameSessionService.compute_expected_balances()`: Skip purchase by ID instead of timestamp cutoff
  - `AppFacade.compute_expected_balances()`: Pass through parameter
  - `PurchasesTab._update_balance_check()`: Pass `self.purchase.id` when editing
- **Behavior change:** Balance checks now correctly exclude only the edited purchase, even when multiple purchases share the same timestamp. No more false positives or false negatives due to time-based approximations.
- **Test coverage:** Added regression test suite (`test_issue_49_purchase_exclusion.py`) covering same-timestamp scenarios and edge cases.
- **Removed code:** Deleted obsolete `_balance_check_cutoff()` helper function from `purchases_tab.py`.

```yaml
id: 2026-02-04-01
type: feature
areas: [ui, tests, cleanup]
summary: "Default date filter presets per tab + close SQLite resources in workers/tests."
files_changed:
  - ui/tabs/purchases_tab.py
  - ui/tabs/redemptions_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/expenses_tab.py
  - ui/tabs/unrealized_tab.py
  - ui/tools_workers.py
  - tests/integration/test_default_date_filter_presets.py
  - tests/integration/test_issue_20_recalc_completion.py
  - tests/integration/test_issue_9_global_refresh.py
  - tests/integration/test_reset_database_flow.py
  - tests/integration/test_settings_dialog_smoke.py
  - tests/integration/test_csv_import_integration.py
  - tests/integration/test_csv_import_user_scoped_methods.py
  - tests/unit/test_database_write_blocking.py
  - tests/unit/test_tools_workers.py
issue: null
```

Notes:
- **UX:** Tabs now start with consistent default date ranges:
  - Purchases / Redemptions / Game Sessions / Expenses: current calendar year
  - Unrealized: all time (2000-01-01 → today)
- **Regression coverage:** Added a headless integration test asserting these tab defaults.
- **Test hygiene:** Ensured worker and test-created SQLite connections/temp files are closed deterministically to avoid `ResourceWarning` noise under newer Python versions.

## 2026-02-03

```yaml
id: 2026-02-03-03
type: fix
areas: [ui]
summary: "Fix spreadsheet selection stats to ignore hidden rows/columns (filtered table selections)."
files_changed:
  - ui/spreadsheet_ux.py
  - tests/unit/test_spreadsheet_ux.py
issue: "#50"
```

Notes:
- **Problem:** After filtering/searching (hidden rows), selection stats could sum values from hidden rows when using range selection.
- **Root cause:** `SpreadsheetUXController._extract_table_selection()` treated any cell inside a selected range as selected, even if its row/column was hidden.
- **Fix:** Exclude hidden rows/columns when extracting selection grids for both QTableWidget and QTableView.
- **Validation:** Added a regression unit test for the hidden-row-in-range case; full pytest suite passes.

```yaml
id: 2026-02-03-02
type: fix
areas: [ui]
summary: "Fix purchase edit balance check to exclude the edited purchase from expected balances."
files_changed:
  - ui/tabs/purchases_tab.py
  - tests/integration/test_purchase_edit_balance_check.py
issue: "#47"
commits: c6b39b0
```

Notes:
- **Problem:** Editing a purchase showed a different (smaller) SC balance mismatch than adding the same purchase.
- **Root cause:** Edit/dialog balance-check computed expected balances at the purchase timestamp; `compute_expected_balances()` includes purchases where `purchase_dt <= cutoff`, so the purchase being edited self-included.
- **Fix:** Standardize purchase balance-check cutoff to “1 second before purchase” (date+time safe, handles midnight rollover) for both edit flow and live dialog checks.
- **Validation:** Added a headless regression test reproducing the Zula example; full pytest suite passes.

```yaml
id: 2026-02-03-01
type: fix
areas: [ui, cleanup]
summary: "Remove dead per-session tax withholding code from EditClosedSessionDialog."
files_changed:
  - ui/tabs/game_sessions_tab.py
commits: 70cfd53
```

Notes:
- **Problem:** `EditClosedSessionDialog.collect_data()` contained orphaned code referencing `self.tax_rate_edit`, a field that never existed in the dialog's `__init__`.
- **Root cause:** Template/copy-paste leftover from the 2026-01-31 tax withholding refactor (commit `153cdf0`), where all per-session tax UI was intentionally removed.
- **Context:** Tax withholding moved entirely to daily-level (not per-session) to fix incorrect totaling. Individual game sessions no longer have tax fields.
- **Previous defensive fix (2026-02-03):** Added `hasattr(self, 'tax_rate_edit')` check to prevent AttributeError crash when editing closed sessions.
- **Proper fix:** Remove entire dead code block (18 lines) including tax variable declarations and return dict fields.
- **Impact:** Cleaner code, removes maintenance burden, prevents future confusion about per-session tax semantics.
- **Validation:** All tests pass (609 total).

## 2026-02-02

```yaml
id: 2026-02-02-07
type: feature
areas: [backup, notifications, settings, ui]
summary: "Issue #35: Automatic backup checkbox persistence + notification settings"
files_changed:
  - ui/tabs/tools_tab.py (unblock signals after loading settings, emit notifications on success/failure)
  - ui/settings.py (add backup notification settings to default config, merge with stored values)
  - ui/settings_dialog.py (add backup notification UI controls)
  - services/notification_rules_service.py (respect user notification preferences, add on_backup_failed)
  - tests/unit/test_backup_notification_settings.py (4 new tests for settings persistence)
  - tests/unit/test_backup_notification_rules.py (6 new tests for notification logic)
branch: fix/issue-35-backup-checkbox-and-notifications
commits: [e7f4d23, 9b8b419, 4352fb5, 3606a40]
issue: "#35"
notes: |
  Fixed automatic backup checkbox not persisting (signals were blocked but never unblocked).
  Added user-configurable backup notification settings:
  - Notify on backup failure (on/off)
  - Notify when backup overdue (on/off)
  - Overdue threshold (days before showing overdue notification)
  
  Default behavior: notify on failure, notify when overdue by 1+ day.
  
  Notification logic now respects user preferences:
  - Overdue notifications only shown if user has enabled them and backup is overdue by threshold
  - Failure notifications only shown if user has enabled them
  - All backup notifications dismissed when backup completes successfully
  
  All 609 tests passing (10 new tests added).
status: complete
```

```yaml
id: 2026-02-02-06
type: fix
areas: [unrealized, repositories, ui]
summary: "Unrealized tab: scope Redeemable SC to current position only"
files_changed:
  - repositories/unrealized_position_repository.py (redeemable_sc scoped to position start)
  - ui/tabs/unrealized_tab.py (clarify column header)
  - tests/integration/test_issue_44_unrealized_live_balances.py (update expectations)
  - docs/PROJECT_SPEC.md (document semantics)
branch: fix/issue-44-unrealized-live-balances
commits: [a5915f5, 31af440]
issue: "#44"
pull_request: "#45"
notes: |
  Fixed Unrealized tab Redeemable SC to only show values from sessions within the current position:
  - Redeemable SC now only shown if last session end >= position start_date (oldest purchase with remaining basis)
  - If session predates position (e.g., fully redeemed old position, then repurchased), shows 0.00
  - Prevents misleading scenario where old session redeemable leaks into new position
  - Column renamed: "Redeemable SC (Last Session)" → "Redeemable SC (Position)"
  - Total SC (Est.) remains the basis for Current Value and Est. Unrealized P/L.
status: complete
```

```yaml
id: 2026-02-02-05
type: fix
areas: [unrealized, repositories, ui]
summary: "Fix Issue #44: Unrealized tab now reflects purchases/redemptions after last session"
files_changed:
  - repositories/unrealized_position_repository.py (incorporate transactions after last session)
  - ui/tabs/unrealized_tab.py (update column headers for clarity)
  - tests/integration/test_issue_44_unrealized_live_balances.py (new comprehensive tests)
  - models/unrealized_position.py (add total_sc and redeemable_sc fields)
branch: fix/issue-44-unrealized-live-balances
commits: [61ba86e, a599408, 2f28164]
issue: "#44"
pull_request: "#45"
notes: |
  Fixed bug where Unrealized tab "Current SC / Current Value / Unrealized P/L" columns
  remained stuck at last session values even after new purchases or redemptions.
  
  Root cause: once any session existed, current_sc was pulled from the most recent
  session's ending balance and ignored all subsequent transactions.
  
  Solution: estimate current balances by taking last session as baseline and applying
  purchases/redemptions that occurred after that session:
  - estimated_total_sc = session_ending_balance + purchases_since - redemptions_since
  - estimated_redeemable_sc = session_ending_redeemable + purchases_since - redemptions_since
  - current_value = estimated_total_sc * sc_rate (uses total, not redeemable)
  - unrealized_pl = current_value - remaining_basis
  
  Semantic clarification (per Issue #44 review discussion):
  - Unrealized P/L represents "money out vs current potential value" (total SC semantics)
  - Use ending_balance (total SC) as baseline when sessions exist, not ending_redeemable
  - Both Total SC and Redeemable SC are shown; Redeemable is informational only
  
  Updated column headers and added columns:
  - "Purchase Basis" → "Remaining Basis"
  - "Current SC" → "Total SC (Est.)" and "Redeemable SC" (two columns)
  - "Unrealized P/L" → "Est. Unrealized P/L"
  
  Added 6 new integration tests covering purchase-after-session, redemption-after-session,
  multiple transactions, no-sessions, last-activity tracking, and basis invariants.
  All 597 tests passing.
status: complete
```

```yaml
id: 2026-02-02-04
type: fix
areas: [tax, recalculation, services]
summary: "Fix Issue #42: Daily Sessions tax withheld missing after CSV import + Recalculate Everything"
files_changed:
  - services/recalculation_service.py (add tax_withholding_service param to __init__)
  - app_facade.py (pass tax_withholding_service to RecalculationService)
  - ui/tools_workers.py (accept settings_dict; create TaxWithholdingService in worker thread)
  - ui/tabs/tools_tab.py (add _get_settings_dict(); pass settings to all RecalculationWorker calls)
branch: fix/issue-42-tax-withholding-after-recalc
commits: [0ed82f2]
issue: "#42"
pull_request: "#43"
notes: |
  Fixed bug where Daily Sessions tab showed Tax Set-Aside = $0.00 after CSV import +
  "Recalculate Everything", particularly for multi-day sessions. Root cause:
  RecalculationService.rebuild_all() had tax recalculation code but it never executed
  because RecalculationService.__init__() didn't accept tax_withholding_service parameter.
  Worker threads creating their own RecalculationService had no tax service wired.
  
  Solution: Wire tax_withholding_service through the full stack:
  1. RecalculationService now accepts and stores tax_withholding_service
  2. AppFacade passes it when creating RecalculationService
  3. RecalculationWorker accepts settings_dict and creates TaxWithholdingService in thread
  4. ToolsTab extracts settings from MainWindow hierarchy for worker threads
  
  Result: Tax withholding now calculates correctly during full rebuild and post-CSV-import
  recalculation. No more manual Settings → Recalculate Tax needed after import.
  All 591 tests passing.
```

```yaml
id: 2026-02-02-03
type: fix
areas: [ui, tables]
summary: "Fix table rows showing wrong/duplicate data after sorting + refresh/search"
files_changed:
  - ui/tabs/redemptions_tab.py (disable sorting during repopulation; reapply header sort after items are set)
  - ui/tabs/purchases_tab.py (same)
  - ui/tabs/game_sessions_tab.py (same)
  - ui/tabs/unrealized_tab.py (same)
  - ui/tabs/expenses_tab.py (same)
  - ui/tabs/sites_tab.py (same)
  - ui/tabs/cards_tab.py (same)
  - ui/tabs/users_tab.py (same)
  - ui/tabs/games_tab.py (same)
  - ui/tabs/game_types_tab.py (same)
  - ui/tabs/redemption_methods_tab.py (same)
  - ui/tabs/redemption_method_types_tab.py (same)
  - tests/unit/test_redemptions_table_sort_repopulate_consistency.py (NEW: regression test)
branch: main
commits: [pending]
issue: "N/A (user-reported UI data display corruption)"
notes: |
  Fixed a QTableWidget gotcha where leaving sorting enabled (via the header sort menu)
  while repopulating rows can cause the widget to reorder rows mid-population.
  That manifests as mixed columns (e.g., wrong Amount for a Site) and apparent duplicates
  that don't exist in the database.

  The fix temporarily disables sorting + UI updates while setting items, then reapplies
  the active header sort once the table is fully populated.
```

```yaml
id: 2026-02-02-02
type: fix
areas: [redemptions, ui, validation]
summary: "Fix Issue #40: Receipt-date-only redemption updates skip unnecessary balance validation"
files_changed:
  - ui/tabs/redemptions_tab.py (skip balance check in dialog when accounting fields unchanged; detect metadata-only changes in tab)
  - tests/integration/test_issue_40_redemption_receipt_date.py (NEW: 5 integration tests)
branch: fix/issue-40-redemption-receipt-date-warning
commits: [b09081c, b660061, f33ebbf, 2a6269f, c5bb89c, fe866bf]
issue: "#40"
pull_request: "#41"
notes: |
  Fixed bug where updating only metadata fields (receipt_date, processed flag, notes) on a
  redemption would trigger full FIFO reprocessing and balance validation, even though no
  accounting changes occurred. This caused false warnings about session balance mismatches
  when purchases existed after the redemption date.
  
  Root cause: Balance validation was happening in TWO places:
  1. In the dialog's _validate_and_accept() method (runs when user clicks OK)
  2. In the tab's _edit_redemption() method (runs after dialog closes)
  
  The dialog validation was running FIRST and blocking the update before we could detect
  metadata-only changes in the tab.
  
  Solution implemented in two layers:
  
  Layer 1 (Dialog - fe866bf): In RedemptionDialog._validate_and_accept(), skip balance
  validation when editing and accounting fields (amount, user, site, date, time) are unchanged.
  This prevents the session balance warning when only metadata fields change.
  
  Layer 2 (Tab - 2a6269f, earlier commits): In RedemptionsTab._edit_redemption(), detect
  metadata-only changes and route to lightweight update_redemption() instead of 
  update_redemption_reprocess(). Normalize redemption_time comparison (None vs "00:00:00").
  
  Tests cover happy path, edge cases with complex purchase timelines, and verify both paths.
```

```yaml
id: 2026-02-02-01
type: fix
areas: [startup, transactions, data-integrity, ui]
summary: "Fix startup crash on corrupted data + add atomic transaction wrapping"
files_changed:
  - ui/main_window.py (wrap tab creation in try/except to force maintenance mode on data errors)
  - ui/tabs/game_sessions_tab.py (remove orphaned tax_rate_edit reference in EndSessionDialog)
  - app_facade.py (wrap create/update/delete purchase and create redemption in transactions)
branch: main
commits: [pending]
issue: "N/A (urgent bug fix)"
notes: |
  Fixed two critical issues:
  1. App crashed at startup before maintenance mode could activate when corrupted data existed
     (e.g., purchases with remaining_amount > amount). Now wraps tab creation in try/except
     to catch ValueError during data loading and gracefully enter maintenance mode.
  2. Database operations could fail mid-operation, leaving partial writes and corrupted data.
     Added transaction wrapping (with self.db.transaction()) to create_purchase, update_purchase,
     delete_purchase, and create_redemption in AppFacade. Operations now roll back entirely on
     failure, ensuring no partial data corruption.
  
  Discovered 3 corrupted purchases in production DB (remaining_amount > amount), likely from
  previous partial operation failure. Transaction wrapping prevents recurrence.
```

## 2026-02-01

```yaml
id: 2026-02-01-04
type: feature
areas: [data-integrity, services, ui, startup]
summary: "Feature Issue #38: Maintenance mode for data integrity violations at startup"
files_changed:
  - services/data_integrity_service.py (NEW: detect violations with quick mode)
  - ui/maintenance_mode_dialog.py (NEW: user-friendly dialog with violation summary)
  - ui/main_window.py (integrity check before tab creation, restricted tab access)
branch: feature/issue-38-maintenance-mode
commits: [5f41b5e, c502e93]
pr: "#38"
issue: "#38"
notes: |
  Prevents app crashes from data integrity violations (e.g., remaining_amount > amount from
  incomplete CSV imports). At startup, runs quick integrity check and shows user-friendly
  dialog if violations detected. Restricts access to Setup tab only (maintenance mode) until
  user completes imports and runs recalculate. Supports 3 check types: invalid remaining_amount,
  negative amounts, orphaned FKs. Fixed refresh_all_tabs() AttributeError in maintenance mode.
  Critical for multi-session CSV import workflows.
```

```yaml
id: 2026-02-01-03
type: fix
areas: [csv-import, services, tests]
summary: "Fix Issue #36: User-scoped FK resolution for redemption methods and cards in CSV imports"
files_changed:
  - services/tools/fk_resolver.py (scope parameter, clear() method, sqlite3.Row keys() fix)
  - services/tools/csv_import_service.py (user_id scope for redemption_methods and cards)
  - tests/integration/test_csv_import_user_scoped_methods.py (new: 4 integration tests)
  - tests/integration/test_csv_export_integration.py (fix: user_id column on cards table)
branch: fix/issue-36-redemption-method-csv-user-scope
commits: [920e1ff, 2934d14]
pr: "#37"
issue: "#36"
notes: |
  CSV imports were failing when multiple users had redemption methods with the same name
  (e.g., 'USAA Checking'). Added scope filtering to FK resolver to match by user_id context.
  Fixed sqlite3.Row 'in' operator bug - must use .keys() for column existence checks.
  All 585 tests passing.
```

```yaml
id: 2026-02-01-02
type: feature
areas: [tax, database, services, ui]
summary: "Complete Issue #29: Tax withholding with date-level calculation, cascade recalc, and Settings UI."
files_changed:
  - repositories/database.py (daily_date_tax table, daily_sessions uses end_date)
  - services/tax_withholding_service.py (date-level with date range filter)
  - services/game_session_service.py (auto-recalc on close/edit, cascade support)
  - services/recalculation_service.py (end_date grouping, tax recalc in rebuild_all)
  - services/daily_sessions_service.py (fetch from daily_date_tax, show at date level)
  - ui/settings_dialog.py (tax settings + recalc dialog launcher)
  - ui/tax_recalc_dialog.py (date range picker with calendar buttons)
  - ui/tabs/daily_sessions_tab.py (edit button, dialog with tax display)
branch: feature/issue-29-tax-withholding-ui
commits: [multiple]
pr: "#34"
issue: "#29"
```

**Architecture: Date-Level Tax Withholding**
- Tax calculated on NET P/L of ALL users for each date (winners netted against losers)
- Storage: `daily_date_tax` table keyed by `session_date` only
- Example: User1: +$342.61, User2: -$205.55 → Net: $137.06 → Tax: $27.41 (20%)
- Display: Tax shown at date level only (not per-user) in Daily Sessions tab

**Database Schema Changes:**
- **New table: `daily_date_tax`**
  - Primary key: `session_date` (date only, not per-user)
  - Columns: `net_daily_pnl`, `tax_withholding_rate_pct`, `tax_withholding_is_custom`, `tax_withholding_amount`, `notes`
  - Notes migrated from `daily_sessions` table (date-level, not user-level)
- **daily_sessions grouping change:**
  - Now groups by `end_date` instead of `session_date` (when session closed, not started)
  - Critical for multi-day sessions: tax counted on close date
- **game_sessions columns removed:**
  - All `tax_withholding_*` columns removed (tax is date-level only)

**Services Layer:**

`TaxWithholdingService`:
- `apply_to_date(session_date, custom_rate_pct)`: Calculate and store tax for ONE date (nets all users)
- `bulk_recalculate(start_date, end_date, overwrite_custom)`: Batch recalc with optional date range
- `_calculate_date_net_pl(session_date)`: Sum ALL users' P/L for date from daily_sessions
- Respects custom rates unless `overwrite_custom=True`

`GameSessionService`:
- Auto-recalc on session close: Syncs daily_sessions + recalcs tax for end_date
- Auto-recalc on session edit: Recalcs tax for affected dates (old + new if date changed)
- `_sync_tax_for_affected_dates()`: NEW - called after cascade recalcs (purchase/redemption edits)
- Ensures tax stays accurate during FIFO rebuilds and session recalculations

`RecalculationService`:
- `rebuild_all()`: Now includes tax recalculation in full rebuild workflow
- Uses `end_date` grouping for daily_sessions (not `session_date`)

`DailySessionsService`:
- `fetch_daily_tax_data()`: Queries `daily_date_tax` table for display
- `group_sessions()`: Shows tax at date level, $0.00 at user level

**UI Changes:**

Settings Dialog (`ui/settings_dialog.py`):
- **Tax Withholding section added:**
  - Enable/disable toggle
  - Default rate percentage (with validation)
  - "Recalculate Tax Withholding" button launches dialog

Tax Recalc Dialog (`ui/tax_recalc_dialog.py`):
- **Date range filter with calendar pickers:**
  - From/To date fields with 📅 calendar buttons
  - Clear buttons for each date
  - Leave empty to recalculate all dates
- **Options:**
  - Overwrite custom rates checkbox
- **Removed:** Site/user filters (incompatible with date-level netting)
- Confirmation dialog shows scope and settings

Daily Sessions Tab (`ui/tabs/daily_sessions_tab.py`):
- **Date-level actions:**
  - "✏️ Edit" button (was "+Add Notes")
  - Edit dialog shows: Net P/L (blue), Tax Amount (red), Tax Rate, Notes
  - Tax fields read-only (use Settings to recalc)
- **User-level actions:**
  - Removed edit button (no user-level tax data)
- **Display:**
  - Tax withholding shown at date level only
  - User rows show $0.00 for tax (not calculated per-user)

**Tax Recalculation Triggers:**

1. **Session closed:** Scoped to end_date
2. **Session edited (already closed):** Scoped to affected date(s)
3. **Purchase/redemption edited:** Cascade recalc triggers tax update for all affected dates
4. **Settings → Recalculate Tax Withholding:** Optional date range filter
5. **Tools → Recalculate Everything:** Full rebuild including tax (all dates)

**Migration Path:**
- Old `game_sessions.tax_withholding_*` columns removed
- Old `daily_sessions.notes` migrated to `daily_date_tax.notes`
- Tax recalculated on first "Recalculate Everything" after upgrade
- No data loss: old tax estimates discarded (date-level netting more accurate)

**Testing:**
- All 580 tests passing
- Tax calculation scenarios validated (net-first, not per-user-first)
- Cascade scenarios covered (purchase/redemption edits trigger tax updates)
- Date range filtering tested

**Benefits:**
- **Accurate:** Tax calculated on net P/L (losses offset gains)
- **Automatic:** Updates on session close, edit, and cascade recalcs
- **Flexible:** Date range filtering for targeted recalculation
- **Transparent:** Clear display in Daily Sessions tab
- **Compliant:** Settings UI for rate configuration and bulk operations

```yaml
id: 2026-02-01-01
type: fix
areas: [repositories, tests, ui]
summary: "Complete tax withholding test fixes and repository cleanup for daily-only semantics."
files_changed:
  - repositories/game_session_repository.py (remove tax column references from INSERT/UPDATE)
  - repositories/database.py (add tax columns to daily_sessions CREATE TABLE)
  - tests/unit/test_tax_withholding_service.py (rewrite for daily_sessions)
  - ui/tax_recalc_dialog.py (update messaging to 'daily sessions')
branch: feature/issue-29-tax-withholding-ui
commits: 644609d
pr: "#34"
issue: "#29"
```

Notes:
- **Problem:** Tests failing after tax refactor; game_session_repository still trying to INSERT/UPDATE removed columns
- **game_session_repository fixes:**
  - Removed tax_withholding_* columns from INSERT statement (25 params → 22 params)
  - Removed tax_withholding_* columns from UPDATE statement
  - Set tax fields to None/False in _row_to_model (columns no longer exist in DB)
- **database.py fix:**
  - Added tax columns to daily_sessions CREATE TABLE statement
  - Previously only added via migration (for existing DBs)
  - Fresh test databases now include tax columns by default
- **test_tax_withholding_service.py rewrite:**
  - Changed from game_sessions to daily_sessions table
  - Updated _insert_daily_session helper (no site_id, keyed by date+user)
  - Fixed queries to use (session_date, user_id) primary key instead of id
  - Fixed type assertions: 20.0 (float) not "20.00" (string)
- **tax_recalc_dialog.py:**
  - Updated UI messaging: "daily sessions" instead of "closed sessions"
  - Updated tooltips and confirmation dialogs
- **Result:** All 580 tests passing
- **Deferred:** Edit Daily Session dialog with per-day tax override (users can use bulk recalc tool for now)

## 2026-01-31

```yaml
id: 2026-01-31-17
type: refactor
areas: [database, services, ui, tax]
summary: "Complete tax withholding refactor: move from game sessions to daily sessions only."
files_changed:
  - repositories/database.py (add tax columns to daily_sessions, remove from game_sessions)
  - services/tax_withholding_service.py (rewrite for daily-only semantics)
  - services/daily_sessions_service.py (add fetch_daily_tax_data, update group_sessions)
  - ui/tabs/game_sessions_tab.py (remove tax UI from all dialogs)
  - ui/tabs/daily_sessions_tab.py (fetch and display daily tax data)
branch: feature/issue-29-tax-withholding-ui
commits: 153cdf0, 22c3925, 3a0220a
pr: "#34"
issue: "#29"
```

Notes:
- **Problem:** Tax withholding was stored per-game-session but taxable events are daily rollups, causing incorrect totaling
- **Solution:** Complete architectural change to daily-only tax withholding
- **Database changes:**
  - Added `tax_withholding_rate_pct`, `tax_withholding_is_custom`, `tax_withholding_amount` to `daily_sessions` table
  - Removed all tax columns from `game_sessions` CREATE TABLE statement
  - Migration tested: columns added successfully to existing databases
- **Service layer changes:**
  - `TaxWithholdingService`: Removed `apply_to_session_model()`, added `apply_to_daily_session(session_date, user_id, net_daily_pl, custom_rate_pct)`
  - `TaxWithholdingService.bulk_recalculate()`: Now targets `daily_sessions` table, respects custom rates
  - `DailySessionsService.fetch_daily_tax_data()`: NEW - queries daily_sessions for tax data by (date, user)
  - `DailySessionsService.group_sessions()`: Updated to accept daily_tax_data parameter, calculate tax at user+date level
- **UI changes:**
  - Removed ~270 lines of tax UI from EditClosedSessionDialog, EndSessionDialog, ViewSessionDialog
  - Daily Sessions tab: Fetches daily tax data, displays at user+date level only
  - Individual sessions and sites show dash (—) in tax column (tax not applicable at those levels)
- **Semantics:** Tax withholding now calculated from daily net P/L: `max(0, net_daily_pl) × (rate_pct/100)` for each (date, user) pair
- **Validation:** App starts without errors, data flow tested
- **Remaining work:** Add Edit Daily Session dialog with tax override, update bulk recalc dialog UI, fix/update tests

```yaml
id: 2026-01-31-16
type: fix
areas: [services, ui, tax]
summary: "Include tax withholding data in daily sessions query for proper display."
files_changed:
  - services/daily_sessions_service.py (add tax fields to query and session dictionary)
```

Notes:
- **Issue:** Tax withholding amounts showing as blank/not displaying in Daily Sessions tab
- **Root cause:** Query in `fetch_sessions()` didn't include tax withholding fields from database
- **Fix:** Added tax_withholding_amount, tax_withholding_rate_pct, and tax_withholding_is_custom to SELECT
- **Result:** Tax Set-Aside column now displays correct amounts for all sessions
- **EditClosedSessionDialog:** Already loads and displays tax values correctly - tax fields show custom rates and computed amounts when editing closed sessions
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-15
type: fix
areas: [ui, tax]
summary: "Fix tax column not appearing at startup and site/user dropdowns not populating."
files_changed:
  - ui/tabs/daily_sessions_tab.py (add showEvent to rebuild columns when tab shown)
  - ui/tax_recalc_dialog.py (fix facade method calls for site/user loading)
```

Notes:
- **Issue 1:** Tax Set-Aside column now appears correctly at startup when enabled
  - Added `showEvent()` override to DailySessionsTab
  - Rebuilds columns when tab is first shown to ensure settings are loaded
  - Previously columns were built during `__init__` before settings were fully initialized
  - Now column structure is refreshed when tab becomes visible
- **Issue 2:** Site/User dropdowns now populate correctly in TaxRecalcDialog
  - Fixed method calls from `facade.site_service.get_all_sites()` to `facade.get_all_sites()`
  - Fixed method calls from `facade.user_service.get_all_users()` to `facade.get_all_users()`
  - Dropdowns now show all available sites and users with placeholder text
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-14
type: fix
areas: [ui, tax]
summary: "Reorder tax fields in EndSessionDialog to match EditClosedSessionDialog layout."
files_changed:
  - ui/tabs/game_sessions_tab.py (move tax fields after Game Type/Game in EndSessionDialog)
```

Notes:
- **Purpose:** Consistent field ordering across End and Edit dialogs
- **Change:** Tax withholding fields now positioned after Game Type/Game in EndSessionDialog
- **Previous order:** Net P/L → Tax fields → Game Type/Game → RTP
- **New order:** Net P/L → Game Type/Game → Tax fields → RTP
- **Matches:** EditClosedSessionDialog layout (Session Details section)
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-13
type: fix
areas: [ui, tax]
summary: "Fix tax withholding UI issues: styling, field visibility, layout reordering."
files_changed:
  - ui/tabs/game_sessions_tab.py (fix ViewSessionDialog styling, add field visibility logic, reorder fields in EditClosedSessionDialog)
```

Notes:
- **Issue 1:** ViewSessionDialog "Tax Set-Aside" label now matches "Net P/L:" styling (font-weight: bold)
- **Issue 2:** Fixed AttributeError in EditClosedSessionDialog - tax fields already exist and are properly initialized
- **Issue 3:** Tax withholding fields now hidden when feature is disabled
  - Added visibility logic to both EndSessionDialog and EditClosedSessionDialog
  - Fields check `facade.tax_withholding_service.get_config().enabled` at init
  - Labels and inputs hidden via `setVisible(False)` when disabled
- **Issue 4:** Reordered fields in EditClosedSessionDialog to improve UX
  - Moved tax withholding fields below Game Type/Game in Session Details section
  - Moved Wager and RTP to Balance Details section (after Balance Check)
  - Dialog height already increased to 700px to accommodate fields
  - Tax fields appear after Game Type/Game as requested
- **User Experience:** When tax withholding is disabled in Settings, tax input fields don't appear in End/Edit dialogs
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-12
type: feature
areas: [ui, tax]
summary: "Add dynamic column refresh for Daily Sessions when tax settings change."
files_changed:
  - ui/tabs/daily_sessions_tab.py (add rebuild_columns method for dynamic column updates)
  - ui/main_window.py (call rebuild_columns when settings dialog closes)
```

Notes:
- **Purpose:** Tax Set-Aside column now dynamically shows/hides when tax withholding feature is enabled/disabled in Settings
- **Implementation:**
  - Added `rebuild_columns()` method to DailySessionsTab that:
    - Rebuilds the columns list based on current tax withholding feature state
    - Updates tree widget column count and headers
    - Refreshes data to re-render with new columns
  - Updated MainWindow._show_settings_dialog() to call `rebuild_columns()` after settings are saved
  - Column structure is now rebuilt immediately when settings change (no app restart required)
- **User Experience:** Toggle tax withholding checkbox in Settings → Save → Daily Sessions column appears/disappears instantly
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-11
type: fix
areas: [ui, tax]
summary: "Fix tax recalc dialog dropdowns and add EditClosedSessionDialog tax fields."
files_changed:
  - ui/tax_recalc_dialog.py (use placeholder text for Site/User combo boxes, handle empty selections as 'all')
  - ui/tabs/game_sessions_tab.py (add tax withholding fields to EditClosedSessionDialog with real-time calculation)
```

Notes:
- **Issue 1:** Site/User dropdowns in tax recalc dialog now populate correctly
  - Removed "All Sites" and "All Users" as items in combo boxes
  - Made them placeholder text only (displayed when combo box is empty)
  - Empty/blank selection now treated as "all" (null filter)
  - `_on_recalculate()` handles empty `currentText()` by checking item data by text
- **Issue 2:** EditClosedSessionDialog now has full tax withholding override support
  - Added `tax_rate_edit` (optional % override input) and `tax_amount_display` (computed amount display)
  - Added `_update_tax_withholding_display()` method for real-time calculation as user edits balances
  - Connected all relevant fields (start_total, end_total, start_redeem, end_redeem) to trigger tax updates
  - Modified `_load_session()` to load existing custom rate if `tax_withholding_is_custom` is true
  - Modified `collect_data()` to persist custom rate and is_custom flag
  - UI layout matches EndSessionDialog pattern
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-10
type: fix
areas: [ui, tax]
summary: "Fix tax withholding UI issues (column visibility, combo boxes, custom override location)."
files_changed:
  - ui/tabs/daily_sessions_tab.py (conditionally show Tax Set-Aside column only when feature enabled)
  - ui/tax_recalc_dialog.py (make Site/User dropdowns editable/searchable combo boxes)
```

Notes:
- **Issue 1:** Tax Set-Aside column now hidden when tax withholding is disabled in Settings
  - Column list built dynamically based on `facade.tax_withholding_service.get_config().enabled`
  - All column index references updated to handle dynamic column presence
  - Column width adjustments handled automatically
- **Issue 2:** TaxRecalcDialog Site/User dropdowns converted to editable/searchable combo boxes
  - Added `setEditable(True)` and `setInsertPolicy(NoInsert)` for type-ahead autocomplete
  - Matches pattern used in AddPurchaseDialog
- **Issue 3:** Custom override field location clarified
  - Field exists in EndSessionDialog at line 3734: "Tax Withholding % (optional)"
  - Positioned after Net P/L, before Game Type/RTP
  - User can enter custom rate or leave blank for default
- **Tests:** All 580 tests passing

```yaml
id: 2026-01-31-09
type: feature
areas: [ui, tax]
summary: "Complete Issue #29 deferred UI items: per-session override + Daily Sessions column."
files_changed:
  - ui/tabs/game_sessions_tab.py (add withholding fields to EndSessionDialog + ViewSessionDialog)
  - ui/tabs/daily_sessions_tab.py (add Tax Set-Aside column to Daily Sessions tab)
  - services/daily_sessions_service.py (aggregate tax_withholding_amount at date/user/site levels)
```

Notes:
- **Purpose:** Complete Issue #29 by adding the "deferred" UI polish items (previously noted as non-blocking).
- **Changes:**
  - **EndSessionDialog:**
    - Added "Tax Withholding % (optional)" input field (QLineEdit, user can override default rate).
    - Added "Tax Withholding (est.)" display (QLabel ValueChip, shows computed amount in real-time).
    - Fields positioned after Net P/L, before Game Type/RTP.
    - Real-time calculation: `_update_tax_withholding_display(net_pl)` updates amount as user types.
    - `collect_data()` now captures custom rate and sets `tax_withholding_is_custom` flag.
  - **ViewSessionDialog:**
    - Added read-only "Tax Set-Aside" row in Balances/Outcomes table (shows rate used, amount, and "(custom)" suffix if applicable).
    - Only displays if feature enabled and session is closed.
  - **Daily Sessions tab:**
    - Added "Tax Set-Aside" column (index 6, between Net P/L and Details).
    - Shows aggregated withholding amounts at date/user/site/session levels.
    - Column sorting and filtering supported.
  - **Service layer:**
    - `daily_sessions_service.group_sessions()` now computes `tax_withholding` aggregates at user/site/date levels.
- **Workflow:**
  - User ends session → sees optional override rate field → can customize withholding for this session or leave blank for default.
  - Viewing closed sessions → see tax withholding details in dialog and Daily Sessions summary.
- **Tests:** All 580 tests passing (no new tests; UI-only additions; backend logic already tested).
- **PR:** #34 (Issue #29 complete — Settings UI + deferred UI items)

```yaml
id: 2026-01-31-08
type: feature
areas: [ui, settings, tax]
summary: "Complete tax withholding estimates Settings UI + bulk recalc (Issue #29, Part 2)."
files_changed:
  - ui/settings_dialog.py (replace placeholder with enable toggle, default rate spinner, recalc button)
  - ui/tax_recalc_dialog.py (new, bulk recalculation UI with site/user filters + overwrite-custom option)
  - ui/main_window.py (wire settings to tax_withholding_service on startup)
  - docs/PROJECT_SPEC.md (update § 6.5 tax withholding to reflect completed state)
```

Notes:
- **Purpose:** Provide user-facing controls for tax withholding estimates (Issue #29 Part 2).
- **Architecture:**
  - Settings → Taxes section: enable/disable toggle, default rate (%) spinner (0-100, 0.1 step), "Recalculate Withholding…" button.
  - TaxRecalcDialog: filters by site/user (dropdowns), "Overwrite custom rates" checkbox, confirmation prompt with scope summary.
  - MainWindow init: wires `self.settings` to `facade.tax_withholding_service.settings` so service can read config.
- **Workflow:**
  - Enable withholding estimates → enter default rate → close sessions (withholding computed automatically).
  - Bulk recalc: select scope/filters → confirm → updates historical closed sessions atomically.
- **Deferred to follow-up:**
  - Per-session override UI (field in session editor dialogs for custom withholding %).
  - Daily Sessions column/aggregates ("Tax set-aside (est.)" display).
  - Both deferred items are non-blocking; backend is ready (values stored/computed); just UI display left.
- **Tests:** All 580 tests passing (no new tests; backend tested in Part 1 PR #32).
- **PR:** TBD (Issue #29, Part 2 — enables closing Issue #29)

```yaml
id: 2026-01-31-05
type: feature
areas: [notifications, ui, services]
summary: "Add notification system with bell widget and periodic evaluation (Issue #28)."
files_changed:
  - models/notification.py (new, Notification model with severity/state)
  - services/notification_service.py (new, CRUD + state management)
  - repositories/notification_repository.py (new, JSON persistence to settings.json)
  - services/notification_rules_service.py (new, backup + redemption rules)
  - ui/notification_widgets.py (new, bell + notification center + item widgets)
  - ui/main_window.py (integrate bell, periodic QTimer)
  - app_facade.py (wire notification services)
  - tests/test_notification_service.py (new, 19 unit tests)
  - docs/PROJECT_SPEC.md (add notification system section 6.4)
```

Notes:
- **Purpose:** Passive, persistent notifications for backup reminders and redemption pending-receipt tracking. No modal popups.
- **Architecture:**
  - Notification model: severity (INFO/WARNING/ERROR), state (read/dismissed/snoozed/deleted), composite key de-duplication (type + subject_id).
  - NotificationService: CRUD, state transitions (mark_read/unread, dismiss, snooze, delete), bulk operations.
  - NotificationRepository: JSON persistence to settings.json (v1; future split to DB-backed for scalability).
  - NotificationRulesService: evaluates backup rules (directory missing, backup due/overdue) and redemption rules (pending receipt > threshold).
- **UI:**
  - Notification bell: lightweight overlay button (no pill background) pinned to the main content inset; shows a red badge when unread > 0.
  - NotificationCenterDialog: grouped sections (Unread / Read / Snoozed) with collapsible headers.
  - Per-item actions: Open (when available), Snooze, Dismiss, Delete, Mark Read, Mark Unread.
  - Badge count updates immediately after dialog actions.
  - macOS theme fix: dialog/scroll viewport forced to paint theme "surface" to avoid dark palette bleed.
  - Periodic evaluation: startup + hourly QTimer.
- **Rules:**
  - Backup: Creates notifications when automatic backup enabled but directory missing, or last backup > frequency threshold.
  - Redemption pending-receipt: Queries redemptions where `receipt_date IS NULL` and older than the configured threshold days; one notification per redemption.
  - Auto-dismiss when conditions resolve (backup completed, redemption received).
- **Tests:** 19 unit tests covering CRUD, de-duplication, state transitions, unread count, bulk operations. All passing.
- **Future:** Integration tests for rule evaluators, headless UI smoke test, split persistence (DB vs settings).
- **Issue:** #28

```yaml
id: 2026-01-31-06
type: feature
areas: [accounting, services, models, repositories]
summary: "Add tax withholding estimates foundation (Issue #29, Part 1/2)."
files_changed:
  - models/game_session.py (add tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount)
  - repositories/database.py (add game_sessions columns + migration)
  - repositories/game_session_repository.py (persist withholding fields)
  - services/tax_withholding_service.py (new, config + compute + bulk recalc)
  - services/game_session_service.py (wire withholding into closed-session recalc)
  - app_facade.py (construct TaxWithholdingService, pass to GameSessionService)
  - tests/unit/test_tax_withholding_service.py (new, 6 unit tests including rollback)
```

Notes:
- **Purpose:** Store and compute per-session tax withholding estimates for informational tax planning (not legal advice).
- **Architecture (Part 1 — backend foundation):**
  - GameSession model: adds `tax_withholding_rate_pct` (Decimal), `tax_withholding_is_custom` (bool), `tax_withholding_amount` (Decimal).
  - DB schema + migration: new columns in `game_sessions`; ALTER TABLE path for existing DBs.
  - TaxWithholdingService: computes `max(0, net_taxable_pl) * (rate / 100)` with Decimal rounding; provides config parsing, apply-to-session, and bulk recalculation.
  - Bulk recalc: transactional, atomic; updates only withholding columns; skips custom-rate sessions unless `overwrite_custom=True`.
  - GameSessionService: optionally calls `apply_to_session_model()` after computing `net_taxable_pl` for closed sessions.
- **Config (placeholder):** Settings keys planned: `tax_withholding_enabled` (bool), `tax_withholding_default_rate_pct` (float).
- **Tests:** 6 unit tests (compute positive/zero/negative, bulk recalc, skip custom, rollback atomicity). All 579 tests passing.
- **Part 2 (pending):** UI + wiring (Settings controls, per-session override in session editor, Daily Sessions column/aggregates, bulk recalc dialog).
- **PR:** #32 (Issue #29, Part 1 — does not close Issue #29)

```yaml
id: 2026-01-31-07
type: feature
areas: [ui, settings]
summary: "Add Settings entry point: gear icon + dialog shell + notification badge (Issue #31)."
files_changed:
  - ui/settings_dialog.py (new, Settings dialog with Notifications + Taxes sections)
  - ui/notification_widgets.py (notification bell with widget-based pill badge)
  - ui/main_window.py (add gear button overlay + bell overlay, wire Settings dialog, badge z-order management)
  - tests/integration/test_settings_dialog_smoke.py (new, headless UI smoke test)
  - requirements.txt (add pytest-qt)
```

Notes:
- **Purpose:** Provide a first-class Settings entry point for notifications configuration and future cross-cutting features (like Issue #29 tax withholding estimates).
- **Architecture:**
  - SettingsDialog: left-nav + stacked content sections (Notifications, Taxes placeholder).
  - Notifications section: `redemption_pending_receipt_threshold_days` spinner (0..365 days).
  - Taxes section: placeholder message for Issue #29 (no functionality yet).
  - Settings persistence: uses existing `ui/settings.py` → `settings.json`.
- **UI:**
  - Settings gear button: 32x32 pill overlay pinned to top-right of main content inset, matches bell styling.
  - Notification bell: includes scalable badge overlay (QLabel) with pill styling; counts cap at "10+"; non-bold, centered text; left edge anchored to bell's horizontal center for stable growth to the right; badge raised above bell/gear via explicit z-order management in MainWindow.
  - Badge styling iterations: increased vertical padding (+1px); decreased font size (-1px); rounded pill shape.
  - Testing override: `SEZZIONS_FORCE_BADGE_TEXT` environment variable to force badge text for UI verification.
- **Tests:** headless UI smoke test passes; full suite (580 tests) passing.
- **PR:** #33
- **Issue:** #31
  - Gear icon (⚙️): transparent button overlay, pinned to the left of the notification bell.
  - Positioning: same top margin as bell; dynamically placed via `_position_notification_bell()`.
  - Settings dialog: modal, ESC to close, Cancel/Save buttons.
  - Saving: persists immediately to `settings.json`; notification rules re-evaluated after close.
- **Tests:** 1 headless UI smoke test (MainWindow → gear exists → dialog can open/close). All 580 tests passing.
- **Future:** Issue #29 will add tax withholding controls to the Taxes section.
- **Issue:** #31

```yaml
id: 2026-01-31-04
type: bug-fix
areas: [ui, ux]
summary: "Add Clear button to notes dialogs; fix Expenses tab selection/actions (Issue #26)."
files_changed:
  - ui/tabs/realized_tab.py (add Clear button to RealizedDateNotesDialog)
  - ui/tabs/unrealized_tab.py (add Clear button to UnrealizedNotesDialog)
  - ui/tabs/daily_sessions_tab.py (add Clear button to DailySessionNotesDialog)
  - ui/tabs/expenses_tab.py (change SelectItems to SelectRows)
```

Notes:
- **Problem 1:** Notes dialogs for Daily Sessions, Unrealized, and Realized tabs lacked a Clear button (only Cancel/Save).
- **Problem 2:** Expenses tab selection didn't reveal View/Edit/Delete buttons; double-click had no effect.
- **Root Cause:** Expenses table used `SelectItems` behavior, so `selectedRows()` was always empty.
- **Solution:**
  - Added `🧹 Clear` button to all three notes dialogs, positioned between Cancel and Save.
  - Changed Expenses table to `SelectRows` selection behavior.
- **Result:** Clear button provides one-click note reset; Expenses tab now shows action buttons and supports double-click to view.
- **Tests:** All 554 tests passing.
- **PR:** #27 (Issue #26)

```yaml
id: 2026-01-31-03
type: bug-fix
areas: [architecture, layering, services]
summary: "Fix UI→DB layering violations (Issue #23)."
files_changed:
  - services/realized_notes_service.py (new)
  - services/redemption_service.py (add get_deletion_impact method)
  - services/game_session_service.py (add get_deletion_impact method)
  - app_facade.py (wire up realized_notes_service)
  - ui/tabs/realized_tab.py (use service instead of direct SQL)
  - ui/tabs/redemptions_tab.py (use service instead of cursor access)
  - ui/tabs/game_sessions_tab.py (use service instead of cursor access)
  - tests/unit/test_realized_notes_service.py (new, 9 tests)
```

Notes:
- **Problem:** UI tabs directly executed SQL or accessed repository cursors (layering violation)
- **Evidence:**
  - `realized_tab.py`: Direct `self.db.execute()` for daily notes CRUD
  - `redemptions_tab.py`: Direct cursor access via `self.facade.redemption_repo.db._connection.cursor()`
  - `game_sessions_tab.py`: Direct cursor access for deletion impact checks
- **Solution:**
  - Created `RealizedNotesService` for daily notes CRUD operations
  - Added `get_deletion_impact(id)` methods to `RedemptionService` and `GameSessionService`
  - Updated UI tabs to call service methods via `AppFacade`
  - All direct SQL/cursor access removed from UI layer
- **Tests:** Added 9 unit tests for RealizedNotesService (554 total tests passing)
- **Architecture:** Enforces UI → Service → Repository layering
- **PR:** #25 (Issue #23)

```yaml
id: 2026-01-31-02
type: decision
areas: [architecture, rollback]
summary: "QTableView migration rejected - reverted PR #24 (Issue #15 closed as won't do)."
files_changed:
  - docs/adr/0002-qtableview-migration-rejected.md (new)
  - ui/tabs/sites_tab.py (reverted to QTableWidget)
  - tests/ui/test_sites_tab_qtableview.py (removed)
  - docs/status/CHANGELOG.md
```

Notes:
- **Decision:** Do NOT migrate tabs from QTableWidget to QTableView
- **Rationale:**
  - Critical functionality loss: TableHeaderFilter (per-column filtering UI) incompatible with QTableView
  - Weak benefits without inline editing (which was removed from scope)
  - Trade-off: Lost user-facing features for minimal architectural improvement
  - This is architecture for architecture's sake without concrete need
- **Actions:**
  - Closed PR #24 without merge
  - Closed Issue #15 as "won't do"
  - Reverted Sites tab to QTableWidget
  - Infrastructure code (BaseTableModel, SpreadsheetUX QTableView support) remains but unused
- **ADR:** See `docs/adr/0002-qtableview-migration-rejected.md` for full rationale
- **If Revisited:** Only if we implement inline editing OR solve column filtering UI for QTableView

```yaml
id: 2026-01-31-01
type: feature
areas: [ui, architecture, tests]
summary: "Add spreadsheet UX with cell selection, copy, and statistics (Issue #14, Phase 1)."
files_changed:
  - ui/spreadsheet_ux.py (new, 325 lines)
  - ui/spreadsheet_stats_bar.py (new, 95 lines)
  - tests/unit/ui/test_spreadsheet_ux.py (new, 32 tests)
  - tests/unit/ui/widgets/test_spreadsheet_stats_bar.py (new, 7 tests)
  - ui/tabs/*.py (14 tabs integrated)
  - docs/status/CHANGELOG.md
  - docs/PROJECT_SPEC.md
```

Notes:
- **Spreadsheet UX Module** (`ui/spreadsheet_ux.py`):
  - Excel-like cell-level selection with multi-cell highlights
  - Copy selection to clipboard as TSV (Tab-Separated Values) via Cmd+C
  - Context menu: Copy, Copy With Headers
  - Selection statistics: Count, Numeric Count, Sum, Avg, Min, Max
  - Currency parsing: handles `$1,234.56`, `(123.45)`, `100%`, `N/A`, empty strings
  - Widget-agnostic: supports QTableWidget (11 tabs) and QTreeWidget (2 tabs)
  - Phase 1: Read-only features (no inline editing or paste yet)

- **Stats Bar Widget** (`ui/spreadsheet_stats_bar.py`):
  - Horizontal layout showing 6 statistics for current selection
  - Format-neutral: works with currency, percentages, raw numbers
  - Updates dynamically on selection change

- **QTreeWidget Support** (Daily Sessions, Realized):
  - Qt limitation: QTreeWidget doesn't support true cell-level selection
  - Workaround: Detect single-cell clicks using `currentColumn()` and `currentItem()`
  - Single-cell selection → extracts only clicked column value for stats
  - Multi-selection → falls back to full row extraction (all columns)
  - Added `setSelectionBehavior(SelectItems)` for visual consistency

- **14 Tabs Integrated**:
  - **QTableWidget (11 tabs)**: Purchases, Redemptions, Games, Game Types, Sites, Users, Cards, Redemption Methods, Redemption Method Types, Unrealized, Game Sessions, Expenses
  - **QTreeWidget (2 tabs)**: Daily Sessions, Realized
  - All tabs: Cell selection, Cmd+C copy, context menu, stats bar integration
  - Selection logic: `_get_selected_row_numbers()` for action button visibility
  - Stats updates: `_on_selection_changed()` handlers update stats bar on selection

- **Tests**: 39 new tests (32 core + 7 widget)
  - Core: Currency parsing, TSV formatting, grid extraction, stats computation
  - Widget: Stats bar display, format handling, empty/numeric/mixed scenarios
  - All 545 tests passing

- **Implementation Fixes** (this session):
  - Fixed runtime errors: Moved methods from dialog classes to main tab classes
  - Fixed clipboard operations: Extract grid first, then pass to clipboard (not widget)
  - Fixed tree cell detection: `currentColumn()` approach for single-cell statistics
  - Fixed selection handlers: Added stats bar updates to all tabs
  - Fixed corrupted method definitions: Restored missing `def` statements (4 tabs)
  - Fixed old method references: Replaced `_get_fully_selected_rows()` with `_get_selected_row_numbers()`

- **Future Work** (Phase 2/3, separate issues):
  - Inline cell editing
  - Paste from clipboard
  - Advanced selection (Shift+Click, range selection)
  - Export with selection preserved

---

## 2026-01-30

```yaml
id: 2026-01-30-03
type: bugfix
areas: [ui, services, tests]
summary: "Fix recalculation crash and TableHeaderFilter AttributeError (Issue #20, PR #21)."
files_changed:
  - services/recalculation_service.py
  - ui/tools_workers.py
  - ui/tabs/tools_tab.py
  - ui/table_header_filters.py
  - tests/integration/test_issue_20_recalc_completion.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Recalculation Crash Fix**: `AttributeError: 'RebuildResult' object has no attribute 'operation'`
  - Added optional `operation: Optional[str]` field to `RebuildResult` dataclass
  - `RecalculationWorker.run()` uses `dataclasses.replace(result, operation=self.operation)` to pass operation through
  - `ToolsTab._on_recalculation_finished()` uses `getattr(result, 'operation', 'all')` for backward compatibility
  - Crash prevented `emit_data_changed()` from completing, masking Games tab RTP auto-refresh
- **Games Tab RTP Auto-Refresh**: Now works via Issue #9 event system
  - Recalculation completion → emits `DataChangeEvent` → MainWindow → setup_tab → games_tab.refresh_data()
  - Fixing crash allowed event emission to complete, automatically fixing RTP refresh
- **TableHeaderFilter AttributeError**: Fixed Qt cleanup race condition
  - Added `hasattr(self, 'table')` guard before accessing `self.table` in `eventFilter()`
  - Prevents AttributeError during widget destruction (common in tests)
- **Tests**: 10 new tests in `test_issue_20_recalc_completion.py`
  - RebuildResult operation field contract (3 tests)
  - RecalculationWorker operation propagation (2 tests)
  - ToolsTab completion handling with/without operation field (3 tests)
  - Games tab refresh contract and event integration (2 tests)
  - All 506 tests passing cleanly (no AttributeError warnings)

```yaml
id: 2026-01-30-01
type: feature
areas: [architecture, ui, services, tests]
summary: "Unified global refresh system with event-driven debouncing and maintenance mode (Issue #9, PR #17)."
files_changed:
  - app_facade.py
  - services/data_change_event.py
  - ui/main_window.py
  - ui/tabs/daily_sessions_tab.py
  - ui/tabs/realized_tab.py
  - ui/tabs/game_sessions_tab.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_issue_9_global_refresh.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Event-Driven Architecture**: Introduced `DataChangeEvent` with operation types and affected tables
  - Single notification channel via `AppFacade.emit_data_changed()`
  - All tabs register listeners via `AppFacade.add_data_change_listener()`
  - Replaces fragmented direct refresh calls and ad-hoc signals
- **Debounced Refresh**: MainWindow debounces rapid events (250ms window) to prevent refresh storms
  - Uses QTimer single-shot mechanism
  - Multiple rapid events (e.g., CSV imports) trigger only one UI refresh
  - Improves UX during bulk operations
- **Standardized Tab Contract**: All tabs now expose `refresh_data()` method
  - DailySessionsTab, RealizedTab, GameSessionsTab, ToolsTab
  - Consistent refresh API across the application
  - MainWindow calls `refresh_data()` on all tabs when events fire
- **Maintenance Mode**: AppFacade coordinates write-blocking during destructive operations
  - `enter_maintenance_mode()` / `exit_maintenance_mode()` wrap reset/restore flows
  - Prevents mid-operation writes that could corrupt state
  - Safe coordination of long-running database operations
- **Tools Integration**: Tools operations (CSV import, recalc, restore, reset) emit unified events
  - Replaced `ToolsTab.data_changed` signal with facade events
  - Consistent event emission across all data-modifying operations
- **Testing**: New integration test suite `test_issue_9_global_refresh.py` with 11 tests:
  - Event propagation and listener registration
  - Maintenance mode write blocking
  - Tab refresh contract verification
  - All 496 tests pass

Architecture Benefits:
- Single source of truth for data change notifications
- Decoupled components (tabs don't directly call each other)
- Predictable refresh behavior (debounced, ordered)
- Safe coordination of destructive operations
- Scalable event-driven design

Refs: Issue #9, PR #17

```yaml
id: 2026-01-30-02
type: fix
areas: [ui, tools, tests]
summary: "ResetDialog button gating and API regressions fixed; comprehensive test coverage added (Issue #18, PR #19)."
files_changed:
  - ui/tools_dialogs.py
  - tests/unit/test_reset_dialog.py
  - tests/integration/test_reset_database_flow.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Bug Context**: ResetDialog had regressed during RestoreDialog sizing refactors (copy/paste bleed)
  - Missing `should_preserve_setup()` API method
  - Broken button gating logic (referenced restore-only `_is_updating_size` attribute)
  - Reset workflow was unusable (button never enabled, crashes on dialog accept)
- **Fixes Applied** (in PR #17, then locked by tests in PR #19):
  - Restored `ResetDialog._update_button_state()` to only check checkbox + "DELETE" text
  - Restored `ResetDialog.should_preserve_setup()` API for Tools tab reset flow
  - Removed restore-dialog sizing logic from ResetDialog
- **Test Coverage Added** (PR #19):
  - **Unit tests** (`test_reset_dialog.py`): 17 tests
    - Button gating: checkbox + "DELETE" confirmation (case-insensitive, whitespace-tolerant)
    - API contract: `should_preserve_setup()` reflects checkbox state
    - Invariants: no restore-only attributes in ResetDialog
  - **Integration smoke tests** (`test_reset_database_flow.py`): 8 tests
    - Headless dialog construction and API validation
    - Tools tab can construct dialog and read options without exceptions
    - Reset flow invariants verified
- **All 496 tests pass** (100% pass rate)
- **Regression Prevention**: Tests explicitly guard against:
  - Missing `should_preserve_setup()` (AttributeError from Tools tab)
  - Missing `_is_updating_size` (AttributeError from button update)
  - Copy/paste bleed from other dialogs

Refs: Issue #18, PR #19

---

## 2026-01-29

```yaml
id: 2026-01-29-01
type: feature
areas: [tools, services, ui, architecture]
summary: "Database tools off UI thread with worker-based execution and exclusive operation locking (Issue #7)."
files_changed:
  - app_facade.py
  - ui/tools_workers.py
  - ui/tabs/tools_tab.py
  - tests/unit/test_tools_workers.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Worker-Based Execution**: Backup, restore, and reset operations now run in background workers (`QRunnable`) off the UI thread
  - Each worker creates its own database connection via `db_path` for SQLite thread safety
  - Workers emit signals for progress, completion, and errors
  - UI remains responsive during long-running database operations
- **Exclusive Operation Lock**: Added `AppFacade._tools_lock` (threading.Lock) to prevent concurrent destructive operations
  - `acquire_tools_lock()` / `release_tools_lock()` manage operation state
  - UI checks `is_tools_operation_active()` before starting new operations
  - Users see clear warning if another tools operation is running
- **AppFacade Integration**: Added worker factory methods to facade layer
  - `create_backup_worker()`, `create_restore_worker()`, `create_reset_worker()`
  - UI calls facade methods instead of directly instantiating services
  - Clean separation: UI → Facade → Workers → Services
- **Data-Changed Signal**: Added `ToolsTab.data_changed` signal emitted after restore/reset operations
  - Enables future cross-tab refresh mechanism
  - Currently triggers refresh indicator/prompt (full architecture in future issue)
- **Progress Dialogs**: All operations show indeterminate progress during execution
- **Restore Atomicity**: Merge restore modes now commit once (all-or-nothing) to avoid partial merges on failure
- **Safety Backups**: Pre-restore and pre-reset safety backups run via background worker (no UI-thread blocking)
- **Maintenance Read-Only Mode**: While a tools operation is active, UI-driven DB writes are blocked (prevents adding/deleting records mid-restore/reset)
- **Testing**: New test suite `test_tools_workers.py` with 14 tests covering:
  - Exclusive lock acquisition/release/thread safety
  - Worker creation and parameter passing
  - Independent database connection architecture
  - All tests pass (100% coverage of new code)
- **No Logic Changes**: Backup/restore/reset service logic unchanged—only execution model refactored

Architecture Benefits:
- UI responsiveness during database operations
- Correctness via atomic operations with proper connection lifecycle
- Clean layering (UI never touches DB directly; always via facade/services)
- Thread-safe concurrent operation prevention

Refs: Issue #7 (Phase 3 follow-up — DB tools off UI thread + facade orchestration + exclusive ops safety)

```yaml
id: 2026-01-29-02
type: fix
areas: [tools, ui]
summary: "Fix DB reset progress dialog crash; prevent Reset worker from emitting spurious errors; stabilize Setup success popups on macOS."
files_changed:
  - ui/tabs/tools_tab.py
  - ui/tools_workers.py
  - ui/tabs/users_tab.py
  - ui/tabs/sites_tab.py
  - ui/tabs/cards_tab.py
  - ui/tabs/redemption_methods_tab.py
  - ui/tabs/redemption_method_types_tab.py
  - ui/tabs/game_types_tab.py
  - ui/tabs/games_tab.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Reset Crash**: `Reset` flow now uses `ProgressDialog.update_progress(...)` instead of calling nonexistent `setLabelText/setRange` on `RecalculationProgressDialog`.
- **Worker Correctness**: `DatabaseResetWorker` no longer emits an error signal unconditionally in `finally` (which could cause false error dialogs or raise `UnboundLocalError`).
- **Restore UX**: Restore now uses the same worker-lifetime safeguards as Backup (strong `QRunnable` reference, `setAutoDelete(False)`, queued signal delivery) so the progress dialog reliably closes on completion.
- **Setup Auto-Refresh**: Setup sub-tabs refresh automatically after Tools restore/reset via `ToolsTab.data_changed` → `SetupTab.refresh_all`.
- **Setup Popups**: “Created” success message boxes in Setup sub-tabs now parent to the top-level window (`self.window() or self`) to avoid odd oversized/blank dialog presentation on macOS.
- **Stray Header Popups**: Header filter menus now require a real header mouse press before acting on release, reducing accidental off-screen popups after dismissing modal dialogs.
- **Debug Aid**: Added optional popup tracing via `SEZZIONS_DEBUG_POPUPS=1` to log which widget is being shown (class/flags/stack) when the remaining popup appears.
- **Main Window**: Fixed stale references to a removed top-level `tools_tab`; Tools menu now navigates to Setup → Tools and refresh-all covers Setup correctly.

---

```yaml
id: 2026-01-29-03
type: fix
areas: [tools, services, tests]
summary: "Fix MERGE_ALL restore failing on empty DB due to foreign key ordering (post-reset)."
files_changed:
  - services/tools/restore_service.py
  - tests/integration/test_database_tools_integration.py
  - docs/status/CHANGELOG.md
```

Notes:
- **FK-Safe Merge**: Merge restores temporarily disable FK enforcement during the atomic merge, then run `PRAGMA foreign_key_check` before commit.
- **Better Failure Mode**: If FK violations remain after a merge (e.g., MERGE_SELECTED without parent/setup data), the restore fails with a clearer error and rolls back.
- **Regression Test**: Added an integration test for backup → full reset (setup wiped) → MERGE_ALL restore.

---

```yaml
id: 2026-01-29-04
type: fix
areas: [tools, ui]
summary: "Run automatic backups in background and add passive in-app busy indicator during tools operations."
files_changed:
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Auto-Backup Worker**: Automatic backups now use the same background `DatabaseBackupWorker` path (no UI-thread blocking).
- **Passive Indicator**: Main window shows a small indeterminate progress indicator + text while any tools operation is active.

---

```yaml
id: 2026-01-29-05
type: fix
areas: [ui]
summary: "Fix macOS Help menu visibility and make Tools → Recalculate navigate to Setup → Tools reliably."
files_changed:
  - ui/main_window.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Help Menu**: Added a non-About Help action so the Help menu remains visible on macOS (Qt can move About into the application menu).
- **Recalculate Navigation**: Recalculate menu action now uses the same Setup → Tools navigation path as other Tools menu entries.

---

```yaml
id: 2026-01-29-06
type: feature
areas: [tools, ui, tests]
summary: "Complete Merge Selected restore UX (Issue #8): compact Restore dialog, table selection, and integration tests."
files_changed:
  - ui/tools_dialogs.py
  - ui/tabs/tools_tab.py
  - tests/integration/test_merge_selected_restore.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Restore Dialog UX**: Restore mode selection moved to a combo box with a mode-specific details panel (progressive disclosure).
- **Validation**: Restore action is disabled until a backup is chosen and a mode is selected; Merge Selected additionally requires at least one table chosen.
- **Table Picker Layout**: Merge Selected uses a two-column table picker (Setup vs Transactions) to keep the dialog compact.
- **Testing**: Added integration coverage for MERGE_SELECTED table selection semantics and failure cases.
- **Dialog Sizing Solution**: Replaced QStackedWidget with show/hide pattern for reliable dynamic height adjustment
  - **Problem**: QStackedWidget's `sizeHint()` tends to reflect the largest page, causing dialogs to stay tall after visiting a larger page
  - **Solution**: Each mode detail widget added directly to layout and shown/hidden based on selection
  - **Pattern**: Hide all widgets → show selected → `layout.activate()` → `adjustSize()` → explicit resize
  - **Result**: Dialog height correctly shrinks/grows to match visible content across all mode switches
  - Standard Qt best practice for dynamic dialog content where size varies significantly between options

Refs: Issue #8, PR #13

---

## 2026-01-28

```yaml
id: 2026-01-28-15
type: refactor
areas: [ui, tools, themes]
summary: "Tools tab visual polish: align Tools with Setup tab styling, use SectionBackground cards, and standardize spacing/buttons." 
files_changed:
  - ui/themes.py
  - ui/tabs/tools_tab.py
  - docs/status/CHANGELOG.md
```

Notes:
- **Page Header**: Tools matches other Setup sub-tabs (simple title, no blurb)
- **Section Styling**: Uses theme-consistent `SectionHeader` + `SectionBackground` cards (rounded, higher-contrast)
- **Typography**: Replaced inline `color: #666` styles with `HelperText` objectName for proper dark theme support
- **Button Styles**: Standardized Tools buttons (emoji + no ellipses); only Reset remains red (`DangerButton`)
- **Spacing/Alignment**: Compact 3-card layout with primary + advanced actions; backup location display is elided with tooltip
- **No Logic Changes**: All business logic, service calls, handlers, and threading behavior unchanged—pure UI refactor
- **Testing**: All 433 tests pass; manual verification confirms Tools operations work identically

Refs: Issue #5 follow-up (visual polish)

```yaml
id: 2026-01-28-14
type: refactor
areas: [ui, tools]
summary: "Tools UI redesign and navigation move (Issue #5): moved Tools from top-level tab to Setup sub-tab, standardized styling to match global app patterns without changing logic."
files_changed:
  - ui/main_window.py
  - ui/tabs/setup_tab.py
  - ui/tabs/tools_tab.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Navigation Change**: Tools is no longer a top-level tab; it's now accessible via Setup → Tools (as a sub-tab alongside Users/Sites/Cards/etc.)
- **Why**: Tools is "periodic/maintenance" functionality and doesn't need prime horizontal space in the main tab bar; legacy also placed Tools within Setup
- **UI Standardization**: Removed inline `setStyleSheet()` calls and replaced with object names (`PrimaryButton`, `SuccessButton`, `DangerButton`) for theme consistency
- **Spacing/Layout**: Standardized margins (16px), spacing (12px/8px), button heights (36px), and group box layouts to match other tabs
- **Typography**: Consistent description label styling (`color: #666; font-style: italic;`)
- **No Logic Changes**: All business logic, service calls, signal handlers, and workflows remain identical—this is a pure UI refactor
- **Settings Persistence**: "last_tab" still works (top-level tabs only; Setup sub-tab state not currently persisted, consistent with other sub-tabbed areas)
- **Testing**: Manual verification of all Tools operations (backup/restore/reset, CSV import/export, recalculation) to confirm no regressions

Refs: Issue #5

```yaml
id: 2026-01-28-13
type: fix
areas: [tools, ui, settings, repository]
summary: "Post-PR improvements (Issue #2 follow-up): fixed settings persistence bugs (MainWindow reload pattern, signal blocking), UI polish (spacing, separator removal), repository hygiene (removed 139 .pyc files, added .gitignore), and service bug fixes."
files_changed:
  - ui/main_window.py
  - ui/tabs/tools_tab.py
  - ui/settings.py
  - services/tools/reset_service.py
  - services/tools/restore_service.py
  - ui/tools_dialogs.py
  - .gitignore
```

Notes:
- **Problem Discovered**: User testing revealed settings persistence bugs—backup directory, auto-backup checkbox state, and frequency spinner weren't saving across app restarts
- **Root Cause**: Two interacting issues:
  1. `QSpinBox.setValue()` triggered `valueChanged` signal during load, causing premature saves with incomplete state
  2. `MainWindow.closeEvent()` created fresh Settings instance with stale data, overwrote automatic_backup config when saving window geometry
- **Signal Blocking Fix**: Block signals before setValue(), set all widgets while blocked, unblock after—prevents premature signal emission during initialization
- **MainWindow Reload Pattern**: Added `self.settings.settings = self.settings._load_settings()` in closeEvent() before saving geometry—ensures latest settings from disk are loaded before partial update
- **Explicit Disk Sync**: Added flush() and fsync() to Settings.save()—forces OS to write buffers immediately, prevents data loss on crash
- **Attribute Init**: Added `self.backup_dir = ''` in __init__—ensures attribute always exists, simplified conditional logic
- **UI Polish**: Removed vertical separator, added spacing (15px between dir/buttons, 20px before checkbox)—cleaner visual hierarchy
- **Repository Hygiene**: Created .gitignore (Python/IDE/OS exclusions), untracked 139 .pyc files—prevents future cache pollution
- **Service Fixes**: reset_service.py, restore_service.py fixed to use DatabaseManager API correctly (fetch_all/fetch_one/execute_no_commit), tools_dialogs.py added missing imports and fixed font rendering
- **Testing**: Manual verification of settings persistence, signal blocking, reload pattern, git status
- **Design Insight**: Qt signals fire during setValue() even if widget not visible; Settings() creates new instance each call, loads from disk; multiple components sharing settings file must reload before partial updates

Refs: Issue #2, PR #3

```yaml
id: 2026-01-28-12
type: feature
areas: [tools, database, ui, testing]
summary: "Complete database tools implementation (Issue #2): backup/restore/reset with automatic scheduling, audit logging, and comprehensive testing."
files_changed:
  - ui/tabs/tools_tab.py
  - ui/tools_dialogs.py
  - ui/settings.py
  - services/tools/backup_service.py
  - services/tools/restore_service.py
  - services/tools/reset_service.py
  - repositories/database.py
  - settings.json
  - tests/integration/test_database_tools_integration.py
  - tests/integration/test_database_tools_audit.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Manual Backup UI**: Directory selection, "Backup Now" button, timestamped files (backup_YYYYMMDD_HHMMSS.db), status display with file size
- **Restore UI**: RestoreDialog with three modes (Replace/Merge All/Merge Selected), safety backups, file validation, confirmations
- **Reset UI**: ResetDialog with preserve setup data option, table count preview, typed "DELETE" confirmation, optional pre-reset backup
- **Automatic Backup**: JSON-based configuration in settings.json with enable toggle, directory selection, frequency (1-168 hrs), QTimer scheduling (5-min checks), non-blocking execution, color-coded status, test button
- **Audit Logging**: DatabaseManager.log_audit() method, all operations log to audit_log table with action type/table/details/timestamp
- **Testing**: 19 tests total (9 existing database tools + 10 new audit logging tests), all passing
- **Services**: BackupService, RestoreService, ResetService use SQLite online backup API
- **Safety Features**: Integrity checks, automatic safety backups, multiple confirmations, typed confirmations for destructive actions

Refs: Issue #2

```yaml
id: 2026-01-28-01
type: docs
areas: [docs, workflow]
summary: "Consolidated docs governance; created master spec, index, status, and reduced root markdown sprawl."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/status/STATUS.md
  - docs/status/CHANGELOG.md
  - docs/TODO.md
  - docs/adr/0001-docs-governance.md
  - .github/copilot-instructions.md
  - AGENTS.md
```

Notes:
- Canonical docs are now in `docs/`.
- Historical docs are archived under `docs/archive/`.

```yaml
id: 2026-01-28-02
type: docs
areas: [docs, tooling]
summary: "Archived phase-era docs into a dated folder; updated canonical pointers; moved schema validation to tools."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/adr/0001-docs-governance.md
  - docs/status/CHANGELOG.md
  - README.md
  - GETTING_STARTED.md
  - tools/validate_schema.py
  - docs/archive/2026-01-28-docs-root-cleanup/README.md
```

Notes:
- `docs/` root now only contains the canonical set (spec/index/todo + status/adr/incidents).
- Phase/checklist documents are preserved under `docs/archive/2026-01-28-docs-root-cleanup/`.

```yaml
id: 2026-01-28-03
type: docs
areas: [docs, workflow]
summary: "Codified the required human+AI development workflow (TODO → code → tests → spec → changelog)."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/TODO.md
  - docs/adr/0001-docs-governance.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

Notes:
- Future work should follow the documented loop so TODO/spec/changelog stay authoritative.

```yaml
id: 2026-01-28-04
type: docs
areas: [docs, onboarding, workflow]
summary: "Added a contributor-facing workflow section to README so new humans+AI discover the required process immediately."
files_changed:
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-05
type: docs
areas: [tools, documentation]
summary: "Created tools/README.md listing supported utilities and clarifying archive folder status."
files_changed:
  - tools/README.md
  - docs/TODO.md
  - docs/status/CHANGELOG.md
```

Notes:
- Tools directory now has clear documentation for supported utilities (schema validation, CRUD matrix).
- Archive folder explicitly marked as not maintained.

```yaml
id: 2026-01-28-06
type: docs
areas: [workflow, governance]
summary: "Documented explicit ad-hoc request and rollback protocols so work stays auditable even when assigned verbally."
files_changed:
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-07
type: docs
areas: [workflow, governance, onboarding]
summary: "Added an owner-approval gate for closing TODO items and clarified when to use incidents vs TODO."
files_changed:
  - docs/TODO.md
  - docs/INDEX.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-08
type: tooling
areas: [github, ci, workflow]
summary: "Added GitHub-native team workflow scaffolding (Issue templates, PR template, CI workflow)."
files_changed:
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - .github/ISSUE_TEMPLATE/feature_request.yml
  - .github/pull_request_template.md
  - .github/workflows/ci.yml
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-09
type: docs
areas: [workflow, governance, github]
summary: "Made GitHub Issues the primary work tracker; kept docs/TODO.md as an optional offline mirror; added CODEOWNERS."
files_changed:
  - docs/TODO.md
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/adr/0001-docs-governance.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - .github/CODEOWNERS
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-10
type: docs
areas: [workflow, github]
summary: "Documented a branching/PR policy (feature branches per Issue; PR review + CI before merge)."
files_changed:
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-11
type: docs
areas: [github, workflow]
summary: "Enhanced GitHub Issue templates to capture implementation/testing detail; instructed agents to draft issues using templates."
files_changed:
  - .github/ISSUE_TEMPLATE/feature_request.yml
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```
