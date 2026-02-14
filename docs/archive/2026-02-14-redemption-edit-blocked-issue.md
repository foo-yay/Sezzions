Summary
Redemption edits fail with “No game sessions have been recorded for this site and user” even when closed sessions exist for that site/user.

Impact / scope
Impact:
- Editing certain redemptions (including notes/receipt date) is blocked.
- User cannot update historical entries.

Scope:
- Redemptions for specific site/user pairs around 2026-02-09/10 with valid sessions present.

Steps to reproduce
1. Open app and locate redemption:
   - 2026-02-10, mrs fooyay, Play Fame, $108.06
   - 2026-02-09, mrs fooyay, Spin Blitz, $1,738.22
   - 2026-02-10, fooyay, Chumba, $101.25
2. Edit the redemption (change notes or receipt date).
3. Save.

Expected behavior
Edits should save when closed sessions exist for the site/user.

Actual behavior
Save is blocked with:
“No game sessions have been recorded for this site and user.”

Logs / traceback
None.

Severity
High (data correctness / workflow blocked)

Environment
macOS (reported). Likely after UTC/timezone storage change.

Acceptance
- This bug involves data correctness (should add/adjust a scenario-based test).
