"""
RedemptionMethodType service - Business logic for RedemptionMethodType operations
"""
from typing import List, Optional
from models.redemption_method_type import RedemptionMethodType
from repositories.redemption_method_type_repository import RedemptionMethodTypeRepository


class RedemptionMethodTypeService:
    """Business logic for RedemptionMethodType operations"""

    def __init__(self, type_repo: RedemptionMethodTypeRepository):
        self.type_repo = type_repo

    def create_type(self, name: str, notes: Optional[str] = None) -> RedemptionMethodType:
        method_type = RedemptionMethodType(name=name, notes=notes)
        return self.type_repo.create(method_type)

    def update_type(self, type_id: int, **kwargs) -> RedemptionMethodType:
        method_type = self.type_repo.get_by_id(type_id)
        if not method_type:
            raise ValueError(f"Method type {type_id} not found")

        for key, value in kwargs.items():
            if hasattr(method_type, key):
                setattr(method_type, key, value)

        method_type.__post_init__()
        return self.type_repo.update(method_type)

    def deactivate_type(self, type_id: int) -> RedemptionMethodType:
        return self.update_type(type_id, is_active=False)

    def activate_type(self, type_id: int) -> RedemptionMethodType:
        return self.update_type(type_id, is_active=True)

    def delete_type(self, type_id: int) -> None:
        """Hard delete redemption method type (use with caution - prefer deactivate_type)"""
        method_type = self.type_repo.get_by_id(type_id)
        if not method_type:
            raise ValueError(f"Redemption method type {type_id} not found")
        
        # Note: Cascade delete behavior is handled at database level
        # via foreign key constraints
        self.type_repo.delete(type_id)

    def list_active_types(self) -> List[RedemptionMethodType]:
        return self.type_repo.get_active()

    def list_all_types(self) -> List[RedemptionMethodType]:
        return self.type_repo.get_all()

    def get_type(self, type_id: int) -> Optional[RedemptionMethodType]:
        return self.type_repo.get_by_id(type_id)
