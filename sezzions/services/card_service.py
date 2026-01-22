"""
Card service - Business logic for Card operations
"""
from typing import List, Optional
from models.card import Card
from repositories.card_repository import CardRepository


class CardService:
    """Business logic for Card operations"""
    
    def __init__(self, card_repo: CardRepository):
        self.card_repo = card_repo
    
    def create_card(
        self,
        name: str,
        user_id: int,
        last_four: Optional[str] = None,
        cashback_rate: float = 0.0,
        notes: Optional[str] = None
    ) -> Card:
        """Create new card with validation"""
        # Create card model (validates in __post_init__)
        card = Card(
            name=name,
            user_id=user_id,
            last_four=last_four,
            cashback_rate=cashback_rate,
            notes=notes
        )
        
        # Save to database
        return self.card_repo.create(card)
    
    def update_card(self, card_id: int, **kwargs) -> Card:
        """Update card with validation"""
        card = self.card_repo.get_by_id(card_id)
        if not card:
            raise ValueError(f"Card {card_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(card, key):
                setattr(card, key, value)
        
        # Validate (will raise if invalid)
        card.__post_init__()
        
        return self.card_repo.update(card)
    
    def deactivate_card(self, card_id: int) -> Card:
        """Deactivate card (soft delete)"""
        return self.update_card(card_id, is_active=False)
    
    def activate_card(self, card_id: int) -> Card:
        """Activate card"""
        return self.update_card(card_id, is_active=True)
    
    def list_user_cards(self, user_id: int, active_only: bool = True) -> List[Card]:
        """Get cards for a user"""
        if active_only:
            return self.card_repo.get_active_by_user(user_id)
        return self.card_repo.get_by_user(user_id)
    
    def list_all_cards(self, active_only: bool = False) -> List[Card]:
        """Get all cards"""
        cards = self.card_repo.get_all()
        if active_only:
            return [c for c in cards if c.is_active]
        return cards
    
    def get_card(self, card_id: int) -> Optional[Card]:
        """Get card by ID"""
        return self.card_repo.get_by_id(card_id)
