"""
Purchase service - Business logic for Purchase operations
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date
from models.purchase import Purchase
from repositories.purchase_repository import PurchaseRepository


class PurchaseService:
    """Business logic for Purchase operations"""
    
    def __init__(self, purchase_repo: PurchaseRepository):
        self.purchase_repo = purchase_repo
    
    def create_purchase(
        self,
        user_id: int,
        site_id: int,
        amount: Decimal,
        purchase_date: date,
        sc_received: Decimal = Decimal("0.00"),
        starting_sc_balance: Decimal = Decimal("0.00"),
        cashback_earned: Decimal = Decimal("0.00"),
        card_id: Optional[int] = None,
        purchase_time: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Purchase:
        """Create new purchase with validation"""
        # Create purchase model (validates in __post_init__)
        purchase = Purchase(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            sc_received=sc_received,
            starting_sc_balance=starting_sc_balance,
            cashback_earned=cashback_earned,
            purchase_date=purchase_date,
            card_id=card_id,
            purchase_time=purchase_time,
            notes=notes
        )
        
        # Save to database
        return self.purchase_repo.create(purchase)
    
    def update_purchase(self, purchase_id: int, force_site_user_change: bool = False, **kwargs) -> Purchase:
        """Update purchase with business rules validation.

        Legacy parity notes:
        - If a purchase has been consumed, amount and purchase_date remain protected.
        - Site/user changes require explicit force (downstream rebuild will clear/recompute allocations).
        """
        purchase = self.purchase_repo.get_by_id(purchase_id)
        if not purchase:
            raise ValueError(f"Purchase {purchase_id} not found")
        
        # Check if purchase has been consumed
        if purchase.consumed_amount > 0:
            # Always protect amount/date when consumed
            for field in ("amount", "purchase_date"):
                if field in kwargs and getattr(purchase, field) != kwargs[field]:
                    raise ValueError(
                        f"Cannot change {field} on a purchase that has been consumed. "
                        f"Consumed: ${purchase.consumed_amount}"
                    )

            # Site/user changes require explicit force
            for field in ("user_id", "site_id"):
                if field in kwargs and getattr(purchase, field) != kwargs[field] and not force_site_user_change:
                    raise ValueError(
                        f"Cannot change {field} on a consumed purchase unless forced. "
                        f"Consumed: ${purchase.consumed_amount}"
                    )
        
        # Update allowed fields
        for key, value in kwargs.items():
            if hasattr(purchase, key):
                setattr(purchase, key, value)
        
        # Validate (will raise if invalid)
        purchase.__post_init__()
        
        return self.purchase_repo.update(purchase)
    
    def delete_purchase(self, purchase_id: int) -> None:
        """Delete purchase with validation"""
        purchase = self.purchase_repo.get_by_id(purchase_id)
        if not purchase:
            raise ValueError(f"Purchase {purchase_id} not found")
        
        # Prevent deletion if consumed
        if purchase.consumed_amount > 0:
            raise ValueError(
                f"Cannot delete purchase that has been consumed. "
                f"Consumed: ${purchase.consumed_amount}"
            )
        
        self.purchase_repo.delete(purchase_id)
    
    def get_purchase(self, purchase_id: int) -> Optional[Purchase]:
        """Get purchase by ID"""
        return self.purchase_repo.get_by_id(purchase_id)
    
    def list_user_purchases(self, user_id: int) -> List[Purchase]:
        """Get all purchases for a user"""
        return self.purchase_repo.get_by_user(user_id)
    
    def list_site_purchases(self, site_id: int) -> List[Purchase]:
        """Get all purchases for a site"""
        return self.purchase_repo.get_by_site(site_id)
    
    def list_purchases(
        self, 
        user_id: Optional[int] = None, 
        site_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Purchase]:
        """Get purchases with optional filters"""
        # For now, use get_all with date filters - could optimize later
        all_purchases = self.purchase_repo.get_all(start_date=start_date, end_date=end_date)
        
        # Apply user/site filters in memory
        if user_id:
            all_purchases = [p for p in all_purchases if p.user_id == user_id]
        if site_id:
            all_purchases = [p for p in all_purchases if p.site_id == site_id]
        
        return all_purchases
    
    def get_available_for_allocation(self, user_id: int, site_id: int) -> List[Purchase]:
        """Get purchases available for FIFO allocation"""
        return self.purchase_repo.get_available_for_fifo(user_id, site_id)
