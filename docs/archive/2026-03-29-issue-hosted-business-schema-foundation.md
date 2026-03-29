Problem / motivation

The hosted path now has account/workspace ownership plus the first workspace-managed user slice, but it does not yet define the full hosted business schema needed to begin porting the real Sezzions UI. Building web CRUD before the hosted data model is complete would create temporary pathways that may not match the final product.

We need a hosted schema that is structurally ready for the app to be ported slice by slice while preserving desktop semantics closely enough that the standalone app can eventually map to the same ownership model and consume hosted data.

Proposed solution

What:
- define hosted workspace-owned table structures for the core Sezzions business model
- carry `workspace_id` through the business-domain tables unless a row is purely system-owned
- scope uniqueness and indexes around workspace ownership
- document the hosted schema direction clearly enough that future UI porting and data import work target the same data contract

Why:
- it creates the stable backend contract the real web app should target
- it avoids building throwaway CRUD surfaces
- it aligns hosted design with the eventual desktop-to-hosted compatibility path

Notes:
- prefer simple workspace-local duplication over premature global/shared catalogs
- business-domain entities such as sites, cards, redemption methods, game types, games, and transactions should be modeled as workspace-owned unless there is a strong reason otherwise

Scope

In-scope:
- hosted structural definitions for core master and transactional business tables
- workspace ownership and key foreign-key relationships
- tests that verify the hosted schema exists and enforces the intended ownership structure
- spec/changelog updates for the hosted schema foundation

Out-of-scope:
- full hosted CRUD/service implementations for every new table
- import execution from legacy SQLite into hosted tables
- web UI implementation

UX / fields / checkboxes

Screen/Tab:
- no UI work in this issue

Implementation notes / strategy

Approach:
- mirror desktop semantics closely while moving to workspace ownership
- add hosted structural tables for users, sites, cards, redemption methods, redemption method types, game types, games, purchases, unrealized positions, redemptions, game sessions, game session event links, game RTP aggregates, redemption allocations, realized transactions, realized daily notes, expenses, daily sessions, daily date tax, and account adjustments
- prefer explicit `workspace_id` columns on business-domain tables to simplify future authorization, querying, imports, and debugging

Data model / migrations (if any):
- extend hosted SQLAlchemy persistence metadata with the full workspace-owned business schema
- add appropriate uniqueness and index definitions scoped by `workspace_id`

Risk areas:
- baking in relationships that do not match desktop semantics
- under-defining transactional tables and leaving UI-port blockers
- introducing unnecessary global/shared tables too early

Acceptance criteria

- Given the hosted persistence metadata, when the schema is created, then all core business-domain tables needed for UI porting are structurally defined.
- Given the hosted schema, when inspecting business-domain tables, then each table is owned by a workspace directly through `workspace_id` or is a system/ownership table by design.
- Given workspace-scoped lookup/master data such as sites, game types, and redemption methods, when two workspaces use the same display names, then the schema allows that without cross-workspace conflicts.
- Given transactional tables, when reviewing their structure, then they reference the hosted workspace-owned parent entities needed to support future UI slices and import work.

Test plan

Automated tests:
- hosted schema tests for expected tables, workspace ownership columns, and scoped uniqueness on key master tables
- targeted relationship tests for core transactional foreign keys

Manual verification:
- none required beyond test and schema inspection for this issue

Area

Database/Repositories

Notes

- [x] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [x] This change likely requires adding/updating scenario-based tests.
- [x] This change likely touches the database schema or migrations.