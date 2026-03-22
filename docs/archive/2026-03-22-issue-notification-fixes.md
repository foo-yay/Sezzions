Summary
Three notification paths are reporting incorrect state. Overdue redemption notifications include synthetic "Balance Closed" loss rows, stale app-update notifications can linger after the app is already current, and overdue-backup notifications can persist after successful automatic backups.

Impact / scope
Impact:
- Notification center reports false-positive overdue redemption items.
- Notification center can keep showing an out-of-date app-update alert for an already-cleared version.
- Notification center can continue showing overdue automatic-backup alerts after the app successfully performs an automatic backup.
- Users may distrust notifications or miss real action items.

Scope:
- Update-notification cleanup when checks report no newer version
- Notification rules service
- Automatic-backup success flow / notification refresh
- Regression coverage for notification logic and UI refresh
- Docs updates for notification semantics

Steps to reproduce
1. Leave an older `app_update_available` notification persisted in settings, then run an update check that reports the app is already up to date.
2. Observe that the stale version alert can remain in notification history / resurfacing paths.
3. Create or keep a zero-dollar "Close Balance" / total-loss redemption old enough to cross the pending-receipt threshold.
4. Open the app and allow notification rules to evaluate.
5. Observe that the notification bell includes an overdue redemption reminder for the loss row even though the redemptions UI shows it as a loss with a displayed receipt date/status.
6. Enable automatic backups with a valid directory and allow an overdue backup notification to appear.
7. Let the scheduled automatic backup complete successfully.
8. Observe that the overdue backup notification can remain visible instead of clearing immediately.

Expected behavior
- Stale update notifications should be pruned when a newer check reports no update is available.
- Synthetic balance-close / total-loss redemptions should not generate overdue pending-receipt notifications.
- Successful automatic backups should clear overdue-backup notifications immediately and refresh the visible notification state.

Actual behavior
- Older `app_update_available` rows can accumulate in persisted notification state and survive later up-to-date checks.
- The overdue-redemption rule queries raw DB fields and still treats total-loss rows as pending because they retain NULL receipt dates and a default PENDING status.
- Automatic backup success updates last backup time and dismisses backup notifications in persistence, but the visible notification state can lag because the full post-backup notification refresh path is not used.

Logs / traceback
Investigation findings:
- Update checks only soft-deleted the currently visible app-update row, so older persisted rows could linger.
- Notification query currently filters on receipt_date IS NULL and COALESCE(status, 'PENDING') = 'PENDING'.
- Close Balance creates $0 redemptions with processed=True but without receipt_date, so the rows still match the overdue query.
- Automatic backup success updates last_backup_time and dismisses backup notifications, but the main-window refresh callback is bypassed.

Severity
High (data incorrect / frequent crash)

Environment
macOS desktop app runtime and source runtime (`python3 sezzions.py`) investigated on 2026-03-22.

Acceptance
- [x] I’ve checked `docs/PROJECT_SPEC.md` and this is unexpected.
- [x] This bug involves data correctness (should add/adjust a scenario-based test).
- [ ] I’m willing to help test a fix.
