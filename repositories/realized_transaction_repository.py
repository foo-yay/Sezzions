"""
Repository for querying realized transactions (completed redemption cash flow)
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date

from models.realized_transaction import RealizedTransaction


class RealizedTransactionRepository:
    """Repository for querying realized transactions"""
    
    def __init__(self, db):
        self.db = db
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        site_ids: Optional[List[int]] = None,
        user_ids: Optional[List[int]] = None
    ) -> List[RealizedTransaction]:
        """
        Get all realized transactions with optional filters.
        Returns cash flow records (cost_basis, payout, net_pl).
        """
        if not self.db:
            return []
        
        query = """
            SELECT 
                rt.id,
                rt.redemption_id,
                rt.redemption_date,
                rt.site_id,
                rt.user_id,
                rt.cost_basis,
                rt.payout,
                rt.net_pl,
                rt.notes,
                s.name as site_name,
                u.name as user_name,
                rm.name as method_name
            FROM realized_transactions rt
            JOIN sites s ON rt.site_id = s.id
            JOIN users u ON rt.user_id = u.id
            LEFT JOIN redemptions r ON rt.redemption_id = r.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE 1=1
        """
        
        params = []
        
        # Date filters
        if start_date:
            query += " AND rt.redemption_date >= ?"
            params.append(start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date)
        
        if end_date:
            query += " AND rt.redemption_date <= ?"
            params.append(end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date)
        
        # Site filter
        if site_ids:
            placeholders = ','.join('?' * len(site_ids))
            query += f" AND rt.site_id IN ({placeholders})"
            params.extend(site_ids)
        
        # User filter
        if user_ids:
            placeholders = ','.join('?' * len(user_ids))
            query += f" AND rt.user_id IN ({placeholders})"
            params.extend(user_ids)
        
        query += " ORDER BY rt.redemption_date DESC, rt.id DESC"
        
        rows = self.db.fetch_all(query, tuple(params))
        
        transactions = []
        for row in rows:
            trans = RealizedTransaction(
                id=row['id'],
                redemption_id=row['redemption_id'],
                redemption_date=row['redemption_date'],
                site_id=row['site_id'],
                user_id=row['user_id'],
                site_name=row['site_name'],
                user_name=row['user_name'],
                cost_basis=Decimal(str(row['cost_basis'])),
                payout=Decimal(str(row['payout'])),
                net_pl=Decimal(str(row['net_pl'])),
                method_name=row['method_name'],
                notes=row['notes'] or ""
            )
            transactions.append(trans)
        
        return transactions
    
    def get_by_redemption(self, redemption_id: int) -> Optional[RealizedTransaction]:
        """Get realized transaction for a specific redemption"""
        transactions = self.get_all()
        for trans in transactions:
            if trans.redemption_id == redemption_id:
                return trans
        return None

    def update_notes(self, redemption_id: int, notes: str) -> None:
        """Update notes for a realized transaction by redemption ID."""
        self.db.execute(
            "UPDATE realized_transactions SET notes = ? WHERE redemption_id = ?",
            (notes, redemption_id),
        )
