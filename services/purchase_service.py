"""
Purchase service - Business logic for Purchase operations
"""
from dataclasses import asdict
from typing import List, Optional, TYPE_CHECKING
from decimal import Decimal
from datetime import date
from models.purchase import Purchase
from repositories.purchase_repository import PurchaseRepository
from repositories.card_repository import CardRepository

if TYPE_CHECKING:
    from services.audit_service import AuditService


class PurchaseService:
    """Business logic for Purchase operations"""
    
    def __init__(self, purchase_repo: PurchaseRepository, card_repo: Optional[CardRepository] = None, audit_service: Optional['AuditService'] = None):
        self.purchase_repo = purchase_repo
        self.card_repo = card_repo
        self.audit_service = audit_service
    
    def _calculate_cashback(self, amount: Decimal, card_id: Optional[int]) -> Decimal:
        """Calculate cashback based on card rate.
        
        Args:
            amount: Purchase amount
            card_id: Card ID (optional)
            
        Returns:
            Calculated cashback amount (0.00 if no card or no card_repo)
        """
        if not card_id or not self.card_repo:
            return Decimal("0.00")
        
        card = self.card_repo.get_by_id(card_id)
        if not card or card.cashback_rate <= 0:
            return Decimal("0.00")
        
        # Calculate: amount * (rate / 100)
        # e.g., $100 * (2.0 / 100) = $2.00
        cashback = amount * Decimal(str(card.cashback_rate)) / Decimal("100")
        return cashback.quantize(Decimal("0.01"))
    
    def create_purchase(
        self,
        user_id: int,
        site_id: int,
        amount: Decimal,
        purchase_date: date,
        sc_received: Decimal = Decimal("0.00"),
        starting_sc_balance: Decimal = Decimal("0.00"),
        cashback_earned: Optional[Decimal] = None,
        card_id: Optional[int] = None,
        purchase_time: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Purchase:
        """Create new purchase with validation.
        
        If cashback_earned is None and card_id is provided, automatically calculates
        cashback based on the card's cashback_rate.
        """
        # Auto-calculate cashback if not provided
        cashback_is_manual = False
        if cashback_earned is None:
            cashback_earned = self._calculate_cashback(amount, card_id)
            cashback_is_manual = False  # Auto-calculated
        else:
            cashback_is_manual = True  # User explicitly provided
        
        # Create purchase model (validates in __post_init__)
        purchase = Purchase(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            sc_received=sc_received,
            starting_sc_balance=starting_sc_balance,
            cashback_earned=cashback_earned,
            cashback_is_manual=cashback_is_manual,
            purchase_date=purchase_date,
            card_id=card_id,
            purchase_time=purchase_time,
            notes=notes
        )
        
        # Save to database (returns Purchase with ID set)
        purchase = self.purchase_repo.create(purchase)
        
        # Log to audit if available
        if self.audit_service:
            self.audit_service.log_create(
                table_name="purchases",
                record_id=purchase.id,
                new_data=asdict(purchase)
            )
        
        return purchase
    
    def update_purchase(self, purchase_id: int, force_site_user_change: bool = False, **kwargs) -> Purchase:
        """Update purchase with business rules validation.

        Legacy parity notes:
        - If a purchase has been consumed, amount and purchase_date remain protected.
        - Site/user changes require explicit force (downstream rebuild will clear/recompute allocations).
        """
        purchase = self.purchase_repo.get_by_id(purchase_id)
        if not purchase:
            raise ValueError(f"Purchase {purchase_id} not found")
        
        # Capture old state for audit (BEFORE any modifications)
        old_data = asdict(purchase)
        
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
        
        # Store old amount BEFORE updating (needed to adjust remaining_amount proportionally)
        old_amount = purchase.amount if "amount" in kwargs else None
        old_remaining = purchase.remaining_amount
        old_card_id = purchase.card_id
        
        # Update allowed fields
        for key, value in kwargs.items():
            if hasattr(purchase, key):
                setattr(purchase, key, value)
        
        # Special case: if amount is changed, adjust remaining_amount proportionally
        # to maintain the same consumed ratio
        if "amount" in kwargs and old_amount is not None:
            new_amount = purchase.amount  # Already updated by the loop above
            
            # Calculate what proportion was remaining
            if old_amount > 0:
                remaining_ratio = old_remaining / old_amount
            else:
                remaining_ratio = Decimal("1")
            
            # Apply the same ratio to the new amount
            purchase.remaining_amount = new_amount * remaining_ratio
        
        # Handle cashback recalculation logic:
        # 1. If user explicitly sets cashback_earned, mark as manual
        # 2. If amount or card changes AND cashback is not manual, auto-recalculate
        # 3. If cashback is manual, preserve it unless explicitly changed
        if "cashback_earned" in kwargs:
            # User explicitly changed cashback - mark as manual
            purchase.cashback_is_manual = True
        elif ("amount" in kwargs or "card_id" in kwargs) and not purchase.cashback_is_manual:
            # Amount or card changed, and cashback is auto-calculated - recalculate it
            purchase.cashback_earned = self._calculate_cashback(purchase.amount, purchase.card_id)
        
        # Validate (will raise if invalid)
        purchase.__post_init__()
        
        result = self.purchase_repo.update(purchase)
        
        # Log update to audit
        if self.audit_service:
            self.audit_service.log_update('purchases', purchase.id, old_data, asdict(result))
        
        return result
    
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
        
        # Capture old state for audit
        old_data = asdict(purchase)
        
        self.purchase_repo.delete(purchase_id)
        
        # Log deletion to audit
        if self.audit_service:
            self.audit_service.log_delete('purchases', purchase_id, old_data)
    
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
