"""
Redemption domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


@dataclass
class Redemption:
    """Represents a redemption/withdrawal of funds"""
    user_id: int
    site_id: int
    amount: Decimal
    redemption_date: date
    cost_basis: Optional[Decimal] = None
    taxable_profit: Optional[Decimal] = None
    fees: Decimal = Decimal("0.00")
    redemption_method_id: Optional[int] = None
    redemption_time: Optional[str] = None
    redemption_entry_time_zone: Optional[str] = None
    receipt_date: Optional[date] = None
    processed: bool = False
    more_remaining: bool = False
    is_free_sc: bool = False
    notes: Optional[str] = None
    # Cancel / Uncancel fields (Issue #148)
    status: str = "PENDING"           # "PENDING" | "PENDING_CANCEL" | "CANCELED"
    canceled_at: Optional[str] = None  # UTC datetime ISO string, set on cancel
    cancel_reason: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return f"Redemption ${self.amount} on {self.redemption_date}"
    
    def __post_init__(self):
        """Validate and initialize redemption data"""
        # Validate user_id
        if not self.user_id or self.user_id <= 0:
            raise ValueError("Valid user_id is required")
        
        # Validate site_id
        if not self.site_id or self.site_id <= 0:
            raise ValueError("Valid site_id is required")
        
        # Validate amount
        if isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))
        if self.amount < 0:
            raise ValueError("Redemption amount cannot be negative")

        if self.fees is None:
            self.fees = Decimal("0.00")
        if isinstance(self.fees, (int, float, str)):
            self.fees = Decimal(str(self.fees))
        if self.fees < 0:
            raise ValueError("Fees cannot be negative")
        
        # Validate redemption_date
        if isinstance(self.redemption_date, str):
            self.redemption_date = datetime.strptime(self.redemption_date, "%Y-%m-%d").date()
        if not isinstance(self.redemption_date, date):
            raise ValueError("Invalid redemption_date format")

        if isinstance(self.receipt_date, str) and self.receipt_date:
            try:
                self.receipt_date = datetime.strptime(self.receipt_date, "%Y-%m-%d").date()
            except Exception:
                self.receipt_date = None

        # Normalize optional numeric fields
        if self.cost_basis is not None and not isinstance(self.cost_basis, Decimal):
            self.cost_basis = Decimal(str(self.cost_basis))
        if self.taxable_profit is not None and not isinstance(self.taxable_profit, Decimal):
            self.taxable_profit = Decimal(str(self.taxable_profit))

        # Normalize status — default PENDING for legacy rows with NULL
        if not self.status:
            self.status = "PENDING"
        if self.status not in ("PENDING", "PENDING_CANCEL", "CANCELED"):
            raise ValueError(f"Invalid redemption status: {self.status!r}")
    
    @property
    def is_canceled(self) -> bool:
        """True when this redemption has been fully canceled."""
        return self.status == "CANCELED"

    @property
    def is_pending_cancel(self) -> bool:
        """True when cancellation is queued waiting for an active session to end."""
        return self.status == "PENDING_CANCEL"

    @property
    def is_pending(self) -> bool:
        """True when this redemption is in the normal pending-receipt state."""
        return self.status == "PENDING"

    @property
    def datetime_str(self) -> str:
        """Get combined date/time string for sorting"""
        time_part = self.redemption_time if self.redemption_time else "00:00:00"
        return f"{self.redemption_date} {time_part}"

    @property
    def has_fifo_allocation(self) -> bool:
        """True if this redemption has FIFO allocation rows or calculated FIFO fields."""
        return bool(
            getattr(self, "_has_fifo_allocation", False)
            or self.cost_basis is not None
            or self.taxable_profit is not None
        )
