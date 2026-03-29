## Problem / motivation

Sezzions now has a working staged deployment lane on cPanel and a verified placeholder page at `dev.sezzions.com`, but there is not yet a real web frontend codebase. The repository needs an actual frontend scaffold so future product work can move from static placeholder deployment into a buildable browser app that targets the same hosted backend strategy as the desktop app.

## Proposed solution

What:
- scaffold a real web frontend under `web/`
- use a static-build-friendly stack that works with the current cPanel deploy lane
- replace the placeholder-only deployment source with a real frontend source tree and build output

Why:
- establish the browser codebase now instead of continuing to deploy a placeholder page
- keep the web rollout moving while backend/API work proceeds separately
- make future UI work testable and reviewable in the repository

Notes:
- the initial scaffold should focus on shell/app structure, landing experience, and deployment compatibility
- this is not the full backend/API implementation

## Scope

In-scope:
- frontend project scaffold under `web/`
- static build configuration suitable for cPanel deploys
- initial landing shell / app structure
- basic automated frontend test coverage
- deploy configuration updates needed to publish the built frontend

Out-of-scope:
- hosted API implementation
- auth integration
- tenant/account management
- full desktop/web feature parity in this change

## UX / fields / checkboxes

Screen/Tab:
- web landing page

Fields:
- none yet beyond navigation shell content

Checkboxes/toggles:
- none

Buttons/actions:
- initial landing/CTA actions only

Warnings/confirmations:
- none

## Implementation notes / strategy

Approach:
- use Vite + React for a static-build-friendly frontend scaffold
- add a small test setup for the initial app shell
- point deployment to generated build output instead of tracked placeholder files
- keep the current placeholder messaging but upgrade it into a real frontend landing page

Data model / migrations (if any):
- none

Risk areas:
- introducing Node tooling into a previously Python-only repo
- making sure deployment paths and ignored build outputs stay aligned
- preserving the staging deployment lane while switching away from the placeholder folder

## Acceptance criteria

- Given the repo checkout, there is a real web frontend project under `web/`
- The frontend can be built into static assets suitable for the cPanel deployment workflow
- The deployment workflow points to built frontend output rather than only a tracked placeholder directory
- At least one automated frontend test covers the initial app shell
- Documentation explains how the frontend is built and deployed

## Test plan

Automated tests:
- frontend test runner for the initial app shell
- frontend production build completes successfully

Manual verification:
- inspect the dev deployment result in the browser after publish
- confirm the web app shell replaces the old static placeholder page

## Area

UI

## Notes

- This change likely requires updating `docs/PROJECT_SPEC.md`.
- This change likely requires adding/updating scenario-based tests.