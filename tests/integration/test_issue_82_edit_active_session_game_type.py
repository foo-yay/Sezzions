"""
Test Issue #82: Verify Game Type & Game fields can be edited on active/in-progress Game Sessions.
"""
import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from desktop.ui.tabs.game_sessions_tab import EditSessionDialog


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def facade_with_active_session(temp_db_path):
    """Create facade with a started (active) game session."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _ = QApplication.instance() or QApplication([])
    
    facade = AppFacade(temp_db_path)
    
    # Create required setup entities
    user = facade.create_user(name="TestUser")
    site = facade.create_site(name="TestSite")
    game_type = facade.create_game_type(name="Slots")
    game1 = facade.create_game(name="Game1", game_type_id=game_type.id, rtp=96.5)
    game2 = facade.create_game(name="Game2", game_type_id=game_type.id, rtp=95.0)
    
    # Start a session (creates active session - left open by not setting ending balance/time)
    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=game1.id,
        session_date=date(2026, 2, 7),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("0.00"),  # 0 or None for active
        starting_redeemable=Decimal("100.00"),
        ending_redeemable=Decimal("0.00"),
        purchases_during=Decimal("0.00"),
        redemptions_during=Decimal("0.00"),
        session_time="10:00:00",
        notes=None,
        calculate_pl=False,
    )
    
    return facade, session, game_type, game1, game2


def test_edit_dialog_allows_game_type_and_game_changes_on_active_session(facade_with_active_session):
    """
    Test that EditSessionDialog allows user to change Game Type and Game fields
    for an active (in-progress) session.
    
    Acceptance Criteria:
    - Game Type combo should be enabled (not disabled)
    - Game Name combo should be enabled (not disabled)
    - User should be able to select/enter different values
    - Changes should be saved successfully
    """
    facade, session, game_type, game1, game2 = facade_with_active_session
    
    # Session should be active
    assert session.status is None or session.status == "Active"
    assert session.game_id == game1.id
    
    # Open edit dialog for active session
    dialog = EditSessionDialog(facade, session=session, parent=None)
    
    # Verify Game Type combo is enabled
    assert dialog.game_type_combo.isEnabled(), "Game Type combo should be enabled for active sessions"
    assert not dialog.game_type_combo.isReadOnly() if hasattr(dialog.game_type_combo, 'isReadOnly') else True
    
    # Verify Game Name combo is enabled
    assert dialog.game_name_combo.isEnabled(), "Game Name combo should be enabled for active sessions"
    assert not dialog.game_name_combo.isReadOnly() if hasattr(dialog.game_name_combo, 'isReadOnly') else True
    
    # Verify initial values are loaded correctly
    assert dialog.game_type_combo.currentText() == "Slots"
    assert dialog.game_name_combo.currentText() == "Game1"
    
    # Simulate user changing the game
    dialog.game_name_combo.setCurrentText("Game2")
    
    # Collect data should succeed
    data, error = dialog.collect_data()
    assert error is None, f"Should be able to collect data after changing game: {error}"
    
    # Verify the new game is selected
    assert data["game_id"] == game2.id, "Should have new game ID"
    
    dialog.close()


def test_update_active_session_with_different_game(facade_with_active_session):
    """
    Test that facade allows updating an active session with a different Game/Game Type.
    """
    facade, session, game_type, game1, game2 = facade_with_active_session
    
    # Verify initial state
    assert session.game_id == game1.id
    
    # Update the session to use Game2
    updated = facade.update_game_session(
        session_id=session.id,
        game_id=game2.id,
        user_id=session.user_id,
        site_id=session.site_id,
        session_date=session.session_date,
        starting_balance=session.starting_balance,
        starting_redeemable=session.starting_redeemable,
        session_time=session.session_time,
        notes=session.notes,
    )
    
    # Verify game was changed
    assert updated.game_id == game2.id
    
    # Reload and verify persistence
    reloaded = facade.get_game_session(session.id)
    assert reloaded.game_id == game2.id


def test_remove_game_from_active_session(facade_with_active_session):
    """
    Test that facade allows removing game (setting game_id=None) from active session.
    
    This tests the reported bug: when user clears game_type/game fields and saves,
    the change should persist. Currently fails due to 'value is not None' check
    in update_session kwargs handling.
    """
    facade, session, game_type, game1, game2 = facade_with_active_session
    
    # Verify initial state
    assert session.game_id == game1.id
    
    # Remove game (clear the field)
    updated = facade.update_game_session(
        session_id=session.id,
        game_id=None,
        user_id=session.user_id,
        site_id=session.site_id,
        session_date=session.session_date,
        starting_balance=session.starting_balance,
        starting_redeemable=session.starting_redeemable,
        session_time=session.session_time,
        notes=session.notes,
    )
    
    # Verify game was removed
    assert updated.game_id is None, f"Expected game_id=None, got {updated.game_id}"
    
    # Reload and verify persistence
    reloaded = facade.get_game_session(session.id)
    assert reloaded.game_id is None
