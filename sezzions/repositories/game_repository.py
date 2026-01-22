"""
Game repository - Data access for Game entity
"""
from typing import Optional, List
from models.game import Game


class GameRepository:
    """Repository for Game entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, game_id: int) -> Optional[Game]:
        """Get game by ID"""
        query = "SELECT * FROM games WHERE id = ?"
        row = self.db.fetch_one(query, (game_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[Game]:
        """Get all games"""
        query = "SELECT * FROM games ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_by_type(self, game_type_id: int) -> List[Game]:
        """Get all games for a game type"""
        query = "SELECT * FROM games WHERE game_type_id = ? ORDER BY name"
        rows = self.db.fetch_all(query, (game_type_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_active(self) -> List[Game]:
        """Get only active games"""
        query = "SELECT * FROM games WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_active_by_type(self, game_type_id: int) -> List[Game]:
        """Get active games for a game type"""
        query = "SELECT * FROM games WHERE game_type_id = ? AND is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query, (game_type_id,))
        return [self._row_to_model(row) for row in rows]
    
    def create(self, game: Game) -> Game:
        """Create new game"""
        query = """
            INSERT INTO games (name, game_type_id, rtp, is_active, notes)
            VALUES (?, ?, ?, ?, ?)
        """
        game_id = self.db.execute(query, (
            game.name,
            game.game_type_id,
            game.rtp,
            1 if game.is_active else 0,
            game.notes
        ))
        game.id = game_id
        return game
    
    def update(self, game: Game) -> Game:
        """Update existing game"""
        if not game.id:
            raise ValueError("Cannot update game without ID")
        
        query = """
            UPDATE games
            SET name = ?, game_type_id = ?, rtp = ?, is_active = ?, 
                notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            game.name,
            game.game_type_id,
            game.rtp,
            1 if game.is_active else 0,
            game.notes,
            game.id
        ))
        return game
    
    def delete(self, game_id: int) -> None:
        """Delete game (hard delete)"""
        query = "DELETE FROM games WHERE id = ?"
        self.db.execute(query, (game_id,))
    
    def _row_to_model(self, row: dict) -> Game:
        """Convert database row to Game model"""
        return Game(
            id=row['id'],
            name=row['name'],
            game_type_id=row['game_type_id'],
            rtp=float(row['rtp']) if row.get('rtp') is not None else None,
            is_active=bool(row['is_active']),
            notes=row.get('notes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
