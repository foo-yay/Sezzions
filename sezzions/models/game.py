"""
Game domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Game:
    """Represents a specific game (e.g., Starburst, Blackjack)"""
    name: str
    game_type_id: int
    rtp: Optional[float] = None
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return self.name
    
    def __post_init__(self):
        """Validate game data"""
        if not self.name or not self.name.strip():
            raise ValueError("Game name is required")
        self.name = self.name.strip()
        
        # Validate game_type_id
        if not self.game_type_id or self.game_type_id <= 0:
            raise ValueError("Valid game_type_id is required")
        
        # Validate RTP if provided
        if self.rtp is not None:
            if self.rtp < 0 or self.rtp > 100:
                raise ValueError("RTP must be between 0 and 100")
