"""
Unit tests for GameSession model
"""
import pytest
from decimal import Decimal
from datetime import date
from models.game_session import GameSession


def test_game_session_creation():
    """Test creating a basic game session"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00")
    )
    assert session.user_id == 1
    assert session.site_id == 1
    assert session.game_id == 1
    assert session.starting_balance == Decimal("100.00")
    assert session.ending_balance == Decimal("120.00")


def test_game_session_with_purchases_and_redemptions():
    """Test session with purchases and redemptions"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("50.00"),
        purchases_during=Decimal("100.00"),
        redemptions_during=Decimal("80.00"),
        ending_balance=Decimal("90.00")
    )
    assert session.purchases_during == Decimal("100.00")
    assert session.redemptions_during == Decimal("80.00")


def test_game_session_total_in():
    """Test total_in calculation"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("50.00"),
        purchases_during=Decimal("100.00")
    )
    assert session.total_in == Decimal("150.00")


def test_game_session_total_out():
    """Test total_out calculation"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        redemptions_during=Decimal("80.00"),
        ending_balance=Decimal("90.00")
    )
    assert session.total_out == Decimal("170.00")


def test_game_session_calculated_pl():
    """Test P/L calculation: total_out - total_in"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("50.00"),
        purchases_during=Decimal("100.00"),
        redemptions_during=Decimal("80.00"),
        ending_balance=Decimal("90.00")
    )
    # Total in: 50 + 100 = 150
    # Total out: 80 + 90 = 170
    # P/L: 170 - 150 = 20
    assert session.calculated_pl == Decimal("20.00")


def test_game_session_negative_pl():
    """Test session with loss (negative P/L)"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("50.00")
    )
    # Total in: 100, Total out: 50, P/L: -50
    assert session.calculated_pl == Decimal("-50.00")


def test_game_session_has_calculated_pl():
    """Test has_calculated_pl property"""
    session1 = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00")
    )
    assert not session1.has_calculated_pl
    
    session2 = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        profit_loss=Decimal("20.00")
    )
    assert session2.has_calculated_pl


def test_game_session_datetime_str():
    """Test datetime_str property"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 15),
        session_time="14:30:00",
        starting_balance=Decimal("100.00")
    )
    assert session.datetime_str == "2026-01-15 14:30:00"


def test_game_session_validation_user_id():
    """Test that invalid user_id raises error"""
    with pytest.raises(ValueError, match="Valid user_id is required"):
        GameSession(user_id=0, site_id=1, game_id=1, session_date=date.today())


def test_game_session_validation_site_id():
    """Test that invalid site_id raises error"""
    with pytest.raises(ValueError, match="Valid site_id is required"):
        GameSession(user_id=1, site_id=0, game_id=1, session_date=date.today())


def test_game_session_validation_game_id():
    """Test that invalid game_id raises error"""
    with pytest.raises(ValueError, match="Valid game_id is required"):
        GameSession(user_id=1, site_id=1, game_id=0, session_date=date.today())


def test_game_session_validation_negative_balances():
    """Test that negative balances raise errors"""
    with pytest.raises(ValueError, match="Starting balance cannot be negative"):
        GameSession(
            user_id=1, site_id=1, game_id=1,
            session_date=date.today(),
            starting_balance=Decimal("-10.00")
        )
    
    with pytest.raises(ValueError, match="Ending balance cannot be negative"):
        GameSession(
            user_id=1, site_id=1, game_id=1,
            session_date=date.today(),
            ending_balance=Decimal("-10.00")
        )


def test_game_session_date_string_conversion():
    """Test that date string is converted to date object"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date="2026-01-15",
        starting_balance=Decimal("100.00")
    )
    assert isinstance(session.session_date, date)
    assert session.session_date == date(2026, 1, 15)


def test_game_session_decimal_conversion():
    """Test that numeric amounts are converted to Decimal"""
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date.today(),
        starting_balance=100.50,
        purchases_during=50.25,
        redemptions_during=75.00,
        ending_balance=90.75
    )
    assert isinstance(session.starting_balance, Decimal)
    assert isinstance(session.purchases_during, Decimal)
    assert isinstance(session.redemptions_during, Decimal)
    assert isinstance(session.ending_balance, Decimal)
