"""
Purchase repository - Data access for Purchase entity
"""
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from tools.timezone_utils import (
    get_accounting_timezone_name,
    get_configured_timezone_name,
    get_entry_timezone_name,
    local_date_range_to_utc_bounds,
    local_date_time_to_utc,
    utc_date_time_to_local,
)
from models.purchase import Purchase


class PurchaseRepository:
    """Repository for Purchase entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, purchase_id: int) -> Optional[Purchase]:
        """Get purchase by ID (excludes soft-deleted)"""
        query = "SELECT * FROM purchases WHERE id = ? AND deleted_at IS NULL"
        row = self.db.fetch_one(query, (purchase_id,))
        return self._row_to_model(row) if row else None

    def get_by_id_any(self, purchase_id: int) -> Optional[Purchase]:
        """Get purchase by ID including soft-deleted rows."""
        query = "SELECT * FROM purchases WHERE id = ?"
        row = self.db.fetch_one(query, (purchase_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Purchase]:
        """Get all purchases with related names, optionally filtered by date range (excludes soft-deleted)"""
        query = """
            SELECT p.*, 
                   u.name as user_name,
                   s.name as site_name,
                   c.name as card_name
            FROM purchases p
            LEFT JOIN users u ON p.user_id = u.id
            LEFT JOIN sites s ON p.site_id = s.id
            LEFT JOIN cards c ON p.card_id = c.id
            WHERE p.deleted_at IS NULL
        """
        params = []
        tz_name = get_accounting_timezone_name()
        
        if start_date:
            start_utc, end_utc = local_date_range_to_utc_bounds(start_date, start_date, tz_name)
            query += " AND (p.purchase_date > ? OR (p.purchase_date = ? AND COALESCE(p.purchase_time, '00:00:00') >= ?))"
            params.extend([start_utc[0], start_utc[0], start_utc[1]])
        
        if end_date:
            start_utc, end_utc = local_date_range_to_utc_bounds(end_date, end_date, tz_name)
            query += " AND (p.purchase_date < ? OR (p.purchase_date = ? AND COALESCE(p.purchase_time, '00:00:00') <= ?))"
            params.extend([end_utc[0], end_utc[0], end_utc[1]])
        
        query += " ORDER BY p.purchase_date DESC, p.purchase_time DESC"
        
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user(self, user_id: int) -> List[Purchase]:
        """Get all purchases for a user (excludes soft-deleted)"""
        query = """
            SELECT * FROM purchases 
            WHERE user_id = ? AND deleted_at IS NULL
            ORDER BY purchase_date DESC, purchase_time DESC
        """
        rows = self.db.fetch_all(query, (user_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_site(self, site_id: int) -> List[Purchase]:
        """Get all purchases for a site (excludes soft-deleted)"""
        query = """
            SELECT * FROM purchases 
            WHERE site_id = ? AND deleted_at IS NULL
            ORDER BY purchase_date DESC, purchase_time DESC
        """
        rows = self.db.fetch_all(query, (site_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user_and_site(self, user_id: int, site_id: int) -> List[Purchase]:
        """Get purchases for a specific user and site (excludes soft-deleted)"""
        query = """
            SELECT * FROM purchases 
            WHERE user_id = ? AND site_id = ? AND deleted_at IS NULL
            ORDER BY purchase_date DESC, purchase_time DESC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def get_available_for_fifo(self, user_id: int, site_id: int) -> List[Purchase]:
        """Get purchases with remaining balance for FIFO allocation (excludes soft-deleted)"""
        query = """
            SELECT * FROM purchases 
            WHERE user_id = ? AND site_id = ? 
              AND CAST(remaining_amount AS REAL) > 0
              AND deleted_at IS NULL
            ORDER BY purchase_date ASC, purchase_time ASC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]

    def get_available_for_fifo_as_of(
        self,
        user_id: int,
        site_id: int,
        redemption_date: str,
        redemption_time: Optional[str] = None,
        entry_time_zone: Optional[str] = None,
    ) -> List[Purchase]:
        """Get purchases with remaining balance up to a redemption timestamp (excludes soft-deleted)."""
        if not redemption_time:
            redemption_time = "23:59:59"

        tz_name = entry_time_zone or get_entry_timezone_name()
        redemption_date, redemption_time = local_date_time_to_utc(redemption_date, redemption_time, tz_name)

        query = """
            SELECT * FROM purchases
            WHERE user_id = ? AND site_id = ? 
              AND CAST(remaining_amount AS REAL) > 0
              AND deleted_at IS NULL
              AND (
                    purchase_date < ? OR
                    (purchase_date = ? AND COALESCE(purchase_time, '00:00:00') <= ?)
                  )
            ORDER BY purchase_date ASC, COALESCE(purchase_time, '00:00:00') ASC, id ASC
        """
        rows = self.db.fetch_all(
            query,
            (user_id, site_id, redemption_date, redemption_date, redemption_time),
        )
        return [self._row_to_model(row) for row in rows]
    
    def create(self, purchase: Purchase) -> Purchase:
        """Create new purchase"""
        entry_tz = purchase.purchase_entry_time_zone or get_entry_timezone_name()
        utc_date, utc_time = local_date_time_to_utc(
            purchase.purchase_date,
            purchase.purchase_time,
            entry_tz,
        )
        query = """
            INSERT INTO purchases 
            (user_id, site_id, amount, sc_received, starting_sc_balance, starting_redeemable_balance, cashback_earned,
             cashback_is_manual, purchase_date, purchase_time, purchase_entry_time_zone,
             card_id, remaining_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        purchase_id = self.db.execute(query, (
            purchase.user_id,
            purchase.site_id,
            str(purchase.amount),
            str(purchase.sc_received),
            str(purchase.starting_sc_balance),
            str(purchase.starting_redeemable_balance),
            str(purchase.cashback_earned),
            1 if purchase.cashback_is_manual else 0,
            utc_date,
            utc_time,
            entry_tz,
            purchase.card_id,
            str(purchase.remaining_amount),
            purchase.notes
        ))
        purchase.id = purchase_id
        purchase.purchase_entry_time_zone = entry_tz
        return purchase
    
    def update(self, purchase: Purchase) -> Purchase:
        """Update existing purchase"""
        if not purchase.id:
            raise ValueError("Cannot update purchase without ID")

        entry_tz = purchase.purchase_entry_time_zone or get_entry_timezone_name()
        utc_date, utc_time = local_date_time_to_utc(
            purchase.purchase_date,
            purchase.purchase_time,
            entry_tz,
        )
        
        query = """
            UPDATE purchases
            SET user_id = ?, site_id = ?, amount = ?, sc_received = ?, starting_sc_balance = ?,
                starting_redeemable_balance = ?, cashback_earned = ?, cashback_is_manual = ?, purchase_date = ?, purchase_time = ?,
                purchase_entry_time_zone = ?, card_id = ?, remaining_amount = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            purchase.user_id,
            purchase.site_id,
            str(purchase.amount),
            str(purchase.sc_received),
            str(purchase.starting_sc_balance),
            str(purchase.starting_redeemable_balance),
            str(purchase.cashback_earned),
            1 if purchase.cashback_is_manual else 0,
            utc_date,
            utc_time,
            entry_tz,
            purchase.card_id,
            str(purchase.remaining_amount),
            purchase.notes,
            purchase.id
        ))
        purchase.purchase_entry_time_zone = entry_tz
        return purchase
    
    def delete(self, purchase_id: int) -> None:
        """Soft delete purchase by setting deleted_at timestamp"""
        query = "UPDATE purchases SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?"
        self.db.execute(query, (purchase_id,))
    
    def restore(self, purchase_id: int) -> None:
        """Restore a soft-deleted purchase by clearing deleted_at"""
        query = "UPDATE purchases SET deleted_at = NULL WHERE id = ?"
        self.db.execute(query, (purchase_id,))
    
    def _row_to_model(self, row: dict) -> Purchase:
        """Convert database row to Purchase model"""
        # Parse date
        purchase_date = row['purchase_date']
        if isinstance(purchase_date, str):
            purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()

        entry_tz = row.get('purchase_entry_time_zone') or get_accounting_timezone_name()
        purchase_date, purchase_time = utc_date_time_to_local(
            purchase_date,
            row.get('purchase_time'),
            entry_tz,
        )
        
        purchase = Purchase(
            id=row['id'],
            user_id=row['user_id'],
            site_id=row['site_id'],
            amount=Decimal(str(row['amount'])),
            sc_received=Decimal(str(row.get('sc_received', '0.00'))),
            starting_sc_balance=Decimal(str(row.get('starting_sc_balance', '0.00'))),
            starting_redeemable_balance=Decimal(str(row.get('starting_redeemable_balance', '0.00'))),
            cashback_earned=Decimal(str(row.get('cashback_earned', '0.00'))),
            cashback_is_manual=bool(row.get('cashback_is_manual', 0)),
            purchase_date=purchase_date,
            purchase_time=purchase_time,
            purchase_entry_time_zone=row.get('purchase_entry_time_zone') or entry_tz,
            card_id=row.get('card_id'),
            remaining_amount=Decimal(str(row['remaining_amount'])),
            status=row.get('status'),  # 'active', 'dormant', or NULL
            notes=row.get('notes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
        
        # Add optional joined fields
        if 'user_name' in row.keys():
            purchase.user_name = row['user_name']
        if 'site_name' in row.keys():
            purchase.site_name = row['site_name']
        if 'card_name' in row.keys():
            purchase.card_name = row['card_name']
        
        return purchase
