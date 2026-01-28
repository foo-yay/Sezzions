"""
RealizedTransaction model - represents a completed redemption cash flow
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class RealizedTransaction:
    """
    A realized transaction represents cash flow from a redemption:
    - cost_basis: Purchase basis consumed (money in)
    - payout: Amount redeemed (money out)
    - net_pl: Cash flow profit/loss (payout - cost_basis)
    
    NOTE: This is CASH FLOW, not taxable P/L. Taxable P/L is in game_sessions.
    """
    redemption_date: date
    site_id: int
    user_id: int
    site_name: str
    user_name: str
    redemption_id: int
    cost_basis: Decimal
    payout: Decimal
    net_pl: Decimal  # payout - cost_basis (CASH FLOW)
    method_name: Optional[str] = None
    notes: str = ""
    id: Optional[int] = None
    
    def __post_init__(self):
        """Convert types if needed"""
        if isinstance(self.redemption_date, str):
            from datetime import datetime
            self.redemption_date = datetime.strptime(self.redemption_date, "%Y-%m-%d").date()
        
        # Convert to Decimal
        for field in ['cost_basis', 'payout', 'net_pl']:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                setattr(self, field, Decimal(str(value)))
