"""
User repository - Data access for User entity
"""
from typing import Optional, List
from models.user import User


class UserRepository:
    """Repository for User entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        query = "SELECT * FROM users WHERE id = ?"
        row = self.db.fetch_one(query, (user_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[User]:
        """Get all users"""
        query = "SELECT * FROM users ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_active(self) -> List[User]:
        """Get active users only"""
        query = "SELECT * FROM users WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def create(self, user: User) -> User:
        """Create new user"""
        query = """
            INSERT INTO users (name, email, is_active, notes)
            VALUES (?, ?, ?, ?)
        """
        user_id = self.db.execute(query, (
            user.name,
            user.email,
            1 if user.is_active else 0,
            user.notes
        ))
        user.id = user_id
        return user
    
    def update(self, user: User) -> User:
        """Update existing user"""
        if not user.id:
            raise ValueError("Cannot update user without ID")
        
        query = """
            UPDATE users
            SET name = ?, email = ?, is_active = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            user.name,
            user.email,
            1 if user.is_active else 0,
            user.notes,
            user.id
        ))
        return user
    
    def delete(self, user_id: int) -> None:
        """Delete user (hard delete)"""
        query = "DELETE FROM users WHERE id = ?"
        self.db.execute(query, (user_id,))
    
    def _row_to_model(self, row: dict) -> User:
        """Convert database row to User model"""
        return User(
            id=row['id'],
            name=row['name'],
            email=row.get('email'),
            is_active=bool(row['is_active']),
            notes=row.get('notes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
