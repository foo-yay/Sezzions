"""
User domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """Represents a user/player"""
    name: str
    email: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return self.name
    
    def __post_init__(self):
        """Validate user data"""
        if not self.name or not self.name.strip():
            raise ValueError("User name is required")
        self.name = self.name.strip()
