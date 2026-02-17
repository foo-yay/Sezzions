# Feature: Add backup directory configuration reminder notification

## Problem

Users may not realize they should configure a backup directory, especially on first use or after settings reset. The existing `backup_directory_missing` notification only appears when automatic backups are enabled, leaving users without a gentle reminder to set up data protection.

## Proposed Solution

Add a new `backup_directory_not_configured` notification that:
- Appears when backup directory is not set, **regardless** of whether automatic backups are enabled
- Severity: INFO (gentle reminder, not urgent)
- Action: Opens Tools → Database Tools
- Cooldown: 7 days when dismissed/deleted
- Resurfaces indefinitely until directory is configured

## Behavior

**When to show:**
- Backup directory is empty/not configured
- No active cooldown from previous dismiss/delete

**When to dismiss:**
- User configures a backup directory (non-empty)

**User control:**
- Mark read: Moves to "Read" group, 7-day cooldown before resurfacing
- Dismiss: Hides notification, 7-day cooldown before resurfacing
- Delete: Same as dismiss (7-day cooldown)
- Snooze: Temporary hide (1hr, 4hrs, 24hrs, until tomorrow)

## Distinction from Existing Notification

- **`backup_directory_not_configured`** (NEW): INFO severity, fires for all users regardless of auto-backup state
- **`backup_directory_missing`** (EXISTING): WARNING severity, only fires when automatic backups are enabled but directory is missing

When both conditions are true (auto-backup enabled + directory missing), the WARNING takes precedence as it's more urgent.

## Implementation

**Files to change:**
- `services/notification_rules_service.py`: Add check at start of `evaluate_backup_rules()`
- `docs/status/CHANGELOG.md`: Document new notification
- `docs/PROJECT_SPEC.md`: Update notification system section

**Test plan:**
- Launch app with no backup directory configured → notification appears
- Configure backup directory → notification dismissed
- Clear directory → notification reappears
- Delete notification → verify 7-day cooldown suppression
- Enable automatic backups with no directory → WARNING notification takes precedence

## Acceptance Criteria

- [ ] Notification appears on startup when backup directory is not configured
- [ ] Notification auto-dismisses when directory is configured
- [ ] Delete/mark read applies 7-day cooldown suppression
- [ ] Notification resurfaces after cooldown expires if directory still not set
- [ ] WARNING notification takes precedence when auto-backup enabled
- [ ] All existing tests pass
- [ ] Manual verification with fresh settings
