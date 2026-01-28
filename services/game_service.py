"""
Game service - Business logic for Game operations
"""
from typing import List, Optional
from models.game import Game
from repositories.game_repository import GameRepository


class GameService:
    """Business logic for Game operations"""
    
    def __init__(self, game_repo: GameRepository):
        self.game_repo = game_repo
    
    def create_game(
        self,
        name: str,
        game_type_id: int,
        rtp: Optional[float] = None,
        notes: Optional[str] = None
    ) -> Game:
        """Create new game with validation"""
        # Create game model (validates in __post_init__)
        game = Game(
            name=name,
            game_type_id=game_type_id,
            rtp=rtp,
            notes=notes
        )
        
        # Save to database
        return self.game_repo.create(game)
    
    def update_game(self, game_id: int, **kwargs) -> Game:
        """Update game with validation"""
        game = self.game_repo.get_by_id(game_id)
        if not game:
            raise ValueError(f"Game {game_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(game, key):
                setattr(game, key, value)
        
        # Validate (will raise if invalid)
        game.__post_init__()
        
        return self.game_repo.update(game)
    
    def deactivate_game(self, game_id: int) -> Game:
        """Deactivate game (soft delete)"""
        return self.update_game(game_id, is_active=False)
    
    def activate_game(self, game_id: int) -> Game:
        """Activate game"""
        return self.update_game(game_id, is_active=True)
    
    def delete_game(self, game_id: int) -> None:
        """Hard delete game (cascades to game_rtp_aggregates)"""
        game = self.game_repo.get_by_id(game_id)
        if not game:
            raise ValueError(f"Game {game_id} not found")
        
        # Note: Will cascade delete to game_rtp_aggregates via ON DELETE CASCADE
        # Game sessions will prevent deletion via foreign key constraint if any exist
        try:
            self.game_repo.delete(game_id)
        except Exception as e:
            if "FOREIGN KEY constraint failed" in str(e):
                raise ValueError(
                    f"Cannot delete game '{game.name}' because game sessions still reference it. "
                    f"Consider deactivating the game instead of deleting."
                ) from e
            raise
    
    def list_active_games(self, game_type_id: Optional[int] = None) -> List[Game]:
        """Get active games, optionally filtered by type"""
        if game_type_id:
            return self.game_repo.get_active_by_type(game_type_id)
        return self.game_repo.get_active()
    
    def list_all_games(self, game_type_id: Optional[int] = None) -> List[Game]:
        """Get all games, optionally filtered by type"""
        if game_type_id:
            return self.game_repo.get_by_type(game_type_id)
        return self.game_repo.get_all()
    
    def get_game(self, game_id: int) -> Optional[Game]:
        """Get game by ID"""
        return self.game_repo.get_by_id(game_id)
