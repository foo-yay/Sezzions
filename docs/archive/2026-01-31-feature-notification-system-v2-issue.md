# Feature request: Robust Notifications System (v2)

## Problem / motivation
Sezzions needs a first-class, modular notifications system so the app can proactively surface operational events and time-sensitive reminders instead of relying on users to remember to check Tools or discover problems after the fact.

Without notifications:
- Backups get missed (data-loss risk).
- Time-sensitive actions (e.g., redemption limits) are easy to miss.
- The app feels “silent” and non-guiding.

This replaces/supersedes the older Notifications System idea in #6, reflecting current architecture (services-driven, UI does not own business rules).

## Proposed solution
What:
- Implement a modular notifications framework with:
  - A global notification bell (badge count) in the main window.
  - A notification center/panel that lists notifications.
  - Manageable notifications: mark read/unread, dismiss, delete, snooze.
  - Actionable notifications (optional): each notification can expose an action (e.g., “Backup now”, “View redemptions”).
  - A rules/evaluator layer that generates notifications from app state (settings + DB) without scattering logic across UI.
- Provide an initial set of notification types (see Scope).

Why:
- Improves safety (backup reminders), correctness (recalc prompts), and time-sensitive workflows (redemption limit reminders).
- Keeps strict layering: services decide *what* to notify; UI renders and routes actions.
- Creates a base that can be extended with new notification rules without changing the UI each time.

Notes:
- Use stable identifiers (notification `type` + `subject_id`) so rules can de-dupe and user actions (dismiss/snooze) can persist across restarts.
- Avoid storing raw callables in persisted notifications. Use `action_key` + `payload`.

## Recommendations (notification types + related features)
Recommended notification categories:
- Operational / safety:
  - Backup: due/overdue, backup directory missing/misconfigured, backup failed.
- Workflow guidance:
  - “Recalculation recommended” after imports/repairs (non-destructive action that navigates user to Tools).
- Time-sensitive reminders:
  - Redemption “pending receipt” time limit (threshold-based; configurable):
    - Notify when a redemption has been submitted but not received for > N days.
    - Keep this as a standard reminder notification (not an ERROR; reserve ERROR for true failures like backup failures).

Nice-to-have notification features (optional follow-ups):
- Notification preferences (per-type enable/disable; thresholds; quiet hours / do-not-disturb).
- Filtering/searching in the notification center (severity/type/date).
- “Mark all read”, “Clear all dismissed”, and/or “Archive” view.
- Optional future channels: email/SMS/webhook (out-of-scope for v1, but design should not prevent it).

Recommended settings (v1 or v1.5):
- Global enable/disable notifications.
- Indicator behavior: show a red dot when unread > 0.
- Optional: show an unread count (instead of dot) as a setting.
- Per-notification-type toggles.
- Default snooze presets (e.g., 1h/4h/1d) and “snooze until tomorrow morning”.
- Thresholds:
  - Redemption pending receipt days (N).
  - (No separate backup grace period; use existing backup cadence).

## Scope
In-scope (v1):
- Core framework
  - `Notification` model (id/type/subject_id/title/body/severity/created_at).
  - State fields for manageability: `read_at`, `dismissed_at`, `snoozed_until`, `deleted_at` (or equivalent).
  - Service-layer APIs: create/upsert, list (active + dismissed), dismiss, delete, snooze, mark read/unread.
  - De-dupe behavior by `(type, subject_id)`.
- Storage
  - Persist notification state so it survives restarts.
  - Recommendation: split storage responsibilities:
    - DB-derived reminders (e.g., redemption time limit) should travel with the database (store state in DB).
    - Machine/ops reminders (e.g., backup directory misconfigured) can remain in settings.json.
  - If splitting storage is too heavy for v1, choose one backend explicitly and document the trade-off.
- UI
  - Main window notification bell + badge.
  - Notification center/panel/dialog:
    - Sort newest-first; show severity icon/color.
    - Per-item actions: Open (if supported), Snooze, Dismiss, Delete.
    - Bulk actions: Mark all read, Clear dismissed (optional).
- Notification rules/evaluators (initial set)
  - Backup notifications:
    - Auto-backup enabled but directory missing/misconfigured → WARNING (persistent).
    - Backup due/overdue based on configured cadence + last successful backup → WARNING (persistent; deduped).
    - Backup failure → ERROR (persistent until addressed).
  - Redemption pending-receipt notifications:
    - When a redemption has been submitted but not received for > N days → WARNING.
    - (Optional) When > M days (higher threshold) → ERROR.
- Scheduling
  - Evaluate rules at startup and periodically (e.g., hourly) via a controller/UI-owned QTimer that calls service-layer evaluators.

Out-of-scope (v1):
- Email/SMS/push notifications.
- Complex analytics-driven alerts (e.g., anomaly detection).
- A full “audit log viewer” UI.
- Large redesign of the backup system itself (only integrate with existing flows).

## UX / fields / checkboxes
Screen/Tab:
- Main window header: notification bell + badge.
- Main window header: settings gear icon next to the bell.
- Notification center panel/dialog (global).
- Settings panel/dialog (global) (new section; not the Tools tab).

Fields:
- List item shows: title, body, timestamp, severity indicator.
- Optional context line (e.g., “Site: …”, “Session: …”) if `subject_id` maps to a domain entity.

Checkboxes/toggles:
- (v1): “Enable notifications” global setting (default true).
- (v1 or v1.5): per-type toggles.
- (v1): “Redemption pending receipt threshold (days)”.
- (v1): “Indicator shows unread only” (default: unread-only).

Buttons/actions:
- Bell: open notification center.
- Gear: open Settings.
- Notification item actions:
  - “Open” (if action exists)
  - “Snooze” (preset options like 1h/4h/1d, plus custom datetime)
  - “Dismiss” (hide from active list)
  - “Delete” (remove/forget)
- Bulk:
  - “Mark all read”
  - “Clear dismissed” (optional)

Warnings/confirmations:
- Deleting a notification should confirm (or provide undo) if deletion is permanent.
- Any action that triggers destructive/bulk operations must preserve existing confirmations.

UX note:
- Do not use pop-up notifications; use a red-dot indicator on the bell when there are unread notifications.

## Implementation notes / strategy
Approach:
- Add a service-layer `NotificationService` and one or more rule evaluators (e.g., `NotificationRulesService`) that computes/upserts notifications.
- Model notifications as plain dataclasses/DTOs + persistence layer (repo) rather than UI-owned objects.
- Use `action_key` + `payload` for actions, so UI can route actions without holding callables in persisted state.
- Ensure all service updates that affect UI are delivered safely to the UI thread (Qt signals/queued invocation) to avoid threading issues.

Data model / migrations (if any):
- Likely yes if we persist notification state in DB.
- If DB-backed:
  - Add a `notifications` table or a `notification_state` table keyed by `(type, subject_id)`.
- If settings-backed:
  - Add a `notifications` object (or `notification_state`) to settings.json.

Risk areas:
- Threading (notifications emitted from background tasks).
- Duplication spam (hourly checks must be idempotent/deduped).
- Persistence semantics (what travels with DB vs machine settings).
- UX overload (too many notifications); mitigate via severity, grouping, and snooze.

## Acceptance criteria
- Given no active notifications, when the app launches, then the bell badge is hidden/0 and the notification center shows an empty state.
- Given at least one active notification, when the app launches, then the bell badge shows the correct count.
- Given a notification is created with `(type, subject_id)`, when the evaluator runs again, then the system upserts/dedupes rather than adding duplicates.
- Given a user dismisses a notification, when the notification center refreshes, then it no longer appears in the active list and badge count updates.
- Given a user snoozes a notification until a future time, when the notification center refreshes, then it is hidden until the snooze expires.
- Given a user deletes a notification, when the notification center refreshes (and after restart), then it does not reappear unless the underlying rule re-creates it.
- Given auto-backup is enabled and backup directory is missing/misconfigured, when the app evaluates rules, then a persistent WARNING notification appears.
- Given backup cadence indicates a backup is due/overdue, when rules evaluate, then a persistent WARNING “backup due” notification appears.
- Given a successful backup completes, when the completion handler runs, then any “backup due” notification is dismissed/cleared automatically.
- Given the redemption pending-receipt threshold is configured, when a redemption has been submitted but not received for > N days, then a redemption-related notification appears with an action that navigates to the relevant view.
- Notification state persists across app restart (read/dismiss/snooze/delete behavior preserved per chosen persistence design).

## Test plan
Automated tests:
- Unit tests:
  - NotificationService CRUD + de-dupe + snooze/dismiss/delete state.
  - Rule evaluators: backup due/misconfig, redemption threshold evaluation.
- Integration tests:
  - Persistence round-trip (DB or settings) for notification state.
- UI smoke (headless):
  - Create a QApplication, instantiate MainWindow(AppFacade(...)), ensure bell widget exists and opening the notification center does not crash.

Manual verification:
- Start app with auto-backup enabled but no directory → see backup config notification.
- Configure directory, run backup → verify due notification clears.
- Create a redemption near/over threshold in test DB → verify notification appears and action navigates.
- Restart app → state persists (snoozed stays hidden until expiry).

## Area
UI / Services / Database/Repositories

## Notes
- [X] This change likely requires updating docs/PROJECT_SPEC.md.
- [X] This change likely requires adding/updating scenario-based tests.
- [X] This change likely touches the database schema or migrations.
- [X] This change includes destructive actions (must add warnings/backup prompts).
