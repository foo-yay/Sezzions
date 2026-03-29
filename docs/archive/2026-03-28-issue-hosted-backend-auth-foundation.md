Problem / motivation

Sezzions now has a real staged web frontend shell on `develop`, but the product is still fundamentally a desktop-only SQLite application. The current data model and runtime assume a local database file, and the existing `users` table represents tracked players/payment entities rather than hosted product accounts.

Without a hosted identity model and shared backend, the web app cannot move past a static shell, and the desktop + web clients cannot safely share the same source of truth. We also need a defined path to port an existing local SQLite database into the hosted system without losing accounting correctness.

Proposed solution

What:
- establish the hosted foundation for shared desktop + web data
- choose and document the canonical stack for hosted auth, API, and database
- define the new account ownership model separately from the current business-domain `users` table
- scaffold the first backend slice that can support authenticated access
- define and implement the initial local SQLite to hosted-data import path

Why:
- building more web UI before auth/ownership/data contracts are real will create avoidable rework
- both clients need one hosted source of truth rather than duplicated business logic or divergent datasets
- existing desktop data must have a safe migration path into the hosted system

Notes:
- cPanel remains a static frontend delivery lane only unless a future hosting plan explicitly supports managed Python app hosting reliably
- do not repurpose the current `users` table as the hosted auth/account model

Scope

In-scope:
- decide the canonical hosted architecture for auth, API, and database
- add repository documentation/spec updates for that direction
- introduce the first backend scaffold/package for hosted API work
- define account/workspace/ownership entities and boundaries
- design the import/migration strategy from local SQLite into the hosted schema
- implement one minimal authenticated vertical slice if the stack choice is finalized

Out-of-scope:
- full port of all desktop features to the web
- production-grade billing/subscription flows
- rewriting accounting rules to fit the web before the shared backend exists
- switching the current desktop runtime away from SQLite immediately

UX / fields / checkboxes

Screen/Tab:
- web sign-in / bootstrap flow
- minimal authenticated landing screen

Fields:
- email
- password or hosted provider identity
- account/workspace name if needed for first-run bootstrap

Buttons/actions:
- sign in
- create account
- sign out
- import existing Sezzions data

Warnings/confirmations:
- import is one-way into the hosted environment unless restored from backup
- imported desktop data must be attached to the selected hosted account/workspace

Implementation notes / strategy

Approach:
- prefer managed PostgreSQL as the hosted system of record
- prefer a Python API layer so Sezzions business logic can be migrated and shared incrementally
- use hosted auth rather than hand-rolling passwords/session storage
- keep desktop accounting logic authoritative while moving rules behind the API gradually

Data model / migrations:
- add a hosted account/tenant boundary that owns imported and future records
- treat current SQLite tables as source data for migration, not as the target hosted schema verbatim
- provide an import tool that reads a local SQLite database and writes into the hosted schema with validation checks

Risk areas:
- confusing business-domain `users` with product auth users
- partial or lossy import of existing accounting data
- introducing ownership fields too late and having to rebuild web flows

Acceptance criteria

- the repository documents the chosen hosted auth, API, and database direction clearly enough to implement against
- the hosted account/auth model is defined separately from the current business-domain `users` table
- a concrete import strategy exists for moving an existing local SQLite database into the hosted system
- at least one authenticated end-to-end slice is defined, with acceptance criteria for web + backend interaction
- follow-up implementation can proceed without needing to re-decide where data lives or how existing data ports over

Test plan

Automated tests:
- schema/model tests for hosted account ownership boundaries
- import tests using a representative SQLite fixture database
- at least one backend auth/access test for the initial protected route

Manual verification:
- verify a user can authenticate into the web app once the first slice is implemented
- verify an existing local Sezzions database can be imported into a hosted account in a non-production environment

Area

Services
Database/Repositories
Docs
Tests

Notes

- This change likely requires updating `docs/PROJECT_SPEC.md`.
- This change likely requires adding/updating scenario-based tests.
- This change likely touches the database schema or migrations.