"""
GameSession model - represents a gambling session with P/L calculation
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class GameSession:
    """
    A game session tracks play at a specific site/game with:
    - Starting/ending balances (total and redeemable SC)
    - Purchases and redemptions during session
    - Proper tax calculation: discoverable_sc + delta_play - basis_consumed
    
    CRITICAL: P/L calculation requires all balance fields to be accurate.
    Sessions must be processed chronologically for expected_start calculations.
    """
    user_id: int
    site_id: int
    session_date: date
    game_id: Optional[int] = None
    game_type_id: Optional[int] = None
    end_date: Optional[date] = None
    end_time: Optional[str] = None
    start_entry_time_zone: Optional[str] = None
    end_entry_time_zone: Optional[str] = None
    
    # Balance fields (required for proper P/L calculation)
    starting_balance: Decimal = Decimal("0.00")  # Total SC at start
    ending_balance: Decimal = Decimal("0.00")    # Total SC at end
    starting_redeemable: Decimal = Decimal("0.00")  # Redeemable SC at start
    ending_redeemable: Decimal = Decimal("0.00")    # Redeemable SC at end
    
    # Transaction amounts during session
    purchases_during: Decimal = Decimal("0.00")
    redemptions_during: Decimal = Decimal("0.00")

    # RTP tracking
    wager_amount: Decimal = Decimal("0.00")
    rtp: Optional[float] = None
    
    # Calculated/derived fields (computed by service layer)
    expected_start_total: Optional[Decimal] = None
    expected_start_redeemable: Optional[Decimal] = None
    discoverable_sc: Optional[Decimal] = None  # Found money (starting_redeem - expected_start_redeem)
    delta_total: Optional[Decimal] = None      # ending_balance - starting_balance
    delta_redeem: Optional[Decimal] = None     # ending_redeemable - starting_redeemable
    session_basis: Optional[Decimal] = None    # Basis added during session (purchases cash value)
    basis_consumed: Optional[Decimal] = None   # Basis consumed (when redeem increases)
    net_taxable_pl: Optional[Decimal] = None   # THE actual taxable P/L
    profit_loss: Optional[Decimal] = None      # Back-compat alias for net_taxable_pl

    # Tax withholding estimate (Issue #29)
    # Stored historically on closed sessions.
    tax_withholding_rate_pct: Optional[Decimal] = None
    tax_withholding_is_custom: bool = False
    tax_withholding_amount: Optional[Decimal] = None
    
    # Metadata
    session_time: str = "00:00:00"
    notes: str = ""
    status: str = "Active"  # Active or Closed
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate and convert types"""
        if not self.user_id or self.user_id <= 0:
            raise ValueError("Valid user_id is required")
        if not self.site_id or self.site_id <= 0:
            raise ValueError("Valid site_id is required")
        if self.game_id is not None and self.game_id <= 0:
            raise ValueError("Valid game_id is required")
        
        # Convert date string to date object
        if isinstance(self.session_date, str):
            self.session_date = datetime.strptime(self.session_date, "%Y-%m-%d").date()
        if isinstance(self.end_date, str):
            self.end_date = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        
        # Convert amounts to Decimal
        for field_name in ['starting_balance', 'ending_balance', 'starting_redeemable', 'ending_redeemable',
                           'purchases_during', 'redemptions_during', 'wager_amount', 'expected_start_total', 
                           'expected_start_redeemable', 'discoverable_sc', 'delta_total', 'delta_redeem',
                           'session_basis', 'basis_consumed', 'net_taxable_pl', 'profit_loss',
                           'tax_withholding_rate_pct', 'tax_withholding_amount']:
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                setattr(self, field_name, Decimal(str(value)))

        if self.net_taxable_pl is None and self.profit_loss is not None:
            self.net_taxable_pl = Decimal(str(self.profit_loss))
        if self.profit_loss is None and self.net_taxable_pl is not None:
            self.profit_loss = Decimal(str(self.net_taxable_pl))

        # Normalize custom flag from int/bool
        if isinstance(self.tax_withholding_is_custom, int):
            self.tax_withholding_is_custom = bool(self.tax_withholding_is_custom)
        
        # Validate non-negative amounts
        if self.starting_balance < 0:
            raise ValueError("Starting balance cannot be negative")
        if self.ending_balance < 0:
            raise ValueError("Ending balance cannot be negative")
        if self.starting_redeemable < 0:
            raise ValueError("Starting redeemable cannot be negative")
        if self.ending_redeemable < 0:
            raise ValueError("Ending redeemable cannot be negative")
        if self.purchases_during < 0:
            raise ValueError("Purchases during session cannot be negative")
        if self.redemptions_during < 0:
            raise ValueError("Redemptions during session cannot be negative")
        if self.wager_amount < 0:
            raise ValueError("Wager amount cannot be negative")
        
        # Validate redeemable cannot exceed total
        if self.starting_redeemable > self.starting_balance:
            raise ValueError("Starting redeemable cannot exceed starting balance")
        if self.ending_redeemable > self.ending_balance:
            raise ValueError("Ending redeemable cannot exceed ending balance")
    
    @property
    def datetime_str(self) -> str:
        """Combined date and time for sorting"""
        return f"{self.session_date} {self.session_time}"

    @property
    def total_in(self) -> Decimal:
        """Total SC in during session (starting + purchases)."""
        return self.starting_balance + self.purchases_during

    @property
    def total_out(self) -> Decimal:
        """Total SC out during session (redemptions + ending)."""
        return self.redemptions_during + self.ending_balance

    @property
    def calculated_pl(self) -> Decimal:
        """Simple P/L (total_out - total_in)."""
        return self.total_out - self.total_in
    
    @property
    def locked_start(self) -> Decimal:
        """Locked (non-redeemable) SC at start"""
        return self.starting_balance - self.starting_redeemable
    
    @property
    def locked_end(self) -> Decimal:
        """Locked (non-redeemable) SC at end"""
        return self.ending_balance - self.ending_redeemable
    
    @property
    def locked_processed(self) -> Decimal:
        """Amount of locked SC that was processed/unlocked"""
        return max(Decimal("0.00"), self.locked_start - self.locked_end)
    
    @property
    def has_calculated_pl(self) -> bool:
        """Check if net_taxable_pl has been calculated"""
        return self.net_taxable_pl is not None
