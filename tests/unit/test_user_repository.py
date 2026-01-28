"""
Unit tests for UserRepository
"""
import pytest
from models.user import User


def test_create_user(user_repo):
    """Test creating a user in database"""
    user = User(name="John Doe", email="john@example.com")
    created_user = user_repo.create(user)
    
    assert created_user.id is not None
    assert created_user.name == "John Doe"
    assert created_user.email == "john@example.com"


def test_get_user_by_id(user_repo):
    """Test getting user by ID"""
    user = User(name="Jane Doe")
    created_user = user_repo.create(user)
    
    retrieved_user = user_repo.get_by_id(created_user.id)
    assert retrieved_user is not None
    assert retrieved_user.name == "Jane Doe"


def test_get_user_by_id_not_found(user_repo):
    """Test getting non-existent user returns None"""
    user = user_repo.get_by_id(9999)
    assert user is None


def test_get_all_users(user_repo):
    """Test getting all users"""
    user_repo.create(User(name="User 1"))
    user_repo.create(User(name="User 2"))
    user_repo.create(User(name="User 3"))
    
    users = user_repo.get_all()
    assert len(users) == 3


def test_get_active_users(user_repo):
    """Test getting only active users"""
    user1 = user_repo.create(User(name="Active User", is_active=True))
    user2 = user_repo.create(User(name="Inactive User", is_active=False))
    
    active_users = user_repo.get_active()
    assert len(active_users) == 1
    assert active_users[0].name == "Active User"


def test_update_user(user_repo):
    """Test updating user"""
    user = user_repo.create(User(name="Old Name"))
    user.name = "New Name"
    user.email = "newemail@example.com"
    
    updated_user = user_repo.update(user)
    assert updated_user.name == "New Name"
    assert updated_user.email == "newemail@example.com"
    
    # Verify in database
    retrieved = user_repo.get_by_id(user.id)
    assert retrieved.name == "New Name"


def test_delete_user(user_repo):
    """Test deleting user"""
    user = user_repo.create(User(name="To Delete"))
    user_id = user.id
    
    user_repo.delete(user_id)
    
    # Verify deleted
    retrieved = user_repo.get_by_id(user_id)
    assert retrieved is None
