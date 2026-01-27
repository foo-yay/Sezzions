"""
Purchase domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


@dataclass
class Purchase:
    """Represents a purchase of sweeps coins"""
    user_id: int
    site_id: int
    amount: Decimal
    purchase_date: date
    sc_received: Decimal = Decimal("0.00")
    starting_sc_balance: Decimal = Decimal("0.00")
    cashback_earned: Decimal = Decimal("0.00")
    card_id: Optional[int] = None
    purchase_time: Optional[str] = None
    remaining_amount: Optional[Decimal] = None
    status: Optional[str] = None  # 'active', 'dormant', or NULL
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return f"Purchase ${self.amount} on {self.purchase_date}"
    
    def __post_init__(self):
        """Validate and initialize purchase data"""
        # Validate user_id
        if not self.user_id or self.user_id <= 0:
            raise ValueError("Valid user_id is required")
        
        # Validate site_id
        if not self.site_id or self.site_id <= 0:
            raise ValueError("Valid site_id is required")
        
        # Validate amount
        if isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))
        if self.amount <= 0:
            raise ValueError("Purchase amount must be positive")

        # Convert and validate SC/cashback fields
        for field_name in ["sc_received", "starting_sc_balance", "cashback_earned"]:
            value = getattr(self, field_name)
            if isinstance(value, (int, float)):
                setattr(self, field_name, Decimal(str(value)))
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name.replace('_', ' ').title()} cannot be negative")
        
        # Validate purchase_date
        if isinstance(self.purchase_date, str):
            self.purchase_date = datetime.strptime(self.purchase_date, "%Y-%m-%d").date()
        if not isinstance(self.purchase_date, date):
            raise ValueError("Invalid purchase_date format")
        
        # Initialize remaining_amount if not set
        if self.remaining_amount is None:
            self.remaining_amount = self.amount
        elif isinstance(self.remaining_amount, (int, float)):
            self.remaining_amount = Decimal(str(self.remaining_amount))
        
        # Validate remaining_amount
        if self.remaining_amount < 0:
            raise ValueError("Remaining amount cannot be negative")
        if self.remaining_amount > self.amount:
            raise ValueError("Remaining amount cannot exceed purchase amount")
    
    @property
    def consumed_amount(self) -> Decimal:
        """Calculate consumed amount"""
        return self.amount - self.remaining_amount
    
    @property
    def is_fully_consumed(self) -> bool:
        """Check if purchase is fully consumed"""
        return self.remaining_amount == 0
    
    @property
    def datetime_str(self) -> str:
        """Get combined date/time string for sorting"""
        time_part = self.purchase_time if self.purchase_time else "00:00:00"
        return f"{self.purchase_date} {time_part}"
