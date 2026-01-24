"""
User service - Business logic for User operations
"""
from typing import List, Optional
from models.user import User
from repositories.user_repository import UserRepository


class UserService:
    """Business logic for User operations"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    def create_user(
        self,
        name: str,
        email: Optional[str] = None,
        notes: Optional[str] = None
    ) -> User:
        """Create new user with validation"""
        # Create user model (validates in __post_init__)
        user = User(name=name, email=email, notes=notes)
        
        # Save to database
        return self.user_repo.create(user)
    
    def update_user(self, user_id: int, **kwargs) -> User:
        """Update user with validation"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        # Validate (will raise if invalid)
        user.__post_init__()
        
        return self.user_repo.update(user)
    
    def deactivate_user(self, user_id: int) -> User:
        """Deactivate user (soft delete)"""
        return self.update_user(user_id, is_active=False)
    
    def activate_user(self, user_id: int) -> User:
        """Activate user"""
        return self.update_user(user_id, is_active=True)
    
    def list_active_users(self) -> List[User]:
        """Get all active users"""
        return self.user_repo.get_active()
    
    def list_all_users(self) -> List[User]:
        """Get all users (including inactive)"""
        return self.user_repo.get_all()
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.user_repo.get_by_id(user_id)

    def delete_user(self, user_id: int) -> None:
        """Delete user"""
        self.user_repo.delete(user_id)
