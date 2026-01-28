"""
Unit tests for GameSessionRepository
"""
import pytest
from decimal import Decimal
from datetime import date
from models.game_session import GameSession


def test_create_game_session(game_session_repo, sample_user, sample_site, sample_game):
    """Test creating a game session"""
    session = game_session_repo.create(GameSession(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00")
    ))
    
    assert session.id is not None
    assert session.user_id == sample_user.id
    assert session.starting_balance == Decimal("100.00")


def test_get_session_by_id(game_session_repo, sample_game_session):
    """Test retrieving session by ID"""
    retrieved = game_session_repo.get_by_id(sample_game_session.id)
    assert retrieved is not None
    assert retrieved.id == sample_game_session.id


def test_get_session_by_id_not_found(game_session_repo):
    """Test retrieving non-existent session"""
    retrieved = game_session_repo.get_by_id(99999)
    assert retrieved is None


def test_get_all_sessions(game_session_repo, sample_game_session):
    """Test retrieving all sessions"""
    sessions = game_session_repo.get_all()
    assert len(sessions) >= 1
    assert any(s.id == sample_game_session.id for s in sessions)


def test_get_by_user(game_session_repo, sample_user, sample_game_session):
    """Test retrieving sessions by user"""
    sessions = game_session_repo.get_by_user(sample_user.id)
    assert len(sessions) >= 1
    assert all(s.user_id == sample_user.id for s in sessions)


def test_get_by_site(game_session_repo, sample_site, sample_game_session):
    """Test retrieving sessions by site"""
    sessions = game_session_repo.get_by_site(sample_site.id)
    assert len(sessions) >= 1
    assert all(s.site_id == sample_site.id for s in sessions)


def test_get_by_user_and_site(game_session_repo, sample_user, sample_site, sample_game_session):
    """Test retrieving sessions by user and site"""
    sessions = game_session_repo.get_by_user_and_site(sample_user.id, sample_site.id)
    assert len(sessions) >= 1
    assert all(s.user_id == sample_user.id and s.site_id == sample_site.id for s in sessions)


def test_update_session(game_session_repo, sample_game_session):
    """Test updating a session"""
    sample_game_session.ending_balance = Decimal("150.00")
    sample_game_session.notes = "Updated notes"
    
    updated = game_session_repo.update(sample_game_session)
    assert updated.ending_balance == Decimal("150.00")
    assert updated.notes == "Updated notes"


def test_delete_session(game_session_repo, sample_user, sample_site, sample_game):
    """Test deleting a session"""
    session = game_session_repo.create(GameSession(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00")
    ))
    session_id = session.id
    
    game_session_repo.delete(session_id)
    
    retrieved = game_session_repo.get_by_id(session_id)
    assert retrieved is None


def test_decimal_handling(game_session_repo, sample_user, sample_site, sample_game):
    """Test that Decimal values are preserved"""
    session = game_session_repo.create(GameSession(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("123.45"),
        purchases_during=Decimal("67.89"),
        redemptions_during=Decimal("50.00"),
        ending_balance=Decimal("141.34"),
        profit_loss=Decimal("18.00")
    ))
    
    retrieved = game_session_repo.get_by_id(session.id)
    assert retrieved.starting_balance == Decimal("123.45")
    assert retrieved.purchases_during == Decimal("67.89")
    assert retrieved.redemptions_during == Decimal("50.00")
    assert retrieved.ending_balance == Decimal("141.34")
    assert retrieved.profit_loss == Decimal("18.00")
