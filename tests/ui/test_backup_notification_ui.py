from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from desktop.ui.settings import Settings
from desktop.ui.main_window import MainWindow


def test_backup_completion_refreshes_notification_bell(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("desktop.ui.settings.default_settings_file", lambda: str(settings_path))
    monkeypatch.setattr("app_facade.settings_file_path", lambda: settings_path)

    settings = Settings(settings_file=str(settings_path))
    settings.set_automatic_backup_config(
        {
            "enabled": True,
            "directory": str(tmp_path / "backups"),
            "frequency_hours": 24,
            "last_backup_time": None,
            "notify_on_failure": True,
            "notify_when_overdue": True,
            "overdue_threshold_days": 1,
        }
    )
    settings.set("update_check_enabled", False)

    facade = AppFacade(str(tmp_path / "backup_notifications.db"))
    window = MainWindow(facade)

    facade.notification_service.create_or_update(
        type="backup_due",
        title="Database Backup Overdue",
        body="A database backup is overdue.",
    )
    window._refresh_notification_badge()
    assert window._notification_bell.toolTip() == "1 notification(s)"

    window.tools_tab._notify_backup_completed()
    app.processEvents()

    active = facade.notification_service.get_all()
    assert all(n.type != "backup_due" for n in active)
    assert window._notification_bell.toolTip() == "Notifications"

    window.close()
    facade.db.close()
    app.processEvents()
