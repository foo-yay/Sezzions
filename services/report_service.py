"""
Report service for aggregating and analyzing data
"""
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import date
from dataclasses import dataclass

from tools.timezone_utils import get_configured_timezone_name, local_date_range_to_utc_bounds


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


@dataclass
class ReportFilter:
    """Shared report filter for Phase 1 reports."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    user_ids: Optional[List[int]] = None
    site_ids: Optional[List[int]] = None
    include_deleted: bool = False


@dataclass
class SnapshotDTO:
    """Phase 1 KPI snapshot output."""
    session_net_pl: Decimal
    total_cashback: Decimal
    session_pl_plus_cashback: Decimal
    total_purchases: Decimal
    total_redemptions: Decimal
    total_fees: Decimal
    outstanding_balance: Decimal


@dataclass
class UserBreakdownRow:
    """Phase 1 breakdown row by user."""
    user_id: int
    user_name: str
    session_net_pl: Decimal
    cashback: Decimal
    purchases: Decimal
    redemptions: Decimal
    fees: Decimal
    session_count: int
    outstanding_balance: Decimal


@dataclass
class SiteBreakdownRow:
    """Phase 1 breakdown row by site."""
    site_id: int
    site_name: str
    session_net_pl: Decimal
    cashback: Decimal
    purchases: Decimal
    redemptions: Decimal
    fees: Decimal
    session_count: int
    outstanding_balance: Decimal


class ReportService:
    """Service for generating reports and analytics"""
    
    def __init__(self, db_manager):
        self.db = db_manager

    def _normalize_filter(self, report_filter: Optional[object]) -> ReportFilter:
        if isinstance(report_filter, ReportFilter):
            return report_filter
        if isinstance(report_filter, dict):
            return ReportFilter(
                start_date=report_filter.get("start_date"),
                end_date=report_filter.get("end_date"),
                user_ids=report_filter.get("user_ids"),
                site_ids=report_filter.get("site_ids"),
                include_deleted=bool(report_filter.get("include_deleted", False)),
            )
        return ReportFilter()

    def _build_where(self, alias: str, date_field: str, report_filter: ReportFilter) -> Tuple[str, List[object]]:
        parts: List[str] = []
        params: List[object] = []

        if report_filter.user_ids:
            placeholders = ",".join(["?"] * len(report_filter.user_ids))
            parts.append(f"{alias}.user_id IN ({placeholders})")
            params.extend(report_filter.user_ids)

        if report_filter.site_ids:
            placeholders = ",".join(["?"] * len(report_filter.site_ids))
            parts.append(f"{alias}.site_id IN ({placeholders})")
            params.extend(report_filter.site_ids)

        if report_filter.start_date:
            parts.append(f"{alias}.{date_field} >= ?")
            params.append(report_filter.start_date.isoformat())

        if report_filter.end_date:
            parts.append(f"{alias}.{date_field} <= ?")
            params.append(report_filter.end_date.isoformat())

        if not report_filter.include_deleted:
            parts.append(f"{alias}.deleted_at IS NULL")

        return (" AND ".join(parts) if parts else "1=1"), params

    def get_kpi_snapshot(self, report_filter: Optional[object] = None) -> SnapshotDTO:
        """Phase 1 KPI snapshot for the Reports tab."""
        filters = self._normalize_filter(report_filter)

        purchase_where, purchase_params = self._build_where("p", "purchase_date", filters)
        redemption_where, redemption_params = self._build_where("r", "redemption_date", filters)
        session_where, session_params = self._build_where("gs", "session_date", filters)

        purchase_row = self.db.fetch_one(
            f"""
            SELECT
                COALESCE(SUM(CAST(p.amount AS REAL)), 0) as total_purchases,
                COALESCE(SUM(CAST(p.cashback_earned AS REAL)), 0) as total_cashback,
                COALESCE(SUM(CAST(p.remaining_amount AS REAL)), 0) as outstanding_balance
            FROM purchases p
            WHERE {purchase_where}
            """,
            tuple(purchase_params)
        )

        redemption_row = self.db.fetch_one(
            f"""
            SELECT
                COALESCE(SUM(CAST(r.amount AS REAL)), 0) as total_redemptions,
                COALESCE(SUM(CAST(r.fees AS REAL)), 0) as total_fees
            FROM redemptions r
            WHERE {redemption_where}
            """,
            tuple(redemption_params)
        )

        session_row = self.db.fetch_one(
            f"""
            SELECT
                COALESCE(SUM(CAST(gs.net_taxable_pl AS REAL)), 0) as total_pl
            FROM game_sessions gs
            WHERE {session_where} AND gs.net_taxable_pl IS NOT NULL
            """,
            tuple(session_params)
        )

        session_net_pl = Decimal(str(session_row["total_pl"]))
        total_cashback = Decimal(str(purchase_row["total_cashback"]))

        return SnapshotDTO(
            session_net_pl=session_net_pl,
            total_cashback=total_cashback,
            session_pl_plus_cashback=session_net_pl + total_cashback,
            total_purchases=Decimal(str(purchase_row["total_purchases"])),
            total_redemptions=Decimal(str(redemption_row["total_redemptions"])),
            total_fees=Decimal(str(redemption_row["total_fees"])),
            outstanding_balance=Decimal(str(purchase_row["outstanding_balance"])),
        )

    def get_user_breakdown(self, report_filter: Optional[object] = None) -> List[UserBreakdownRow]:
        """Phase 1 breakdown by user."""
        filters = self._normalize_filter(report_filter)

        purchase_where, purchase_params = self._build_where("p", "purchase_date", filters)
        redemption_where, redemption_params = self._build_where("r", "redemption_date", filters)
        session_where, session_params = self._build_where("gs", "session_date", filters)

        user_filter_clause = ""
        user_filter_params: List[object] = []
        if filters.user_ids:
            placeholders = ",".join(["?"] * len(filters.user_ids))
            user_filter_clause = f"AND u.id IN ({placeholders})"
            user_filter_params.extend(filters.user_ids)

        query = f"""
            WITH purchase_totals AS (
                SELECT p.user_id,
                       COALESCE(SUM(CAST(p.amount AS REAL)), 0) as purchases,
                       COALESCE(SUM(CAST(p.cashback_earned AS REAL)), 0) as cashback,
                       COALESCE(SUM(CAST(p.remaining_amount AS REAL)), 0) as outstanding_balance
                FROM purchases p
                WHERE {purchase_where}
                GROUP BY p.user_id
            ),
            redemption_totals AS (
                SELECT r.user_id,
                       COALESCE(SUM(CAST(r.amount AS REAL)), 0) as redemptions,
                       COALESCE(SUM(CAST(r.fees AS REAL)), 0) as fees
                FROM redemptions r
                WHERE {redemption_where}
                GROUP BY r.user_id
            ),
            session_totals AS (
                SELECT gs.user_id,
                       COALESCE(SUM(CAST(gs.net_taxable_pl AS REAL)), 0) as session_net_pl,
                       COUNT(*) as session_count
                FROM game_sessions gs
                WHERE {session_where} AND gs.net_taxable_pl IS NOT NULL
                GROUP BY gs.user_id
            )
            SELECT u.id as user_id,
                   u.name as user_name,
                   COALESCE(s.session_net_pl, 0) as session_net_pl,
                   COALESCE(p.cashback, 0) as cashback,
                   COALESCE(p.purchases, 0) as purchases,
                   COALESCE(r.redemptions, 0) as redemptions,
                   COALESCE(r.fees, 0) as fees,
                   COALESCE(s.session_count, 0) as session_count,
                   COALESCE(p.outstanding_balance, 0) as outstanding_balance
            FROM users u
            LEFT JOIN purchase_totals p ON p.user_id = u.id
            LEFT JOIN redemption_totals r ON r.user_id = u.id
            LEFT JOIN session_totals s ON s.user_id = u.id
            WHERE (
                COALESCE(p.purchases, 0) != 0
                OR COALESCE(r.redemptions, 0) != 0
                OR COALESCE(s.session_net_pl, 0) != 0
                OR COALESCE(p.cashback, 0) != 0
                OR COALESCE(p.outstanding_balance, 0) != 0
            )
            {user_filter_clause}
            ORDER BY u.name
        """

        params = purchase_params + redemption_params + session_params + user_filter_params
        rows = self.db.fetch_all(query, tuple(params))

        return [
            UserBreakdownRow(
                user_id=row["user_id"],
                user_name=row["user_name"],
                session_net_pl=Decimal(str(row["session_net_pl"])),
                cashback=Decimal(str(row["cashback"])),
                purchases=Decimal(str(row["purchases"])),
                redemptions=Decimal(str(row["redemptions"])),
                fees=Decimal(str(row["fees"])),
                session_count=row["session_count"],
                outstanding_balance=Decimal(str(row["outstanding_balance"])),
            )
            for row in rows
        ]

    def get_site_breakdown(self, report_filter: Optional[object] = None) -> List[SiteBreakdownRow]:
        """Phase 1 breakdown by site."""
        filters = self._normalize_filter(report_filter)

        purchase_where, purchase_params = self._build_where("p", "purchase_date", filters)
        redemption_where, redemption_params = self._build_where("r", "redemption_date", filters)
        session_where, session_params = self._build_where("gs", "session_date", filters)

        site_filter_clause = ""
        site_filter_params: List[object] = []
        if filters.site_ids:
            placeholders = ",".join(["?"] * len(filters.site_ids))
            site_filter_clause = f"AND s.id IN ({placeholders})"
            site_filter_params.extend(filters.site_ids)

        query = f"""
            WITH purchase_totals AS (
                SELECT p.site_id,
                       COALESCE(SUM(CAST(p.amount AS REAL)), 0) as purchases,
                       COALESCE(SUM(CAST(p.cashback_earned AS REAL)), 0) as cashback,
                       COALESCE(SUM(CAST(p.remaining_amount AS REAL)), 0) as outstanding_balance
                FROM purchases p
                WHERE {purchase_where}
                GROUP BY p.site_id
            ),
            redemption_totals AS (
                SELECT r.site_id,
                       COALESCE(SUM(CAST(r.amount AS REAL)), 0) as redemptions,
                       COALESCE(SUM(CAST(r.fees AS REAL)), 0) as fees
                FROM redemptions r
                WHERE {redemption_where}
                GROUP BY r.site_id
            ),
            session_totals AS (
                SELECT gs.site_id,
                       COALESCE(SUM(CAST(gs.net_taxable_pl AS REAL)), 0) as session_net_pl,
                       COUNT(*) as session_count
                FROM game_sessions gs
                WHERE {session_where} AND gs.net_taxable_pl IS NOT NULL
                GROUP BY gs.site_id
            )
            SELECT s.id as site_id,
                   s.name as site_name,
                   COALESCE(t.session_net_pl, 0) as session_net_pl,
                   COALESCE(p.cashback, 0) as cashback,
                   COALESCE(p.purchases, 0) as purchases,
                   COALESCE(r.redemptions, 0) as redemptions,
                   COALESCE(r.fees, 0) as fees,
                   COALESCE(t.session_count, 0) as session_count,
                   COALESCE(p.outstanding_balance, 0) as outstanding_balance
            FROM sites s
            LEFT JOIN purchase_totals p ON p.site_id = s.id
            LEFT JOIN redemption_totals r ON r.site_id = s.id
            LEFT JOIN session_totals t ON t.site_id = s.id
            WHERE (
                COALESCE(p.purchases, 0) != 0
                OR COALESCE(r.redemptions, 0) != 0
                OR COALESCE(t.session_net_pl, 0) != 0
                OR COALESCE(p.cashback, 0) != 0
                OR COALESCE(p.outstanding_balance, 0) != 0
            )
            {site_filter_clause}
            ORDER BY s.name
        """

        params = purchase_params + redemption_params + session_params + site_filter_params
        rows = self.db.fetch_all(query, tuple(params))

        return [
            SiteBreakdownRow(
                site_id=row["site_id"],
                site_name=row["site_name"],
                session_net_pl=Decimal(str(row["session_net_pl"])),
                cashback=Decimal(str(row["cashback"])),
                purchases=Decimal(str(row["purchases"])),
                redemptions=Decimal(str(row["redemptions"])),
                fees=Decimal(str(row["fees"])),
                session_count=row["session_count"],
                outstanding_balance=Decimal(str(row["outstanding_balance"])),
            )
            for row in rows
        ]
    
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
        
        tz_name = None
        if start_date or end_date:
            tz_name = get_configured_timezone_name()

        if start_date:
            start_utc, _ = local_date_range_to_utc_bounds(start_date, start_date, tz_name)
            where_parts.append(
                "(r.redemption_date > ? OR (r.redemption_date = ? AND COALESCE(r.redemption_time, '00:00:00') >= ?))"
            )
            params.extend([start_utc[0], start_utc[0], start_utc[1]])
        
        if end_date:
            _, end_utc = local_date_range_to_utc_bounds(end_date, end_date, tz_name)
            where_parts.append(
                "(r.redemption_date < ? OR (r.redemption_date = ? AND COALESCE(r.redemption_time, '00:00:00') <= ?))"
            )
            params.extend([end_utc[0], end_utc[0], end_utc[1]])
        
        where_clause = " AND ".join(where_parts)
        
        query = f"""
            SELECT 
                COALESCE(SUM(CAST(rt.cost_basis AS REAL)), 0) as total_cost_basis,
                COALESCE(SUM(CAST(rt.payout AS REAL)), 0) as total_proceeds,
                COALESCE(SUM(CAST(rt.net_pl AS REAL)), 0) as total_gain_loss
            FROM realized_transactions rt
            LEFT JOIN redemptions r ON rt.redemption_id = r.id
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
        tz_name = None
        
        if user_id:
            where_parts.append("user_id = ?")
            params.append(user_id)
        
        if site_id:
            where_parts.append("site_id = ?")
            params.append(site_id)
        
        if start_date:
            tz_name = get_configured_timezone_name()
            start_utc, _ = local_date_range_to_utc_bounds(start_date, start_date, tz_name)
            where_parts.append(
                "(session_date > ? OR (session_date = ? AND COALESCE(session_time, '00:00:00') >= ?))"
            )
            params.extend([start_utc[0], start_utc[0], start_utc[1]])
        
        if end_date:
            tz_name = tz_name or get_configured_timezone_name()
            _, end_utc = local_date_range_to_utc_bounds(end_date, end_date, tz_name)
            where_parts.append(
                "(session_date < ? OR (session_date = ? AND COALESCE(session_time, '00:00:00') <= ?))"
            )
            params.extend([end_utc[0], end_utc[0], end_utc[1]])
        
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
