"""
RedemptionMethod repository - Data access for RedemptionMethod entity
"""
from typing import Optional, List
from models.redemption_method import RedemptionMethod


class RedemptionMethodRepository:
    """Repository for RedemptionMethod entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, method_id: int) -> Optional[RedemptionMethod]:
        """Get redemption method by ID"""
        query = "SELECT * FROM redemption_methods WHERE id = ?"
        row = self.db.fetch_one(query, (method_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[RedemptionMethod]:
        """Get all redemption methods"""
        query = "SELECT * FROM redemption_methods ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_active(self) -> List[RedemptionMethod]:
        """Get only active redemption methods"""
        query = "SELECT * FROM redemption_methods WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def create(self, method: RedemptionMethod) -> RedemptionMethod:
        """Create new redemption method"""
        query = """
            INSERT INTO redemption_methods (name, method_type, user_id, is_active, notes)
            VALUES (?, ?, ?, ?, ?)
        """
        method_id = self.db.execute(query, (
            method.name,
            method.method_type,
            method.user_id,
            1 if method.is_active else 0,
            method.notes
        ))
        method.id = method_id
        return method
    
    def update(self, method: RedemptionMethod) -> RedemptionMethod:
        """Update existing redemption method"""
        if not method.id:
            raise ValueError("Cannot update redemption method without ID")
        
        query = """
            UPDATE redemption_methods
            SET name = ?, method_type = ?, user_id = ?, is_active = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            method.name,
            method.method_type,
            method.user_id,
            1 if method.is_active else 0,
            method.notes,
            method.id
        ))
        return method
    
    def delete(self, method_id: int) -> None:
        """Delete redemption method (hard delete)"""
        query = "DELETE FROM redemption_methods WHERE id = ?"
        self.db.execute(query, (method_id,))
    
    def _row_to_model(self, row: dict) -> RedemptionMethod:
        """Convert database row to RedemptionMethod model"""
        return RedemptionMethod(
            id=row['id'],
            name=row['name'],
            method_type=row['method_type'] if 'method_type' in row.keys() else None,
            user_id=row['user_id'] if 'user_id' in row.keys() else None,
            is_active=bool(row['is_active']),
            notes=row['notes'] if 'notes' in row.keys() else None,
            created_at=row['created_at'] if 'created_at' in row.keys() else None,
            updated_at=row['updated_at'] if 'updated_at' in row.keys() else None
        )
