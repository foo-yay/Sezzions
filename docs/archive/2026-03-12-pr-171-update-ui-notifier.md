## Summary
- Adds user-facing updater UX for Issue #171.
- Integrates update checks into Help menu, Settings dialog, and bell notifications.
- Preserves MVP updater boundary (check/download/verify only; no installer handoff).

## What changed
- Help menu: adds `Check for Updates...` action.
- Settings dialog:
  - software version display,
  - `Check for Updates Now` button,
  - notification settings for auto-check enable + interval hours.
- Main window:
  - periodic update check loop using persisted interval + `update_last_checked_at`,
  - manual check path used by Help/settings/notification action,
  - creates `app_update_available` notification when newer version exists,
  - dismisses stale update notifications when app is up to date.
- Notification action routing:
  - `open_updates` now triggers manual update check flow.
- Docs:
  - `docs/PROJECT_SPEC.md` updated with update UX semantics.
  - `docs/status/CHANGELOG.md` entry added.

## Tests (Red -> Green)
- Added new UI regression tests:
  - `tests/ui/test_update_ui.py`
- Validation run:
  - `pytest -q tests/ui/test_update_ui.py tests/unit/test_update_service.py tests/unit/test_app_update_facade.py`
  - `pytest -q tests/ui/test_issue_92_ui_smoke.py tests/ui/test_settings_undo_retention_ui.py tests/integration/test_notification_cooldown.py`
  - `pytest -q` (full suite): `994 passed, 1 skipped`

## Manual verification (<=5 min)
- Open app, verify `Help -> Check for Updates...` exists.
- Open Settings gear, verify software version + check-now button + update-check controls.
- Trigger check and verify bell notification behavior for update available/up-to-date paths.

## Pitfalls / Follow-ups
- Current UI check action reports via existing notification channel; if users want a richer release-notes experience, follow-up issue should add a dedicated update result dialog.
- `update_manifest_url` remains a settings key; if made user-editable later, add URL validation + safe reset UX.
- ResourceWarning noise in baseline full suite is pre-existing and unrelated to this issue.

Closes #171
