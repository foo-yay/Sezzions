## Summary
Refine session dialog UX and balance behaviors across Start, Edit, and Edit Closed Session dialogs.

## Requested Changes
1. Auto-calc checkbox cleanup
- Remove the explicit label `Auto End Redeemable:`
- Keep only the checkbox and rename text to `Auto-Calc Redeemable SC`
- Apply in all dialogs where auto-calc checkbox appears.

2. Balance Check redesign
- Keep the `Balance Check` label.
- Replace single-line helper with two real-time lines:
  - `Starting SC:`
  - `Starting Redeemable:`
- Values should reflect last known expected values and update in real time.
- Should also work when session fields are system-generated (purchase-created session, End & Start New flow).

3. Starting Redeemable auto-population behavior
- In Start, Edit, and Edit Closed Session dialogs:
  - When Site/User selected, auto-populate Starting Redeemable if user has not manually entered a value.
  - Auto value should influence Balance Check updates in  - Auto value should influence Balance Check updates in  - Auto value ssh  - Auto  v  - Auto value should influence Balance Check updates in  - Auto value should influence Balance Ches.  - Auto value shos f  - Auto value should influUser, return to auto mode and repopulate.
  - If saved with no manual value, persist the auto-generated value.

## Acceptance Criteria
- Checkbox text/layout updated consistently in - Checkbox h auto-calc checkbox.
- Balance Check displays bo- Balance Check displays bo- Balance Check displays bs in real time.
- Starting Redeemable auto-fill/manual-override behavior works exactly as specified.
- Existing session creation/edit flows still work (including purchase-generated and End & Start New workflows).

## Test Plan
- UI tests for:
  - auto-calc checkbox text/layout in affected dialogs
  - Balance Check two-line expected   - Balance Check two-line expected   - Balance Check two-line expected   - Balance Check two-line expelate behavior
- Regression tests for End & Start New and existing dialog flows.
