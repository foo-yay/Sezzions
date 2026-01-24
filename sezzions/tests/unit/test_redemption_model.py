"""
Unit tests for Redemption model
"""
import pytest
from decimal import Decimal
from datetime import date
from models.redemption import Redemption


def test_redemption_creation():
    """Test creating a redemption"""
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        redemption_date=date(2026, 1, 15)
    )
    assert redemption.user_id == 1
    assert redemption.site_id == 1
    assert redemption.amount == Decimal("100.00")
    assert redemption.cost_basis is None
    assert redemption.taxable_profit is None
    assert not redemption.has_fifo_allocation


def test_redemption_with_time():
    """Test redemption with time"""
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=100,
        redemption_date=date(2026, 1, 15),
        redemption_time="14:30:00"
    )
    assert redemption.redemption_time == "14:30:00"
    assert redemption.datetime_str == "2026-01-15 14:30:00"


def test_redemption_with_fifo():
    """Test redemption with FIFO allocation"""
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        redemption_date=date(2026, 1, 15),
        cost_basis=Decimal("80.00"),
        taxable_profit=Decimal("20.00")
    )
    assert redemption.cost_basis == Decimal("80.00")
    assert redemption.taxable_profit == Decimal("20.00")
    assert redemption.has_fifo_allocation


def test_redemption_validation_user_id():
    """Test that invalid user_id raises error"""
    with pytest.raises(ValueError, match="Valid user_id is required"):
        Redemption(user_id=0, site_id=1, amount=100, redemption_date=date.today())


def test_redemption_validation_site_id():
    """Test that invalid site_id raises error"""
    with pytest.raises(ValueError, match="Valid site_id is required"):
        Redemption(user_id=1, site_id=0, amount=100, redemption_date=date.today())


def test_redemption_validation_negative_amount():
    """Test that negative amount raises error"""
    with pytest.raises(ValueError, match="Redemption amount cannot be negative"):
        Redemption(user_id=1, site_id=1, amount=-100, redemption_date=date.today())


def test_redemption_date_string_conversion():
    """Test that date string is converted to date object"""
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=100,
        redemption_date="2026-01-15"
    )
    assert isinstance(redemption.redemption_date, date)
    assert redemption.redemption_date == date(2026, 1, 15)


def test_redemption_amount_conversion():
    """Test that numeric amounts are converted to Decimal"""
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=100.50,
        redemption_date=date.today()
    )
    assert isinstance(redemption.amount, Decimal)
    assert redemption.amount == Decimal("100.50")
