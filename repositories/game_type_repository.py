"""
GameType repository - Data access for GameType entity
"""
from typing import Optional, List
from models.game_type import GameType


class GameTypeRepository:
    """Repository for GameType entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, type_id: int) -> Optional[GameType]:
        """Get game type by ID"""
        query = "SELECT * FROM game_types WHERE id = ?"
        row = self.db.fetch_one(query, (type_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[GameType]:
        """Get all game types"""
        query = "SELECT * FROM game_types ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_active(self) -> List[GameType]:
        """Get only active game types"""
        query = "SELECT * FROM game_types WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def create(self, game_type: GameType) -> GameType:
        """Create new game type"""
        query = """
            INSERT INTO game_types (name, is_active, notes)
            VALUES (?, ?, ?)
        """
        type_id = self.db.execute(query, (
            game_type.name,
            1 if game_type.is_active else 0,
            game_type.notes
        ))
        game_type.id = type_id
        return game_type
    
    def update(self, game_type: GameType) -> GameType:
        """Update existing game type"""
        if not game_type.id:
            raise ValueError("Cannot update game type without ID")
        
        query = """
            UPDATE game_types
            SET name = ?, is_active = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            game_type.name,
            1 if game_type.is_active else 0,
            game_type.notes,
            game_type.id
        ))
        return game_type
    
    def delete(self, type_id: int) -> None:
        """Delete game type (hard delete)"""
        query = "DELETE FROM game_types WHERE id = ?"
        self.db.execute(query, (type_id,))
    
    def _row_to_model(self, row: dict) -> GameType:
        """Convert database row to GameType model"""
        return GameType(
            id=row['id'],
            name=row['name'],
            is_active=bool(row['is_active']),
            notes=row.get('notes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
