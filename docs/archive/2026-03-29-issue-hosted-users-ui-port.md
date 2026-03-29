Problem / motivation

Now that the hosted schema is structurally ready, the first real UI slice to port should be Users. Users come before sites/cards because those workflows attach to users, and the web shell needs a genuine product-facing `Setup -> Users` surface rather than temporary CRUD scaffolding.

Proposed solution

What:
- add a real authenticated hosted app shell with a `Setup` area and `Users` tab
- port the desktop Users workflow as faithfully as practical for the web, using the hosted API and hosted users model
- keep the visual direction aligned with the current Python app Dark theme where practical

Why:
- Users is the first dependency-bearing master-data slice for later sites/cards workflows
- the UI should start resembling the real hosted product, not a temporary admin page
- the sooner the shell/layout is real, the easier it will be to port later slices consistently

Notes:
- preserve the desktop semantics and workflow as closely as practical
- web UX may adapt mechanics such as dialogs/modals, but behavior should remain familiar
- highlighted fields, autocomplete, modal editing flows, and list behavior should be treated as first-class porting requirements where relevant

Scope

In-scope:
- authenticated app-shell layout with a real `Setup -> Users` surface
- list/create/edit/deactivate-style users workflow against hosted users APIs
- dark-theme styling aligned to the Python app direction

Out-of-scope:
- sites/cards UI
- temporary placeholder tabs that do not reflect the intended long-term shell

Implementation notes / strategy

Approach:
- treat this as the first real hosted desktop-to-web port slice
- use the hosted users API and the existing hosted account/workspace/session model
- structure the shell so later Setup tabs can be added without reworking the layout again

Acceptance criteria

- Given an authenticated hosted account, when it enters the hosted web app, then it can reach a real `Setup -> Users` surface.
- Given the Users surface, when managing hosted users, then the core workflow faithfully reflects the desktop product behavior within reasonable web UX adaptations.
- Given the web shell styling, when viewing the Users slice, then it follows the current Sezzions dark-theme direction rather than a temporary generic layout.

Test plan

Automated tests:
- focused web tests for app shell navigation and Users workflow
- targeted API/service tests if the Users slice needs additional backend behavior

Manual verification:
- sign in on staging and create/edit a hosted user through the new Users surface

Area

UI

Notes

- [x] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [x] This change likely requires adding/updating scenario-based tests.