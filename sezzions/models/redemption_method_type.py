"""
RedemptionMethodType domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class RedemptionMethodType:
    """Represents a type of redemption method (e.g., Bank, Crypto)"""
    name: str
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __str__(self) -> str:
        return self.name

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Method type name is required")
        self.name = self.name.strip()
