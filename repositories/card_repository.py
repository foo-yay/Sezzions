"""
Card repository - Data access for Card entity
"""
from typing import Optional, List
from models.card import Card


class CardRepository:
    """Repository for Card entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, card_id: int) -> Optional[Card]:
        """Get card by ID with user name"""
        query = """
            SELECT c.*, u.name as user_name
            FROM cards c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.id = ?
        """
        row = self.db.fetch_one(query, (card_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[Card]:
        """Get all cards with user names"""
        query = """
            SELECT c.*, u.name as user_name
            FROM cards c
            LEFT JOIN users u ON c.user_id = u.id
            ORDER BY c.name
        """
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user(self, user_id: int) -> List[Card]:
        """Get all cards for a user"""
        query = "SELECT * FROM cards WHERE user_id = ? ORDER BY name"
        rows = self.db.fetch_all(query, (user_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_active_by_user(self, user_id: int) -> List[Card]:
        """Get active cards for a user"""
        query = "SELECT * FROM cards WHERE user_id = ? AND is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query, (user_id,))
        return [self._row_to_model(row) for row in rows]
    
    def create(self, card: Card) -> Card:
        """Create new card"""
        query = """
            INSERT INTO cards (name, user_id, last_four, cashback_rate, is_active, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        card_id = self.db.execute(query, (
            card.name,
            card.user_id,
            card.last_four,
            card.cashback_rate,
            1 if card.is_active else 0,
            card.notes
        ))
        card.id = card_id
        return card
    
    def update(self, card: Card) -> Card:
        """Update existing card"""
        if not card.id:
            raise ValueError("Cannot update card without ID")
        
        query = """
            UPDATE cards
            SET name = ?, user_id = ?, last_four = ?, cashback_rate = ?, 
                is_active = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            card.name,
            card.user_id,
            card.last_four,
            card.cashback_rate,
            1 if card.is_active else 0,
            card.notes,
            card.id
        ))
        return card
    
    def delete(self, card_id: int) -> None:
        """Delete card (hard delete)"""
        query = "DELETE FROM cards WHERE id = ?"
        self.db.execute(query, (card_id,))
    
    def _row_to_model(self, row: dict) -> Card:
        """Convert database row to Card model"""
        card = Card(
            id=row['id'],
            name=row['name'],
            user_id=row['user_id'],
            last_four=row.get('last_four'),
            cashback_rate=float(row['cashback_rate']) if row.get('cashback_rate') else 0.0,
            is_active=bool(row['is_active']),
            notes=row.get('notes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
        # Add user_name if present (from JOIN)
        if 'user_name' in row.keys():
            card.user_name = row['user_name']
        return card
