"""
Adjustment service - Business logic for account adjustments
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date
from models.adjustment import Adjustment, AdjustmentType
from repositories.adjustment_repository import AdjustmentRepository


class AdjustmentService:
    """Business logic for account adjustments (basis corrections and balance checkpoints)"""
    
    def __init__(self, adjustment_repo: AdjustmentRepository):
        self.adjustment_repo = adjustment_repo
    
    def create_basis_adjustment(
        self,
        user_id: int,
        site_id: int,
        effective_date: date,
        delta_basis_usd: Decimal,
        reason: str,
        effective_time: str = "00:00:00",
        notes: Optional[str] = None,
        related_table: Optional[str] = None,
        related_id: Optional[int] = None
    ) -> Adjustment:
        """Create a basis USD correction adjustment.
        
        Args:
            user_id: User ID
            site_id: Site ID
            effective_date: Effective date of the adjustment
            delta_basis_usd: Change in basis (positive = add, negative = remove)
            reason: Required explanation for the adjustment
            effective_time: Time of day (default 00:00:00)
            notes: Optional additional notes
            related_table: Optional related table name (e.g., 'purchases')
            related_id: Optional related record ID
            
        Returns:
            Created Adjustment
            
        Raises:
            ValueError: If validation fails
        """
        # Validate delta is non-zero
        if delta_basis_usd == Decimal("0.00"):
            raise ValueError("Basis adjustment delta cannot be zero")
        
        # Create adjustment model (validates in __post_init__)
        adjustment = Adjustment(
            user_id=user_id,
            site_id=site_id,
            effective_date=effective_date,
            effective_time=effective_time,
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=delta_basis_usd,
            reason=reason,
            notes=notes,
            related_table=related_table,
            related_id=related_id
        )
        
        # Save to repository
        return self.adjustment_repo.create(adjustment)
    
    def create_balance_checkpoint(
        self,
        user_id: int,
        site_id: int,
        effective_date: date,
        checkpoint_total_sc: Decimal,
        checkpoint_redeemable_sc: Decimal,
        reason: str,
        effective_time: str = "00:00:00",
        notes: Optional[str] = None,
        related_table: Optional[str] = None,
        related_id: Optional[int] = None
    ) -> Adjustment:
        """Create a balance checkpoint adjustment.
        
        This establishes a known balance continuity anchor at a specific timestamp.
        
        Args:
            user_id: User ID
            site_id: Site ID
            effective_date: Effective date of the checkpoint
            checkpoint_total_sc: Known total SC balance at this timestamp
            checkpoint_redeemable_sc: Known redeemable SC balance at this timestamp
            reason: Required explanation for the checkpoint
            effective_time: Time of day (default 00:00:00)
            notes: Optional additional notes
            related_table: Optional related table name
            related_id: Optional related record ID
            
        Returns:
            Created Adjustment
            
        Raises:
            ValueError: If validation fails
        """
        # Validate at least one non-zero balance
        if checkpoint_total_sc == Decimal("0.00") and checkpoint_redeemable_sc == Decimal("0.00"):
            raise ValueError("Balance checkpoint must specify at least one non-zero balance")
        
        # Create adjustment model (validates in __post_init__)
        adjustment = Adjustment(
            user_id=user_id,
            site_id=site_id,
            effective_date=effective_date,
            effective_time=effective_time,
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=checkpoint_total_sc,
            checkpoint_redeemable_sc=checkpoint_redeemable_sc,
            reason=reason,
            notes=notes,
            related_table=related_table,
            related_id=related_id
        )
        
        # Save to repository
        return self.adjustment_repo.create(adjustment)
    
    def get_by_id(self, adjustment_id: int) -> Optional[Adjustment]:
        """Get adjustment by ID"""
        return self.adjustment_repo.get_by_id(adjustment_id)
    
    def get_all(
        self,
        user_id: Optional[int] = None,
        site_id: Optional[int] = None,
        adjustment_type: Optional[AdjustmentType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False
    ) -> List[Adjustment]:
        """Get all adjustments with optional filters"""
        return self.adjustment_repo.get_all(
            user_id=user_id,
            site_id=site_id,
            adjustment_type=adjustment_type,
            start_date=start_date,
            end_date=end_date,
            include_deleted=include_deleted
        )
    
    def get_by_user_and_site(
        self,
        user_id: int,
        site_id: int,
        include_deleted: bool = False
    ) -> List[Adjustment]:
        """Get adjustments for a specific user and site"""
        return self.adjustment_repo.get_by_user_and_site(
            user_id, site_id, include_deleted
        )
    
    def get_active_checkpoints_before(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "23:59:59"
    ) -> List[Adjustment]:
        """Get active balance checkpoint adjustments before a cutoff datetime.
        
        Returns checkpoints ordered DESC by effective datetime (most recent first).
        """
        return self.adjustment_repo.get_active_checkpoints_before(
            user_id, site_id, cutoff_date, cutoff_time
        )
    
    def get_latest_checkpoint_before(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "23:59:59"
    ) -> Optional[Adjustment]:
        """Get the most recent active checkpoint before a cutoff datetime.
        
        Returns None if no checkpoint exists before the cutoff.
        """
        checkpoints = self.get_active_checkpoints_before(
            user_id, site_id, cutoff_date, cutoff_time
        )
        return checkpoints[0] if checkpoints else None
    
    def get_active_basis_adjustments(
        self,
        user_id: int,
        site_id: int
    ) -> List[Adjustment]:
        """Get all active basis adjustments for FIFO pipeline integration.
        
        Returns adjustments ordered ASC by effective datetime (earliest first).
        """
        return self.adjustment_repo.get_active_basis_adjustments(user_id, site_id)
    
    def update_notes(self, adjustment_id: int, notes: Optional[str]) -> bool:
        """Update adjustment notes (limited field update).
        
        This is the only field that can be updated after creation.
        """
        adjustment = self.adjustment_repo.get_by_id(adjustment_id)
        if not adjustment:
            raise ValueError(f"Adjustment {adjustment_id} not found")
        
        if adjustment.is_deleted():
            raise ValueError("Cannot update a deleted adjustment")
        
        adjustment.notes = notes
        return self.adjustment_repo.update(adjustment)
    
    def soft_delete(self, adjustment_id: int, reason: str) -> bool:
        """Soft delete an adjustment.
        
        Args:
            adjustment_id: ID of adjustment to delete
            reason: Required reason for deletion
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If adjustment not found or already deleted
        """
        if not reason or not reason.strip():
            raise ValueError("Deletion reason is required")
        
        adjustment = self.adjustment_repo.get_by_id(adjustment_id)
        if not adjustment:
            raise ValueError(f"Adjustment {adjustment_id} not found")
        
        if adjustment.is_deleted():
            raise ValueError("Adjustment is already deleted")
        
        return self.adjustment_repo.soft_delete(adjustment_id, reason)
    
    def restore(self, adjustment_id: int) -> bool:
        """Restore a soft-deleted adjustment.
        
        Returns:
            True if restored successfully
            
        Raises:
            ValueError: If adjustment not found or not deleted
        """
        adjustment = self.adjustment_repo.get_by_id(adjustment_id)
        if not adjustment:
            raise ValueError(f"Adjustment {adjustment_id} not found")
        
        if not adjustment.is_deleted():
            raise ValueError("Adjustment is not deleted")
        
        return self.adjustment_repo.restore(adjustment_id)
