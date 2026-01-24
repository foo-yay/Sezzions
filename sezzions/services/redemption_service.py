"""
Redemption service - Business logic for Redemption operations
"""
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import date
from models.redemption import Redemption
from repositories.redemption_repository import RedemptionRepository
from services.fifo_service import FIFOService


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
            receipt_date=receipt_date,
            processed=processed,
            more_remaining=more_remaining,
            notes=notes,
            fees=fees
        )
        
        # Apply FIFO if requested
        if apply_fifo:
            cost_basis, taxable_profit, allocations = self.fifo_service.calculate_cost_basis(
                user_id,
                site_id,
                amount,
                redemption_date,
                redemption_time or "23:59:59",
            )

            redemption.cost_basis = cost_basis
            redemption.taxable_profit = taxable_profit
            redemption._has_fifo_allocation = True
            
            # Save redemption first (without FIFO results)
            redemption = self.redemption_repo.create(redemption)
            
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
        else:
            # Save without FIFO
            redemption = self.redemption_repo.create(redemption)
        
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
        
        return self.redemption_repo.update(redemption)
    
    def delete_redemption(self, redemption_id: int) -> None:
        """
        Delete redemption and reverse FIFO allocation.
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")
        
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
