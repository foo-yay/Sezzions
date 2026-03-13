## Summary
Add user-configurable database location management:
1) First-run startup prompt to choose DB folder before app fully starts.
2) Settings > Data section shows current DB path and allows changing it safely.

## Problem
- Packaged app startup can fail or be confusing when default DB path is not user-intentional.
- Users need explicit control over where their data lives.
- Changing DB location manually is error-prone.

## Proposed UX
### First run (no configured DB path)
- Before loading the main app, show a modal startup prompt:
  - Option A: Use default recommended location.
  - Option B: Choose custom folder/file location.
- Create or load DB from selected location.
- Persist selected path in app settings so future launches skip the prompt.

### Settings > Data
- Display current DB path (copyable/selectable).
- Add `Change Database Location...` action.
- On change, show guided migration dialog:
  - `Copy and Switch` (recommended default)
  - `Move and Switch` (copy + verify + delete source)
  - Optional checkbox (or follow-up prompt) to delete old DB after successful copy.
- After successful switch, app uses the new DB path immediately (or after a controlled restart if required).

## Recommended behavior (safety)
Default to **Copy and Switch**, then optionally offer deleting old DB.
Reason:
- Minimizes data-loss risk if interrupted.
- Easier rollback if user picked wrong destination.
- Move can be offered as advanced option, but should still use copy-verify-delete semantics.

## Scope
- Startup path resolution/persistence logic.
- First-run selection dialog and validation.
- Settings > Data UI additions for path display and relocation flow.
- Safe DB relocation implementation (copy/move with verification).
- Error handling and user messaging.
- Tests + docs/changelog updates.

## Acceptance Criteria
1. First launch with no configured DB path prompts user before main app is fully initialized.
2. User can select custom location; app creates/loads DB there and persists setting.
3. Settings > Data shows active DB path.
4. User can change location from Settings > Data.
5. `Copy and Switch` works and preserves existing data.
6. Optional delete-old step only occurs after successful copy+verification.
7. Failures (permission denied, invalid path, copy failure) leave current DB unchanged.
8. No partial migration state; app remains usable.

## Test Matrix (required)
### Happy paths
- First-run select custom location and create new DB.
- Change location with `Copy and Switch` and verify data presence in new location.

### Edge cases
- Destination path unwritable.
- Destination already has existing DB file (confirm overwrite/abort behavior).
- User cancels prompt (define fallback behavior explicitly).

### Failure injection
- Simulate copy failure mid-operation and assert source DB remains active and intact.

### Invariants
- Active DB path only updates after successful migration.
- Source DB remains unchanged unless explicit successful delete-old step.

## Non-goals
- Multi-database profiles/switcher.
- Cloud sync.

## Docs to update (when implementing)
- docs/PROJECT_SPEC.md
- docs/status/CHANGELOG.md

## Notes
- This issue is for planning/implementation tracking only.
- Do not start implementation until owner approval.