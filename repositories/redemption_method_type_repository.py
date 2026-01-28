"""
RedemptionMethodType repository - Data access for RedemptionMethodType entity
"""
from typing import Optional, List
from models.redemption_method_type import RedemptionMethodType


class RedemptionMethodTypeRepository:
    """Repository for RedemptionMethodType entity"""

    def __init__(self, db_manager):
        self.db = db_manager

    def get_by_id(self, type_id: int) -> Optional[RedemptionMethodType]:
        query = "SELECT * FROM redemption_method_types WHERE id = ?"
        row = self.db.fetch_one(query, (type_id,))
        return self._row_to_model(row) if row else None

    def get_all(self) -> List[RedemptionMethodType]:
        query = "SELECT * FROM redemption_method_types ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]

    def get_active(self) -> List[RedemptionMethodType]:
        query = "SELECT * FROM redemption_method_types WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]

    def create(self, method_type: RedemptionMethodType) -> RedemptionMethodType:
        query = """
            INSERT INTO redemption_method_types (name, is_active, notes)
            VALUES (?, ?, ?)
        """
        type_id = self.db.execute(query, (
            method_type.name,
            1 if method_type.is_active else 0,
            method_type.notes
        ))
        method_type.id = type_id
        return method_type

    def update(self, method_type: RedemptionMethodType) -> RedemptionMethodType:
        if not method_type.id:
            raise ValueError("Cannot update method type without ID")

        query = """
            UPDATE redemption_method_types
            SET name = ?, is_active = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            method_type.name,
            1 if method_type.is_active else 0,
            method_type.notes,
            method_type.id
        ))
        return method_type

    def delete(self, type_id: int) -> None:
        query = "DELETE FROM redemption_method_types WHERE id = ?"
        self.db.execute(query, (type_id,))

    def _row_to_model(self, row: dict) -> RedemptionMethodType:
        return RedemptionMethodType(
            id=row['id'],
            name=row['name'],
            is_active=bool(row['is_active']),
            notes=row['notes'] if 'notes' in row.keys() else None,
            created_at=row['created_at'] if 'created_at' in row.keys() else None,
            updated_at=row['updated_at'] if 'updated_at' in row.keys() else None
        )
