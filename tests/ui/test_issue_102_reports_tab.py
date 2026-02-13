"""
Headless UI smoke tests for Issue #102 (Reports tab Phase 1)
"""
import pytest
from PySide6.QtWidgets import QApplication
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


def test_reports_tab_more_filters_toggle(main_window):
    """More Filters drawer should toggle via the tool button."""
    reports_tab = main_window.reports_tab
    assert reports_tab.more_filters_drawer.isHidden()

    reports_tab.more_filters_btn.setChecked(True)
    assert not reports_tab.more_filters_drawer.isHidden()

    reports_tab.more_filters_btn.setChecked(False)
    assert reports_tab.more_filters_drawer.isHidden()
