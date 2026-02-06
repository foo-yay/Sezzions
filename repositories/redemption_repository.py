"""
Redemption repository - Data access for Redemption entity
"""
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from models.redemption import Redemption


class RedemptionRepository:
    """Repository for Redemption entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, redemption_id: int) -> Optional[Redemption]:
        """Get redemption by ID"""
        query = """
            SELECT r.*,
                   EXISTS(
                       SELECT 1 FROM redemption_allocations ra
                       WHERE ra.redemption_id = r.id
                   ) AS has_fifo_allocation
            FROM redemptions r
            WHERE r.id = ?
        """
        row = self.db.fetch_one(query, (redemption_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Redemption]:
        """Get all redemptions with related names and optional date filters"""
        query = """
                 SELECT r.*, 
                     u.name as user_name,
                     s.name as site_name,
                     rm.name as method_name,
                     rm.method_type as method_type,
                     (SELECT COALESCE(SUM(ra.allocated_amount), 0)
                      FROM redemption_allocations ra
                      WHERE ra.redemption_id = r.id) AS allocated_basis,
                     (SELECT COALESCE(SUM(rt.cost_basis), 0)
                      FROM realized_transactions rt
                      WHERE rt.redemption_id = r.id) AS realized_cost_basis,
                     EXISTS(
                         SELECT 1 FROM redemption_allocations ra
                         WHERE ra.redemption_id = r.id
                     ) AS has_fifo_allocation
            FROM redemptions r
            LEFT JOIN users u ON r.user_id = u.id
            LEFT JOIN sites s ON r.site_id = s.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND r.redemption_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND r.redemption_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY r.redemption_date DESC, r.redemption_time DESC"
        
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user(self, user_id: int) -> List[Redemption]:
        """Get all redemptions for a user"""
        query = """
            SELECT r.*, 
                   EXISTS(
                       SELECT 1 FROM redemption_allocations ra
                       WHERE ra.redemption_id = r.id
                   ) AS has_fifo_allocation
            FROM redemptions r
            WHERE r.user_id = ? 
            ORDER BY redemption_date DESC, redemption_time DESC
        """
        rows = self.db.fetch_all(query, (user_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_site(self, site_id: int) -> List[Redemption]:
        """Get all redemptions for a site"""
        query = """
            SELECT r.*, 
                   EXISTS(
                       SELECT 1 FROM redemption_allocations ra
                       WHERE ra.redemption_id = r.id
                   ) AS has_fifo_allocation
            FROM redemptions r
            WHERE r.site_id = ? 
            ORDER BY redemption_date DESC, redemption_time DESC
        """
        rows = self.db.fetch_all(query, (site_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user_and_site(self, user_id: int, site_id: int) -> List[Redemption]:
        """Get redemptions for a specific user and site"""
        query = """
            SELECT r.*, 
                   EXISTS(
                       SELECT 1 FROM redemption_allocations ra
                       WHERE ra.redemption_id = r.id
                   ) AS has_fifo_allocation
            FROM redemptions r
            WHERE r.user_id = ? AND r.site_id = ? 
            ORDER BY redemption_date DESC, redemption_time DESC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def create(self, redemption: Redemption) -> Redemption:
        """Create new redemption"""
        query = """
            INSERT INTO redemptions 
            (user_id, site_id, amount, fees, redemption_date, redemption_time, 
             redemption_method_id, is_free_sc, receipt_date, processed, more_remaining, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        redemption_id = self.db.execute(query, (
            redemption.user_id,
            redemption.site_id,
            str(redemption.amount),
            str(redemption.fees),
            redemption.redemption_date.isoformat(),
            redemption.redemption_time,
            redemption.redemption_method_id,
            1 if redemption.is_free_sc else 0,
            redemption.receipt_date.isoformat() if redemption.receipt_date else None,
            1 if redemption.processed else 0,
            1 if redemption.more_remaining else 0,
            redemption.notes
        ))
        redemption.id = redemption_id
        return redemption
    
    def update(self, redemption: Redemption) -> Redemption:
        """Update existing redemption"""
        if not redemption.id:
            raise ValueError("Cannot update redemption without ID")
        
        query = """
            UPDATE redemptions
            SET user_id = ?, site_id = ?, amount = ?, fees = ?, redemption_date = ?, 
                redemption_time = ?, redemption_method_id = ?, is_free_sc = ?,
                receipt_date = ?, processed = ?, more_remaining = ?,
                notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            redemption.user_id,
            redemption.site_id,
            str(redemption.amount),
            str(redemption.fees),
            redemption.redemption_date.isoformat(),
            redemption.redemption_time,
            redemption.redemption_method_id,
            1 if redemption.is_free_sc else 0,
            redemption.receipt_date.isoformat() if redemption.receipt_date else None,
            1 if redemption.processed else 0,
            1 if redemption.more_remaining else 0,
            redemption.notes,
            redemption.id
        ))
        return redemption
    
    def delete(self, redemption_id: int) -> None:
        """Delete redemption (hard delete)"""
        query = "DELETE FROM redemptions WHERE id = ?"
        self.db.execute(query, (redemption_id,))
    
    def _row_to_model(self, row: dict) -> Redemption:
        """Convert database row to Redemption model"""
        # Parse date
        redemption_date = row['redemption_date']
        if isinstance(redemption_date, str):
            redemption_date = datetime.strptime(redemption_date, "%Y-%m-%d").date()
        
        redemption = Redemption(
            id=row['id'],
            user_id=row['user_id'],
            site_id=row['site_id'],
            amount=Decimal(str(row['amount'])),
            fees=Decimal(str(row['fees'])) if 'fees' in row.keys() and row['fees'] is not None else Decimal("0.00"),
            redemption_date=redemption_date,
            cost_basis=Decimal(str(row['cost_basis'])) if 'cost_basis' in row.keys() and row['cost_basis'] is not None else None,
            taxable_profit=Decimal(str(row['taxable_profit'])) if 'taxable_profit' in row.keys() and row['taxable_profit'] is not None else None,
            redemption_time=row['redemption_time'] if 'redemption_time' in row.keys() else None,
            redemption_method_id=row['redemption_method_id'] if 'redemption_method_id' in row.keys() else None,
            receipt_date=row['receipt_date'] if 'receipt_date' in row.keys() else None,
            processed=bool(row['processed']) if 'processed' in row.keys() else False,
            more_remaining=bool(row['more_remaining']) if 'more_remaining' in row.keys() else False,
            is_free_sc=bool(row['is_free_sc']) if 'is_free_sc' in row.keys() else False,
            notes=row['notes'] if 'notes' in row.keys() else None,
            created_at=row['created_at'] if 'created_at' in row.keys() else None,
            updated_at=row['updated_at'] if 'updated_at' in row.keys() else None
        )
        
        # Add optional joined fields
        if 'user_name' in row.keys():
            redemption.user_name = row['user_name']
        if 'site_name' in row.keys():
            redemption.site_name = row['site_name']
        if 'method_name' in row.keys():
            redemption.method_name = row['method_name']
        if 'method_type' in row.keys():
            redemption.method_type = row['method_type']

        if 'allocated_basis' in row.keys():
            redemption.allocated_basis = Decimal(str(row['allocated_basis']))
        if 'realized_cost_basis' in row.keys():
            redemption.realized_cost_basis = Decimal(str(row['realized_cost_basis']))

        if 'has_fifo_allocation' in row.keys():
            redemption._has_fifo_allocation = bool(row['has_fifo_allocation'])
        
        return redemption
