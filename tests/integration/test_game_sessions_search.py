"""Integration test for Game Sessions tab search (Issue #71)."""

import pytest
from decimal import Decimal
from datetime import date
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from desktop.ui.tabs.game_sessions_tab import GameSessionsTab


@pytest.fixture
def app(qapp):
    """Ensure QApplication exists."""
    return qapp


@pytest.fixture
def facade():
    """Create AppFacade with test database."""
    return AppFacade(":memory:")


@pytest.fixture
def populated_facade(facade):
    """Create facade with sample data for search testing."""
    # Create users
    user1 = facade.create_user(name="Alice Smith", email="alice@test.com")
    user2 = facade.create_user(name="Bob Jones", email="bob@test.com")
    
    # Create sites
    site1 = facade.create_site(name="CasinoX", url="https://casinox.com")
    site2 = facade.create_site(name="LuckyY", url="https://luckyy.com")
    
    # Create game type and games
    game_type = facade.create_game_type(name="Slots")
    game1 = facade.create_game(
        name="Mega Fortune",
        game_type_id=game_type.id,
    )
    game2 = facade.create_game(
        name="Lucky Stars",
        game_type_id=game_type.id,
    )
    
    # Create game sessions
    facade.create_game_session(
        user_id=user1.id,
        site_id=site1.id,
        game_id=game1.id,
        session_date=date(2024, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("150.00"),
        starting_redeemable=Decimal("100.00"),
        ending_redeemable=Decimal("150.00"),
        notes="Won big on spins",
    )
    
    facade.create_game_session(
        user_id=user2.id,
        site_id=site2.id,
        game_id=game2.id,
        session_date=date(2024, 1, 16),
        starting_balance=Decimal("200.00"),
        ending_balance=Decimal("180.00"),
        starting_redeemable=Decimal("200.00"),
        ending_redeemable=Decimal("180.00"),
        notes="Lost a bit",
    )
    
    return facade


def test_search_by_user_name(app, populated_facade, qtbot):
    """Search by user name should filter sessions correctly."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time" so test sessions from 2024 are visible
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Verify we have sessions
    assert len(tab.sessions) == 2
    
    # Search for "Alice" (user name)
    tab.search_edit.setText("Alice")
    tab.apply_filters()
    
    # Check filtered results
    filtered = tab.filtered_sessions
    assert len(filtered) == 1
    assert filtered[0].user_id == populated_facade.get_all_users()[0].id


def test_search_by_site_name(app, populated_facade, qtbot):
    """Search by site name should filter sessions correctly."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time"
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Search for "LuckyY" (site name)
    tab.search_edit.setText("LuckyY")
    tab.apply_filters()
    
    # Check filtered results
    filtered = tab.filtered_sessions
    assert len(filtered) == 1
    sites = {s.id: s for s in populated_facade.get_all_sites()}
    assert sites[filtered[0].site_id].name == "LuckyY"


def test_search_by_game_name(app, populated_facade, qtbot):
    """Search by game name should filter sessions correctly."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time"
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Search for "Fortune" (partial game name)
    tab.search_edit.setText("Fortune")
    tab.apply_filters()
    
    # Check filtered results
    filtered = tab.filtered_sessions
    assert len(filtered) == 1
    games = {g.id: g for g in populated_facade.list_all_games()}
    assert "Fortune" in games[filtered[0].game_id].name


def test_search_by_numeric_value(app, populated_facade, qtbot):
    """Search by numeric balance should still work."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time"
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Search for "200" (starting balance of second session)
    tab.search_edit.setText("200")
    tab.apply_filters()
    
    # Check filtered results
    filtered = tab.filtered_sessions
    assert len(filtered) == 1
    assert filtered[0].starting_balance == Decimal("200.00")


def test_search_no_results(app, populated_facade, qtbot):
    """Search with no matches should return empty list."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time"
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Search for something that doesn't exist
    tab.search_edit.setText("NonexistentTerm")
    tab.apply_filters()
    
    # Check filtered results
    filtered = tab.filtered_sessions
    assert len(filtered) == 0


def test_search_case_insensitive(app, populated_facade, qtbot):
    """Search should be case-insensitive."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time"
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Search for lowercase version of site name
    tab.search_edit.setText("casinox")
    tab.apply_filters()
    
    # Check filtered results
    filtered = tab.filtered_sessions
    assert len(filtered) == 1
    sites = {s.id: s for s in populated_facade.get_all_sites()}
    assert sites[filtered[0].site_id].name == "CasinoX"


def test_clear_search_shows_all(app, populated_facade, qtbot):
    """Clearing search should show all sessions."""
    tab = GameSessionsTab(populated_facade)
    qtbot.addWidget(tab)
    
    # Set date filter to "All Time"
    tab.date_filter.set_all_time()
    tab.apply_filters()
    
    # Search for something
    tab.search_edit.setText("Alice")
    tab.apply_filters()
    assert len(tab.filtered_sessions) == 1
    
    # Clear search
    tab.search_edit.setText("")
    tab.apply_filters()
    
    # All sessions should be visible again
    assert len(tab.filtered_sessions) == 2
