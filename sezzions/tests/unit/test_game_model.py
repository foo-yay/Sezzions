"""
Unit tests for Game model
"""
import pytest
from models.game import Game


def test_game_creation():
    """Test creating a game"""
    game = Game(name="Starburst", game_type_id=1, rtp=96.1)
    assert game.name == "Starburst"
    assert game.game_type_id == 1
    assert game.rtp == 96.1
    assert game.is_active is True
    assert game.id is None


def test_game_validation_empty_name():
    """Test that empty name raises error"""
    with pytest.raises(ValueError, match="Game name is required"):
        Game(name="", game_type_id=1)


def test_game_validation_whitespace_name():
    """Test that whitespace-only name raises error"""
    with pytest.raises(ValueError, match="Game name is required"):
        Game(name="   ", game_type_id=1)


def test_game_strips_name():
    """Test that game name is stripped of whitespace"""
    game = Game(name="  Blackjack  ", game_type_id=1)
    assert game.name == "Blackjack"


def test_game_validation_no_type_id():
    """Test that missing game_type_id raises error"""
    with pytest.raises(ValueError, match="Valid game_type_id is required"):
        Game(name="Test Game", game_type_id=0)


def test_game_validation_invalid_rtp():
    """Test that invalid RTP raises error"""
    with pytest.raises(ValueError, match="RTP must be between 0 and 100"):
        Game(name="Test Game", game_type_id=1, rtp=-1)
    
    with pytest.raises(ValueError, match="RTP must be between 0 and 100"):
        Game(name="Test Game", game_type_id=1, rtp=101)


def test_game_str():
    """Test string representation"""
    game = Game(name="Roulette", game_type_id=1)
    assert str(game) == "Roulette"


def test_game_optional_rtp():
    """Test game creation without RTP"""
    game = Game(name="Mystery Game", game_type_id=1)
    assert game.rtp is None
