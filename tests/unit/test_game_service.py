"""
Unit tests for GameService
"""
import pytest
from models.game import Game


def test_create_game_service(game_service, sample_game_type):
    """Test creating game through service"""
    game = game_service.create_game(
        name="Starburst",
        game_type_id=sample_game_type.id,
        rtp=96.1,
        notes="Popular slot game"
    )
    
    assert game.id is not None
    assert game.name == "Starburst"
    assert game.rtp == 96.1


def test_create_game_validation_empty_name(game_service, sample_game_type):
    """Test service validates game name"""
    with pytest.raises(ValueError, match="Game name is required"):
        game_service.create_game(name="", game_type_id=sample_game_type.id)


def test_create_game_validation_invalid_rtp(game_service, sample_game_type):
    """Test service validates RTP"""
    with pytest.raises(ValueError, match="RTP must be between 0 and 100"):
        game_service.create_game(name="Test Game", game_type_id=sample_game_type.id, rtp=101)


def test_update_game_service(game_service, sample_game):
    """Test updating game through service"""
    updated = game_service.update_game(
        sample_game.id,
        name="Updated Name",
        rtp=97.5
    )
    
    assert updated.name == "Updated Name"
    assert updated.rtp == 97.5


def test_deactivate_game(game_service, sample_game):
    """Test deactivating game"""
    game = game_service.deactivate_game(sample_game.id)
    assert game.is_active is False


def test_activate_game(game_service, sample_game):
    """Test activating game"""
    # First deactivate
    game_service.deactivate_game(sample_game.id)
    
    # Then activate
    game = game_service.activate_game(sample_game.id)
    assert game.is_active is True


def test_list_active_games(game_service, sample_game_type):
    """Test listing active games"""
    game_service.create_game(name="Active 1", game_type_id=sample_game_type.id)
    game_service.create_game(name="Active 2", game_type_id=sample_game_type.id)
    game3 = game_service.create_game(name="Inactive", game_type_id=sample_game_type.id)
    game_service.deactivate_game(game3.id)
    
    active = game_service.list_active_games()
    assert len(active) == 2


def test_list_active_games_by_type(game_service, type_service):
    """Test listing active games filtered by type"""
    type1 = type_service.create_type(name="Type 1")
    type2 = type_service.create_type(name="Type 2")
    
    game_service.create_game(name="Type1 Active", game_type_id=type1.id)
    game_service.create_game(name="Type2 Active", game_type_id=type2.id)
    
    type1_games = game_service.list_active_games(game_type_id=type1.id)
    assert len(type1_games) == 1
    assert type1_games[0].name == "Type1 Active"


def test_list_all_games(game_service, sample_game_type):
    """Test listing all games"""
    game_service.create_game(name="Game 1", game_type_id=sample_game_type.id)
    game_service.create_game(name="Game 2", game_type_id=sample_game_type.id)
    game3 = game_service.create_game(name="Game 3", game_type_id=sample_game_type.id)
    game_service.deactivate_game(game3.id)
    
    all_games = game_service.list_all_games()
    assert len(all_games) == 3


def test_list_all_games_by_type(game_service, type_service):
    """Test listing all games filtered by type"""
    type1 = type_service.create_type(name="Type 1")
    type2 = type_service.create_type(name="Type 2")
    
    game_service.create_game(name="Type1 Game1", game_type_id=type1.id)
    game_service.create_game(name="Type1 Game2", game_type_id=type1.id)
    game_service.create_game(name="Type2 Game1", game_type_id=type2.id)
    
    type1_games = game_service.list_all_games(game_type_id=type1.id)
    assert len(type1_games) == 2
