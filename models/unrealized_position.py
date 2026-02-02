"""
UnrealizedPosition model - represents an open position (site with remaining basis)
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class UnrealizedPosition:
    """
    An unrealized position represents a site/user combination with remaining purchase basis.
    Shows current SC balance, value, and unrealized P/L (not taxable until closed).
    """
    site_id: int
    user_id: int
    site_name: str
    user_name: str
    start_date: date  # Oldest purchase with remaining basis
    purchase_basis: Decimal  # Sum of remaining_amount from purchases
    total_sc: Decimal  # Current total SC balance (estimated from last session + transactions)
    redeemable_sc: Decimal  # Current redeemable SC balance (estimated, informational only)
    current_value: Decimal  # total_sc * sc_rate (typically 1:1)
    unrealized_pl: Decimal  # current_value - purchase_basis
    last_activity: Optional[date] = None
    notes: str = ""
    
    def __post_init__(self):
        """Convert types if needed"""
        if isinstance(self.start_date, str):
            from datetime import datetime
            self.start_date = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        
        if self.last_activity and isinstance(self.last_activity, str):
            from datetime import datetime
            self.last_activity = datetime.strptime(self.last_activity, "%Y-%m-%d").date()
        
        # Convert to Decimal
        for field in ['purchase_basis', 'total_sc', 'redeemable_sc', 'current_value', 'unrealized_pl']:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                setattr(self, field, Decimal(str(value)))
