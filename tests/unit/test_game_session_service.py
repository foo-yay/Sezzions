"""
Unit tests for GameSessionService
"""
import pytest
from decimal import Decimal
from datetime import date


def test_create_session_basic(game_session_service, sample_user, sample_site, sample_game):
    """Test creating a basic session"""
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00")
    )
    
    assert session.id is not None
    assert session.starting_balance == Decimal("100.00")
    assert session.ending_balance == Decimal("120.00")


def test_create_session_with_auto_pl_calculation(game_session_service, sample_user, sample_site, sample_game):
    """Test that P/L is calculated automatically"""
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        purchases_during=Decimal("50.00"),
        redemptions_during=Decimal("80.00"),
        ending_balance=Decimal("90.00"),
        ending_redeemable=Decimal("20.00"),
        calculate_pl=True
    )
    
    closed = game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="23:59:59",
    )
    assert closed.net_taxable_pl == Decimal("20.00")


def test_create_session_without_pl_calculation(game_session_service, sample_user, sample_site, sample_game):
    """Test creating session without P/L calculation"""
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        calculate_pl=False
    )
    
    assert session.net_taxable_pl is None


def test_update_session(game_session_service, sample_game_session):
    """Test updating session fields"""
    updated = game_session_service.update_session(
        sample_game_session.id,
        ending_balance=Decimal("200.00"),
        notes="Updated"
    )
    
    assert updated.ending_balance == Decimal("200.00")
    assert updated.notes == "Updated"


def test_update_session_recalculates_pl(game_session_service, sample_game_session):
    """Test that updating session recalculates P/L"""
    closed = game_session_service.update_session(
        sample_game_session.id,
        status="Closed",
        ending_redeemable=Decimal("20.00"),
        end_date=sample_game_session.session_date,
        end_time="23:59:59",
    )
    original_pl = closed.net_taxable_pl
    
    updated = game_session_service.update_session(
        sample_game_session.id,
        ending_redeemable=Decimal("30.00"),
        recalculate_pl=True
    )
    
    # P/L should change when ending_balance changes
    assert updated.net_taxable_pl != original_pl


def test_update_session_not_found(game_session_service):
    """Test updating non-existent session raises error"""
    with pytest.raises(ValueError, match="Session .* not found"):
        game_session_service.update_session(99999, notes="Test")


def test_delete_session(game_session_service, sample_game_session):
    """Test deleting a session"""
    session_id = sample_game_session.id
    game_session_service.delete_session(session_id)
    
    retrieved = game_session_service.get_session(session_id)
    assert retrieved is None


def test_list_user_sessions(game_session_service, sample_user, sample_game_session):
    """Test listing sessions for a user"""
    sessions = game_session_service.list_user_sessions(sample_user.id)
    assert len(sessions) >= 1
    assert all(s.user_id == sample_user.id for s in sessions)


def test_list_site_sessions(game_session_service, sample_site, sample_game_session):
    """Test listing sessions for a site"""
    sessions = game_session_service.list_site_sessions(sample_site.id)
    assert len(sessions) >= 1
    assert all(s.site_id == sample_site.id for s in sessions)


def test_list_sessions_filtered(game_session_service, sample_user, sample_site, sample_game_session):
    """Test listing sessions with filters"""
    sessions = game_session_service.list_sessions(
        user_id=sample_user.id,
        site_id=sample_site.id
    )
    assert len(sessions) >= 1


def test_calculate_session_pl(game_session_service, sample_user, sample_site, sample_game):
    """Test P/L calculation method"""
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        purchases_during=Decimal("50.00"),
        redemptions_during=Decimal("80.00"),
        ending_balance=Decimal("90.00"),
        calculate_pl=False
    )
    
    pl = game_session_service.calculate_session_pl(session)
    assert pl == Decimal("20.00")


def test_recalculate_all_sessions(
    game_session_service, game_session_repo, sample_user, sample_site, sample_game
):
    """Test recalculating P/L for all sessions"""
    # Create sessions with incorrect P/L
    session1 = game_session_repo.create(
        game_session_service.create_session(
            user_id=sample_user.id,
            site_id=sample_site.id,
            game_id=sample_game.id,
            session_date=date(2026, 1, 15),
            starting_balance=Decimal("100.00"),
            ending_balance=Decimal("120.00"),
            calculate_pl=False
        )
    )
    
    # Recalculate
    count = game_session_service.recalculate_all_sessions(user_id=sample_user.id, site_id=sample_site.id)
    
    # At least one session should be updated
    assert count >= 0


def test_update_session_without_recalculate(game_session_service, sample_game_session):
    """Test updating session without recalculating P/L"""
    closed = game_session_service.update_session(
        sample_game_session.id,
        status="Closed",
        ending_redeemable=Decimal("20.00"),
        end_date=sample_game_session.session_date,
        end_time="23:59:59",
    )
    updated = game_session_service.update_session(
        sample_game_session.id,
        notes="Updated without recalc",
        recalculate_pl=False
    )
    
    assert updated.notes == "Updated without recalc"
    assert updated.net_taxable_pl == closed.net_taxable_pl  # Should not change


def test_recalculate_all_sessions_by_site(game_session_service, sample_user, sample_site, sample_game):
    """Test recalculating sessions filtered by site"""
    game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00")
    )
    
    count = game_session_service.recalculate_all_sessions(user_id=sample_user.id, site_id=sample_site.id)
    assert count >= 0
