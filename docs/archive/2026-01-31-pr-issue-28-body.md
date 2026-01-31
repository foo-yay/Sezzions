# Feature: Notification System with Bell Widget & Snooze/Dismiss/Delete (Issue #28)

## Summary

Implements a passive notification system for Sezzions to alert users about important events (backup reminders, redemption pending-receipt tracking) without modal popups. Users have full control over notification lifecycle via a notification center dialog.

Closes #28

## Changes

### Core Notification Framework

**New Files:**
- `models/notification.py`: Notification dataclass with severity (INFO/WARNING/ERROR), state management (read/dismissed/snoozed/deleted), composite key de-duplication
- `services/notification_service.py`: CRUD operations, state transitions, bulk operations (103 lines)
- `repositories/notification_repository.py`: JSON persistence to settings.json (87 lines)
- `services/notification_rules_service.py`: Rule evaluators for backup and redemption conditions (73 lines)

**Modified Files:**
- `app_facade.py`: Initialize and wire notification services

### UI Components

**New Files:**
- `ui/notification_widgets.py`: Bell widget with badge, notification center dialog, notification item widgets (308 lines)

**Modified Files:**
- `ui/main_window.py`: Integrate bell in menu bar corner, periodic QTimer evaluation (hourly), event handlers

### Tests

**New Files:**
- `tests/test_notification_service.py`: 19 unit tests covering:
  - CRUD operations
  - Composite key de-duplication
  - State transitions (read/unread, dismiss, snooze, delete)
  - Unread count calculation
  - Bulk operations (clear dismissed, dismiss by type)
  - All tests passing ✅

### Documentation

**Modified Files:**
- `docs/PROJECT_SPEC.md`: Added section 6.4 documenting notification system architecture, model, services, UI, rules, persistence
- `docs/status/CHANGELOG.md`: Added entry 2026-01-31-05 summarizing Issue #28 work

## Architecture

### Notification Model
- **Identity**: `type` (string), `subject_id` (optional), `title`, `body`, `severity` (enum)
- **Actions**: `action_key` (string), `action_payload` (dict) for routing user clicks to tabs/dialogs
- **State**: `created_at`, `read_at`, `dismissed_at`, `snoozed_until`, `deleted_at`
- **Properties**: `is_read`, `is_dismissed`, `is_snoozed`, `is_deleted`, `is_active`
- **De-duplication**: Composite key `(type, subject_id)` ensures only one notification per monitored condition

### NotificationService
- `create_or_update()`: De-dupes by composite key; updates existing if found
- `get_all()`, `get_active()`, `get_by_id()`, `get_unread_count()`
- State transitions: `mark_read()`, `mark_unread()`, `mark_all_read()`
- User actions: `dismiss()`, `snooze()`, `snooze_for_hours()`, `snooze_until_tomorrow()`, `delete()`
- Bulk: `clear_dismissed()`, `dismiss_by_type()`

### NotificationRulesService
- `evaluate_all_rules()`: Entry point called by QTimer (hourly) and on app startup
- **Backup rules**:
  - `backup_directory_missing`: automatic_backup enabled but directory not configured
  - `backup_due`: last backup > frequency threshold (warning severity)
  - `backup_overdue`: last backup > 2x frequency threshold (error severity)
  - Rules auto-dismiss when conditions resolve
- **Redemption pending-receipt rules**:
  - Queries: `SELECT * FROM redemptions WHERE receipt_date IS NULL AND redemption_date <= ?`
  - Creates one notification per pending redemption (`subject_id = redemption_id`)
  - Severity: INFO if < 30 days, WARNING if ≥ 30 days
  - Auto-dismisses when `redemption_service` marks `receipt_date`
- Event handlers: `on_backup_completed()`, `on_redemption_received(redemption_id)` called by Tools/Redemptions tabs

### UI Components
- **NotificationBellWidget**: QPushButton with badge count; lives in MainWindow menu bar corner
  - Shows "🔔" (no badge) when `unread_count = 0`
  - Shows "🔔 N" (with badge) when `unread_count > 0`
  - Clicks open NotificationCenterDialog
- **NotificationItemWidget**: QFrame for single notification in list
  - Severity icon (ℹ️/⚠️/❌), title (bold if unread), body, timestamp
  - Actions: "Open" (if action_key), "Snooze", "Dismiss", "Delete"
  - Background color differentiation for unread (light blue tint)
- **NotificationCenterDialog**: Scrollable list of active notifications
  - "Mark All Read" button
  - Snooze dialog: 1hr, 4hrs, 24hrs, "Until tomorrow 8am"
  - Delete confirmation dialog
  - Refreshes bell badge on close

### Persistence (v1)
- settings.json backed via NotificationRepository
- Future: Split DB-backed (redemption reminders) vs settings-backed (backup alerts) for scalability

### Periodic Evaluation
- MainWindow initializes QTimer (hourly) calling `_evaluate_notifications()`
- Evaluates on app startup
- Tools tab calls `main_window.on_backup_completed()` after backup success
- Redemptions tab can call `main_window.on_redemption_received(redemption_id)` after marking receipt_date

## Testing

**Unit Tests (19 tests, all passing):**
- `TestNotificationCRUD`: create, get_all, get_active, filtering
- `TestDeduplication`: composite key behavior
- `TestStateManagement`: read/unread, dismiss, snooze, delete transitions
- `TestUnreadCount`: count calculation, exclusions
- `TestBulkOperations`: clear_dismissed, dismiss_by_type

**Coverage:**
- NotificationService: 89% (11/103 lines uncovered: helper methods)
- NotificationRepository: 90% (9/87 lines uncovered: error paths)
- Notification model: 90% (6/61 lines uncovered: edge cases)

**No integration tests yet:**
- Future: Mock DB/settings, assert notification creation/dismissal for rule evaluators
- Future: Headless UI smoke test (boot MainWindow, assert bell exists, open center)

## Commits

1. `585a598`: Add notification models, services, and repositories (Issue #28 WIP)
2. `f29b4c2`: Add notification bell UI and periodic evaluation (Issue #28 WIP)
3. `50d16f9`: Add comprehensive notification service tests (Issue #28)
4. `c12fa92`: Update docs for notification system (Issue #28)

## Screenshots / Manual Testing

**Manual Verification Steps:**
1. Boot app (`python3 sezzions.py`)
2. Verify bell widget appears in menu bar (top right corner)
3. Enable automatic backup but don't configure directory → verify "Backup Directory Missing" notification
4. Configure automatic backup directory and set frequency to 1 hour → verify "Backup Due" notification if last backup > 1 hour ago
5. Create redemption and leave `receipt_date` NULL for > 30 days → verify "Redemption Pending Receipt" notification
6. Click bell → verify notification center opens with scrollable list
7. Test actions: Mark Read, Dismiss, Snooze (1hr, 4hrs, 24hrs, until tomorrow), Delete
8. Mark all read → verify badge count updates
9. Complete backup in Tools tab → verify backup notifications auto-dismiss
10. Mark redemption as received → verify redemption notification auto-dismisses

**UI Screenshot Placeholders:**
- (Add screenshots after manual testing if desired)

## Rollout / Deployment Notes

- No migrations required (settings.json persistence)
- No breaking changes
- Backward compatible: settings.json will create `notifications` array on first save
- No user action required on upgrade

## Future Enhancements (Out of Scope)

- Split persistence: DB-backed for redemption reminders (queryable), settings-backed for backup alerts
- Integration tests for NotificationRulesService
- Headless UI smoke test
- Custom notification sounds (optional, user-configurable)
- Notification filtering/search in center dialog
- "Dismiss all of this type" bulk action
- Email/webhook notification delivery (advanced)

## Issue Link

Closes #28
