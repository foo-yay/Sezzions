## Summary

Adds the first hosted business-domain data slice after account/workspace bootstrap: workspace-managed users.

This preserves the intended product model where:
- the authenticated owner signs into Sezzions and gets a hosted account/workspace
- that owner can create and manage multiple business-domain users/players inside the workspace
- those managed users stay distinct from the auth account and will later own cards, purchases, redemptions, sessions, and related accounting records

## What Changed

- added `hosted_users` persistence keyed by `workspace_id`
- added hosted user repository + service for create/list flows
- added protected `GET /v1/workspace/users` and `POST /v1/workspace/users`
- added focused service/API tests for workspace isolation and validation
- updated `docs/PROJECT_SPEC.md` and `docs/status/CHANGELOG.md`

## Validation

- `pytest -q tests/services/hosted/test_workspace_user_service.py tests/api/test_workspace_users.py`

## Pitfalls / Follow-ups

- This PR does not add a web UI for workspace user CRUD yet.
- This PR does not import legacy SQLite `users` into `hosted_users` yet.
- Later hosted business tables should continue to attach to managed workspace users, not to auth account records.

Closes #220