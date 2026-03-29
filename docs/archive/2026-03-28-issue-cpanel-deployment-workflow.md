## Problem / motivation

Sezzions now has a protected `develop` to `main` workflow, but there is no matching deployment path for a staged web rollout. The repository needs an environment-aware deployment workflow so future web artifacts can be pushed to a dev/staging destination from `develop` and to production from `main`, with the required GitHub environment gates and clear cPanel setup instructions for the project owner.

## Proposed solution

What:
- add a deployment workflow that is environment-aware and compatible with cPanel-style SSH deployment
- route `develop` deployments through the `development` GitHub environment and `main` deployments through `production`
- document the required cPanel/server setup, GitHub secrets, and deploy paths

Why:
- keep dev and live separated
- make future deploys reproducible and safe
- allow Copilot/VS Code work to flow through GitHub instead of ad-hoc server edits

Notes:
- this should be safe scaffolding for the future web app/API rollout, not a production web implementation
- deployment should use environment secrets and avoid hardcoding server details in the repo

## Scope

In-scope:
- GitHub Actions deployment workflow scaffold
- GitHub environment usage for development and production
- repository documentation updates for deploy process
- cPanel owner checklist for SSH key, paths, subdomains, and secrets

Out-of-scope:
- building the actual web frontend
- building the actual hosted API/backend
- provisioning a managed database or auth provider
- DNS changes beyond documenting what is needed

## UX / fields / checkboxes

Screen/Tab:
- none

Fields:
- none

Checkboxes/toggles:
- none

Buttons/actions:
- GitHub Actions workflow dispatch / automatic deploy on branch push

Warnings/confirmations:
- production deploys should remain gated by the `production` GitHub environment

## Implementation notes / strategy

Approach:
- create a deploy workflow that selects target environment from branch name
- use SSH-based publish steps suitable for cPanel hosting
- keep deploy paths and connection settings in GitHub environment secrets/variables
- document the owner-side cPanel setup in repo docs

Data model / migrations (if any):
- none

Risk areas:
- cPanel feature variability across hosting plans
- deploying before the web app exists could create confusion if the workflow is not clearly documented as scaffold/infrastructure
- accidental production deploys if environment separation is not clear

## Acceptance criteria

- Given a push to `develop`, the repository has a deployment workflow path that targets the `development` GitHub environment
- Given a push to `main`, the repository has a deployment workflow path that targets the `production` GitHub environment
- The workflow uses secrets/variables rather than hardcoded hostnames, usernames, or paths
- The repository documents exactly what must be configured in cPanel and GitHub before deployment can succeed
- The documented workflow preserves the branch model: feature -> `develop`, then promotion to `main`

## Test plan

Automated tests:
- YAML/workflow validation via editor diagnostics
- optional dry-run shell validation for deploy script fragments if practical

Manual verification:
- inspect workflow triggers and environment selection logic
- verify docs list the required GitHub environment secrets/variables and cPanel steps

## Area

Tools

## Notes

- This change likely requires updating `docs/PROJECT_SPEC.md`.