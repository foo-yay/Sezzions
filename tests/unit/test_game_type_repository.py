"""
Unit tests for GameTypeRepository
"""
import pytest
from models.game_type import GameType


def test_create_type(type_repo):
    """Test creating a game type in database"""
    game_type = GameType(name="Slots")
    created_type = type_repo.create(game_type)
    
    assert created_type.id is not None
    assert created_type.name == "Slots"


def test_get_type_by_id(type_repo):
    """Test getting game type by ID"""
    game_type = GameType(name="Table Games")
    created_type = type_repo.create(game_type)
    
    retrieved_type = type_repo.get_by_id(created_type.id)
    assert retrieved_type is not None
    assert retrieved_type.name == "Table Games"


def test_get_type_by_id_not_found(type_repo):
    """Test getting non-existent game type returns None"""
    game_type = type_repo.get_by_id(9999)
    assert game_type is None


def test_get_all_types(type_repo):
    """Test getting all game types"""
    type_repo.create(GameType(name="Slots"))
    type_repo.create(GameType(name="Table Games"))
    type_repo.create(GameType(name="Live Dealer"))
    
    types = type_repo.get_all()
    assert len(types) == 3


def test_get_active_types(type_repo):
    """Test getting only active game types"""
    type_repo.create(GameType(name="Active", is_active=True))
    type_repo.create(GameType(name="Inactive", is_active=False))
    
    active_types = type_repo.get_active()
    assert len(active_types) == 1
    assert active_types[0].name == "Active"


def test_update_type(type_repo):
    """Test updating game type"""
    game_type = type_repo.create(GameType(name="Old Name"))
    game_type.name = "New Name"
    game_type.notes = "Updated notes"
    
    updated_type = type_repo.update(game_type)
    assert updated_type.name == "New Name"
    assert updated_type.notes == "Updated notes"
    
    # Verify in database
    retrieved = type_repo.get_by_id(game_type.id)
    assert retrieved.name == "New Name"


def test_delete_type(type_repo):
    """Test deleting game type"""
    game_type = type_repo.create(GameType(name="To Delete"))
    type_id = game_type.id
    
    type_repo.delete(type_id)
    
    # Verify deleted
    retrieved = type_repo.get_by_id(type_id)
    assert retrieved is None
