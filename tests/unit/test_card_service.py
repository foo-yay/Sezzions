"""
Unit tests for CardService
"""
import pytest
from models.card import Card


def test_create_card_service(card_service, sample_user):
    """Test creating card through service"""
    card = card_service.create_card(
        name="Chase Sapphire",
        user_id=sample_user.id,
        last_four="1234",
        cashback_rate=2.5,
        notes="Test card"
    )
    
    assert card.id is not None
    assert card.name == "Chase Sapphire"
    assert card.last_four == "1234"
    assert card.cashback_rate == 2.5


def test_create_card_validation_empty_name(card_service, sample_user):
    """Test service validates card name"""
    with pytest.raises(ValueError, match="Card name is required"):
        card_service.create_card(name="", user_id=sample_user.id)


def test_create_card_validation_invalid_cashback(card_service, sample_user):
    """Test service validates cashback rate"""
    with pytest.raises(ValueError, match="Cashback rate must be between 0 and 100"):
        card_service.create_card(name="Test Card", user_id=sample_user.id, cashback_rate=101)


def test_create_card_validation_invalid_last_four(card_service, sample_user):
    """Test service validates last four"""
    with pytest.raises(ValueError, match="Last four must be exactly 4 characters"):
        card_service.create_card(name="Test Card", user_id=sample_user.id, last_four="123")


def test_update_card_service(card_service, sample_card):
    """Test updating card through service"""
    updated = card_service.update_card(
        sample_card.id,
        name="Updated Name",
        last_four="9999"
    )
    
    assert updated.name == "Updated Name"
    assert updated.last_four == "9999"


def test_deactivate_card(card_service, sample_card):
    """Test deactivating card"""
    card = card_service.deactivate_card(sample_card.id)
    assert card.is_active is False


def test_activate_card(card_service, sample_card):
    """Test activating card"""
    # First deactivate
    card_service.deactivate_card(sample_card.id)
    
    # Then activate
    card = card_service.activate_card(sample_card.id)
    assert card.is_active is True


def test_list_user_cards_active_only(card_service, sample_user):
    """Test listing active cards for user"""
    card1 = card_service.create_card(name="Active 1", user_id=sample_user.id)
    card2 = card_service.create_card(name="Active 2", user_id=sample_user.id)
    card3 = card_service.create_card(name="Inactive", user_id=sample_user.id)
    card_service.deactivate_card(card3.id)
    
    active = card_service.list_user_cards(sample_user.id, active_only=True)
    assert len(active) == 2


def test_list_user_cards_all(card_service, sample_user):
    """Test listing all cards for user"""
    card_service.create_card(name="Card 1", user_id=sample_user.id)
    card_service.create_card(name="Card 2", user_id=sample_user.id)
    card3 = card_service.create_card(name="Card 3", user_id=sample_user.id)
    card_service.deactivate_card(card3.id)
    
    all_cards = card_service.list_user_cards(sample_user.id, active_only=False)
    assert len(all_cards) == 3


def test_card_display_name_in_service(card_service, sample_user):
    """Test that display_name works correctly"""
    card = card_service.create_card(
        name="Chase",
        user_id=sample_user.id,
        last_four="1234"
    )
    
    # Retrieve and test display name
    retrieved = card_service.get_card(card.id)
    assert retrieved.display_name() == "Chase -- x1234"
