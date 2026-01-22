"""
Unit tests for GameRepository
"""
import pytest
from models.game import Game


def test_create_game(game_repo, sample_game_type):
    """Test creating a game in database"""
    game = Game(name="Starburst", game_type_id=sample_game_type.id, rtp=96.1)
    created_game = game_repo.create(game)
    
    assert created_game.id is not None
    assert created_game.name == "Starburst"
    assert created_game.rtp == 96.1
    assert created_game.game_type_id == sample_game_type.id


def test_get_game_by_id(game_repo, sample_game_type):
    """Test getting game by ID"""
    game = Game(name="Blackjack", game_type_id=sample_game_type.id)
    created_game = game_repo.create(game)
    
    retrieved_game = game_repo.get_by_id(created_game.id)
    assert retrieved_game is not None
    assert retrieved_game.name == "Blackjack"


def test_get_game_by_id_not_found(game_repo):
    """Test getting non-existent game returns None"""
    game = game_repo.get_by_id(9999)
    assert game is None


def test_get_all_games(game_repo, sample_game_type):
    """Test getting all games"""
    game_repo.create(Game(name="Game 1", game_type_id=sample_game_type.id))
    game_repo.create(Game(name="Game 2", game_type_id=sample_game_type.id))
    game_repo.create(Game(name="Game 3", game_type_id=sample_game_type.id))
    
    games = game_repo.get_all()
    assert len(games) == 3


def test_get_games_by_type(game_repo, type_service):
    """Test getting games by type"""
    type1 = type_service.create_type(name="Type 1")
    type2 = type_service.create_type(name="Type 2")
    
    game_repo.create(Game(name="Type1 Game1", game_type_id=type1.id))
    game_repo.create(Game(name="Type1 Game2", game_type_id=type1.id))
    game_repo.create(Game(name="Type2 Game1", game_type_id=type2.id))
    
    type1_games = game_repo.get_by_type(type1.id)
    assert len(type1_games) == 2
    
    type2_games = game_repo.get_by_type(type2.id)
    assert len(type2_games) == 1


def test_get_active_games(game_repo, sample_game_type):
    """Test getting only active games"""
    game_repo.create(Game(name="Active Game", game_type_id=sample_game_type.id, is_active=True))
    game_repo.create(Game(name="Inactive Game", game_type_id=sample_game_type.id, is_active=False))
    
    active_games = game_repo.get_active()
    assert len(active_games) == 1
    assert active_games[0].name == "Active Game"


def test_get_active_games_by_type(game_repo, type_service):
    """Test getting active games for a specific type"""
    type1 = type_service.create_type(name="Type 1")
    
    game_repo.create(Game(name="Active", game_type_id=type1.id, is_active=True))
    game_repo.create(Game(name="Inactive", game_type_id=type1.id, is_active=False))
    
    active_type1 = game_repo.get_active_by_type(type1.id)
    assert len(active_type1) == 1
    assert active_type1[0].name == "Active"


def test_update_game(game_repo, sample_game_type):
    """Test updating game"""
    game = game_repo.create(Game(name="Old Name", game_type_id=sample_game_type.id))
    game.name = "New Name"
    game.rtp = 95.5
    
    updated_game = game_repo.update(game)
    assert updated_game.name == "New Name"
    assert updated_game.rtp == 95.5
    
    # Verify in database
    retrieved = game_repo.get_by_id(game.id)
    assert retrieved.name == "New Name"


def test_delete_game(game_repo, sample_game_type):
    """Test deleting game"""
    game = game_repo.create(Game(name="To Delete", game_type_id=sample_game_type.id))
    game_id = game.id
    
    game_repo.delete(game_id)
    
    # Verify deleted
    retrieved = game_repo.get_by_id(game_id)
    assert retrieved is None
