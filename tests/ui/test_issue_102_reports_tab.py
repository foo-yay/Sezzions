"""
Headless UI smoke tests for Issue #102 (Reports tab Phase 1)
"""
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from app_facade import AppFacade
from ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication once for all tests in this module"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def app_facade():
    """Create in-memory app facade"""
    facade = AppFacade(":memory:")
    yield facade
    facade.db.close()


@pytest.fixture
def main_window(qapp, app_facade):
    """Create main window without showing it"""
    window = MainWindow(app_facade)
    yield window
    window.close()


def test_reports_tab_exists(main_window):
    """Reports tab should be present in the main tab bar."""
    labels = [main_window.tab_bar.tabText(i) for i in range(main_window.tab_bar.count())]
    assert any("Reports" in label for label in labels)


def test_reports_tab_widget_registered(main_window):
    """Reports tab widget should be attached to the main window stack."""
    assert hasattr(main_window, "reports_tab")
    assert main_window.stack.indexOf(main_window.reports_tab) != -1


def test_reports_tab_handles_refresh_error(main_window, monkeypatch):
    """Reports tab refresh should handle service errors without crashing."""
    reports_tab = main_window.reports_tab

    def _raise_error(*_args, **_kwargs):
        raise RuntimeError("Boom")

    monkeypatch.setattr(reports_tab.report_service, "get_kpi_snapshot", _raise_error)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

    reports_tab.refresh_data()
