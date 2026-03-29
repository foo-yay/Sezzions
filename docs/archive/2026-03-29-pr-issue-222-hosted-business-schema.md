## Summary

Defines the hosted workspace-owned business schema foundation needed before real UI porting begins.

This PR does not add broad CRUD or web UI work. It establishes the hosted data contract so future web slices can target the real long-term model instead of temporary admin-only pathways.

## What Changed

- expanded hosted persistence metadata to define the core workspace-owned business tables
- kept business-domain ownership explicit with `workspace_id` on hosted business tables
- added scoped uniqueness for key master tables such as users, sites, game types, and redemption method types
- added focused schema tests for expected tables, workspace ownership, and core transactional foreign keys
- updated `docs/PROJECT_SPEC.md` and `docs/status/CHANGELOG.md`

## Validation

- `pytest -q tests/services/hosted/test_account_bootstrap_service.py tests/services/hosted/test_workspace_user_service.py tests/services/hosted/test_business_schema_foundation.py tests/api/test_workspace_users.py`

## Pitfalls / Follow-ups

- This PR defines the hosted schema structurally, but does not yet add repositories/services for every new table.
- This PR does not yet add import logic from desktop SQLite into the new hosted tables.
- This PR does not yet add web UI slices; the next UI work should target these real hosted tables directly.

Closes #222