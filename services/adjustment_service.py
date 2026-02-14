"""
Adjustment service - Business logic for account adjustments
"""
import uuid
from dataclasses import asdict
from typing import List, Optional, TYPE_CHECKING
from decimal import Decimal
from datetime import date, datetime
from models.adjustment import Adjustment, AdjustmentType
from repositories.adjustment_repository import AdjustmentRepository

if TYPE_CHECKING:
    from services.audit_service import AuditService
    from services.undo_redo_service import UndoRedoService


class AdjustmentService:
    """Business logic for account adjustments (basis corrections and balance checkpoints)"""
    
    def __init__(
        self,
        adjustment_repo: AdjustmentRepository,
        audit_service: Optional['AuditService'] = None,
        undo_redo_service: Optional['UndoRedoService'] = None,
    ):
        self.adjustment_repo = adjustment_repo
        self.audit_service = audit_service
        self.undo_redo_service = undo_redo_service
    
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
        group_id = self.audit_service.generate_group_id() if self.audit_service else str(uuid.uuid4())
        if self.audit_service:
            with self.adjustment_repo.db.transaction():
                adjustment = self.adjustment_repo.create(adjustment, auto_commit=False)
                self.audit_service.log_create(
                    table_name="account_adjustments",
                    record_id=adjustment.id,
                    new_data=asdict(adjustment),
                    group_id=group_id,
                    auto_commit=False,
                )
        else:
            adjustment = self.adjustment_repo.create(adjustment)

        if self.undo_redo_service and self.audit_service:
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Create basis adjustment (${adjustment.delta_basis_usd})",
                timestamp=datetime.now().isoformat(),
            )

        return adjustment
    
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
        group_id = self.audit_service.generate_group_id() if self.audit_service else str(uuid.uuid4())
        if self.audit_service:
            with self.adjustment_repo.db.transaction():
                adjustment = self.adjustment_repo.create(adjustment, auto_commit=False)
                self.audit_service.log_create(
                    table_name="account_adjustments",
                    record_id=adjustment.id,
                    new_data=asdict(adjustment),
                    group_id=group_id,
                    auto_commit=False,
                )
        else:
            adjustment = self.adjustment_repo.create(adjustment)

        if self.undo_redo_service and self.audit_service:
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Create balance checkpoint ({adjustment.checkpoint_total_sc:,.2f} SC)",
                timestamp=datetime.now().isoformat(),
            )

        return adjustment
    
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

    def get_by_related(
        self,
        related_table: str,
        related_id: int,
        include_deleted: bool = False,
    ) -> List[Adjustment]:
        """Get adjustments explicitly linked to a record via related_table/related_id."""
        return self.adjustment_repo.get_by_related(
            related_table=related_table,
            related_id=related_id,
            include_deleted=include_deleted,
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

    def get_active_checkpoints_after(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "00:00:00",
    ) -> List[Adjustment]:
        """Get active balance checkpoint adjustments strictly after a cutoff datetime.

        Returns checkpoints ordered ASC by effective datetime (earliest first).
        """
        return self.adjustment_repo.get_active_checkpoints_after(
            user_id, site_id, cutoff_date, cutoff_time
        )

    def get_next_checkpoint_after(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "00:00:00",
    ) -> Optional[Adjustment]:
        """Get the earliest active checkpoint strictly after a cutoff datetime."""
        checkpoints = self.get_active_checkpoints_after(
            user_id, site_id, cutoff_date, cutoff_time
        )
        return checkpoints[0] if checkpoints else None

    def get_checkpoint_window_for_timestamp(
        self,
        user_id: int,
        site_id: int,
        anchor_date: date,
        anchor_time: str = "23:59:59",
    ) -> tuple[Optional[Adjustment], Optional[Adjustment]]:
        """Return (start_checkpoint, end_checkpoint) for a basis-period window.

        Window is defined as:
        - start_checkpoint: latest checkpoint at-or-before the anchor timestamp
        - end_checkpoint: next checkpoint strictly after the anchor timestamp

        Either side may be None if no checkpoint exists.
        """
        start_checkpoint = self.get_latest_checkpoint_before(
            user_id=user_id,
            site_id=site_id,
            cutoff_date=anchor_date,
            cutoff_time=anchor_time or "23:59:59",
        )
        end_checkpoint = self.get_next_checkpoint_after(
            user_id=user_id,
            site_id=site_id,
            cutoff_date=anchor_date,
            cutoff_time=anchor_time or "23:59:59",
        )
        return start_checkpoint, end_checkpoint

    def get_active_adjustments_in_checkpoint_window(
        self,
        user_id: int,
        site_id: int,
        anchor_date: date,
        anchor_time: str = "23:59:59",
    ) -> List[Adjustment]:
        """Get active adjustments/checkpoints in the anchor's checkpoint window.

        The window bounds are inclusive, so the end checkpoint itself is included
        when present.
        """
        start_checkpoint, end_checkpoint = self.get_checkpoint_window_for_timestamp(
            user_id=user_id,
            site_id=site_id,
            anchor_date=anchor_date,
            anchor_time=anchor_time,
        )

        start_date = start_checkpoint.effective_date if start_checkpoint else None
        start_time = start_checkpoint.effective_time if start_checkpoint else "00:00:00"
        end_date = end_checkpoint.effective_date if end_checkpoint else None
        end_time = end_checkpoint.effective_time if end_checkpoint else "23:59:59"

        return self.adjustment_repo.get_active_adjustments_in_window(
            user_id=user_id,
            site_id=site_id,
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
        )

    def get_active_adjustments_in_window(
        self,
        user_id: int,
        site_id: int,
        start_date: Optional[date] = None,
        start_time: str = "00:00:00",
        end_date: Optional[date] = None,
        end_time: str = "23:59:59",
    ) -> List[Adjustment]:
        """Get active adjustments/checkpoints in an inclusive datetime window."""
        return self.adjustment_repo.get_active_adjustments_in_window(
            user_id=user_id,
            site_id=site_id,
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
        )
    
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
        
        old_data = asdict(adjustment)
        group_id = self.audit_service.generate_group_id() if self.audit_service else str(uuid.uuid4())

        if self.audit_service:
            with self.adjustment_repo.db.transaction():
                self.adjustment_repo.soft_delete(adjustment_id, reason, auto_commit=False)
                self.audit_service.log_delete(
                    table_name="account_adjustments",
                    record_id=adjustment_id,
                    old_data=old_data,
                    group_id=group_id,
                    auto_commit=False,
                )
        else:
            self.adjustment_repo.soft_delete(adjustment_id, reason)

        if self.undo_redo_service and self.audit_service:
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Delete adjustment #{adjustment_id}",
                timestamp=datetime.now().isoformat(),
            )

        return True

    def get_soft_delete_warning_summary(self, adjustment_id: int) -> dict:
        """Return a downstream-activity summary used to warn before soft-delete.

        The caller can treat any non-zero count as a signal that deleting this
        adjustment/checkpoint may alter derived balances/continuity for later activity.
        """
        adjustment = self.adjustment_repo.get_by_id(adjustment_id)
        if not adjustment:
            raise ValueError(f"Adjustment {adjustment_id} not found")

        summary = self.adjustment_repo.get_downstream_activity_summary(
            user_id=adjustment.user_id,
            site_id=adjustment.site_id,
            effective_date=adjustment.effective_date,
            effective_time=adjustment.effective_time or "00:00:00",
            exclude_adjustment_id=adjustment.id,
        )
        total = 0
        for v in summary.values():
            try:
                total += int(v)
            except Exception:
                continue
        summary["has_downstream_activity"] = total > 0
        return summary
    
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
        
        group_id = self.audit_service.generate_group_id() if self.audit_service else str(uuid.uuid4())

        if self.audit_service:
            with self.adjustment_repo.db.transaction():
                self.adjustment_repo.restore(adjustment_id, auto_commit=False)
                restored = self.adjustment_repo.get_by_id(adjustment_id)
                if restored:
                    self.audit_service.log_restore(
                        table_name="account_adjustments",
                        record_id=adjustment_id,
                        restored_data=asdict(restored),
                        group_id=group_id,
                        auto_commit=False,
                    )
        else:
            self.adjustment_repo.restore(adjustment_id)

        if self.undo_redo_service and self.audit_service:
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Restore adjustment #{adjustment_id}",
                timestamp=datetime.now().isoformat(),
            )

        return True
