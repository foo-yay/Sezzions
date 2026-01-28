"""
Site domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Site:
    """Represents a casino site"""
    name: str
    url: Optional[str] = None
    sc_rate: float = 1.0
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return self.name
    
    def __post_init__(self):
        """Validate site data"""
        if not self.name or not self.name.strip():
            raise ValueError("Site name is required")
        self.name = self.name.strip()
        
        # Validate sc_rate
        if self.sc_rate <= 0:
            raise ValueError("SC rate must be positive")
