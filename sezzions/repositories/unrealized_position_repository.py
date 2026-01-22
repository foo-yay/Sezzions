"""
Repository for querying unrealized positions (open positions with remaining basis)
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date

from models.unrealized_position import UnrealizedPosition


class UnrealizedPositionRepository:
    """Repository for querying unrealized positions"""
    
    def __init__(self, db):
        self.db = db
    
    def get_all_positions(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[UnrealizedPosition]:
        """
        Get all unrealized positions (site/user with remaining basis).
        Matches legacy refresh_unrealized_positions() logic.
        """
        if not self.db:
            return []
        
        positions = []
        
        # Get all site/user combinations with remaining basis
        query = """
            SELECT DISTINCT
                p.site_id,
                p.user_id,
                s.name as site_name,
                u.name as user_name
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN users u ON p.user_id = u.id
            WHERE p.remaining_amount > 0.001
        """
        
        pairs = self.db.fetch_all(query)
        
        for pair in pairs:
            site_id = pair['site_id']
            user_id = pair['user_id']
            
            # Get remaining basis and start date
            basis_query = """
                SELECT 
                    MIN(purchase_date) as start_date,
                    SUM(remaining_amount) as remaining_basis
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                  AND remaining_amount > 0.001
            """
            
            basis_data = self.db.fetch_one(basis_query, (site_id, user_id))
            
            if not basis_data or not basis_data['remaining_basis']:
                continue
            
            remaining_basis = Decimal(str(basis_data['remaining_basis']))
            
            # Skip if less than 1 cent
            if remaining_basis < Decimal("0.01"):
                continue
            
            # Get current SC balance from last game session
            session_query = """
                SELECT ending_redeemable, ending_balance, session_date
                FROM game_sessions
                WHERE site_id = ? AND user_id = ?
                  AND ending_balance IS NOT NULL
                ORDER BY session_date DESC, session_time DESC
                LIMIT 1
            """
            
            last_session = self.db.fetch_one(session_query, (site_id, user_id))
            
            if last_session:
                # Use redeemable SC, fallback to total balance
                current_sc = Decimal(str(last_session['ending_redeemable'] or last_session['ending_balance'] or 0))
                last_activity = last_session['session_date']
            else:
                # No sessions yet - check for purchases
                purchase_query = """
                    SELECT COALESCE(SUM(sc_received), 0) as total_sc, MAX(purchase_date) as last_date
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                """
                purchase_data = self.db.fetch_one(purchase_query, (site_id, user_id))
                current_sc = Decimal(str(purchase_data['total_sc'] or 0))
                last_activity = purchase_data['last_date']
            
            # Get SC rate (default 1:1)
            site_query = "SELECT sc_rate FROM sites WHERE id = ?"
            site_data = self.db.fetch_one(site_query, (site_id,))
            sc_rate = Decimal(str(site_data['sc_rate'] if site_data and site_data['sc_rate'] else 1.0))
            
            # Calculate current value and unrealized P/L
            current_value = current_sc * sc_rate
            unrealized_pl = current_value - remaining_basis
            
            position = UnrealizedPosition(
                site_id=site_id,
                user_id=user_id,
                site_name=pair['site_name'],
                user_name=pair['user_name'],
                start_date=basis_data['start_date'],
                purchase_basis=remaining_basis,
                current_sc=current_sc,
                current_value=current_value,
                unrealized_pl=unrealized_pl,
                last_activity=last_activity,
                notes=""
            )
            
            positions.append(position)
        
        # Apply date filter to start_date
        if start_date:
            positions = [p for p in positions if p.start_date >= start_date]
        if end_date:
            positions = [p for p in positions if p.start_date <= end_date]
        
        return positions
    
    def get_position_by_site_user(self, site_id: int, user_id: int) -> Optional[UnrealizedPosition]:
        """Get specific position for a site/user pair"""
        all_positions = self.get_all_positions()
        for pos in all_positions:
            if pos.site_id == site_id and pos.user_id == user_id:
                return pos
        return None
