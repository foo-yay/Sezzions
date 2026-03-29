## Summary
Add the next hosted product slice after account/workspace bootstrap: an authenticated workspace import-planning flow that inspects the user’s local Sezzions SQLite database and shows a hosted inventory summary before any real data migration occurs.

## Problem
Hosted auth and workspace bootstrap now work, but the hosted product still has no bridge from an existing desktop user’s local `sezzions.db` into the hosted account/workspace. We already have a read-only CLI inventory tool for SQLite inspection, but there is no hosted API or web UI flow that makes that planning information part of the staged hosted product.

## Proposal
Implement an authenticated hosted import-planning slice that:
- records or confirms the source database path for the hosted workspace
- exposes a protected API endpoint that returns a read-only inventory summary for that source SQLite database
- renders the import-planning summary in the web shell after hosted bootstrap
- does not perform any data writes into hosted business tables yet

## Scope
In scope:
- protected hosted API endpoint for workspace import planning
- service-layer orchestration that reuses the existing SQLite inventory logic
- web-shell UI for showing import-planning readiness and inventory results
- focused tests for happy path, edge cases, and a failure case
- docs/changelog updates for the new hosted slice

Out of scope:
- actual record migration from SQLite to Supabase Postgres
- bidirectional sync
- background jobs / resumable imports
- hosted CRUD for business entities

## Acceptance Criteria
- authenticated users with a bootstrapped hosted workspace can request a read-only import inventory summary
- the API response includes enough planning data to judge migration readiness, including table counts and basic metadata already available from the existing inventory tool
- the web shell displays the inventory summary clearly after auth/bootstrap succeeds
- missing or invalid source DB paths fail safely with an actionable error, without changing hosted state
- no business-domain rows are imported yet

## Test Matrix
Happy path:
- authenticated request returns inventory summary for a valid source SQLite file

Edge cases:
- workspace has no source DB path yet
- source DB path exists in workspace state but the file is missing on disk

Failure injection:
- SQLite inspection raises an error mid-read and the API returns a safe failure without mutating hosted records

Invariants:
- hosted account/workspace identity remains unchanged
- no hosted business-domain data is created
- request still requires bearer auth

## Manual Verification
- sign in on staged web
- confirm hosted bootstrap succeeds
- request/import-planning summary and confirm the UI shows read-only inventory data or a clear actionable error

## Labels
- feature
- status:ready
- type:feature
