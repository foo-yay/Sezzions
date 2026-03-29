## Summary

Adds the hosted account authorization foundation needed before deeper hosted UI porting.

This PR does not build the admin dashboard yet. It establishes explicit hosted account role and lifecycle status fields so future customer UI, Sezzions admin UI, and support flows can target a real permission model.

## What Changed

- added `role` and `status` to hosted account persistence/model records
- defaulted self-serve hosted accounts to `owner` + `active`
- exposed role/status in hosted bootstrap summaries
- added focused bootstrap/API tests for the new defaults and response fields
- documented the intended distinction between customer owners and Sezzions administrators
- documented the future admin dashboard / bug-reporting direction in the spec

## Validation

- `pytest -q tests/services/hosted/test_account_bootstrap_service.py tests/api/test_app.py`

## Pitfalls / Follow-ups

- This PR does not yet add role-guarded admin APIs.
- This PR does not yet add an admin dashboard UI.
- This PR does not yet implement bug-report submission or support tooling.

Closes #224