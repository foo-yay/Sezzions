"""
Unit tests for CardRepository
"""
import pytest
from models.card import Card


def test_create_card(card_repo, sample_user):
    """Test creating a card in database"""
    card = Card(name="Chase", user_id=sample_user.id, last_four="1234")
    created_card = card_repo.create(card)
    
    assert created_card.id is not None
    assert created_card.name == "Chase"
    assert created_card.last_four == "1234"
    assert created_card.user_id == sample_user.id


def test_get_card_by_id(card_repo, sample_user):
    """Test getting card by ID"""
    card = Card(name="Amex", user_id=sample_user.id)
    created_card = card_repo.create(card)
    
    retrieved_card = card_repo.get_by_id(created_card.id)
    assert retrieved_card is not None
    assert retrieved_card.name == "Amex"


def test_get_card_by_id_not_found(card_repo):
    """Test getting non-existent card returns None"""
    card = card_repo.get_by_id(9999)
    assert card is None


def test_get_all_cards(card_repo, sample_user):
    """Test getting all cards"""
    card_repo.create(Card(name="Card 1", user_id=sample_user.id))
    card_repo.create(Card(name="Card 2", user_id=sample_user.id))
    card_repo.create(Card(name="Card 3", user_id=sample_user.id))
    
    cards = card_repo.get_all()
    assert len(cards) == 3


def test_get_cards_by_user(card_repo, user_service):
    """Test getting cards by user"""
    user1 = user_service.create_user(name="User 1")
    user2 = user_service.create_user(name="User 2")
    
    card_repo.create(Card(name="User1 Card1", user_id=user1.id))
    card_repo.create(Card(name="User1 Card2", user_id=user1.id))
    card_repo.create(Card(name="User2 Card1", user_id=user2.id))
    
    user1_cards = card_repo.get_by_user(user1.id)
    assert len(user1_cards) == 2
    
    user2_cards = card_repo.get_by_user(user2.id)
    assert len(user2_cards) == 1


def test_get_active_cards_by_user(card_repo, sample_user):
    """Test getting only active cards for a user"""
    card1 = card_repo.create(Card(name="Active Card", user_id=sample_user.id, is_active=True))
    card2 = card_repo.create(Card(name="Inactive Card", user_id=sample_user.id, is_active=False))
    
    active_cards = card_repo.get_active_by_user(sample_user.id)
    assert len(active_cards) == 1
    assert active_cards[0].name == "Active Card"


def test_update_card(card_repo, sample_user):
    """Test updating card"""
    card = card_repo.create(Card(name="Old Name", user_id=sample_user.id))
    card.name = "New Name"
    card.last_four = "9999"
    card.cashback_rate = 3.0
    
    updated_card = card_repo.update(card)
    assert updated_card.name == "New Name"
    assert updated_card.last_four == "9999"
    assert updated_card.cashback_rate == 3.0
    
    # Verify in database
    retrieved = card_repo.get_by_id(card.id)
    assert retrieved.name == "New Name"


def test_delete_card(card_repo, sample_user):
    """Test deleting card"""
    card = card_repo.create(Card(name="To Delete", user_id=sample_user.id))
    card_id = card.id
    
    card_repo.delete(card_id)
    
    # Verify deleted
    retrieved = card_repo.get_by_id(card_id)
    assert retrieved is None
