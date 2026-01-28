"""
Card domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Card:
    """Represents a payment card"""
    name: str
    user_id: int
    last_four: Optional[str] = None
    cashback_rate: float = 0.0
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return self.display_name()
    
    def __post_init__(self):
        """Validate card data"""
        if not self.name or not self.name.strip():
            raise ValueError("Card name is required")
        self.name = self.name.strip()
        
        # Validate user_id
        if not self.user_id or self.user_id <= 0:
            raise ValueError("Valid user_id is required")
        
        # Validate cashback_rate
        if self.cashback_rate < 0 or self.cashback_rate > 100:
            raise ValueError("Cashback rate must be between 0 and 100")
        
        # Validate last_four if provided
        if self.last_four and len(self.last_four) != 4:
            raise ValueError("Last four must be exactly 4 characters")
    
    def display_name(self) -> str:
        """Returns formatted name with suffix (e.g., 'Chase -- x1234')"""
        if self.last_four:
            return f"{self.name} -- x{self.last_four}"
        return self.name
