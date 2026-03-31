## Problem / motivation

The web app currently only supports Setup -> Users. Sites are the next entity in the dependency chain (Cards, Games, and Purchases all reference Sites). Without a Sites CRUD page, we cannot proceed to port any downstream entities.

## Proposed solution

Port the desktop Setup -> Sites tab to the hosted web app, following the same architecture established by the Users implementation:

- **API layer**: Add CRUD endpoints for workspace sites (`/v1/workspace/sites`)
- **Service layer**: Add `HostedWorkspaceSiteService` mirroring `HostedWorkspaceUserService`
- **Web component**: Add `SitesTab/` component group mirroring `UsersTab/`

The hosted `sites` table already exists in the PostgreSQL schema (`HostedSiteRecord` in `services/hosted/persistence.py`) with columns: id, workspace_id, name, url, sc_rate, playthrough_requirement, is_active, notes, created_at, updated_at.

## Scope

In-scope:
- FastAPI endpoints: list (paginated), create, update, delete, batch-delete
- `HostedWorkspaceSiteService` with workspace-scoped CRUD
- `SitesTab` React component with table, search, column filters, sorting, keyboard nav
- Site modal (view/create/edit modes) with all fields
- Export CSV
- Enable the "Sites" rail nav button in AppShell
- Web tests (Vitest) covering CRUD flows, edge cases, failure injection
- API tests (pytest) covering endpoint behavior

Out-of-scope:
- Cards or other entities that reference Sites
- Import/migration of Sites from SQLite
- Desktop app changes

## UX / fields / checkboxes

Screen/Tab: Setup -> Sites (rail nav, already listed but disabled)

Table columns:
- Name
- URL
- SC Rate
- Playthrough Requirement
- Status (Active/Inactive chip)
- Notes (truncated to 100 chars)

Site modal fields:
- Name (required, text input)
- URL (optional, text input)
- SC Rate (number input, default 1.0)
- Playthrough Requirement (number input, default 1.0)
- Is Active (checkbox/toggle, edit mode only)
- Notes (optional, textarea)

Buttons/actions:
- Add Site, View, Edit, Delete, Export CSV, Refresh
- Delete confirmation modal (single and batch)
- Dirty-form confirmation on Escape/close

## Implementation notes / strategy

Approach:
- Copy the Users pattern exactly: service, router, React component group
- API endpoints register in `api/app.py` alongside existing user routes
- `SitesTab` receives `apiBaseUrl` and `hostedWorkspaceReady` props (same as UsersTab)
- Enable the Sites tab in `setupTabs` array in `AppShell.jsx` (`enabled: true`)
- Unique constraint on (workspace_id, name) already exists in schema; API should return 409 on duplicate

Data model / migrations:
- No schema changes needed; `HostedSiteRecord` already defined in persistence.py

Risk areas:
- SC Rate and Playthrough Requirement are numeric fields; need input validation (positive numbers, reasonable bounds)
- URL field needs basic format validation or accept freeform text

## Acceptance criteria

- Given a signed-in user with a bootstrapped workspace, when they click "Sites" in the Setup rail nav, then the Sites table loads and displays all workspace sites
- Given no sites exist, when the user clicks "Add Site" and fills in the name, then a new site is created and appears in the table
- Given an existing site, when the user double-clicks it, then the View Site modal opens with all fields displayed read-only
- Given the Edit modal is open, when the user changes the name and clicks Save, then the site is updated via PATCH and the table refreshes
- Given one or more sites are selected, when the user clicks Delete and confirms, then the sites are removed
- Given sites exist, when the user types in the search bar, then the table filters by name, URL, and notes
- Given sites exist, when the user clicks Export CSV, then a CSV file downloads with the filtered/selected sites
- All new API endpoints return appropriate error codes (400 for validation, 404 for not found, 409 for duplicate name)
- Web test suite passes with new Sites tests added
- Desktop test suite remains green (no regressions)

## Test plan

Automated tests:
- API (pytest): list, create, update, delete, batch-delete, duplicate name (409), missing fields (422), not-found (404)
- Web (Vitest): render Sites tab after bootstrap, create site, edit site, delete site with confirmation, search filtering, Export CSV modal

Manual verification:
- Sign in, navigate to Sites, add/edit/delete a site, verify table updates
- Confirm SC Rate and Playthrough fields accept and display decimal values correctly
