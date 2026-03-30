from PySide6.QtWidgets import QApplication
from pathlib import Path
import zipfile

import __init__ as sezzions_package
from app_facade import AppFacade
from desktop.ui.main_window import MainWindow
from desktop.ui.settings_dialog import SettingsDialog


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


def test_manual_update_check_routes_to_update_now_dialog(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_dialog.db"))
    window = MainWindow(facade)

    captured = {}

    def _capture_dialog(result):
        captured["result"] = result

    monkeypatch.setattr(window, "_show_update_available_dialog", _capture_dialog)

    facade.check_for_app_updates = lambda manifest_url=None: {
        "current_version": "1.0.0",
        "latest_version": "1.0.1",
        "update_available": True,
        "asset": {"platform": "macos-arm64", "url": "https://example.com/update.zip", "sha256": "abc"},
        "notes_url": "https://example.com/notes",
        "published_at": "2026-03-12T00:00:00Z",
        "error": None,
    }

    window._perform_update_check(show_messages=True)

    assert "result" in captured
    assert captured["result"]["latest_version"] == "1.0.1"

    window.close()
    facade.db.close()
    app.processEvents()


def test_running_app_bundle_path_none_when_running_from_source(tmp_path):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_bundle_detect.db"))
    window = MainWindow(facade)

    assert window._running_app_bundle_path() is None

    window.close()
    facade.db.close()
    app.processEvents()


def test_update_now_disabled_in_development_runtime(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_dev_guard.db"))
    window = MainWindow(facade)

    monkeypatch.setattr(window, "_is_development_runtime", lambda: True)

    info_calls = {}

    def _fake_info(parent, title, text):
        info_calls["title"] = title
        info_calls["text"] = text

    monkeypatch.setattr("desktop.ui.main_window.QtWidgets.QMessageBox.information", _fake_info)

    update_now_called = {"called": False}

    def _fake_update_now(result):
        update_now_called["called"] = True

    monkeypatch.setattr(window, "_update_now", _fake_update_now)

    window._show_update_available_dialog({"latest_version": "1.0.1"})

    assert info_calls["title"] == "Update Available"
    assert "development build" in info_calls["text"]
    assert update_now_called["called"] is False

    window.close()
    facade.db.close()
    app.processEvents()


def test_update_now_fallback_includes_failure_reason_and_log_path(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_fallback.db"))
    window = MainWindow(facade)

    downloaded_zip = tmp_path / "Downloads" / "Sezzions Updates" / "v1.0.3" / "sezzions-macos-arm64.zip"
    downloaded_zip.parent.mkdir(parents=True, exist_ok=True)
    downloaded_zip.write_bytes(b"fake")

    facade.download_app_update = lambda asset, destination_dir: str(downloaded_zip)

    monkeypatch.setattr(window, "_try_auto_install_downloaded_update", lambda path: False)
    window._last_update_install_error = "No write permission for app destination"

    open_calls = {}
    monkeypatch.setattr(
        "desktop.ui.main_window.QtGui.QDesktopServices.openUrl",
        lambda url: open_calls.setdefault("url", str(url.toString())),
    )

    info_calls = {}

    def _fake_info(parent, title, text):
        info_calls["title"] = title
        info_calls["text"] = text

    monkeypatch.setattr("desktop.ui.main_window.QtWidgets.QMessageBox.information", _fake_info)

    window._update_now(
        {
            "asset": {"platform": "macos-arm64", "url": "https://example.com/app.zip", "sha256": "abc"},
            "latest_version": "1.0.3",
        }
    )

    assert "Update Downloaded" == info_calls["title"]
    assert "No write permission for app destination" in info_calls["text"]
    assert "update-installer.log" in info_calls["text"]
    assert "url" in open_calls

    window.close()
    facade.db.close()
    app.processEvents()


def test_record_update_install_error_writes_details_to_log(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_log.db"))
    window = MainWindow(facade)

    log_file = tmp_path / "update-installer.log"
    monkeypatch.setattr(window, "_update_install_log_path", lambda: log_file)

    window._record_update_install_error("test failure", details="trace line 1")

    assert window._last_update_install_error == "test failure"
    assert log_file.exists()
    assert "trace line 1" in log_file.read_text(encoding="utf-8")

    window.close()
    facade.db.close()
    app.processEvents()


def test_auto_install_uses_system_applications_when_translocated(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_translocated_system.db"))
    window = MainWindow(facade)

    downloaded_zip = tmp_path / "sezzions-macos-arm64.zip"
    with zipfile.ZipFile(downloaded_zip, "w") as archive:
        archive.writestr("sezzions-macos-arm64.app/Contents/MacOS/sezzions", "bin")

    translocated_bundle = Path(
        "/private/var/folders/test/AppTranslocation/random/d/sezzions-macos-arm64.app"
    )
    monkeypatch.setattr(window, "_running_app_bundle_path", lambda: translocated_bundle)

    log_file = tmp_path / "update-installer.log"
    monkeypatch.setattr(window, "_update_install_log_path", lambda: log_file)

    popen_calls = {}

    class _DummyProcess:
        pass

    def _fake_popen(args, **kwargs):
        popen_calls["args"] = args
        return _DummyProcess()

    monkeypatch.setattr("desktop.ui.main_window.subprocess.Popen", _fake_popen)
    monkeypatch.setattr(
        "desktop.ui.main_window.os.access",
        lambda p, mode: str(p) == "/Applications",
    )

    assert window._try_auto_install_downloaded_update(downloaded_zip) is True
    assert "args" in popen_calls
    assert popen_calls["args"][3] == "/Applications/sezzions-macos-arm64.app"

    window.close()
    facade.db.close()
    app.processEvents()


def test_auto_install_falls_back_to_user_applications_when_translocated(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_translocated_user.db"))
    window = MainWindow(facade)

    downloaded_zip = tmp_path / "sezzions-macos-arm64.zip"
    with zipfile.ZipFile(downloaded_zip, "w") as archive:
        archive.writestr("sezzions-macos-arm64.app/Contents/MacOS/sezzions", "bin")

    translocated_bundle = Path(
        "/private/var/folders/test/AppTranslocation/random/d/sezzions-macos-arm64.app"
    )
    monkeypatch.setattr(window, "_running_app_bundle_path", lambda: translocated_bundle)

    fake_home = tmp_path / "fake-home"
    expected_parent = fake_home / "Applications"
    expected_target = expected_parent / "sezzions-macos-arm64.app"

    monkeypatch.setattr("desktop.ui.main_window.Path.home", staticmethod(lambda: fake_home))
    monkeypatch.setattr(
        "desktop.ui.main_window.os.access",
        lambda p, mode: str(p) == str(expected_parent),
    )

    popen_calls = {}

    class _DummyProcess:
        pass

    def _fake_popen(args, **kwargs):
        popen_calls["args"] = args
        return _DummyProcess()

    monkeypatch.setattr("desktop.ui.main_window.subprocess.Popen", _fake_popen)
    monkeypatch.setattr(window, "_update_install_log_path", lambda: tmp_path / "update-installer.log")

    assert window._try_auto_install_downloaded_update(downloaded_zip) is True
    assert "args" in popen_calls
    assert popen_calls["args"][3] == str(expected_target)

    window.close()
    facade.db.close()
    app.processEvents()


def test_auto_install_script_clears_quarantine_and_retries_open(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_script_resilience.db"))
    window = MainWindow(facade)

    downloaded_zip = tmp_path / "sezzions-macos-arm64.zip"
    with zipfile.ZipFile(downloaded_zip, "w") as archive:
        archive.writestr("sezzions-macos-arm64.app/Contents/MacOS/sezzions", "bin")

    app_bundle = tmp_path / "sezzions-macos-arm64.app"
    monkeypatch.setattr(window, "_running_app_bundle_path", lambda: app_bundle)
    monkeypatch.setattr(
        "desktop.ui.main_window.os.access",
        lambda p, mode: str(p) == str(app_bundle.parent),
    )
    monkeypatch.setattr(window, "_update_install_log_path", lambda: tmp_path / "update-installer.log")

    popen_calls = {}

    class _DummyProcess:
        pass

    def _fake_popen(args, **kwargs):
        popen_calls["args"] = args
        return _DummyProcess()

    monkeypatch.setattr("desktop.ui.main_window.subprocess.Popen", _fake_popen)

    assert window._try_auto_install_downloaded_update(downloaded_zip) is True
    script_path = Path(popen_calls["args"][1])
    script_content = script_path.read_text(encoding="utf-8")

    assert "xattr -dr com.apple.quarantine" in script_content
    assert "TMP_APP=\"${TARGET_APP}.updating\"" in script_content
    assert "chmod -R u+rwx,go+rx \"$TMP_APP/Contents/MacOS\"" in script_content
    assert "open -n \"$TARGET_APP\"" in script_content

    window.close()
    facade.db.close()
    app.processEvents()


def test_auto_install_uses_ditto_extraction_on_macos(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    facade = AppFacade(str(tmp_path / "ui_updates_ditto_extract.db"))
    window = MainWindow(facade)

    downloaded_zip = tmp_path / "sezzions-macos-arm64.zip"
    downloaded_zip.write_bytes(b"placeholder")

    app_bundle = tmp_path / "sezzions-macos-arm64.app"
    monkeypatch.setattr(window, "_running_app_bundle_path", lambda: app_bundle)
    monkeypatch.setattr(window, "_update_install_log_path", lambda: tmp_path / "update-installer.log")
    monkeypatch.setattr("desktop.ui.main_window.sys.platform", "darwin")
    monkeypatch.setattr("desktop.ui.main_window.shutil.which", lambda cmd: "/usr/bin/ditto" if cmd == "ditto" else None)
    monkeypatch.setattr(
        "desktop.ui.main_window.os.access",
        lambda p, mode: str(p) == str(app_bundle.parent),
    )

    run_calls = {}

    class _RunResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(args, **kwargs):
        run_calls["args"] = args
        extract_dir = Path(args[-1])
        extracted_app = extract_dir / "sezzions-macos-arm64.app" / "Contents" / "MacOS"
        extracted_app.mkdir(parents=True, exist_ok=True)
        (extracted_app / "sezzions").write_text("bin", encoding="utf-8")
        return _RunResult()

    monkeypatch.setattr("desktop.ui.main_window.subprocess.run", _fake_run)

    popen_calls = {}

    class _DummyProcess:
        pass

    def _fake_popen(args, **kwargs):
        popen_calls["args"] = args
        return _DummyProcess()

    monkeypatch.setattr("desktop.ui.main_window.subprocess.Popen", _fake_popen)

    assert window._try_auto_install_downloaded_update(downloaded_zip) is True
    assert run_calls["args"][:3] == ["ditto", "-x", "-k"]
    assert "args" in popen_calls
    extracted_candidate = Path(popen_calls["args"][2])
    assert extracted_candidate.stat().st_mode & 0o111

    window.close()
    facade.db.close()
    app.processEvents()
