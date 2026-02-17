# Feature: Add automatic backup enablement reminder notification

## Problem

Users may not realize they should enable automatic backups, especially on first use or after settings reset. The existing `backup_directory_missing` notification only appears when automatic backups are already enabled but directory is missing, leaving users without a gentle reminder to enable data protection.

## Proposed Solution

Add a new `backup_not_enabled` notification that:
- Appears when automatic backups are disabled
- Severity: INFO (gentle reminder, not urgent)
- Action: Opens Tools → Database Tools
- Cooldown: 7 days when dismissed/deleted
- Resurfaces indefinitely until automatic backups are enabled

## Behavior

**When to show:**
- Automatic backups are disabled (`automatic_backup.enabled = False`)
- No active cooldown from previous dismiss/delete

**When to dismiss:**
- User enables automatic backups

**User control:**
- Mark read: Moves to "Read" group, 7-day cooldown before resurfacing
- Dismiss: Hides notification, 7-day cooldown before resurfacing
- Delete: Same as dismiss (7-day cooldown)
- Snooze: Temporary hide (1hr, 4hrs, 24hrs, until tomorrow)

## Distinction from Existing Notification

- **`backup_not_enabled`** (NEW): INFO severity, fires when automatic backups are disabled
- **`backup_directory_missing`** (EXISTING): WARNING severity, fires when automatic backups are enabled but directory is missing

These notifications are mutually exclusive: INFO shows when auto-backup is off, WARNING shows when auto-backup is on but misconfigured.

## Implementation

**Files to change:**
- `services/notification_rules_service.py`: Add check at start of `evaluate_backup_rules()`
- `docs/status/CHANGELOG.md`: Document new notification
- `docs/PROJECT_SPEC.md`: Update notification system section

**Test plan:**
- Launch app with automatic backups disabled → notification appears
- Enable automatic backups → notification dismissed
- Disable automatic backups → notification reappears after cooldown expires
- Delete notification → verify 7-day cooldown suppression
- Enable automatic backups with no directory set → WARNING notification appears instead

## Acceptance Criteria

- [ ] Notification appears on startup when automatic backups are disabled
- [ ] Notification auto-dismisses when automatic backups are enabled
- [ ] Delete/mark read applies 7-day cooldown suppression
- [ ] Notification resurfaces after cooldown expires if auto-backup still disabled
- [ ] WARNING notification appears when auto-backup enabled but directory missing
- [ ] All existing tests pass
- [ ] Manual verification with fresh settings
