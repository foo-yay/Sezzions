## Summary

Unify the Notes UX across session dialogs so they open compact and behave consistently:

- Notes start **collapsed** (even when notes already exist)
- Clicking the notes header expands the dialog to show notes
- Clicking again collapses and shrinks the dialog back

This matches the desired End Session behavior and removes minor inconsistencies between dialogs.

## Changes

- Update session dialogs to compute tight/expanded heights from Qt size hints (no hard-coded magic heights)
  - End Session dialog
  - Edit Session dialog (via `StartSessionDialog`)
  - Edit Closed Session dialog
- Update toggle text to use `📝 Show Notes...` when notes exist but are collapsed

## Tests

- `pytest -q` (full suite)
- Added headless regression tests:
  - `tests/integration/test_end_session_dialog_notes_layout.py`
  - `tests/integration/test_edit_session_dialog_notes_layout.py`

## Pitfalls / Follow-ups

- Size hints can vary slightly by platform/theme; tests validate relative expand/collapse behavior rather than exact pixel values.
