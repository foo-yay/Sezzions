# Feature request: Settings entry point (gear icon next to bell) + shared Settings shell

## Problem / motivation
We need a first-class, always-available Settings entry point in the main header so users can discover and manage:
- Notification preferences (Issue #28 follow-on: thresholds, enable/disable certain rules, etc.)
- Future cross-cutting features that are not tied to a single tab (Issue #29 tax withholding estimates)

Right now, configuration is scattered (e.g., backup settings live in Tools). Notifications also has a pending “settings entry point” requirement.

## Proposed solution
Add a Settings entry point in the main header:
- A **gear icon** placed **next to the notification bell** (same header zone).
- Clicking it opens a **Settings dialog** (or drawer-like dialog) with:
  - A left navigation list (or simple tabs) for Settings sections.
  - A content area for the selected section.

### Initial Settings sections (v1)
- **Notifications** (host existing notification rule configuration)
  - Redemption pending-receipt threshold days (existing setting key)
  - Optional toggles to enable/disable rules by category (backup, redemptions)
- **Taxes** (placeholder section for Issue #29)
  - (No functionality required in this issue; just ensure the Settings shell can host it)

## Scope
In-scope:
- UI:
  - Add gear icon button next to bell in the main header overlay.
  - Implement a Settings dialog shell with section navigation.
  - Add a Notifications section UI that edits existing settings values (no popups).
- Services/Settings:
  - Use the existing settings persistence mechanism (settings.json via `ui/settings.py`).
  - Provide a safe API for reading/writing notification-related settings (prefer a small service layer wrapper if needed).

Out-of-scope:
- Implementing Issue #29 behavior/UI inside Settings (this issue should just enable it cleanly).
- Changing the existing Tools/backup configuration UX.

## UX / design requirements
- No modal popups for “notifications”; the gear should open a standard dialog.
- Keep header alignment consistent with the current notification bell overlay/inset.
- Settings dialog should match current theme behavior (Light/Blue/macOS).
- Keyboard: ESC closes the dialog.

## Acceptance criteria
- Gear icon appears next to the notification bell.
- Clicking gear opens Settings dialog.
- Settings dialog contains at least one real section: Notifications.
- Notifications section can edit:
  - `redemption_pending_receipt_threshold_days` (number input, min 0)
  - (Optional) enable/disable pending receipt rule entirely
- Saving settings persists to settings.json and takes effect without restart.

## Test plan
- Headless UI smoke:
  - Boot `QApplication`, instantiate `MainWindow(AppFacade(...))`, process events, click gear action, ensure dialog can open/close.
- Unit tests:
  - Settings write/read for the notification threshold key.

## Notes
- This issue is intentionally designed to support Issue #29 (tax withholding estimates) without duplicating settings entry points.
