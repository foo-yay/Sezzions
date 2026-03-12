from PySide6.QtWidgets import QApplication

import __init__ as sezzions_package
from app_facade import AppFacade
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog


def test_help_menu_has_check_for_updates_action(tmp_path):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_menu.db"))
    window = MainWindow(facade)
    app.processEvents()

    assert hasattr(window, "check_updates_action")
    assert window.check_updates_action is not None
    assert "Check for" in window.check_updates_action.text()
    assert "Update" in window.check_updates_action.text()

    window.close()
    facade.db.close()


def test_settings_dialog_shows_software_version_and_update_controls(tmp_path):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_settings.db"))
    window = MainWindow(facade)

    dialog = SettingsDialog(window.settings, window)
    assert dialog.software_version_value_label.text() == getattr(sezzions_package, "__version__", "0.1.0")
    assert dialog.check_updates_now_button.text() == "Check for Updates Now"
    assert dialog.update_check_enabled_checkbox is not None
    assert dialog.update_check_interval_spin is not None

    dialog.close()
    window.close()
    facade.db.close()
    app.processEvents()


def test_periodic_update_check_creates_bell_notification(tmp_path):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_notify.db"))
    window = MainWindow(facade)

    facade.check_for_app_updates = lambda manifest_url=None: {
        "current_version": "0.1.0",
        "latest_version": "9.9.9",
        "update_available": True,
        "asset": {"platform": "macos-arm64", "url": "https://example.com/update.dmg", "sha256": "abc"},
        "notes_url": "https://example.com/notes",
        "published_at": "2026-03-12T00:00:00Z",
        "error": None,
    }

    window._perform_update_check(show_messages=False)

    notifications = facade.notification_service.get_all(
        include_dismissed=True,
        include_deleted=False,
        include_snoozed=True,
    )
    update_notifications = [n for n in notifications if n.type == "app_update_available" and not n.is_dismissed]
    assert len(update_notifications) == 1
    assert update_notifications[0].action_key == "open_updates"

    window.close()
    facade.db.close()
    app.processEvents()


def test_up_to_date_check_clears_existing_update_notification(tmp_path):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_clear.db"))
    window = MainWindow(facade)

    facade.check_for_app_updates = lambda manifest_url=None: {
        "current_version": "1.0.0",
        "latest_version": "9.9.9",
        "update_available": True,
        "asset": {"platform": "macos-arm64", "url": "https://example.com/update.zip", "sha256": "abc"},
        "notes_url": "https://example.com/notes",
        "published_at": "2026-03-12T00:00:00Z",
        "error": None,
    }
    window._perform_update_check(show_messages=False)

    facade.check_for_app_updates = lambda manifest_url=None: {
        "current_version": "1.0.0",
        "latest_version": "1.0.0",
        "update_available": False,
        "asset": None,
        "notes_url": None,
        "published_at": None,
        "error": None,
    }
    window._perform_update_check(show_messages=False)

    active = facade.notification_service.get_all(
        include_dismissed=False,
        include_deleted=False,
        include_snoozed=True,
    )
    assert all(n.type != "app_update_available" for n in active)

    all_notifications = facade.notification_service.get_all(
        include_dismissed=True,
        include_deleted=True,
        include_snoozed=True,
    )
    update_rows = [n for n in all_notifications if n.type == "app_update_available"]
    assert len(update_rows) == 1
    assert update_rows[0].is_deleted

    window.close()
    facade.db.close()
    app.processEvents()
