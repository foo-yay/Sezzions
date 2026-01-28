"""
RedemptionMethod service - Business logic for RedemptionMethod operations
"""
from typing import List, Optional
from models.redemption_method import RedemptionMethod
from repositories.redemption_method_repository import RedemptionMethodRepository


class RedemptionMethodService:
    """Business logic for RedemptionMethod operations"""
    
    def __init__(self, method_repo: RedemptionMethodRepository):
        self.method_repo = method_repo
    
    def create_method(
        self,
        name: str,
        method_type: Optional[str] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> RedemptionMethod:
        """Create new redemption method with validation"""
        # Create method model (validates in __post_init__)
        method = RedemptionMethod(
            name=name,
            method_type=method_type,
            user_id=user_id,
            notes=notes
        )
        
        # Save to database
        return self.method_repo.create(method)
    
    def update_method(self, method_id: int, **kwargs) -> RedemptionMethod:
        """Update redemption method with validation"""
        method = self.method_repo.get_by_id(method_id)
        if not method:
            raise ValueError(f"Redemption method {method_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(method, key):
                setattr(method, key, value)
        
        # Validate (will raise if invalid)
        method.__post_init__()
        
        return self.method_repo.update(method)
    
    def deactivate_method(self, method_id: int) -> RedemptionMethod:
        """Deactivate redemption method (soft delete)"""
        return self.update_method(method_id, is_active=False)
    
    def activate_method(self, method_id: int) -> RedemptionMethod:
        """Activate redemption method"""
        return self.update_method(method_id, is_active=True)
    
    def delete_method(self, method_id: int) -> None:
        """Hard delete redemption method (use with caution - prefer deactivate_method)"""
        method = self.method_repo.get_by_id(method_id)
        if not method:
            raise ValueError(f"Redemption method {method_id} not found")
        
        # Note: Cascade delete behavior is handled at database level
        # via foreign key constraints
        self.method_repo.delete(method_id)
    
    def list_active_methods(self) -> List[RedemptionMethod]:
        """Get all active redemption methods"""
        return self.method_repo.get_active()
    
    def list_all_methods(self) -> List[RedemptionMethod]:
        """Get all redemption methods"""
        return self.method_repo.get_all()
    
    def get_method(self, method_id: int) -> Optional[RedemptionMethod]:
        """Get redemption method by ID"""
        return self.method_repo.get_by_id(method_id)
