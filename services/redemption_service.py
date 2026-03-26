"""
Redemption service - Business logic for Redemption operations
"""
import uuid
from dataclasses import asdict
from typing import List, Optional, Tuple, TYPE_CHECKING
from decimal import Decimal
from datetime import date, datetime, timezone
from models.redemption import Redemption
from tools.timezone_utils import get_entry_timezone_name, local_date_time_to_utc
from repositories.redemption_repository import RedemptionRepository
from services.fifo_service import FIFOService

if TYPE_CHECKING:
    from services.audit_service import AuditService
    from services.undo_redo_service import UndoRedoService


class RedemptionService:
    """Business logic for Redemption operations"""
    
    def __init__(
        self, 
        redemption_repo: RedemptionRepository,
        fifo_service: FIFOService,
        db_manager=None
    ):
        self.redemption_repo = redemption_repo
        self.fifo_service = fifo_service
        self.db = db_manager
        self.audit_service: Optional['AuditService'] = None
        self.undo_redo_service: Optional['UndoRedoService'] = None

    def _get_total_remaining_basis_as_of(
        self,
        user_id: int,
        site_id: int,
        redemption_date: date,
        redemption_time: Optional[str],
        redemption_entry_time_zone: Optional[str],
    ) -> Decimal:
        purchases = self.fifo_service.purchase_repo.get_available_for_fifo_as_of(
            user_id,
            site_id,
            redemption_date,
            redemption_time or "23:59:59",
            entry_time_zone=redemption_entry_time_zone,
        )
        return sum((purchase.remaining_amount for purchase in purchases), Decimal("0.00"))
    
    def create_redemption(
        self,
        user_id: int,
        site_id: int,
        amount: Decimal,
        redemption_date: date,
        redemption_method_id: Optional[int] = None,
        redemption_time: Optional[str] = None,
        receipt_date: Optional[date] = None,
        processed: bool = False,
        more_remaining: bool = False,
        notes: Optional[str] = None,
        apply_fifo: bool = True,
        fees: Decimal = Decimal("0.00")
    ) -> Redemption:
        """
        Create new redemption with optional FIFO allocation.
        
        Args:
            apply_fifo: If True, automatically calculate and apply FIFO allocation
        """
        # Create redemption model
        redemption = Redemption(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            redemption_date=redemption_date,
            redemption_method_id=redemption_method_id,
            redemption_time=redemption_time,
            redemption_entry_time_zone=get_entry_timezone_name(),
            receipt_date=receipt_date,
            processed=processed,
            more_remaining=more_remaining,
            notes=notes,
            fees=fees
        )
        
        # Apply FIFO if requested
        if apply_fifo:
            # For Full redemptions (more_remaining=False), consume ALL remaining basis
            if not more_remaining:
                total_remaining = self._get_total_remaining_basis_as_of(
                    user_id,
                    site_id,
                    redemption_date,
                    redemption_time,
                    redemption.redemption_entry_time_zone,
                )
                
                # Calculate FIFO for ALL remaining basis (not just redemption amount)
                cost_basis, taxable_profit, allocations = self.fifo_service.calculate_cost_basis(
                    user_id,
                    site_id,
                    total_remaining,  # Consume ALL remaining
                    redemption_date,
                    redemption_time or "23:59:59",
                    redemption_entry_time_zone=redemption.redemption_entry_time_zone,
                )
                
                # Recalculate profit: payout - cost_basis (may be negative for loss)
                taxable_profit = amount - cost_basis
            else:
                # Partial redemption - just use the redemption amount
                cost_basis, taxable_profit, allocations = self.fifo_service.calculate_cost_basis(
                    user_id,
                    site_id,
                    amount,
                    redemption_date,
                    redemption_time or "23:59:59",
                    redemption_entry_time_zone=redemption.redemption_entry_time_zone,
                )

            redemption.cost_basis = cost_basis
            redemption.taxable_profit = taxable_profit
            redemption._has_fifo_allocation = True
            
            # Save redemption first (without FIFO results) - returns Redemption with ID set
            redemption = self.redemption_repo.create(redemption)
            
            # Log to audit and undo/redo stack
            group_id = str(uuid.uuid4())
            if self.audit_service:
                self.audit_service.log_create(
                    table_name="redemptions",
                    record_id=redemption.id,
                    new_data=asdict(redemption),
                    group_id=group_id
                )
            
            if self.undo_redo_service:
                from datetime import datetime
                self.undo_redo_service.push_operation(
                    group_id=group_id,
                    description=f"Create redemption (${amount})",
                    timestamp=datetime.now().isoformat()
                )
            
            # Save allocations to redemption_allocations table
            self._save_allocations(redemption.id, allocations)
            
            # Apply allocations to purchases
            self.fifo_service.apply_allocation(allocations)
            
            # Create realized_transaction record with FIFO results
            self._create_realized_transaction(
                redemption_id=redemption.id,
                redemption_date=redemption_date,
                user_id=user_id,
                site_id=site_id,
                cost_basis=cost_basis,
                payout=amount,
                net_pl=taxable_profit
            )
            
            return redemption
        else:
            # Save without FIFO - returns Redemption with ID set
            redemption = self.redemption_repo.create(redemption)
            
            # Log to audit and undo/redo stack
            group_id = str(uuid.uuid4())
            if self.audit_service:
                self.audit_service.log_create(
                    table_name="redemptions",
                    record_id=redemption.id,
                    new_data=asdict(redemption),
                    group_id=group_id
                )
            
            if self.undo_redo_service:
                from datetime import datetime
                self.undo_redo_service.push_operation(
                    group_id=group_id,
                    description=f"Create redemption (${redemption.amount})",
                    timestamp=datetime.now().isoformat()
                )
            
            return redemption
    
    def update_redemption(
        self, 
        redemption_id: int, 
        **kwargs
    ) -> Redemption:
        """Update redemption with business rules validation"""
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")
        if getattr(redemption, 'status', 'PENDING') != 'PENDING':
            raise ValueError("Only PENDING redemptions may be updated through the lightweight update path.")

        forbidden_fields = {
            'status',
            'canceled_at',
            'cancel_reason',
            'cost_basis',
            'taxable_profit',
        }
        attempted_forbidden = sorted(field for field in kwargs if field in forbidden_fields)
        if attempted_forbidden:
            names = ", ".join(attempted_forbidden)
            raise ValueError(f"Cancel lifecycle/accounting fields are not directly editable: {names}")
        
        # Capture old state for audit (BEFORE any modifications)
        old_data = asdict(redemption)
        
        # Check if FIFO has been allocated
        if redemption.has_fifo_allocation:
            # Protect critical fields when FIFO allocated
            protected_fields = ['user_id', 'site_id', 'amount', 'redemption_date']
            for field in protected_fields:
                if field in kwargs and getattr(redemption, field) != kwargs[field]:
                    raise ValueError(
                        f"Cannot change {field} on redemption with FIFO allocation. "
                        f"Delete and recreate redemption instead."
                    )
        
        # Update allowed fields
        for key, value in kwargs.items():
            if hasattr(redemption, key):
                setattr(redemption, key, value)
        
        # Validate
        redemption.__post_init__()
        
        result = self.redemption_repo.update(redemption)
        
        # Log update to audit and undo/redo stack
        group_id = str(uuid.uuid4())
        if self.audit_service:
            self.audit_service.log_update('redemptions', redemption.id, old_data, asdict(result), group_id=group_id)
        
        if self.undo_redo_service:
            from datetime import datetime
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Update redemption #{redemption.id}",
                timestamp=datetime.now().isoformat()
            )
        
        return result
    
    def delete_redemption(self, redemption_id: int) -> None:
        """
        Delete redemption and reverse FIFO allocation.
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")
        
        # Capture old state for audit
        old_data = asdict(redemption)
        
        # Check if allocations exist
        allocations = self._get_allocations(redemption_id)
        
        if allocations:
            # Reverse the allocations (restore purchase remaining_amount)
            self.fifo_service.reverse_allocation(allocations)
            
            # Delete allocation records
            self._delete_allocations(redemption_id)
            
            # Delete realized_transaction record
            self._delete_realized_transaction(redemption_id)
        
        # Delete the redemption
        self.redemption_repo.delete(redemption_id)
        
        # Log deletion to audit and undo/redo stack
        group_id = str(uuid.uuid4())
        if self.audit_service:
            self.audit_service.log_delete('redemptions', redemption_id, old_data, group_id=group_id)
        
        if self.undo_redo_service:
            from datetime import datetime
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Delete redemption #{redemption_id}",
                timestamp=datetime.now().isoformat()
            )
    
    def delete_redemptions_bulk(self, redemption_ids: List[int]) -> None:
        """
        Delete multiple redemptions in a single transaction.
        More efficient than calling delete_redemption in a loop.
        """
        if not redemption_ids:
            return
        
        # Generate group_id for bulk operation
        import uuid
        group_id = str(uuid.uuid4())
        
        # Process all deletes in a single transaction
        for redemption_id in redemption_ids:
            redemption = self.redemption_repo.get_by_id(redemption_id)
            if not redemption:
                continue
            
            # Capture old state for audit
            old_data = asdict(redemption)
            
            # Check if allocations exist
            allocations = self._get_allocations(redemption_id)
            
            if allocations:
                # Reverse the allocations (restore purchase remaining_amount)
                self.fifo_service.reverse_allocation(allocations)
                
                # Delete allocation records
                self._delete_allocations(redemption_id)
                
                # Delete realized_transaction record
                self._delete_realized_transaction(redemption_id)
            
            # Delete the redemption
            self.redemption_repo.delete(redemption_id)
            
            # Log deletion to audit with group_id
            if self.audit_service:
                self.audit_service.log_delete('redemptions', redemption_id, old_data, group_id=group_id)
            
            # Delete the redemption
            self.redemption_repo.delete(redemption_id)
        
        # Commit once at the end
        self.db.commit()
        
        # Push bulk operation to undo/redo stack (after successful commit)
        if self.undo_redo_service:
            from datetime import datetime
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Delete {len(redemption_ids)} redemptions",
                timestamp=datetime.now().isoformat()
            )
    
    def get_redemption(self, redemption_id: int) -> Optional[Redemption]:
        """Get redemption by ID"""
        return self.redemption_repo.get_by_id(redemption_id)
    
    def list_user_redemptions(self, user_id: int) -> List[Redemption]:
        """Get all redemptions for a user"""
        return self.redemption_repo.get_by_user(user_id)
    
    def list_site_redemptions(self, site_id: int) -> List[Redemption]:
        """Get all redemptions for a site"""
        return self.redemption_repo.get_by_site(site_id)

    # -----------------------------------------------------------------------
    # Cancel / Uncancel (Issue #148)
    # -----------------------------------------------------------------------

    def cancel_redemption(
        self,
        redemption_id: int,
        reason: str,
        has_active_session: bool = False,
        notification_service=None,
        group_id: Optional[str] = None,
    ) -> Redemption:
        """Cancel a pending redemption, reversing its FIFO allocation.

        If *has_active_session* is True the cancellation is deferred to status
        PENDING_CANCEL and no FIFO reversal happens yet.  The reversal occurs
        when the session closes (via :meth:`process_pending_cancels`).

        Raises:
            ValueError: if the redemption cannot be canceled (wrong status,
                        already received, not found).
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")

        if redemption.status == 'PENDING_CANCEL':
            raise ValueError("Cancellation is already pending for this redemption.")
        if redemption.status == 'CANCELED':
            raise ValueError("This redemption has already been canceled.")
        if redemption.status != 'PENDING':
            raise ValueError(f"Cannot cancel a redemption with status '{redemption.status}'.")
        if redemption.receipt_date is not None:
            raise ValueError(
                "Cannot cancel a completed redemption (receipt date is set). "
                "Only unprocessed (pending) redemptions may be canceled."
            )

        old_data = asdict(redemption)
        group_id = group_id or str(uuid.uuid4())

        if has_active_session:
            # Defer — mark as PENDING_CANCEL, no FIFO reversal yet
            redemption.status = 'PENDING_CANCEL'
            redemption.cancel_reason = reason
            self.redemption_repo.update(redemption)

            if self.audit_service:
                self.audit_service.log_update(
                    'redemptions', redemption.id, old_data, asdict(redemption),
                    group_id=group_id,
                )
            if self.undo_redo_service:
                self.undo_redo_service.push_operation(
                    group_id=group_id,
                    description=f"Queue cancel for redemption #{redemption_id} (session active)",
                    timestamp=datetime.now().isoformat(),
                )
            return self.redemption_repo.get_by_id(redemption_id)

        # Immediate cancel — reverse FIFO in a single transaction
        self._execute_cancel(redemption, reason, group_id, old_data, notification_service)
        return self.redemption_repo.get_by_id(redemption_id)

    def _execute_cancel(
        self,
        redemption: Redemption,
        reason: str,
        group_id: str,
        old_data: dict,
        notification_service=None,
        push_undo: bool = True,
    ) -> None:
        """Inner helper that performs the actual FIFO reversal and status update."""
        with self.db.transaction():
            self._execute_cancel_no_commit(redemption, reason, group_id, old_data)

        # Dismiss any pending-receipt notification for this redemption
        if notification_service is not None:
            try:
                notification_service.dismiss_by_type(
                    'redemption_pending_receipt',
                    subject_id=str(redemption.id),
                )
            except Exception:
                pass

        if push_undo and self.undo_redo_service:
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Cancel redemption #{redemption.id}",
                timestamp=datetime.now().isoformat(),
            )

    def _execute_cancel_no_commit(
        self,
        redemption: Redemption,
        reason: str,
        group_id: str,
        old_data: dict,
    ) -> None:
        """Apply cancel accounting changes without committing."""
        allocations = self._get_allocations(redemption.id)
        if allocations:
            self._reverse_allocations_no_commit(allocations)
            self._delete_allocations_no_commit(redemption.id)

        # Realized rows must be removed for every completed cancel, including
        # zero-basis/full redemptions that never had FIFO allocation rows.
        self._delete_realized_transaction_no_commit(redemption.id)

        canceled_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        redemption.status = 'CANCELED'
        redemption.canceled_at = canceled_at
        redemption.cancel_reason = reason
        redemption.cost_basis = None
        redemption.taxable_profit = None
        self._update_redemption_no_commit(redemption)

        if self.audit_service:
            self.audit_service.log_update(
                'redemptions', redemption.id, old_data, asdict(redemption),
                group_id=group_id,
                auto_commit=False,
            )

    def uncancel_redemption(
        self,
        redemption_id: int,
        group_id: Optional[str] = None,
        restore_fifo: bool = True,
    ) -> Redemption:
        """Uncancel a previously canceled redemption, re-applying FIFO.

        Raises:
            ValueError: if the redemption is not in CANCELED status or not found.
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")
        if redemption.status != 'CANCELED':
            raise ValueError(
                f"Cannot uncancel a redemption with status '{redemption.status}'. "
                "Only CANCELED redemptions may be uncanceled."
            )

        old_data = asdict(redemption)
        group_id = group_id or str(uuid.uuid4())

        if not restore_fifo:
            with self.db.transaction():
                redemption.status = 'PENDING'
                redemption.canceled_at = None
                redemption.cancel_reason = None
                redemption.receipt_date = None
                redemption.cost_basis = None
                redemption.taxable_profit = None
                self._update_redemption_no_commit(redemption)

                if self.audit_service:
                    self.audit_service.log_update(
                        'redemptions', redemption.id, old_data, asdict(redemption),
                        group_id=group_id,
                        auto_commit=False,
                    )

            if self.undo_redo_service:
                self.undo_redo_service.push_operation(
                    group_id=group_id,
                    description=f"Uncancel redemption #{redemption_id}",
                    timestamp=datetime.now().isoformat(),
                )

            refreshed = self.redemption_repo.get_by_id(redemption_id)
            if refreshed is None:
                raise ValueError(f"Redemption {redemption_id} not found after uncancel")
            return refreshed

        # Re-apply FIFO — same logic as create_redemption
        cost_basis, taxable_profit, allocations = self._calculate_fifo_for_redemption(redemption)

        # Persist allocations and restore accounting records
        with self.db.transaction():
            self._save_allocations_no_commit(redemption.id, allocations)
            self._apply_allocations_no_commit(allocations)
            self._create_realized_transaction_no_commit(
                redemption_id=redemption.id,
                redemption_date=redemption.redemption_date,
                user_id=redemption.user_id,
                site_id=redemption.site_id,
                cost_basis=cost_basis,
                payout=Decimal(str(redemption.amount)),
                net_pl=taxable_profit,
            )

            # Restore to PENDING
            redemption.status = 'PENDING'
            redemption.canceled_at = None
            redemption.cancel_reason = None
            redemption.receipt_date = None   # returning to pending state
            redemption.cost_basis = cost_basis
            redemption.taxable_profit = taxable_profit
            self._update_redemption_no_commit(redemption)

            if self.audit_service:
                self.audit_service.log_update(
                    'redemptions', redemption.id, old_data, asdict(redemption),
                    group_id=group_id,
                    auto_commit=False,
                )

        if self.undo_redo_service:
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Uncancel redemption #{redemption_id}",
                timestamp=datetime.now().isoformat(),
            )

        return self.redemption_repo.get_by_id(redemption_id)

    def process_pending_cancels(
        self,
        user_id: int,
        site_id: int,
        notification_service=None,
        group_id: Optional[str] = None,
        push_undo: bool = True,
        auto_commit: bool = True,
    ) -> List[int]:
        """Complete all PENDING_CANCEL redemptions for a user/site after a session ends.

        Called by GameSessionService.update_session() when status transitions
        to 'Closed'.  Processes in chronological order of redemption_date so
        FIFO reversal is applied in the correct sequence.

        Returns:
            List of redemption IDs that were fully canceled.
        """
        pending = self.redemption_repo.get_pending_cancel_for_user_site(user_id, site_id)
        canceled_ids: List[int] = []
        if not pending:
            return canceled_ids

        gid = group_id or str(uuid.uuid4())

        def _run_batch() -> None:
            for r in pending:
                old_data = asdict(r)
                old_data['status'] = 'PENDING'
                old_data['canceled_at'] = None
                old_data['cancel_reason'] = None
                self._execute_cancel_no_commit(
                    r,
                    r.cancel_reason or "",
                    gid,
                    old_data,
                )
                canceled_ids.append(r.id)

        if auto_commit:
            with self.db.transaction():
                _run_batch()
        else:
            _run_batch()

        if notification_service is not None:
            for redemption_id in canceled_ids:
                try:
                    notification_service.dismiss_by_type(
                        'redemption_pending_receipt',
                        subject_id=str(redemption_id),
                    )
                except Exception:
                    pass

        if push_undo and self.undo_redo_service:
            count = len(canceled_ids)
            noun = "redemption" if count == 1 else "redemptions"
            self.undo_redo_service.push_operation(
                group_id=gid,
                description=f"Process pending cancel for {count} {noun}",
                timestamp=datetime.now().isoformat(),
            )
        return canceled_ids

    def reconcile_post_undo_redo(self, redemption_id: int, has_active_session: bool) -> Optional[Redemption]:
        """Repair physical accounting state after an external snapshot restore.

        Undo/redo restores row snapshots but does not restore related FIFO rows.
        This helper brings allocations/realized rows back in sync with the
        current redemption status.
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if redemption is None:
            return None

        if redemption.status == 'PENDING_CANCEL' and not has_active_session:
            redemption.status = 'PENDING'
            redemption.canceled_at = None
            redemption.cancel_reason = None
            self.redemption_repo.update(redemption)
            redemption = self.redemption_repo.get_by_id(redemption_id)
            if redemption is None:
                return None

        allocations = self._get_allocations(redemption_id)
        needs_fifo = (
            redemption.status in ('PENDING', 'PENDING_CANCEL')
            and redemption.receipt_date is None
            and Decimal(str(redemption.amount or 0)) > 0
        )

        if redemption.status == 'CANCELED':
            if allocations:
                with self.db.transaction():
                    self._reverse_allocations_no_commit(allocations)
                    self._delete_allocations_no_commit(redemption_id)
                    self._delete_realized_transaction_no_commit(redemption_id)
            return self.redemption_repo.get_by_id(redemption_id)

        if needs_fifo and not allocations:
            cost_basis, taxable_profit, new_allocations = self._calculate_fifo_for_redemption(redemption)
            with self.db.transaction():
                self._save_allocations_no_commit(redemption_id, new_allocations)
                self._apply_allocations_no_commit(new_allocations)
                if not self._has_realized_transaction(redemption_id):
                    self._create_realized_transaction_no_commit(
                        redemption_id=redemption.id,
                        redemption_date=redemption.redemption_date,
                        user_id=redemption.user_id,
                        site_id=redemption.site_id,
                        cost_basis=cost_basis,
                        payout=Decimal(str(redemption.amount)),
                        net_pl=taxable_profit,
                    )
                redemption.cost_basis = cost_basis
                redemption.taxable_profit = taxable_profit
                self._update_redemption_no_commit(redemption)
            return self.redemption_repo.get_by_id(redemption_id)

        return redemption

    def _calculate_fifo_for_redemption(
        self,
        redemption: Redemption,
    ) -> Tuple[Decimal, Decimal, List[Tuple[int, Decimal]]]:
        if not redemption.more_remaining:
            total_remaining = self._get_total_remaining_basis_as_of(
                redemption.user_id,
                redemption.site_id,
                redemption.redemption_date,
                redemption.redemption_time,
                redemption.redemption_entry_time_zone,
            )
            cost_basis, taxable_profit, allocations = self.fifo_service.calculate_cost_basis(
                redemption.user_id,
                redemption.site_id,
                total_remaining,
                redemption.redemption_date,
                redemption.redemption_time or "23:59:59",
                redemption_entry_time_zone=redemption.redemption_entry_time_zone,
            )
            taxable_profit = Decimal(str(redemption.amount)) - cost_basis
            return cost_basis, taxable_profit, allocations

        return self.fifo_service.calculate_cost_basis(
            redemption.user_id,
            redemption.site_id,
            Decimal(str(redemption.amount)),
            redemption.redemption_date,
            redemption.redemption_time or "23:59:59",
            redemption_entry_time_zone=redemption.redemption_entry_time_zone,
        )
    
    def list_redemptions(
        self, 
        user_id: Optional[int] = None, 
        site_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Redemption]:
        """Get redemptions with optional filters"""
        # Get all redemptions with date filter
        redemptions = self.redemption_repo.get_all(start_date=start_date, end_date=end_date)
        
        # Apply in-memory filters for user/site
        if user_id:
            redemptions = [r for r in redemptions if r.user_id == user_id]
        if site_id:
            redemptions = [r for r in redemptions if r.site_id == site_id]
        
        return redemptions
    
    def _save_allocations(self, redemption_id: int, allocations: List[Tuple[int, Decimal]]) -> None:
        """Save FIFO allocations to redemption_allocations table"""
        if not self.db:
            return  # Skip if no db manager
        
        for purchase_id, amount in allocations:
            query = """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
            """
            self.db.execute(query, (redemption_id, purchase_id, str(amount)))

    def _save_allocations_no_commit(self, redemption_id: int, allocations: List[Tuple[int, Decimal]]) -> None:
        if not self.db:
            return
        for purchase_id, amount in allocations:
            self.db.execute_no_commit(
                """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
                """,
                (redemption_id, purchase_id, str(amount)),
            )
    
    def _get_allocations(self, redemption_id: int) -> List[Tuple[int, Decimal]]:
        """Retrieve FIFO allocations from redemption_allocations table"""
        if not self.db:
            return []
        
        query = """
            SELECT purchase_id, allocated_amount 
            FROM redemption_allocations 
            WHERE redemption_id = ?
        """
        rows = self.db.fetch_all(query, (redemption_id,))
        return [(row["purchase_id"], Decimal(row["allocated_amount"])) for row in rows]
    
    def _delete_allocations(self, redemption_id: int) -> None:
        """Delete allocation records for a redemption"""
        if not self.db:
            return
        
        query = "DELETE FROM redemption_allocations WHERE redemption_id = ?"
        self.db.execute(query, (redemption_id,))

    def _delete_allocations_no_commit(self, redemption_id: int) -> None:
        if not self.db:
            return
        self.db.execute_no_commit(
            "DELETE FROM redemption_allocations WHERE redemption_id = ?",
            (redemption_id,),
        )
    
    def _create_realized_transaction(
        self, 
        redemption_id: int, 
        redemption_date, 
        user_id: int, 
        site_id: int,
        cost_basis: Decimal,
        payout: Decimal,
        net_pl: Decimal
    ) -> None:
        """Create realized_transaction record (tax session) for redemption"""
        if not self.db:
            return
        
        query = """
            INSERT INTO realized_transactions 
            (redemption_id, redemption_date, user_id, site_id, cost_basis, payout, net_pl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.db.execute(query, (
            redemption_id,
            redemption_date.isoformat() if hasattr(redemption_date, 'isoformat') else redemption_date,
            user_id,
            site_id,
            str(cost_basis),
            str(payout),
            str(net_pl)
        ))

    def _create_realized_transaction_no_commit(
        self,
        redemption_id: int,
        redemption_date,
        user_id: int,
        site_id: int,
        cost_basis: Decimal,
        payout: Decimal,
        net_pl: Decimal,
    ) -> None:
        if not self.db:
            return
        self.db.execute_no_commit(
            """
            INSERT INTO realized_transactions
            (redemption_id, redemption_date, user_id, site_id, cost_basis, payout, net_pl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                redemption_id,
                redemption_date.isoformat() if hasattr(redemption_date, 'isoformat') else redemption_date,
                user_id,
                site_id,
                str(cost_basis),
                str(payout),
                str(net_pl),
            ),
        )
    
    def _delete_realized_transaction(self, redemption_id: int) -> None:
        """Delete realized_transaction record for a redemption"""
        if not self.db:
            return
        
        query = "DELETE FROM realized_transactions WHERE redemption_id = ?"
        self.db.execute(query, (redemption_id,))

    def _delete_realized_transaction_no_commit(self, redemption_id: int) -> None:
        if not self.db:
            return
        self.db.execute_no_commit(
            "DELETE FROM realized_transactions WHERE redemption_id = ?",
            (redemption_id,),
        )

    def _has_realized_transaction(self, redemption_id: int) -> bool:
        if not self.db:
            return False
        row = self.db.fetch_one(
            "SELECT 1 FROM realized_transactions WHERE redemption_id = ? LIMIT 1",
            (redemption_id,),
        )
        return bool(row)

    def _apply_allocations_no_commit(self, allocations: List[Tuple[int, Decimal]]) -> None:
        for purchase_id, amount_allocated in allocations:
            purchase = self.fifo_service.purchase_repo.get_by_id(purchase_id)
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            new_remaining = purchase.remaining_amount - amount_allocated
            if new_remaining < 0:
                raise ValueError(
                    f"Cannot allocate ${amount_allocated} from purchase {purchase_id}. "
                    f"Only ${purchase.remaining_amount} remaining."
                )
            self.db.execute_no_commit(
                "UPDATE purchases SET remaining_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(new_remaining), purchase_id),
            )

    def _reverse_allocations_no_commit(self, allocations: List[Tuple[int, Decimal]]) -> None:
        for purchase_id, amount_allocated in allocations:
            purchase = self.fifo_service.purchase_repo.get_by_id(purchase_id)
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            new_remaining = purchase.remaining_amount + amount_allocated
            if new_remaining > purchase.amount:
                raise ValueError(
                    f"Cannot restore ${amount_allocated} to purchase {purchase_id}. "
                    f"Would exceed original amount ${purchase.amount}."
                )
            self.db.execute_no_commit(
                "UPDATE purchases SET remaining_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(new_remaining), purchase_id),
            )

    def _update_redemption_no_commit(self, redemption: Redemption) -> None:
        entry_tz = redemption.redemption_entry_time_zone or get_entry_timezone_name()
        utc_date, utc_time = local_date_time_to_utc(
            redemption.redemption_date,
            redemption.redemption_time,
            entry_tz,
        )
        self.db.execute_no_commit(
            """
            UPDATE redemptions
            SET user_id = ?, site_id = ?, amount = ?, fees = ?, redemption_date = ?,
                redemption_time = ?, redemption_entry_time_zone = ?, redemption_method_id = ?, is_free_sc = ?,
                receipt_date = ?, processed = ?, more_remaining = ?,
                notes = ?, status = ?, canceled_at = ?, cancel_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                redemption.user_id,
                redemption.site_id,
                str(redemption.amount),
                str(redemption.fees),
                utc_date,
                utc_time,
                entry_tz,
                redemption.redemption_method_id,
                1 if redemption.is_free_sc else 0,
                redemption.receipt_date.isoformat() if redemption.receipt_date else None,
                1 if redemption.processed else 0,
                1 if redemption.more_remaining else 0,
                redemption.notes,
                getattr(redemption, 'status', 'PENDING') or 'PENDING',
                getattr(redemption, 'canceled_at', None),
                getattr(redemption, 'cancel_reason', None),
                redemption.id,
            ),
        )

    def get_deletion_impact(self, redemption_id: int) -> str:
        """
        Check if deleting a redemption would affect FIFO allocations or game sessions.

        This method replaces direct UI cursor access to check deletion impact.

        Args:
            redemption_id: ID of redemption to check

        Returns:
            Formatted impact message string, or empty string if no impact
        """
        if not self.db:
            return ""

        try:
            cursor = self.db._connection.cursor()

            # Check FIFO allocations (redemption_allocations)
            cursor.execute(
                """
                SELECT COUNT(*) as count,
                       COALESCE(SUM(CAST(allocated_amount AS REAL)), 0) as total
                FROM redemption_allocations
                WHERE redemption_id = ?
                """,
                (redemption_id,),
            )
            alloc_result = cursor.fetchone()
            alloc_count = alloc_result["count"] if alloc_result else 0
            alloc_total = Decimal(str(alloc_result["total"] or 0)) if alloc_result else Decimal("0")

            # Check affected game sessions
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM game_sessions gs
                WHERE EXISTS (
                    SELECT 1
                    FROM redemption_allocations ra
                    JOIN purchases p ON ra.purchase_id = p.id
                    WHERE ra.redemption_id = ?
                      AND p.user_id = gs.user_id AND p.site_id = gs.site_id
                      AND gs.session_date >= p.purchase_date
                      AND gs.end_date IS NOT NULL
                )
                """,
                (redemption_id,),
            )
            session_result = cursor.fetchone()
            session_count = session_result["count"] if session_result else 0

            if alloc_count > 0 or session_count > 0:
                msg = f"This redemption has {alloc_count} FIFO allocation(s) totaling ${float(alloc_total):,.2f} SC.\n"
                if session_count > 0:
                    msg += f"{session_count} closed game session(s) may be affected.\n"
                msg += "Deleting will recalculate all affected sessions."
                return msg

            return ""
        except Exception as e:
            print(f"Error checking redemption deletion impact: {e}")
            return ""
