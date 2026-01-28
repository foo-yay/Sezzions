"""
Unit tests for Card model
"""
import pytest
from models.card import Card


def test_card_creation():
    """Test creating a card"""
    card = Card(name="Chase Sapphire", user_id=1, last_four="1234", cashback_rate=2.5)
    assert card.name == "Chase Sapphire"
    assert card.user_id == 1
    assert card.last_four == "1234"
    assert card.cashback_rate == 2.5
    assert card.is_active is True
    assert card.id is None


def test_card_validation_empty_name():
    """Test that empty name raises error"""
    with pytest.raises(ValueError, match="Card name is required"):
        Card(name="", user_id=1)


def test_card_validation_whitespace_name():
    """Test that whitespace-only name raises error"""
    with pytest.raises(ValueError, match="Card name is required"):
        Card(name="   ", user_id=1)


def test_card_strips_name():
    """Test that card name is stripped of whitespace"""
    card = Card(name="  Chase  ", user_id=1)
    assert card.name == "Chase"


def test_card_validation_no_user_id():
    """Test that missing user_id raises error"""
    with pytest.raises(ValueError, match="Valid user_id is required"):
        Card(name="Test Card", user_id=0)


def test_card_validation_invalid_cashback_rate():
    """Test that invalid cashback rate raises error"""
    with pytest.raises(ValueError, match="Cashback rate must be between 0 and 100"):
        Card(name="Test Card", user_id=1, cashback_rate=-1)
    
    with pytest.raises(ValueError, match="Cashback rate must be between 0 and 100"):
        Card(name="Test Card", user_id=1, cashback_rate=101)


def test_card_validation_invalid_last_four():
    """Test that invalid last_four raises error"""
    with pytest.raises(ValueError, match="Last four must be exactly 4 characters"):
        Card(name="Test Card", user_id=1, last_four="123")
    
    with pytest.raises(ValueError, match="Last four must be exactly 4 characters"):
        Card(name="Test Card", user_id=1, last_four="12345")


def test_card_display_name_with_suffix():
    """Test display name includes last four digits"""
    card = Card(name="Chase Sapphire", user_id=1, last_four="1234")
    assert card.display_name() == "Chase Sapphire -- x1234"


def test_card_display_name_without_suffix():
    """Test display name without last four digits"""
    card = Card(name="Chase Sapphire", user_id=1)
    assert card.display_name() == "Chase Sapphire"


def test_card_str():
    """Test string representation uses display_name"""
    card = Card(name="Amex", user_id=1, last_four="5678")
    assert str(card) == "Amex -- x5678"
