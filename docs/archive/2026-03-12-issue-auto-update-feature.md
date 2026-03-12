## Problem / motivation
Sezzions currently requires manual updates. Users must notice a new release, download it, and install it themselves.

This causes:
- users running stale versions (bug fixes/security fixes delayed),
- inconsistent support/debugging when users are on different versions,
- higher operational friction for each release.

We need a safe, reproducible update path sourced from GitHub Releases.

## Proposed solution
What:
- Build an in-app update system that checks GitHub Releases (via a manifest), prompts the user when an update is available, downloads the correct installer artifact, verifies integrity, and performs install-on-restart.
- Start with macOS support first (current user platform), while designing for cross-platform extension.

Why:
- Reduce manual update friction.
- Improve version consistency and supportability.
- Ensure update integrity through checksum (and optionally signature) verification.

Notes:
- Do NOT use `git pull` as an end-user update mechanism.
- Use immutable release artifacts from GitHub Releases.
- Keep UX explicit (prompt + release notes + user-controlled install action).

## Scope
In-scope:
- Add version source-of-truth in app (e.g., `APP_VERSION`).
- Add update manifest contract (e.g., `latest.json`) hosted with GitHub Release assets.
- Add update service to:
  - check for newer version,
  - compare semantic versions,
  - fetch release metadata,
  - download platform-specific artifact,
  - verify SHA-256 checksum,
  - stage installer for install-on-restart.
- Add a UI path for:
  - "Check for Updates",
  - update-available prompt with release notes,
  - download progress/status,
  - install/restart confirmation.
- Add GitHub Actions release workflow support for publishing artifacts + manifest.
- Add tests and docs for reproducibility.

Out-of-scope (for initial issue):
- Silent/background forced installs without user prompt.
- Delta/binary patch updates.
- Auto-updating while app is still running without restart.
- Full cross-platform parity in one pass (Windows/Linux can be follow-up issues).

## UX / fields / checkboxes
Screen/Tab:
- Main window app menu (or Help menu): `Check for Updates` action.
- Update dialog/modal for available update details.

Fields:
- Current version
- Latest version
- Release date
- Release notes summary

Checkboxes/toggles:
- Optional: `Automatically check for updates on startup` (default ON).

Buttons/actions:
- `Check Now`
- `Download Update`
- `Install on Restart`
- `Later`

Warnings/confirmations:
- Confirm before install/restart.
- Show clear error if checksum/signature verification fails and block install.

## Implementation notes / strategy
Approach:
1. Versioning:
   - Introduce canonical app version constant (single source of truth).
2. Update metadata:
   - Define `latest.json` contract, e.g.:
     - `version`
     - `published_at`
     - `notes_url`
     - `assets[]` with platform, url, sha256, size
3. Service layer:
   - `services/update_service.py` for check/download/verify logic.
   - Keep UI separated from HTTP/file logic (UI -> service only).
4. Installer handoff:
   - Stage downloaded file in app cache/update directory.
   - Trigger installer on app exit or restart flow.
5. Release automation:
   - GitHub Actions workflow to build artifacts and publish/update `latest.json`.

Data model / migrations:
- No DB schema migration required for MVP.
- If adding persisted update preference, use existing settings mechanism.

Risk areas:
- Corrupt or partial download handling.
- MITM or tampered artifact risk (must verify hash/signature).
- Platform-specific installer invocation behavior.
- Network timeouts/retries and clear user messaging.

## Acceptance criteria
- Given the app is on an older version, when user checks for updates, then app reports a newer version and shows release details.
- Given an available update, when user downloads it, then app verifies checksum before allowing install.
- Given checksum mismatch, when verification runs, then install is blocked and user sees actionable error.
- Given no new version, when user checks updates, then app clearly reports "up to date".
- Given startup auto-check enabled and network available, then app performs non-blocking check and only prompts if newer version exists.
- Given update install is initiated, then app can complete via restart flow without data loss.
- Release workflow publishes required manifest/asset metadata used by updater.

## Test plan
Automated tests:
- Unit tests for version comparison, manifest parsing, checksum verification, and error paths.
- Service tests with mocked HTTP responses:
  - no update,
  - update available,
  - malformed manifest,
  - download interrupted,
  - checksum mismatch.
- UI smoke/regression tests for update prompt actions and status transitions.
- Workflow validation test (or script) that manifest fields and artifact references are consistent.

Manual verification:
- Run app on older version build and verify prompt appears for newer GitHub release.
- Download and verify successful update package staging.
- Tamper test: modify downloaded file and confirm verification failure blocks install.
- Confirm app remains stable when offline and during timeout scenarios.

## Area
- UI
- Services
- Tools
- Docs
- Tests

## Notes
- [x] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [x] This change likely requires adding/updating scenario-based tests.
- [ ] This change likely touches the database schema or migrations.
- [ ] This change includes destructive actions (must add warnings/backup prompts).
