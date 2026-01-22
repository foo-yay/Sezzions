"""
Unit tests for UserService
"""
import pytest
from models.user import User


def test_create_user_service(user_service):
    """Test creating user through service"""
    user = user_service.create_user(
        name="John Doe",
        email="john@example.com",
        notes="Test user"
    )
    
    assert user.id is not None
    assert user.name == "John Doe"
    assert user.email == "john@example.com"


def test_create_user_validation(user_service):
    """Test service validates user input"""
    with pytest.raises(ValueError, match="User name is required"):
        user_service.create_user(name="")


def test_update_user_service(user_service, sample_user):
    """Test updating user through service"""
    updated = user_service.update_user(
        sample_user.id,
        name="Updated Name",
        email="updated@example.com"
    )
    
    assert updated.name == "Updated Name"
    assert updated.email == "updated@example.com"


def test_deactivate_user(user_service, sample_user):
    """Test deactivating user"""
    user = user_service.deactivate_user(sample_user.id)
    assert user.is_active is False


def test_activate_user(user_service, sample_user):
    """Test activating user"""
    # First deactivate
    user_service.deactivate_user(sample_user.id)
    
    # Then activate
    user = user_service.activate_user(sample_user.id)
    assert user.is_active is True


def test_list_active_users(user_service):
    """Test listing active users"""
    user1 = user_service.create_user(name="Active 1")
    user2 = user_service.create_user(name="Active 2")
    user3 = user_service.create_user(name="Inactive")
    user_service.deactivate_user(user3.id)
    
    active = user_service.list_active_users()
    assert len(active) == 2


def test_list_all_users(user_service):
    """Test listing all users"""
    user_service.create_user(name="User 1")
    user_service.create_user(name="User 2")
    user_service.create_user(name="User 3")
    
    all_users = user_service.list_all_users()
    assert len(all_users) == 3
