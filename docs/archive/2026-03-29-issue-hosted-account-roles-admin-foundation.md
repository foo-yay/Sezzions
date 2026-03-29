Problem / motivation

The hosted schema is now structurally ready for real UI porting, but the hosted account layer does not yet define Sezzions-owned administrative roles or account-level operational controls. Before we port substantial end-user UI such as a faithful `Setup -> Users` slice, we need the hosted access-control foundation clear enough that future screens and APIs can enforce the intended privilege boundaries.

The product needs at least two layers of account behavior:
- normal customer account/workspace ownership
- Sezzions-controlled elevated administrative access for platform operations such as disabling, restoring, reviewing, and correcting customer accounts when needed

Proposed solution

What:
- define hosted account roles and account lifecycle status at the hosted account layer
- reserve platform-admin capabilities for Sezzions-controlled accounts, distinct from normal customer workspaces
- expose enough structure to support a future admin dashboard for signed-in hosted accounts
- document future bug-report/support goals so they align with the same hosted access-control model

Why:
- permissions are a cross-cutting concern and should be established before deep UI porting
- future customer UI should not be built against assumptions that conflict with owner/admin behavior
- support workflows such as account disable/restore and future bug-triage need a clear privilege model

Notes:
- no need for password access or sensitive auth-provider internals beyond what the hosted auth/session model already exposes
- future cross-account analytics may exist later, but they are not required for this issue

Scope

In-scope:
- hosted account role/status schema foundation
- basic role/status representation on hosted account records and summaries
- explicit documentation of platform-admin capabilities vs customer capabilities

Out-of-scope:
- full admin dashboard UI
- cross-account analytics
- full bug-report submission and triage implementation
- end-user users/sites/cards CRUD porting

Implementation notes / strategy

Approach:
- add hosted account role and lifecycle status fields at the hosted account layer
- preserve customer workspace ownership while introducing Sezzions platform-admin privileges above the workspace layer
- keep the model simple and explicit so later APIs can enforce role-based access cleanly

Data model / migrations (if any):
- extend `hosted_accounts` with role and status fields
- document the intended role/status values and their semantics

Risk areas:
- conflating workspace ownership with system-wide admin privileges
- over-designing RBAC before the product needs it
- leaving future admin/support features undocumented enough that UI slices drift

Acceptance criteria

- Given a hosted account record, when it is inspected, then it includes explicit role and lifecycle status fields suitable for future authorization checks.
- Given the hosted product spec, when reading account-role behavior, then the distinction between customer workspace owner access and Sezzions platform admin access is clear.
- Given future admin operations such as disable, restore, or account correction, when planning later APIs/UI, then the hosted account model already contains the privilege foundation needed to support them.

Test plan

Automated tests:
- hosted account bootstrap/config tests updated for the new role/status defaults
- targeted persistence/service tests for role/status defaults and summaries

Manual verification:
- none required beyond focused tests for this issue

Area

Database/Repositories

Notes

- [x] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [x] This change likely requires adding/updating scenario-based tests.
- [x] This change likely touches the database schema or migrations.