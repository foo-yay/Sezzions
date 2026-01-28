"""
Report service for aggregating and analyzing data
"""
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import date
from dataclasses import dataclass


@dataclass
class UserSummary:
    """Summary of user activity"""
    user_id: int
    user_name: str
    total_purchases: Decimal
    total_redemptions: Decimal
    total_sessions: int
    total_profit_loss: Decimal
    available_balance: Decimal  # Sum of purchase remaining_amount


@dataclass
class SiteSummary:
    """Summary of site activity"""
    site_id: int
    site_name: str
    total_purchases: Decimal
    total_redemptions: Decimal
    total_sessions: int
    total_profit_loss: Decimal


@dataclass
class FIFOAllocationReport:
    """FIFO allocation details for a redemption"""
    redemption_id: int
    redemption_date: date
    redemption_amount: Decimal
    cost_basis: Decimal
    taxable_profit: Decimal
    purchase_allocations: List[Tuple[int, date, Decimal]]  # (purchase_id, date, amount_used)


class ReportService:
    """Service for generating reports and analytics"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_user_summary(self, user_id: int, site_id: Optional[int] = None) -> UserSummary:
        """
        Get summary of user activity
        Optionally filter by site
        """
        from models.user import User
        
        # Get user info
        user_row = self.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if not user_row:
            raise ValueError(f"User {user_id} not found")
        
        # Build WHERE clause
        where_clause = "user_id = ?"
        params = [user_id]
        if site_id:
            where_clause += " AND site_id = ?"
            params.append(site_id)
        
        # Get purchase totals
        purchase_query = f"""
            SELECT 
                COALESCE(SUM(CAST(amount AS REAL)), 0) as total_purchases,
                COALESCE(SUM(CAST(remaining_amount AS REAL)), 0) as available_balance
            FROM purchases 
            WHERE {where_clause}
        """
        purchase_row = self.db.fetch_one(purchase_query, tuple(params))
        
        # Get redemption totals
        redemption_query = f"""
            SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) as total_redemptions
            FROM redemptions 
            WHERE {where_clause}
        """
        redemption_row = self.db.fetch_one(redemption_query, tuple(params))
        
        # Get session totals
        session_query = f"""
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(CAST(net_taxable_pl AS REAL)), 0) as total_profit_loss
            FROM game_sessions 
            WHERE {where_clause} AND net_taxable_pl IS NOT NULL
        """
        session_row = self.db.fetch_one(session_query, tuple(params))
        
        return UserSummary(
            user_id=user_id,
            user_name=user_row["name"],
            total_purchases=Decimal(str(purchase_row["total_purchases"])),
            total_redemptions=Decimal(str(redemption_row["total_redemptions"])),
            total_sessions=session_row["total_sessions"],
            total_profit_loss=Decimal(str(session_row["total_profit_loss"])),
            available_balance=Decimal(str(purchase_row["available_balance"]))
        )
    
    def get_site_summary(self, site_id: int, user_id: Optional[int] = None) -> SiteSummary:
        """
        Get summary of site activity
        Optionally filter by user
        """
        # Get site info
        site_row = self.db.fetch_one("SELECT * FROM sites WHERE id = ?", (site_id,))
        if not site_row:
            raise ValueError(f"Site {site_id} not found")
        
        # Build WHERE clause
        where_clause = "site_id = ?"
        params = [site_id]
        if user_id:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        
        # Get purchase totals
        purchase_query = f"""
            SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) as total_purchases
            FROM purchases 
            WHERE {where_clause}
        """
        purchase_row = self.db.fetch_one(purchase_query, tuple(params))
        
        # Get redemption totals
        redemption_query = f"""
            SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) as total_redemptions
            FROM redemptions 
            WHERE {where_clause}
        """
        redemption_row = self.db.fetch_one(redemption_query, tuple(params))
        
        # Get session totals
        session_query = f"""
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(CAST(net_taxable_pl AS REAL)), 0) as total_profit_loss
            FROM game_sessions 
            WHERE {where_clause} AND net_taxable_pl IS NOT NULL
        """
        session_row = self.db.fetch_one(session_query, tuple(params))
        
        return SiteSummary(
            site_id=site_id,
            site_name=site_row["name"],
            total_purchases=Decimal(str(purchase_row["total_purchases"])),
            total_redemptions=Decimal(str(redemption_row["total_redemptions"])),
            total_sessions=session_row["total_sessions"],
            total_profit_loss=Decimal(str(session_row["total_profit_loss"]))
        )
    
    def get_all_user_summaries(self, site_id: Optional[int] = None) -> List[UserSummary]:
        """Get summaries for all users, optionally filtered by site"""
        user_query = "SELECT id FROM users WHERE is_active = 1 ORDER BY name"
        user_rows = self.db.fetch_all(user_query)
        
        summaries = []
        for row in user_rows:
            try:
                summary = self.get_user_summary(row["id"], site_id)
                summaries.append(summary)
            except ValueError:
                continue
        
        return summaries
    
    def get_all_site_summaries(self, user_id: Optional[int] = None) -> List[SiteSummary]:
        """Get summaries for all sites, optionally filtered by user"""
        site_query = "SELECT id FROM sites WHERE is_active = 1 ORDER BY name"
        site_rows = self.db.fetch_all(site_query)
        
        summaries = []
        for row in site_rows:
            try:
                summary = self.get_site_summary(row["id"], user_id)
                summaries.append(summary)
            except ValueError:
                continue
        
        return summaries
    
    def get_tax_report(
        self, 
        user_id: int, 
        site_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Decimal]:
        """
        Generate tax report with realized gains/losses
        Returns dict with:
        - total_cost_basis: Total amount spent (allocated via FIFO)
        - total_proceeds: Total redemptions with FIFO applied
        - total_gain_loss: Net gain or loss
        """
        # Build WHERE clause
        where_parts = ["rt.user_id = ?"]
        params = [user_id]
        
        if site_id:
            where_parts.append("rt.site_id = ?")
            params.append(site_id)
        
        if start_date:
            where_parts.append("rt.redemption_date >= ?")
            params.append(start_date.isoformat())
        
        if end_date:
            where_parts.append("rt.redemption_date <= ?")
            params.append(end_date.isoformat())
        
        where_clause = " AND ".join(where_parts)
        
        query = f"""
            SELECT 
                COALESCE(SUM(CAST(rt.cost_basis AS REAL)), 0) as total_cost_basis,
                COALESCE(SUM(CAST(rt.payout AS REAL)), 0) as total_proceeds,
                COALESCE(SUM(CAST(rt.net_pl AS REAL)), 0) as total_gain_loss
            FROM realized_transactions rt
            WHERE {where_clause}
        """
        
        result = self.db.fetch_one(query, tuple(params))
        
        return {
            "total_cost_basis": Decimal(str(result["total_cost_basis"])),
            "total_proceeds": Decimal(str(result["total_proceeds"])),
            "total_gain_loss": Decimal(str(result["total_gain_loss"]))
        }
    
    def get_session_profit_loss_report(
        self,
        user_id: Optional[int] = None,
        site_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, any]:
        """
        Generate session P/L report
        Returns dict with session statistics
        """
        where_parts = ["net_taxable_pl IS NOT NULL"]
        params = []
        
        if user_id:
            where_parts.append("user_id = ?")
            params.append(user_id)
        
        if site_id:
            where_parts.append("site_id = ?")
            params.append(site_id)
        
        if start_date:
            where_parts.append("session_date >= ?")
            params.append(start_date.isoformat())
        
        if end_date:
            where_parts.append("session_date <= ?")
            params.append(end_date.isoformat())
        
        where_clause = " AND ".join(where_parts)
        
        query = f"""
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(CAST(net_taxable_pl AS REAL)), 0) as total_pl,
                COALESCE(AVG(CAST(net_taxable_pl AS REAL)), 0) as avg_pl,
                COUNT(CASE WHEN CAST(net_taxable_pl AS REAL) > 0 THEN 1 END) as winning_sessions,
                COUNT(CASE WHEN CAST(net_taxable_pl AS REAL) < 0 THEN 1 END) as losing_sessions,
                MAX(CAST(net_taxable_pl AS REAL)) as best_session,
                MIN(CAST(net_taxable_pl AS REAL)) as worst_session
            FROM game_sessions
            WHERE {where_clause}
        """
        
        result = self.db.fetch_one(query, tuple(params))
        
        return {
            "total_sessions": result["total_sessions"],
            "total_pl": Decimal(str(result["total_pl"])),
            "average_pl": Decimal(str(result["avg_pl"])),
            "winning_sessions": result["winning_sessions"],
            "losing_sessions": result["losing_sessions"],
            "win_rate": (result["winning_sessions"] / result["total_sessions"] * 100) if result["total_sessions"] > 0 else 0,
            "best_session": Decimal(str(result["best_session"])) if result["best_session"] else Decimal("0"),
            "worst_session": Decimal(str(result["worst_session"])) if result["worst_session"] else Decimal("0")
        }
