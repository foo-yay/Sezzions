"""
Adjustment repository - Data access for Adjustment entity
"""
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from models.adjustment import Adjustment, AdjustmentType


class AdjustmentRepository:
    """Repository for Adjustment entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, adjustment_id: int) -> Optional[Adjustment]:
        """Get adjustment by ID"""
        query = "SELECT * FROM account_adjustments WHERE id = ?"
        row = self.db.fetch_one(query, (adjustment_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(
        self,
        user_id: Optional[int] = None,
        site_id: Optional[int] = None,
        adjustment_type: Optional[AdjustmentType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False
    ) -> List[Adjustment]:
        """Get all adjustments with optional filters"""
        query = """
            SELECT a.*, 
                   u.name as user_name,
                   s.name as site_name
            FROM account_adjustments a
            LEFT JOIN users u ON a.user_id = u.id
            LEFT JOIN sites s ON a.site_id = s.id
            WHERE 1=1
        """
        params = []
        
        if not include_deleted:
            query += " AND a.deleted_at IS NULL"
        
        if user_id:
            query += " AND a.user_id = ?"
            params.append(user_id)
        
        if site_id:
            query += " AND a.site_id = ?"
            params.append(site_id)
        
        if adjustment_type:
            query += " AND a.type = ?"
            params.append(adjustment_type.value)
        
        if start_date:
            query += " AND a.effective_date >= ?"
            params.append(start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date)
        
        if end_date:
            query += " AND a.effective_date <= ?"
            params.append(end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date)
        
        query += " ORDER BY a.effective_date DESC, a.effective_time DESC"
        
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user_and_site(
        self,
        user_id: int,
        site_id: int,
        include_deleted: bool = False
    ) -> List[Adjustment]:
        """Get adjustments for a specific user and site"""
        query = """
            SELECT * FROM account_adjustments 
            WHERE user_id = ? AND site_id = ?
        """
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        
        query += " ORDER BY effective_date ASC, effective_time ASC"
        
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def get_active_checkpoints_before(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "23:59:59"
    ) -> List[Adjustment]:
        """Get active balance checkpoint adjustments before a cutoff datetime"""
        query = """
            SELECT * FROM account_adjustments 
            WHERE user_id = ? 
            AND site_id = ?
            AND type = ?
            AND deleted_at IS NULL
            AND (
                effective_date < ?
                OR (effective_date = ? AND effective_time <= ?)
            )
            ORDER BY effective_date DESC, effective_time DESC
        """
        rows = self.db.fetch_all(
            query,
            (
                user_id,
                site_id,
                AdjustmentType.BALANCE_CHECKPOINT_CORRECTION.value,
                cutoff_date.isoformat() if hasattr(cutoff_date, 'isoformat') else cutoff_date,
                cutoff_date.isoformat() if hasattr(cutoff_date, 'isoformat') else cutoff_date,
                cutoff_time
            )
        )
        return [self._row_to_model(row) for row in rows]
    
    def get_active_basis_adjustments(
        self,
        user_id: int,
        site_id: int
    ) -> List[Adjustment]:
        """Get all active basis adjustments for FIFO pipeline"""
        query = """
            SELECT * FROM account_adjustments 
            WHERE user_id = ? 
            AND site_id = ?
            AND type = ?
            AND deleted_at IS NULL
            ORDER BY effective_date ASC, effective_time ASC
        """
        rows = self.db.fetch_all(
            query,
            (user_id, site_id, AdjustmentType.BASIS_USD_CORRECTION.value)
        )
        return [self._row_to_model(row) for row in rows]
    
    def create(self, adjustment: Adjustment) -> Adjustment:
        """Create a new adjustment"""
        query = """
            INSERT INTO account_adjustments (
                user_id, site_id, effective_date, effective_time, type,
                delta_basis_usd, checkpoint_total_sc, checkpoint_redeemable_sc,
                reason, notes, related_table, related_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            adjustment.user_id,
            adjustment.site_id,
            adjustment.effective_date.isoformat() if hasattr(adjustment.effective_date, 'isoformat') else adjustment.effective_date,
            adjustment.effective_time or "00:00:00",
            adjustment.type.value if isinstance(adjustment.type, AdjustmentType) else adjustment.type,
            str(adjustment.delta_basis_usd),
            str(adjustment.checkpoint_total_sc),
            str(adjustment.checkpoint_redeemable_sc),
            adjustment.reason,
            adjustment.notes,
            adjustment.related_table,
            adjustment.related_id
        )
        
        adjustment.id = self.db.execute(query, params)
        return adjustment
    
    def update(self, adjustment: Adjustment) -> bool:
        """Update an existing adjustment (limited fields)"""
        if not adjustment.id:
            raise ValueError("Adjustment ID is required for update")
        
        query = """
            UPDATE account_adjustments 
            SET notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        params = (
            adjustment.notes,
            adjustment.id
        )
        
        self.db.execute(query, params)
        return True
    
    def soft_delete(self, adjustment_id: int, reason: str) -> bool:
        """Soft delete an adjustment"""
        query = """
            UPDATE account_adjustments 
            SET deleted_at = CURRENT_TIMESTAMP,
                deleted_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        self.db.execute(query, (reason, adjustment_id))
        return True
    
    def restore(self, adjustment_id: int) -> bool:
        """Restore a soft-deleted adjustment"""
        query = """
            UPDATE account_adjustments 
            SET deleted_at = NULL,
                deleted_reason = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NOT NULL
        """
        self.db.execute(query, (adjustment_id,))
        return True
    
    def _row_to_model(self, row) -> Optional[Adjustment]:
        """Convert database row to Adjustment model"""
        if not row:
            return None
        
        # Parse datetime fields
        created_at = None
        if row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'])
            except (ValueError, TypeError):
                pass
        
        updated_at = None
        if row['updated_at']:
            try:
                updated_at = datetime.fromisoformat(row['updated_at'])
            except (ValueError, TypeError):
                pass
        
        deleted_at = None
        if row['deleted_at']:
            try:
                deleted_at = datetime.fromisoformat(row['deleted_at'])
            except (ValueError, TypeError):
                pass
        
        # Parse date
        effective_date = row['effective_date']
        if isinstance(effective_date, str):
            effective_date = date.fromisoformat(effective_date)
        
        return Adjustment(
            id=row['id'],
            user_id=row['user_id'],
            site_id=row['site_id'],
            effective_date=effective_date,
            effective_time=row['effective_time'] or "00:00:00",
            type=AdjustmentType(row['type']),
            delta_basis_usd=Decimal(row['delta_basis_usd']),
            checkpoint_total_sc=Decimal(row['checkpoint_total_sc']),
            checkpoint_redeemable_sc=Decimal(row['checkpoint_redeemable_sc']),
            reason=row['reason'],
            notes=row['notes'],
            related_table=row['related_table'],
            related_id=row['related_id'],
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            deleted_reason=row['deleted_reason']
        )
