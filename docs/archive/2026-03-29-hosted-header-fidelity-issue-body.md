## Problem / motivation
The current hosted web header is still too large and web-shell-like compared with the desktop app. The large “Hosted Workspace” banner, the full “Signed in as” panel, and the expanded hosted status affordance consume too much vertical and horizontal space. This weakens fidelity with the desktop app, which uses a compact title area and utility-style header icons such as the notification bell and settings gear.

## Proposed solution
What:
- Shrink the hosted header dramatically and replace the large hero-like title with the product name: `Sezzions - Sweepstakes Session Tracker`.
- Replace the current full-width signed-in account summary with compact header utility icons.
- Introduce desktop-inspired utility controls in the hosted header: notifications bell, settings gear, account entry point, and compact status entry point.
- Keep detailed account and hosted-status information available behind compact controls instead of always-visible header blocks.

Why:
- Improves parity with the desktop app’s structure and visual density.
- Frees space for the actual workflow content.
- Creates a more scalable pattern for future hosted features without reintroducing a bulky SaaS-style top shell.

Notes:
- A reasonable first pass is to keep Account details in the existing Account section while using a compact account icon in the header as the entry point.
- Hosted status should remain available but not visually dominant.

## Scope
In-scope:
- Reduce the signed-in header height and simplify the title treatment.
- Replace the current signed-in identity block with an icon-based account entry point.
- Make the hosted status affordance more compact.
- Add desktop-inspired header utility icons/patterns.
- Update frontend tests for the new header behavior.

Out-of-scope:
- Full notification-center backend functionality.
- Full settings/workspace-preferences feature set.
- New hosted business workflows beyond header navigation and presentation.

## UX / fields / checkboxes
Screen/Tab:
- Hosted signed-in web shell header
- Setup primary shell
- Account access entry point
- Hosted status entry point

Fields:
- Product title text: `Sezzions - Sweepstakes Session Tracker`
- Account summary fields remain available behind account entry instead of in the main header
- Hosted status details remain available behind compact status access

Checkboxes/toggles:
- None required for first pass

Buttons/actions:
- Notifications bell
- Settings gear
- Account icon/button
- Status icon/button
- Existing Account/Status details remain reachable from those compact controls

Warnings/confirmations:
- None expected beyond existing destructive confirmations such as user delete

## Implementation notes / strategy
Approach:
- Rework the hosted topbar into a compact desktop-inspired utility row.
- Reuse the existing Account primary tab or a dedicated modal as the detail surface for account information.
- Reuse the existing hosted status modal but reduce the header button footprint.
- Add a lightweight notifications surface if needed for parity, even if it initially reports no notifications.

Data model / migrations (if any):
- None

Risk areas:
- Header utility icons should remain accessible and understandable on smaller screens.
- The refactor should not regress sign-out, status access, or account discoverability.

## Acceptance criteria
- Given a signed-in hosted user, when the shell loads, then the header shows a compact product title rather than a large banner-style workspace header.
- Given a signed-in hosted user, when viewing the shell, then account identity is no longer shown as a large always-visible summary block in the header.
- Given a signed-in hosted user, when viewing the shell, then a compact account entry point is available in the header.
- Given a signed-in hosted user, when viewing the shell, then hosted status is still accessible from the header through a compact control.
- Given a signed-in hosted user, when using the header, then the layout more closely matches the desktop utility-icon pattern by including notifications/settings/account-oriented controls.
- Given a signed-in hosted user, when using the header controls, then existing account/status information remains reachable without breaking current workflows.

## Test plan
Automated tests:
- Update frontend tests for the compact header layout and utility controls.
- Verify account/status access still works from the new compact controls.

Manual verification:
- Launch the hosted web app locally with Vite.
- Confirm the new compact header leaves more room for Setup content.
- Confirm account and status information remain easy to reach.
- Confirm the layout still works at narrower widths.

## Area
UI

## Notes
- This change likely requires updating `docs/PROJECT_SPEC.md`.
