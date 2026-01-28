"""
Unit tests for User model
"""
import pytest
from models.user import User


def test_user_creation():
    """Test creating a user"""
    user = User(name="John Doe", email="john@example.com")
    assert user.name == "John Doe"
    assert user.email == "john@example.com"
    assert user.is_active is True
    assert user.id is None


def test_user_validation_empty_name():
    """Test that empty name raises error"""
    with pytest.raises(ValueError, match="User name is required"):
        User(name="")


def test_user_validation_whitespace_name():
    """Test that whitespace-only name raises error"""
    with pytest.raises(ValueError, match="User name is required"):
        User(name="   ")


def test_user_strips_name():
    """Test that user name is stripped of whitespace"""
    user = User(name="  John Doe  ")
    assert user.name == "John Doe"


def test_user_str():
    """Test string representation"""
    user = User(name="John Doe")
    assert str(user) == "John Doe"
