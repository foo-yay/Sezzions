## Summary
Add support for site-level playthrough requirement and use it in End Session to auto-calculate Ending Redeemable SC.

## Problem
Ending Redeemable SC is currently always manually entered, which is error-prone and inconsistent across sites with different playthrough requirements.

## Proposal
1. Add `playthrough_requirement` to Sites (default `1.0`).
2. In End Session dialog, add checkbox toggle:
   - Label: `Auto-Calculate End Redeemable SC`
   - Checked: Ending Redeemable input is read-only and auto-populated in real time.
   - Unchecked: Ending Redeemable input is editable manually.
3. Auto-calc should use:
   - Start SC
   - Start Redeemable
   - End SC
   - Site playthrough requirement

## Scope
- DB schema + migration for new site field.
- Site model/repository/service/facade wiring.
- Sites tab add/edit/view/table updates for playthrough requirement.
- End Session dialog toggle + live calculation + validation behavi- End Session dialog toggle + live calculation + validation behavi- End Sessor- Eaving/ed- End Session dialog toggle + live calculation + validation behavi- End Session dialog toggle + live calculation + efa- t `1.0`.
- End Session dialog toggle + live calculation + validation behavi- End Session dialog toggle + live calculation + validation behavi- End Sessor-henever End SC chan- End Session dialog toggle + live calculation + validis user-editable.
- Auto-calculated value respects s- Auto-calculated value respects s- Auto-calcior remains unchanged when toggle is unchecked.

## Test Plan
- Unit tests for site model/repo/service include playthrough field defaults and validation.
- Migration test verifies column added with default for existing rows.
- UI test verifies toggle enables/disabl- UI test verifies toggle enables/disabl-ue.
- Run full pytest suite.
