"""
GameType service - Business logic for GameType operations
"""
from typing import List, Optional
from models.game_type import GameType
from repositories.game_type_repository import GameTypeRepository


class GameTypeService:
    """Business logic for GameType operations"""
    
    def __init__(self, type_repo: GameTypeRepository):
        self.type_repo = type_repo
    
    def create_type(
        self,
        name: str,
        notes: Optional[str] = None
    ) -> GameType:
        """Create new game type with validation"""
        # Create type model (validates in __post_init__)
        game_type = GameType(
            name=name,
            notes=notes
        )
        
        # Save to database
        return self.type_repo.create(game_type)
    
    def update_type(self, type_id: int, **kwargs) -> GameType:
        """Update game type with validation"""
        game_type = self.type_repo.get_by_id(type_id)
        if not game_type:
            raise ValueError(f"Game type {type_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(game_type, key):
                setattr(game_type, key, value)
        
        # Validate (will raise if invalid)
        game_type.__post_init__()
        
        return self.type_repo.update(game_type)
    
    def deactivate_type(self, type_id: int) -> GameType:
        """Deactivate game type (soft delete)"""
        return self.update_type(type_id, is_active=False)
    
    def activate_type(self, type_id: int) -> GameType:
        """Activate game type"""
        return self.update_type(type_id, is_active=True)
    
    def list_active_types(self) -> List[GameType]:
        """Get all active game types"""
        return self.type_repo.get_active()
    
    def list_all_types(self) -> List[GameType]:
        """Get all game types"""
        return self.type_repo.get_all()
    
    def get_type(self, type_id: int) -> Optional[GameType]:
        """Get game type by ID"""
        return self.type_repo.get_by_id(type_id)
