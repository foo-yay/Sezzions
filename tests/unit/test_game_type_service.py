"""
Unit tests for GameTypeService
"""
import pytest
from models.game_type import GameType


def test_create_type_service(type_service):
    """Test creating game type through service"""
    game_type = type_service.create_type(
        name="Slots",
        notes="Slot machines"
    )
    
    assert game_type.id is not None
    assert game_type.name == "Slots"
    assert game_type.notes == "Slot machines"


def test_create_type_validation(type_service):
    """Test service validates game type name"""
    with pytest.raises(ValueError, match="Game type name is required"):
        type_service.create_type(name="")


def test_update_type_service(type_service, sample_game_type):
    """Test updating game type through service"""
    updated = type_service.update_type(
        sample_game_type.id,
        name="Updated Name",
        notes="Updated notes"
    )
    
    assert updated.name == "Updated Name"
    assert updated.notes == "Updated notes"


def test_deactivate_type(type_service, sample_game_type):
    """Test deactivating game type"""
    game_type = type_service.deactivate_type(sample_game_type.id)
    assert game_type.is_active is False


def test_activate_type(type_service, sample_game_type):
    """Test activating game type"""
    # First deactivate
    type_service.deactivate_type(sample_game_type.id)
    
    # Then activate
    game_type = type_service.activate_type(sample_game_type.id)
    assert game_type.is_active is True


def test_list_active_types(type_service):
    """Test listing active game types"""
    type_service.create_type(name="Active 1")
    type_service.create_type(name="Active 2")
    type3 = type_service.create_type(name="Inactive")
    type_service.deactivate_type(type3.id)
    
    active = type_service.list_active_types()
    assert len(active) == 2


def test_list_all_types(type_service):
    """Test listing all game types"""
    type_service.create_type(name="Type 1")
    type_service.create_type(name="Type 2")
    type3 = type_service.create_type(name="Type 3")
    type_service.deactivate_type(type3.id)
    
    all_types = type_service.list_all_types()
    assert len(all_types) == 3
