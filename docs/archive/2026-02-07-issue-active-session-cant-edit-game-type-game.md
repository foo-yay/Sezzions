## Summary
Unable to edit/remove the **Game Type** and **Game** fields for an in-progress/active Game Session.

## Impact / scope
Impact:
- Impairs correcting an active session when the wrong Game Type/Game was selected.
- Forces workaround (end session + start new, or edit DB) which is error-prone.

Scope:
- Game Sessions tab (in-progress/active session editing).
- Affects UI flow; may also impact data correctness if users cannot correct mistakes.

## Steps to reproduce
1. Open Sezzions.
2. Go to **Game Sessions**.
3. Start a new session (so it becomes **Active / In Progress**).
4. Select the active session.
5. Try to edit the session and change **Game Type** and/or **Game**, or clear/remove them.

## Expected behavior
- While a session is active, the user should be able to change **Game Type** and **Game** (or clear them if allowed by the model), with any necessary validation.
- If changing these fields is intentionally disallowed during an active session, the UI should clearly explain why and provide an approved alternative workflow.

## Actual behavior
- The UI does not allow editing/removing **Game Type** and **Game** on an active session (controls appear disabled or the change does not apply).

## Logs / traceback
- N/A (no crash observed).

## Severity
Medium (workflow impaired)

## Environment
- macOS
- Sezzions desktop app

## Acceptance
- [ ] I’ve checked `docs/PROJECT_SPEC.md` and this is unexpected.
- [ ] I’m willing to help test a fix.
- [ ] This bug involves data correctness (should add/adjust a scenario-based test).
