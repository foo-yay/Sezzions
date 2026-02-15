"""
Adjustment domain model
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class AdjustmentType(Enum):
    """Types of account adjustments"""
    BASIS_USD_CORRECTION = "BASIS_USD_CORRECTION"
    BALANCE_CHECKPOINT_CORRECTION = "BALANCE_CHECKPOINT_CORRECTION"


@dataclass
class Adjustment:
    """Represents an account adjustment (basis correction or balance checkpoint)"""
    user_id: int
    site_id: int
    effective_date: date
    type: AdjustmentType
    reason: str
    effective_time: str = "00:00:00"
    effective_entry_time_zone: Optional[str] = None
    delta_basis_usd: Decimal = Decimal("0.00")
    checkpoint_total_sc: Decimal = Decimal("0.00")
    checkpoint_redeemable_sc: Decimal = Decimal("0.00")
    notes: Optional[str] = None
    related_table: Optional[str] = None
    related_id: Optional[int] = None
    deleted_at: Optional[datetime] = None
    deleted_reason: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        if self.type == AdjustmentType.BASIS_USD_CORRECTION:
            return f"Basis Adjustment ${self.delta_basis_usd} on {self.effective_date}"
        else:
            return f"Balance Checkpoint on {self.effective_date}"
    
    def __post_init__(self):
        """Validate and initialize adjustment data"""
        # Validate user_id
        if not self.user_id or self.user_id <= 0:
            raise ValueError("Valid user_id is required")
        
        # Validate site_id
        if not self.site_id or self.site_id <= 0:
            raise ValueError("Valid site_id is required")
        
        # Convert effective_date to date if needed
        if isinstance(self.effective_date, str):
            self.effective_date = date.fromisoformat(self.effective_date)
        
        # Validate and normalize effective_time
        if not self.effective_time:
            self.effective_time = "00:00:00"
        
        # Convert type string to enum if needed
        if isinstance(self.type, str):
            self.type = AdjustmentType(self.type)
        
        # Validate reason
        if not self.reason or not self.reason.strip():
            raise ValueError("Reason is required")
        
        # Convert decimal fields
        for field_name in ["delta_basis_usd", "checkpoint_total_sc", "checkpoint_redeemable_sc"]:
            field_value = getattr(self, field_name)
            if isinstance(field_value, (int, float)):
                setattr(self, field_name, Decimal(str(field_value)))
        
        # Type-specific validation
        if self.type == AdjustmentType.BASIS_USD_CORRECTION:
            if self.delta_basis_usd == Decimal("0.00"):
                raise ValueError("Basis adjustment delta cannot be zero")
        elif self.type == AdjustmentType.BALANCE_CHECKPOINT_CORRECTION:
            # Checkpoints must specify balances
            if self.checkpoint_total_sc == Decimal("0.00") and self.checkpoint_redeemable_sc == Decimal("0.00"):
                raise ValueError("Balance checkpoint must specify at least one non-zero balance")
    
    def is_deleted(self) -> bool:
        """Check if adjustment is soft-deleted"""
        return self.deleted_at is not None
