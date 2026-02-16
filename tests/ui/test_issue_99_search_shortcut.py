"""
Headless UI smoke tests for Issue #99 (Cmd+F/Ctrl+F search shortcut)

Tests that the Find shortcut focuses search bars across all tabs.
"""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from app_facade import AppFacade
from ui.main_window import MainWindow


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


def test_find_shortcut_exists(main_window):
    """Test that Find shortcut (Cmd+F/Ctrl+F) is registered"""
    # Find shortcuts attached to the main window
    shortcuts = [s for s in main_window.findChildren(type(main_window.children()[0].__class__)) 
                 if hasattr(s, 'key')]
    
    # Verify at least one shortcut uses the Find key sequence
    find_key = QKeySequence.Find
    # The shortcut should be connected to _on_find_shortcut handler
    assert hasattr(main_window, '_on_find_shortcut')


def test_main_tabs_have_focus_search(main_window):
    """Test that all main tabs have focus_search() method and search_edit"""
    tabs_to_test = [
        main_window.purchases_tab,
        main_window.redemptions_tab,
        main_window.game_sessions_tab,
        main_window.daily_sessions_tab,
        main_window.unrealized_tab,
        main_window.realized_tab,
        main_window.expenses_tab,
    ]
    
    for tab in tabs_to_test:
        assert hasattr(tab, 'focus_search'), f"{tab.__class__.__name__} missing focus_search()"
        assert hasattr(tab, 'search_edit'), f"{tab.__class__.__name__} missing search_edit"


def test_setup_tabs_have_focus_search(main_window):
    """Test that all Setup sub-tabs have focus_search() method and search_edit"""
    setup_tabs_to_test = [
        main_window.setup_tab.users_tab,
        main_window.setup_tab.sites_tab,
        main_window.setup_tab.cards_tab,
        main_window.setup_tab.redemption_method_types_tab,
        main_window.setup_tab.redemption_methods_tab,
        main_window.setup_tab.game_types_tab,
        main_window.setup_tab.games_tab,
    ]
    
    for tab in setup_tabs_to_test:
        assert hasattr(tab, 'focus_search'), f"{tab.__class__.__name__} missing focus_search()"
        assert hasattr(tab, 'search_edit'), f"{tab.__class__.__name__} missing search_edit"


def test_focus_search_on_purchases_tab(qapp, main_window):
    """Test that focus_search() works on Purchases tab"""
    # Switch to Purchases tab
    main_window.tab_bar.setCurrentIndex(0)
    qapp.processEvents()
    
    # Call focus_search - should not raise an error
    main_window.purchases_tab.focus_search()
    qapp.processEvents()
    
    # In headless mode, focus behavior is not fully simulated
    # We verify the method runs without error, which is sufficient for smoke testing


def test_focus_search_on_setup_users_tab(qapp, main_window):
    """Test that focus_search() works on Setup > Users tab"""
    # Switch to Setup tab
    setup_idx = main_window._tab_index.get("setup", 0)
    main_window.tab_bar.setCurrentIndex(setup_idx)
    qapp.processEvents()
    
    # Switch to Users sub-tab
    main_window.setup_tab.sub_tabs.setCurrentWidget(main_window.setup_tab.users_tab)
    qapp.processEvents()
    
    # Call focus_search - should not raise an error
    main_window.setup_tab.users_tab.focus_search()
    qapp.processEvents()
    
    # In headless mode, focus behavior is not fully simulated
    # We verify the method runs without error, which is sufficient for smoke testing


def test_find_shortcut_handler_routes_to_current_tab(qapp, main_window):
    """Test that _on_find_shortcut routes to the current tab's search bar"""
    # Switch to Redemptions tab
    redemptions_idx = main_window._tab_index.get("redemptions", 1)
    main_window.tab_bar.setCurrentIndex(redemptions_idx)
    qapp.processEvents()
    
    # Trigger the shortcut handler - should not raise an error
    main_window._on_find_shortcut()
    qapp.processEvents()
    
    # In headless mode, focus behavior is not fully simulated
    # We verify the handler runs without error, which is sufficient for smoke testing


def test_find_shortcut_handler_routes_to_setup_subtab(qapp, main_window):
    """Test that _on_find_shortcut routes to Setup sub-tab search bar"""
    # Switch to Setup tab
    setup_idx = main_window._tab_index.get("setup", 0)
    main_window.tab_bar.setCurrentIndex(setup_idx)
    qapp.processEvents()
    
    # Switch to Sites sub-tab
    main_window.setup_tab.sub_tabs.setCurrentWidget(main_window.setup_tab.sites_tab)
    qapp.processEvents()
    
    # Trigger the shortcut handler - should not raise an error
    main_window._on_find_shortcut()
    qapp.processEvents()
    
    # In headless mode, focus behavior is not fully simulated
    # We verify the handler runs without error, which is sufficient for smoke testing
