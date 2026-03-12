## Summary
Add a one-command release automation tool for Sezzions so publishing updates requires minimal manual steps.

## Problem
Releasing currently requires multiple manual shell commands (build, zip, checksum, manifest rewrite, release upload), which is error-prone and slows down frequent releases.

## Proposal
Create `tools/release_update.py` that:
1. Validates git/gh preconditions.
2. Builds macOS arm64 artifact using PyInstaller.
3. Creates release zip from app bundle.
4. Generates `latest.json` with computed SHA-256 and release URLs.
5. Publishes/updates release assets in `foo-yay/sezzions-updates`.
6. Optionally creates source release tag in `foo-yay/Sezzions`.

## Scope
- In scope: CLI tool + docs + tests for manifest/content generation helpers.
- Out of scope: installer automation and platform installers beyond current macOS arm64 zip flow.

## Acceptance Criteria
- Single command can publish update assets and manifest for version `X.Y.Z`.
- Manifest URL points at public `sezzions-updates` release assets.
- CLI has dry-run mode and clear failure messages.
- Docs include exact usage examples.

## Test Plan
- Unit tests for manifest payload generation and version normalization.
- Manual dry-run and real run verification against a test version.
