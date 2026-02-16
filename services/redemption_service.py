"""
Redemption service - Business logic for Redemption operations
"""
import uuid
from dataclasses import asdict
from typing import List, Optional, Tuple, TYPE_CHECKING
from decimal import Decimal
from datetime import date
from models.redemption import Redemption
from tools.timezone_utils import get_entry_timezone_name
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
                # Get total remaining basis for this site/user as of redemption timestamp
                available_purchases = self.redemption_repo.db.fetch_one(
                    """
                    SELECT COALESCE(SUM(remaining_amount), 0) as total_remaining
                    FROM purchases
                    WHERE user_id = ? AND site_id = ? AND remaining_amount > 0
                      AND (purchase_date < ? OR 
                           (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') <= ?))
                    """,
                    (user_id, site_id, redemption_date, redemption_date, redemption_time or "23:59:59")
                )
                
                total_remaining = Decimal(str(available_purchases['total_remaining'])) if available_purchases else Decimal("0.00")
                
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
    
    def _delete_realized_transaction(self, redemption_id: int) -> None:
        """Delete realized_transaction record for a redemption"""
        if not self.db:
            return
        
        query = "DELETE FROM realized_transactions WHERE redemption_id = ?"
        self.db.execute(query, (redemption_id,))

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
