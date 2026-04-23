"""
Unit tests for Purchase model
"""
import pytest
from decimal import Decimal
from datetime import date
from models.purchase import Purchase


def test_purchase_creation():
    """Test creating a purchase"""
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15)
    )
    assert purchase.user_id == 1
    assert purchase.site_id == 1
    assert purchase.amount == Decimal("100.00")
    assert purchase.remaining_amount == Decimal("100.00")
    assert purchase.consumed_amount == Decimal("0.00")
    assert not purchase.is_fully_consumed


def test_purchase_with_time():
    """Test purchase with time"""
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=100,
        purchase_date=date(2026, 1, 15),
        purchase_time="14:30:00"
    )
    assert purchase.purchase_time == "14:30:00"
    assert purchase.datetime_str == "2026-01-15 14:30:00"


def test_purchase_consumed_amount():
    """Test consumed amount calculation"""
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15),
        remaining_amount=Decimal("60.00")
    )
    assert purchase.consumed_amount == Decimal("40.00")
    assert not purchase.is_fully_consumed


def test_purchase_fully_consumed():
    """Test fully consumed purchase"""
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15),
        remaining_amount=Decimal("0.00")
    )
    assert purchase.consumed_amount == Decimal("100.00")
    assert purchase.is_fully_consumed


def test_purchase_validation_user_id():
    """Test that invalid user_id raises error"""
    with pytest.raises(ValueError, match="Valid user_id is required"):
        Purchase(user_id=0, site_id=1, amount=100, purchase_date=date.today())


def test_purchase_validation_site_id():
    """Test that invalid site_id raises error"""
    with pytest.raises(ValueError, match="Valid site_id is required"):
        Purchase(user_id=1, site_id=0, amount=100, purchase_date=date.today())


def test_purchase_validation_negative_amount():
    """Test that negative amount raises error"""
    with pytest.raises(ValueError, match="Purchase amount cannot be negative"):
        Purchase(user_id=1, site_id=1, amount=-100, purchase_date=date.today())


def test_purchase_validation_remaining_exceeds_amount():
    """Test that remaining > amount raises error"""
    with pytest.raises(ValueError, match="Remaining amount cannot exceed purchase amount"):
        Purchase(
            user_id=1,
            site_id=1,
            amount=Decimal("100.00"),
            purchase_date=date.today(),
            remaining_amount=Decimal("150.00")
        )


def test_purchase_validation_negative_remaining():
    """Test that negative remaining raises error"""
    with pytest.raises(ValueError, match="Remaining amount cannot be negative"):
        Purchase(
            user_id=1,
            site_id=1,
            amount=Decimal("100.00"),
            purchase_date=date.today(),
            remaining_amount=Decimal("-10.00")
        )


def test_purchase_date_string_conversion():
    """Test that date string is converted to date object"""
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=100,
        purchase_date="2026-01-15"
    )
    assert isinstance(purchase.purchase_date, date)
    assert purchase.purchase_date == date(2026, 1, 15)


def test_purchase_amount_conversion():
    """Test that numeric amounts are converted to Decimal"""
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=100.50,
        purchase_date=date.today()
    )
    assert isinstance(purchase.amount, Decimal)
    assert purchase.amount == Decimal("100.50")
