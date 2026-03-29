Problem / motivation

The hosted path currently stops at account/workspace bootstrap and read-only migration planning. It does not yet model the business-domain people that an account owner manages inside a workspace.

The intended product behavior is:
- an authenticated person signs up and gets a hosted account
- that account owns one or more hosted workspaces
- inside a hosted workspace, the account owner can create and manage business-domain users/players
- those players are distinct from the auth account owner and will eventually own cards, purchases, redemptions, sessions, and related accounting records

This preserves the current desktop semantics where one operator can manage multiple people such as `fooyay` and `mrs. fooyay`, each with their own transactions and cards.

Proposed solution

What:
- add a hosted workspace-managed player model that belongs to a hosted workspace
- add service/repository support for creating and listing hosted players inside a workspace
- add a protected API slice so an authenticated hosted account can create and list the players in its workspace

Why:
- it proves the account owner is not the same thing as the business-domain player
- it gives the hosted schema a stable parent record for later cards/transactions/import work
- it starts the hosted product with the same mental model as the desktop app

Notes:
- use `workspace_id` as the ownership key for managed players
- do not repurpose legacy desktop `users` as hosted auth/account records
- keep this slice intentionally small and avoid import logic in the same issue

Scope

In-scope:
- hosted persistence/schema for workspace-owned players
- repository/service coverage for create/list behavior
- protected API coverage for create/list behavior scoped to the authenticated user's workspace
- spec/changelog updates for the new hosted data model slice

Out-of-scope:
- importing legacy SQLite users into hosted tables
- hosted cards, purchases, redemptions, sessions, or reports
- full web CRUD UI for players unless needed for a minimal smoke path

UX / fields / checkboxes

Screen/Tab:
- no desktop UI changes required for the first slice
- web UI may remain unchanged if the first slice is API-only

Fields:
- player name
- optional email
- optional notes
- active/inactive status

Buttons/actions:
- create player
- list players

Warnings/confirmations:
- duplicate-name rules should be explicit if enforced

Implementation notes / strategy

Approach:
- add a hosted player record keyed by `workspace_id`
- resolve the authenticated user's workspace from `supabase_user_id`
- create/list players only within that workspace
- preserve room for later mapping from legacy desktop `users`

Data model / migrations (if any):
- new hosted table for workspace-owned players
- unique/index strategy should support workspace scoping

Risk areas:
- accidentally mixing auth account identity with business-domain players
- locking into a schema that makes later transaction ownership awkward
- introducing API paths without clear workspace authorization boundaries

Acceptance criteria

- Given an authenticated hosted account with a bootstrapped workspace, when it creates a managed player, then the hosted API persists a workspace-owned player record distinct from the auth account record.
- Given multiple managed players in one hosted workspace, when the owner lists players, then the API returns only the players for that workspace in a stable order.
- Given two different hosted accounts/workspaces, when each creates managed players, then one workspace cannot list or create records in the other workspace.
- Given a player with optional email/notes omitted, when it is created, then the API stores the player successfully with those fields empty.
- Given invalid input such as blank player name, when create is attempted, then the API returns a safe validation error and does not create a record.

Test plan

Automated tests:
- hosted repository/service tests for create/list and workspace isolation
- protected API tests for create/list behavior and auth requirements
- failure-injection case proving invalid create does not persist a partial record

Manual verification:
- authenticated API smoke check against staging after merge

Area

Database/Repositories

Notes

- [x] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [x] This change likely requires adding/updating scenario-based tests.
- [x] This change likely touches the database schema or migrations.