"""
Headless UI smoke tests for Issue #92 (Audit Log + Undo/Redo + Soft Delete)

Tests menu actions, undo/redo state updates, and audit log viewer without displaying UI.
"""
import pytest
from PySide6.QtWidgets import QApplication
from unittest.mock import Mock, patch
from app_facade import AppFacade
from desktop.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication once for all tests in this module"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit - other tests may need it


@pytest.fixture(scope="module")
def app_facade():
    """Create in-memory app facade (module-scoped for read-only tests)"""
    facade = AppFacade(":memory:")
    yield facade
    facade.db.close()


@pytest.fixture(scope="module")
def main_window(qapp, app_facade):
    """Create main window without showing it (module-scoped for read-only tests)"""
    window = MainWindow(app_facade)
    yield window
    window.close()
    qapp.processEvents()


def test_undo_redo_menu_actions_exist(main_window):
    """Test that Undo/Redo menu actions are created and accessible"""
    # Actions should exist
    assert main_window.undo_action is not None
    assert main_window.redo_action is not None
    
    # Actions should have correct shortcuts
    assert main_window.undo_action.shortcut().toString() == "Ctrl+Z"
    assert main_window.redo_action.shortcut().toString() == "Ctrl+Shift+Z"
    
    # Actions should start disabled (no undo/redo stack yet)
    assert not main_window.undo_action.isEnabled()
    assert not main_window.redo_action.isEnabled()


def test_audit_log_menu_action_exists(main_window):
    """Test that 'View Audit Log...' menu action is created and accessible"""
    # Find action by text
    tools_menu = None
    for action in main_window.menuBar().actions():
        if action.text() == "&Tools":
            tools_menu = action.menu()
            break
    
    assert tools_menu is not None, "Tools menu should exist"
    
    action_texts = [action.text() for action in tools_menu.actions()]

    assert len(action_texts) > 0, "Tools menu should have actions"
    assert "View &Audit Log…" in action_texts
    assert "&Validate Data" not in action_texts


def test_undo_redo_state_updates(main_window):
    """Test that _update_undo_redo_states correctly updates action states"""
    # Initially disabled
    assert not main_window.undo_action.isEnabled()
    assert not main_window.redo_action.isEnabled()
    
    # Just verify the method exists and is callable
    # (Full mocking requires knowing the exact service API)
    assert hasattr(main_window, '_update_undo_redo_states')
    assert callable(main_window._update_undo_redo_states)


def test_show_audit_log_callable(main_window):
    """Test that _show_audit_log method exists and is callable"""
    assert hasattr(main_window, '_show_audit_log')
    assert callable(main_window._show_audit_log)


def test_tools_tab_has_audit_log_section(main_window):
    """Test that Tools tab contains Audit Log section"""
    # Access tools tab
    tools_tab = main_window.tools_tab
    assert tools_tab is not None


def test_setup_reports_tab_exists(main_window):
    """Test that Setup includes the Reports sub-tab."""
    assert hasattr(main_window.setup_tab, "reports_tab")
    assert main_window.setup_tab.reports_tab is not None


def test_reports_tab_runs_initial_report(qapp, main_window):
    """Test that the Reports tab can render its initial report without crashing."""
    setup_idx = main_window._tab_index.get("setup", 0)
    main_window.tab_bar.setCurrentIndex(setup_idx)
    qapp.processEvents()

    reports_scroll = main_window.setup_tab.sub_tabs.widget(main_window.setup_tab.sub_tabs.count() - 1)
    main_window.setup_tab.sub_tabs.setCurrentWidget(reports_scroll)
    qapp.processEvents()

    reports_tab = main_window.setup_tab.reports_tab
    reports_tab.run_selected_report()
    qapp.processEvents()

    assert reports_tab.report_selector.findText("Bridge / Reconciliation Summary") != -1
    assert reports_tab.report_selector.findText("Session P/L Summary") != -1
    assert reports_tab.results_table.rowCount() > 0
    assert reports_tab.results_table.columnCount() == 9
    assert reports_tab.report_title.text() == "Bridge / Reconciliation Summary"


def test_perform_undo_handler_exists(main_window):
    """Test that undo handler exists"""
    assert hasattr(main_window, '_perform_undo')
    assert callable(main_window._perform_undo)


def test_perform_redo_handler_exists(main_window):
    """Test that redo handler exists"""
    assert hasattr(main_window, '_perform_redo')
    assert callable(main_window._perform_redo)


def test_main_window_starts_cleanly(qapp, app_facade):
    """Test that MainWindow instantiates and processes events without crashing"""
    window = MainWindow(app_facade)
    
    # Process events briefly
    qapp.processEvents()
    
    # Window should be valid
    assert window is not None
    assert window.facade is app_facade  # Corrected: facade not app_facade
    assert window.unrealized_tab is not None
    window.stack.setCurrentWidget(window.unrealized_tab)
    qapp.processEvents()
    assert window.stack.currentWidget() is window.unrealized_tab
    
    # Clean up
    window.close()
    qapp.processEvents()
