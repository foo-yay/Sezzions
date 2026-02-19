"""
FIFO Service - Cost basis calculation using First-In-First-Out
"""
from typing import List, Tuple
from decimal import Decimal
from models.purchase import Purchase
from models.redemption import Redemption
from repositories.purchase_repository import PurchaseRepository


class FIFOService:
    """Implements FIFO (First-In-First-Out) cost basis calculation"""
    
    def __init__(self, purchase_repo: PurchaseRepository):
        self.purchase_repo = purchase_repo
    
    def calculate_cost_basis(
        self, 
        user_id: int, 
        site_id: int, 
        redemption_amount: Decimal,
        redemption_date,
        redemption_time: str = "23:59:59",
        redemption_entry_time_zone: str | None = None,
    ) -> Tuple[Decimal, Decimal, List[Tuple[int, Decimal]]]:
        """
        Calculate cost basis and profit for a redemption using FIFO.
        
        Returns:
            Tuple of (cost_basis, taxable_profit, allocations)
            - cost_basis: Total cost basis consumed
            - taxable_profit: Profit (redemption_amount - cost_basis)
            - allocations: List of (purchase_id, amount_allocated) tuples
        
        Raises:
            ValueError: If insufficient purchases available
        """
        # Get available purchases in FIFO order (oldest first)
        # Only include purchases on or before the redemption timestamp
        available_purchases = self.purchase_repo.get_available_for_fifo_as_of(
            user_id,
            site_id,
            redemption_date,
            redemption_time,
            entry_time_zone=redemption_entry_time_zone,
        )
        
        # Allocate from purchases using FIFO
        # NOTE: It's OK if total_available < redemption_amount (that's profit!)
        # Cost basis = what we can allocate from purchases
        # Profit = redemption_amount - cost_basis
        remaining_to_allocate = redemption_amount
        cost_basis = Decimal("0.00")
        allocations = []
        
        for purchase in available_purchases:
            if remaining_to_allocate <= 0:
                break
            
            # Calculate how much to allocate from this purchase
            amount_to_allocate = min(remaining_to_allocate, purchase.remaining_amount)
            
            # Track allocation
            allocations.append((purchase.id, amount_to_allocate))
            
            # Cost basis is same as amount allocated (1:1 ratio)
            cost_basis += amount_to_allocate
            
            # Reduce remaining
            remaining_to_allocate -= amount_to_allocate
        
        # Calculate profit
        taxable_profit = redemption_amount - cost_basis
        
        return cost_basis, taxable_profit, allocations
    
    def apply_allocation(
        self, 
        allocations: List[Tuple[int, Decimal]]
    ) -> None:
        """
        Apply FIFO allocations by reducing purchase remaining_amount.
        
        Args:
            allocations: List of (purchase_id, amount_allocated) tuples
        """
        for purchase_id, amount_allocated in allocations:
            purchase = self.purchase_repo.get_by_id(purchase_id)
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            
            # Reduce remaining amount
            new_remaining = purchase.remaining_amount - amount_allocated
            if new_remaining < 0:
                raise ValueError(
                    f"Cannot allocate ${amount_allocated} from purchase {purchase_id}. "
                    f"Only ${purchase.remaining_amount} remaining."
                )
            
            purchase.remaining_amount = new_remaining
            self.purchase_repo.update(purchase)
    
    def reverse_allocation(
        self, 
        allocations: List[Tuple[int, Decimal]],
        strict: bool = True,
        include_deleted: bool = False,
    ) -> None:
        """
        Reverse FIFO allocations by restoring purchase remaining_amount.
        Used when deleting or editing redemptions.
        
        Args:
            allocations: List of (purchase_id, amount_allocated) tuples
            strict: If True, raise when purchase is missing. If False, skip missing rows.
            include_deleted: If True, lookup includes soft-deleted purchases.
        """
        for purchase_id, amount_allocated in allocations:
            if include_deleted and hasattr(self.purchase_repo, "get_by_id_any"):
                purchase = self.purchase_repo.get_by_id_any(purchase_id)
            else:
                purchase = self.purchase_repo.get_by_id(purchase_id)
            if not purchase:
                if strict:
                    raise ValueError(f"Purchase {purchase_id} not found")
                continue
            
            # Restore remaining amount
            new_remaining = purchase.remaining_amount + amount_allocated
            if new_remaining > purchase.amount:
                raise ValueError(
                    f"Cannot restore ${amount_allocated} to purchase {purchase_id}. "
                    f"Would exceed original amount ${purchase.amount}."
                )
            
            purchase.remaining_amount = new_remaining
            self.purchase_repo.update(purchase)
