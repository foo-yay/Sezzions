"""
RedemptionMethod domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class RedemptionMethod:
    """Represents a method for redeeming funds (e.g., ACH, Check, PayPal)"""
    name: str
    method_type: Optional[str] = None
    user_id: Optional[int] = None
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return self.name
    
    def __post_init__(self):
        """Validate redemption method data"""
        if not self.name or not self.name.strip():
            raise ValueError("Redemption method name is required")
        self.name = self.name.strip()
        if self.method_type is not None:
            self.method_type = self.method_type.strip() or None
