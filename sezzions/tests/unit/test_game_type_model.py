"""
Unit tests for GameType model
"""
import pytest
from models.game_type import GameType


def test_type_creation():
    """Test creating a game type"""
    game_type = GameType(name="Slots", notes="Slot machines")
    assert game_type.name == "Slots"
    assert game_type.notes == "Slot machines"
    assert game_type.is_active is True
    assert game_type.id is None


def test_type_validation_empty_name():
    """Test that empty name raises error"""
    with pytest.raises(ValueError, match="Game type name is required"):
        GameType(name="")


def test_type_validation_whitespace_name():
    """Test that whitespace-only name raises error"""
    with pytest.raises(ValueError, match="Game type name is required"):
        GameType(name="   ")


def test_type_strips_name():
    """Test that game type name is stripped of whitespace"""
    game_type = GameType(name="  Table Games  ")
    assert game_type.name == "Table Games"


def test_type_str():
    """Test string representation"""
    game_type = GameType(name="Live Dealer")
    assert str(game_type) == "Live Dealer"
