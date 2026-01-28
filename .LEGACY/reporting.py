"""
Reporting Service Layer
=======================
Provides clean API for generating reports with KPIs, time-series data, and tabular exports.

Design principles:
- Return plain dicts (never sqlite3.Row objects)
- Standardized filters across all reports
- Time bucketing (daily/weekly/monthly/quarterly/yearly)
- Calendar year defaults for tax reporting
- matplotlib chart generation
- CSV export support

API:
    run_report(report_id, filters) -> ReportResult
    list_available_reports() -> List[ReportInfo]
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
import sqlite3


@dataclass
class ReportFilters:
    """Standardized filter set for all reports"""
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    user_ids: Optional[List[int]] = None
    site_ids: Optional[List[int]] = None
    game_ids: Optional[List[int]] = None
    card_ids: Optional[List[int]] = None
    redemption_method_ids: Optional[List[int]] = None
    group_interval: str = "daily"  # daily, weekly, monthly, quarterly, yearly


@dataclass
class ReportKPI:
    """Single KPI with label, value, and optional formatting"""
    label: str
    value: Any
    format_type: str = "currency"  # currency, percent, number, text
    trend: Optional[float] = None  # % change vs previous period
    section: Optional[str] = None  # Section grouping (e.g., "Cashflow", "Performance")
    
    def formatted_value(self) -> str:
        if self.value is None:
            return "N/A"
        if self.format_type == "currency":
            return f"${self.value:,.2f}"
        elif self.format_type == "percent":
            return f"{self.value:.1f}%"
        elif self.format_type == "number":
            return f"{self.value:,.0f}"
        else:
            return str(self.value)


@dataclass
class ReportSeries:
    """Time-series data for charting"""
    name: str
    data: List[Tuple[str, float]]  # [(label, value), ...]
    series_type: str = "line"  # line, bar, area
    color: Optional[str] = None  # hex color code (e.g., "#FF0000")


@dataclass
class ReportResult:
    """Complete report output"""
    report_id: str
    title: str
    kpis: List[ReportKPI]
    series: List[ReportSeries]
    rows: List[Dict[str, Any]]  # Tabular data for export
    filters_applied: ReportFilters
    generated_at: datetime


@dataclass
class ReportInfo:
    """Report metadata for catalog"""
    report_id: str
    title: str
    description: str
    category: str
    requires_filters: List[str]  # e.g., ["site_id", "user_id"]


class ReportingService:
    """Service layer for report generation"""
    
    def __init__(self, db):
        self.db = db
        
    def list_available_reports(self) -> List[ReportInfo]:
        """Return catalog of all available reports"""
        return [
            ReportInfo(
                report_id="overall_dashboard",
                title="Overall Dashboard",
                description="High-level KPIs with dynamic context-specific metrics",
                category="Dashboard",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="cashflow_overview",
                title="Cashflow Overview",
                description="Money in/out tracking: purchases, redemptions, fees",
                category="Dashboard",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="pl_overview",
                title="Profit & Loss Overview",
                description="Gameplay performance: taxable P/L, sessions, win rate",
                category="Dashboard",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="site_summary",
                title="Site Summary",
                description="Purchases, redemptions, fees, and net by site",
                category="Sites",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="game_performance",
                title="Game Performance",
                description="Sessions, wager, net P/L, and RTP by game",
                category="Games",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="session_trend",
                title="Session Trend",
                description="Sessions over time with win rate and average net",
                category="Sessions",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="redemption_timing",
                title="Redemption Timing Analysis",
                description="Lag analysis and volume by site/method",
                category="Redemptions",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="cashback_summary",
                title="Cashback Summary",
                description="Cashback earned by site and card",
                category="Cashback",
                requires_filters=[],
            ),
            ReportInfo(
                report_id="tax_winnings_losses",
                title="Tax Diary: Wins/Losses",
                description="Session wins, losses, net P/L, expenses, and fees breakdown",
                category="Tax Center",
                requires_filters=[],
            ),
        ]
    
    def run_report(self, report_id: str, filters: ReportFilters) -> ReportResult:
        """Execute report and return structured result"""
        # Set default date range to current calendar year if not specified
        if not filters.start_date and not filters.end_date:
            today = date.today()
            filters.start_date = f"{today.year}-01-01"
            filters.end_date = today.strftime("%Y-%m-%d")
        
        # Route to specific report implementation
        if report_id == "overall_dashboard":
            return self._run_overall_dashboard(filters)
        elif report_id == "cashflow_overview":
            return self._run_cashflow_overview(filters)
        elif report_id == "pl_overview":
            return self._run_pl_overview(filters)
        elif report_id == "site_summary":
            return self._run_site_summary(filters)
        elif report_id == "game_performance":
            return self._run_game_performance(filters)
        elif report_id == "session_trend":
            return self._run_session_trend(filters)
        elif report_id == "redemption_timing":
            return self._run_redemption_timing(filters)
        elif report_id == "cashback_summary":
            return self._run_cashback_summary(filters)
        elif report_id == "tax_winnings_losses":
            return self._run_tax_winnings_losses(filters)
        else:
            raise ValueError(f"Unknown report_id: {report_id}")
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert sqlite3.Row to plain dict"""
        if row is None:
            return {}
        return {key: row[key] for key in row.keys()}
    
    def _build_filter_clauses(self, filters: ReportFilters, table_alias: str = "") -> Tuple[str, List]:
        """Build WHERE clause and params from filters
        
        Args:
            filters: ReportFilters object
            table_alias: Optional table alias (e.g., "p" for purchases)
            
        Returns:
            (where_clause, params) - SQL string and parameter list
        """
        clauses = []
        params = []
        prefix = f"{table_alias}." if table_alias else ""
        
        if filters.start_date:
            # Determine appropriate date column based on context
            # Caller should specify which date column to filter on
            clauses.append(f"{prefix}date >= ?")
            params.append(filters.start_date)
        
        if filters.end_date:
            clauses.append(f"{prefix}date <= ?")
            params.append(filters.end_date)
        
        if filters.user_ids:
            placeholders = ",".join("?" * len(filters.user_ids))
            clauses.append(f"{prefix}user_id IN ({placeholders})")
            params.extend(filters.user_ids)
        
        if filters.site_ids:
            placeholders = ",".join("?" * len(filters.site_ids))
            clauses.append(f"{prefix}site_id IN ({placeholders})")
            params.extend(filters.site_ids)
        
        where_clause = " AND ".join(clauses) if clauses else "1=1"
        return where_clause, params
    
    def _bucket_sql(self, date_column: str, group_interval: str) -> str:
        """Return SQL expression for time bucketing
        
        Args:
            date_column: Name of the date column to bucket
            group_interval: One of daily, weekly, monthly, quarterly, yearly, or None for all-time
            
        Returns:
            SQL expression for grouping
        """
        if not group_interval or group_interval == "all_time":
            # For all-time, create a single bucket labeled "All Time"
            return "'All Time'"
        elif group_interval == "daily":
            return date_column
        elif group_interval == "weekly":
            # Week starting Monday: use strftime %W for ISO week
            return f"date({date_column}, 'weekday 0', '-6 days')"
        elif group_interval == "monthly":
            return f"strftime('%Y-%m', {date_column})"
        elif group_interval == "quarterly":
            # Format as "2024-Q1"
            return f"strftime('%Y', {date_column}) || '-Q' || ((CAST(strftime('%m', {date_column}) AS INTEGER) - 1) / 3 + 1)"
        elif group_interval == "yearly":
            return f"strftime('%Y', {date_column})"
        else:
            return f"strftime('%Y-%m', {date_column})"  # Default to monthly
    
    # =========================================================================
    # Report Implementations
    # =========================================================================
    
    def _run_dashboard_overview(self, filters: ReportFilters) -> ReportResult:
        """Overall Dashboard: net cashflow, session net, top sites"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build date filter for all queries (no table prefix for standalone queries)
        date_where_purchases = "1=1"
        date_where_redemptions = "1=1"
        date_where_sessions = "1=1"
        # Filters for JOIN conditions (with table prefixes)
        date_where_purchases_join = "1=1"
        date_where_redemptions_join = "1=1"
        date_where_sessions_join = "1=1"
        params_p = []
        params_r = []
        params_s = []
        params_p_join = []
        params_r_join = []
        params_s_join = []
        
        if filters.start_date:
            date_where_purchases += " AND purchase_date >= ?"
            date_where_redemptions += " AND redemption_date >= ?"
            date_where_sessions += " AND session_date >= ?"
            date_where_purchases_join += " AND p.purchase_date >= ?"
            date_where_redemptions_join += " AND r.redemption_date >= ?"
            date_where_sessions_join += " AND gs.session_date >= ?"
            params_p.append(filters.start_date)
            params_r.append(filters.start_date)
            params_s.append(filters.start_date)
            params_p_join.append(filters.start_date)
            params_r_join.append(filters.start_date)
            params_s_join.append(filters.start_date)
        
        if filters.end_date:
            date_where_purchases += " AND purchase_date <= ?"
            date_where_redemptions += " AND redemption_date <= ?"
            date_where_sessions += " AND session_date <= ?"
            date_where_purchases_join += " AND p.purchase_date <= ?"
            date_where_redemptions_join += " AND r.redemption_date <= ?"
            date_where_sessions_join += " AND gs.session_date <= ?"
            params_p.append(filters.end_date)
            params_r.append(filters.end_date)
            params_s.append(filters.end_date)
            params_p_join.append(filters.end_date)
            params_r_join.append(filters.end_date)
            params_s_join.append(filters.end_date)
        
        # User filter
        if filters.user_ids:
            placeholders = ",".join("?" * len(filters.user_ids))
            date_where_purchases += f" AND user_id IN ({placeholders})"
            date_where_redemptions += f" AND user_id IN ({placeholders})"
            date_where_sessions += f" AND user_id IN ({placeholders})"
            date_where_purchases_join += f" AND p.user_id IN ({placeholders})"
            date_where_redemptions_join += f" AND r.user_id IN ({placeholders})"
            date_where_sessions_join += f" AND gs.user_id IN ({placeholders})"
            params_p.extend(filters.user_ids)
            params_r.extend(filters.user_ids)
            params_s.extend(filters.user_ids)
            params_p_join.extend(filters.user_ids)
            params_r_join.extend(filters.user_ids)
            params_s_join.extend(filters.user_ids)
        
        # Site filter
        if filters.site_ids:
            placeholders = ",".join("?" * len(filters.site_ids))
            date_where_purchases += f" AND site_id IN ({placeholders})"
            date_where_redemptions += f" AND site_id IN ({placeholders})"
            date_where_sessions += f" AND site_id IN ({placeholders})"
            date_where_purchases_join += f" AND p.site_id IN ({placeholders})"
            date_where_redemptions_join += f" AND r.site_id IN ({placeholders})"
            date_where_sessions_join += f" AND gs.site_id IN ({placeholders})"
            params_p.extend(filters.site_ids)
            params_r.extend(filters.site_ids)
            params_s.extend(filters.site_ids)
            params_p_join.extend(filters.site_ids)
            params_r_join.extend(filters.site_ids)
            params_s_join.extend(filters.site_ids)
        
        # KPI 1: Total Purchases
        c.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) as total_purchases
            FROM purchases
            WHERE {date_where_purchases}
            """,
            params_p,
        )
        total_purchases = c.fetchone()["total_purchases"]
        
        # KPI 2: Total Redemptions (net of fees)
        c.execute(
            f"""
            SELECT 
                COALESCE(SUM(amount), 0) as total_redemptions,
                COALESCE(SUM(fees), 0) as total_fees
            FROM redemptions
            WHERE {date_where_redemptions}
            """,
            params_r,
        )
        redemption_row = c.fetchone()
        total_redemptions = redemption_row["total_redemptions"]
        total_fees = redemption_row["total_fees"]
        net_redemptions = total_redemptions - total_fees
        
        # KPI 3: Net Cashflow
        net_cashflow = net_redemptions - total_purchases
        
        # KPI 4: Total Session Net (from game_sessions - actual gameplay P/L)
        c.execute(
            f"""
            SELECT COALESCE(SUM(net_taxable_pl), 0) as total_session_net
            FROM game_sessions
            WHERE {date_where_sessions}
            """,
            params_s,
        )
        total_session_net = c.fetchone()["total_session_net"]
        
        # KPI 5: Session Count (daily tax sessions - IRS reportable units)
        c.execute(
            f"""
            SELECT COUNT(*) as session_count
            FROM daily_tax_sessions
            WHERE {date_where_sessions}
            """,
            params_s,
        )
        session_count = c.fetchone()["session_count"]
        
        # KPI 6: Win Rate (based on daily tax sessions - reportable units)
        c.execute(
            f"""
            SELECT 
                SUM(CASE WHEN total_session_pnl > 0 THEN 1 ELSE 0 END) as wins,
                COUNT(*) as total_sessions
            FROM daily_tax_sessions
            WHERE {date_where_sessions}
            """,
            params_s,
        )
        win_row = c.fetchone()
        win_rate = (win_row["wins"] / win_row["total_sessions"] * 100) if win_row["total_sessions"] > 0 else 0
        
        kpis = [
            ReportKPI(label="Total Purchases", value=total_purchases, format_type="currency"),
            ReportKPI(label="Net Redemptions", value=net_redemptions, format_type="currency"),
            ReportKPI(label="Net Cashflow", value=net_cashflow, format_type="currency"),
            ReportKPI(label="Session Net P/L", value=total_session_net, format_type="currency"),
            ReportKPI(label="Total Sessions", value=session_count, format_type="number"),
            ReportKPI(label="Win Rate", value=win_rate, format_type="percent"),
        ]
        
        # Time series: Daily net cashflow
        bucket_expr = self._bucket_sql("purchase_date", filters.group_interval)
        bucket_expr_redemptions = self._bucket_sql("redemption_date", filters.group_interval)
        c.execute(
            f"""
            WITH all_periods AS (
                SELECT DISTINCT {bucket_expr} as period
                FROM purchases
                WHERE {date_where_purchases}
                UNION
                SELECT DISTINCT {bucket_expr_redemptions} as period
                FROM redemptions
                WHERE {date_where_redemptions}
            ),
            purchases_by_period AS (
                SELECT 
                    {bucket_expr} as period,
                    SUM(amount) as total_purchases
                FROM purchases
                WHERE {date_where_purchases}
                GROUP BY period
            ),
            redemptions_by_period AS (
                SELECT 
                    {bucket_expr_redemptions} as period,
                    SUM(amount - COALESCE(fees, 0)) as net_redemptions
                FROM redemptions
                WHERE {date_where_redemptions}
                GROUP BY period
            )
            SELECT 
                a.period,
                COALESCE(p.total_purchases, 0) as purchases,
                COALESCE(r.net_redemptions, 0) as redemptions,
                COALESCE(r.net_redemptions, 0) - COALESCE(p.total_purchases, 0) as net_cashflow
            FROM all_periods a
            LEFT JOIN purchases_by_period p ON a.period = p.period
            LEFT JOIN redemptions_by_period r ON a.period = r.period
            ORDER BY a.period
            """,
            params_p + params_r + params_p + params_r,  # Need params for each CTE that uses the filters
        )
        cashflow_data = [(self._row_to_dict(row)["period"], self._row_to_dict(row)["net_cashflow"]) 
                         for row in c.fetchall()]
        
        series = [
            ReportSeries(name="Net Cashflow", data=cashflow_data, series_type="bar"),
        ]
        
        # Top sites by volume (aggregate each table separately to avoid Cartesian product)
        c.execute(
            f"""
            WITH site_sessions AS (
                SELECT 
                    site_id,
                    COUNT(*) as session_count
                FROM game_sessions
                WHERE {date_where_sessions}
                GROUP BY site_id
            ),
            site_purchases AS (
                SELECT 
                    site_id,
                    SUM(amount) as total_purchases
                FROM purchases
                WHERE {date_where_purchases}
                GROUP BY site_id
            ),
            site_redemptions AS (
                SELECT 
                    site_id,
                    SUM(amount - COALESCE(fees, 0)) as net_redemptions
                FROM redemptions
                WHERE {date_where_redemptions}
                GROUP BY site_id
            )
            SELECT 
                s.name as site_name,
                COALESCE(ss.session_count, 0) as session_count,
                COALESCE(sp.total_purchases, 0) as total_purchases,
                COALESCE(sr.net_redemptions, 0) as net_redemptions
            FROM sites s
            LEFT JOIN site_sessions ss ON s.id = ss.site_id
            LEFT JOIN site_purchases sp ON s.id = sp.site_id
            LEFT JOIN site_redemptions sr ON s.id = sr.site_id
            WHERE ss.session_count > 0 OR sp.total_purchases > 0 OR sr.net_redemptions > 0
            ORDER BY session_count DESC
            LIMIT 10
            """,
            params_s + params_p + params_r,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        conn.close()
        
        return ReportResult(
            report_id="dashboard_overview",
            title="Overall Dashboard",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_overall_dashboard(self, filters: ReportFilters) -> ReportResult:
        """Overall Dashboard: Core KPIs with dynamic drill-down metrics"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build filter conditions for all tables
        where_purchases = "1=1"
        where_redemptions = "1=1"
        where_sessions = "1=1"
        where_expenses = "1=1"
        params_p = []
        params_r = []
        params_s = []
        params_e = []
        
        if filters.start_date:
            where_purchases += " AND purchase_date >= ?"
            where_redemptions += " AND redemption_date >= ?"
            where_sessions += " AND session_date >= ?"
            where_expenses += " AND expense_date >= ?"
            params_p.append(filters.start_date)
            params_r.append(filters.start_date)
            params_s.append(filters.start_date)
            params_e.append(filters.start_date)
        
        if filters.end_date:
            where_purchases += " AND purchase_date <= ?"
            where_redemptions += " AND redemption_date <= ?"
            where_sessions += " AND session_date <= ?"
            where_expenses += " AND expense_date <= ?"
            params_p.append(filters.end_date)
            params_r.append(filters.end_date)
            params_s.append(filters.end_date)
            params_e.append(filters.end_date)
        
        if filters.user_ids:
            placeholders = ",".join("?" * len(filters.user_ids))
            where_purchases += f" AND user_id IN ({placeholders})"
            where_redemptions += f" AND user_id IN ({placeholders})"
            where_sessions += f" AND user_id IN ({placeholders})"
            where_expenses += f" AND user_id IN ({placeholders})"
            params_p.extend(filters.user_ids)
            params_r.extend(filters.user_ids)
            params_s.extend(filters.user_ids)
            params_e.extend(filters.user_ids)
        
        if filters.site_ids:
            placeholders = ",".join("?" * len(filters.site_ids))
            where_purchases += f" AND site_id IN ({placeholders})"
            where_redemptions += f" AND site_id IN ({placeholders})"
            where_sessions += f" AND site_id IN ({placeholders})"
            params_p.extend(filters.site_ids)
            params_r.extend(filters.site_ids)
            params_s.extend(filters.site_ids)
        
        # Core KPIs organized into sections
        kpis = []
        
        # === CASHFLOW SECTION ===
        # Total Purchases
        c.execute(f"SELECT COALESCE(SUM(amount), 0) FROM purchases WHERE {where_purchases}", params_p)
        total_purchases = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Purchases", value=total_purchases, format_type="currency", section="Cashflow"))
        
        # Realized Basis (Consumed)
        c.execute(
            f"SELECT COALESCE(SUM(amount), 0) - COALESCE(SUM(remaining_amount), 0) FROM purchases WHERE {where_purchases}",
            params_p
        )
        realized_basis = c.fetchone()[0]
        kpis.append(ReportKPI(label="Realized Basis", value=realized_basis, format_type="currency", section="Cashflow"))
        
        # Unrealized Basis
        c.execute(
            f"SELECT COALESCE(SUM(remaining_amount), 0) FROM purchases WHERE {where_purchases} AND status = 'active'",
            params_p
        )
        unrealized_basis = c.fetchone()[0]
        kpis.append(ReportKPI(label="Unrealized Basis", value=unrealized_basis, format_type="currency", section="Cashflow"))
        
        # Redeemed P/L (Realized Profit)
        # Build WHERE clause with r. prefix for redemptions table
        where_r_parts = ["1=1"]
        params_r_query = []
        
        if filters.start_date:
            where_r_parts.append("r.redemption_date >= ?")
            params_r_query.append(filters.start_date)
        
        if filters.end_date:
            where_r_parts.append("r.redemption_date <= ?")
            params_r_query.append(filters.end_date)
        
        if filters.user_ids:
            placeholders = ",".join("?" * len(filters.user_ids))
            where_r_parts.append(f"r.user_id IN ({placeholders})")
            params_r_query.extend(filters.user_ids)
        
        if filters.site_ids:
            placeholders = ",".join("?" * len(filters.site_ids))
            where_r_parts.append(f"r.site_id IN ({placeholders})")
            params_r_query.extend(filters.site_ids)
        
        where_r_qualified = " AND ".join(where_r_parts)
        
        c.execute(
            f"""
            SELECT COALESCE(SUM(rt.net_pl), 0)
            FROM realized_transactions rt
            JOIN redemptions r ON r.id = rt.redemption_id
            WHERE {where_r_qualified}
            """,
            params_r_query
        )
        redeemed_pl = c.fetchone()[0]
        kpis.append(ReportKPI(label="Redeemed P/L", value=redeemed_pl, format_type="currency", section="Cashflow"))
        
        # Total Cashback
        c.execute(f"SELECT COALESCE(SUM(cashback_earned), 0) FROM purchases WHERE {where_purchases}", params_p)
        total_cashback = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Cashback", value=total_cashback, format_type="currency", section="Cashflow"))
        
        # Total Expenses
        c.execute(f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE {where_expenses}", params_e)
        total_expenses = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Expenses", value=total_expenses, format_type="currency", section="Cashflow"))
        
        # === SESSION PERFORMANCE SECTION ===
        # Total Session P/L
        c.execute(f"SELECT COALESCE(SUM(net_taxable_pl), 0) FROM game_sessions WHERE {where_sessions}", params_s)
        session_pl = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Session P/L", value=session_pl, format_type="currency", section="Session Performance"))
        
        # Total Game Sessions
        c.execute(f"SELECT COUNT(*) FROM game_sessions WHERE {where_sessions}", params_s)
        total_game_sessions = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Game Sessions", value=total_game_sessions, format_type="number", section="Session Performance"))
        
        # Calculate unique days played
        c.execute(f"SELECT COUNT(DISTINCT session_date) FROM game_sessions WHERE {where_sessions}", params_s)
        unique_days = c.fetchone()[0] or 0
        
        # Calculate total hours played (using session duration)
        c.execute(
            f"""
            SELECT SUM(
                CASE 
                    WHEN end_date IS NOT NULL AND end_time IS NOT NULL 
                    THEN (JULIANDAY(end_date || ' ' || end_time) - JULIANDAY(session_date || ' ' || start_time)) * 24
                    ELSE 0
                END
            ) as total_hours
            FROM game_sessions 
            WHERE {where_sessions}
            """,
            params_s
        )
        total_hours = c.fetchone()[0] or 0
        
        # Avg Session P/L (Daily)
        daily_pl = (session_pl / unique_days) if unique_days > 0 else 0
        kpis.append(ReportKPI(label="Avg Session P/L (Daily)", value=daily_pl, format_type="currency", section="Session Performance"))
        
        # Avg Session P/L (Hourly)
        hourly_pl = (session_pl / total_hours) if total_hours > 0 else 0
        kpis.append(ReportKPI(label="Avg Session P/L (Hourly)", value=hourly_pl, format_type="currency", section="Session Performance"))
        
        # Avg Session P/L (Annually) - calculated as full-time job equivalent (40 hrs/week × 52 weeks)
        # This shows "what if you earned this hourly rate at a regular full-time job"
        annual_pl = hourly_pl * 40 * 52  # 2,080 hours per year (standard full-time)
        
        kpis.append(ReportKPI(label="Avg Session P/L (Annually)", value=annual_pl, format_type="currency", section="Session Performance"))
        
        # === POSITION SECTION (removed - now using Unrealized Basis in Cashflow) ===
        
        # Context-specific KPIs (shown when filters are applied)
        context_kpis = []
        
        # === SITE METRICS (when single site filtered) ===
        if filters.site_ids and len(filters.site_ids) == 1:
            c.execute(
                f"""
                SELECT AVG(JULIANDAY(receipt_date) - JULIANDAY(redemption_date)) as avg_days
                FROM redemptions
                WHERE {where_redemptions} AND receipt_date IS NOT NULL
                """,
                params_r
            )
            result = c.fetchone()
            avg_days = result[0] if result and result[0] else 0
            context_kpis.append(ReportKPI(
                label="Avg Redemption Time (Days)",
                value=avg_days,
                format_type="number",
                section="Site Metrics"
            ))
            
            # Avg Session P/L for site
            avg_session_pl = (session_pl / total_game_sessions) if total_game_sessions > 0 else 0
            context_kpis.append(ReportKPI(
                label="Avg Session P/L",
                value=avg_session_pl,
                format_type="currency",
                section="Site Metrics"
            ))
        
        # === USER METRICS (when single user filtered) ===
        if filters.user_ids and len(filters.user_ids) == 1:
            # Net redemptions for user
            c.execute(
                f"SELECT COALESCE(SUM(amount - COALESCE(fees, 0)), 0) FROM redemptions WHERE {where_redemptions}",
                params_r
            )
            net_redemptions = c.fetchone()[0]
            context_kpis.append(ReportKPI(
                label="Net Redemptions",
                value=net_redemptions,
                format_type="currency",
                section="User Metrics"
            ))
            
            # Net cashflow for user
            net_cashflow = net_redemptions - total_purchases
            context_kpis.append(ReportKPI(
                label="Net Cashflow",
                value=net_cashflow,
                format_type="currency",
                section="User Metrics"
            ))
        
        # Combine core and context KPIs
        all_kpis = kpis + context_kpis
        
        # No charts for this dashboard - pure KPI focus
        series = []
        
        # Table: Top performers (sites or games depending on context)
        if filters.site_ids and len(filters.site_ids) == 1:
            # Show top games for this site
            c.execute(
                f"""
                SELECT 
                    game_name,
                    COUNT(*) as session_count,
                    COALESCE(SUM(net_taxable_pl), 0) as total_pl,
                    COALESCE(AVG(rtp), 0) as avg_rtp
                FROM game_sessions
                WHERE {where_sessions} AND game_name IS NOT NULL
                GROUP BY game_name
                ORDER BY total_pl DESC
                LIMIT 10
                """,
                params_s
            )
            rows = [self._row_to_dict(row) for row in c.fetchall()]
        else:
            # Build explicit WHERE clauses for CTE with table prefixes
            where_gs_parts = ["1=1"]
            where_p_parts = ["1=1"]
            params_gs = []
            params_p_cte = []
            
            if filters.start_date:
                where_gs_parts.append("gs.session_date >= ?")
                where_p_parts.append("p.purchase_date >= ?")
                params_gs.append(filters.start_date)
                params_p_cte.append(filters.start_date)
            
            if filters.end_date:
                where_gs_parts.append("gs.session_date <= ?")
                where_p_parts.append("p.purchase_date <= ?")
                params_gs.append(filters.end_date)
                params_p_cte.append(filters.end_date)
            
            if filters.user_ids:
                placeholders = ",".join("?" * len(filters.user_ids))
                where_gs_parts.append(f"gs.user_id IN ({placeholders})")
                where_p_parts.append(f"p.user_id IN ({placeholders})")
                params_gs.extend(filters.user_ids)
                params_p_cte.extend(filters.user_ids)
            
            if filters.site_ids:
                placeholders = ",".join("?" * len(filters.site_ids))
                where_gs_parts.append(f"gs.site_id IN ({placeholders})")
                where_p_parts.append(f"p.site_id IN ({placeholders})")
                params_gs.extend(filters.site_ids)
                params_p_cte.extend(filters.site_ids)
            
            where_gs = " AND ".join(where_gs_parts)
            where_p = " AND ".join(where_p_parts)
            
            # Show top sites
            c.execute(
                f"""
                WITH site_sessions AS (
                    SELECT gs.site_id, COUNT(*) as session_count, SUM(gs.net_taxable_pl) as total_pl
                    FROM game_sessions gs
                    WHERE {where_gs}
                    GROUP BY gs.site_id
                ),
                site_purchases AS (
                    SELECT p.site_id, SUM(p.amount) as total_purchases
                    FROM purchases p
                    WHERE {where_p}
                    GROUP BY p.site_id
                )
                SELECT 
                    s.name as site_name,
                    COALESCE(ss.session_count, 0) as session_count,
                    COALESCE(sp.total_purchases, 0) as total_purchases,
                    COALESCE(ss.total_pl, 0) as total_pl
                FROM sites s
                LEFT JOIN site_sessions ss ON s.id = ss.site_id
                LEFT JOIN site_purchases sp ON s.id = sp.site_id
                WHERE ss.session_count > 0 OR sp.total_purchases > 0
                ORDER BY total_pl DESC
                LIMIT 10
                """,
                params_gs + params_p_cte
            )
            rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # Build title with filter info
        title_parts = ["Overall Dashboard"]
        
        # Add site name if single site filtered
        if filters.site_ids and len(filters.site_ids) == 1:
            c.execute("SELECT name FROM sites WHERE id = ?", (filters.site_ids[0],))
            site = c.fetchone()
            if site:
                title_parts.append(site['name'])
        
        # Add user name if single user filtered
        if filters.user_ids and len(filters.user_ids) == 1:
            c.execute("SELECT name FROM users WHERE id = ?", (filters.user_ids[0],))
            user = c.fetchone()
            if user:
                title_parts.append(user['name'])
        
        report_title = " - ".join(title_parts)
        
        conn.close()
        
        return ReportResult(
            report_id="overall_dashboard",
            title=report_title,
            kpis=all_kpis,
            series=series,
            rows=[],  # No table for Overall Dashboard
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_cashflow_overview(self, filters: ReportFilters) -> ReportResult:
        """Cashflow Overview: Money in/out tracking"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build filter conditions
        date_where_purchases = "1=1"
        date_where_redemptions = "1=1"
        params_p = []
        params_r = []
        
        if filters.start_date:
            date_where_purchases += " AND purchase_date >= ?"
            date_where_redemptions += " AND redemption_date >= ?"
            params_p.append(filters.start_date)
            params_r.append(filters.start_date)
        
        if filters.end_date:
            date_where_purchases += " AND purchase_date <= ?"
            date_where_redemptions += " AND redemption_date <= ?"
            params_p.append(filters.end_date)
            params_r.append(filters.end_date)
        
        if filters.user_ids:
            placeholders = ",".join("?" * len(filters.user_ids))
            date_where_purchases += f" AND user_id IN ({placeholders})"
            date_where_redemptions += f" AND user_id IN ({placeholders})"
            params_p.extend(filters.user_ids)
            params_r.extend(filters.user_ids)
        
        if filters.site_ids:
            placeholders = ",".join("?" * len(filters.site_ids))
            date_where_purchases += f" AND site_id IN ({placeholders})"
            date_where_redemptions += f" AND site_id IN ({placeholders})"
            params_p.extend(filters.site_ids)
            params_r.extend(filters.site_ids)
        
        # KPIs
        kpis = []
        
        # Total Purchases
        c.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM purchases WHERE {date_where_purchases}",
            params_p,
        )
        total_purchases = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Purchases", value=total_purchases, format_type="currency"))
        
        # Net Redemptions
        c.execute(
            f"SELECT COALESCE(SUM(amount - COALESCE(fees, 0)), 0) FROM redemptions WHERE {date_where_redemptions}",
            params_r,
        )
        net_redemptions = c.fetchone()[0]
        kpis.append(ReportKPI(label="Net Redemptions", value=net_redemptions, format_type="currency"))
        
        # Total Fees
        c.execute(
            f"SELECT COALESCE(SUM(fees), 0) FROM redemptions WHERE {date_where_redemptions}",
            params_r,
        )
        total_fees = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Fees", value=total_fees, format_type="currency"))
        
        # Net Cashflow
        net_cashflow = net_redemptions - total_purchases
        kpis.append(ReportKPI(label="Net Cashflow", value=net_cashflow, format_type="currency"))
        
        # Time series: Purchases and Redemptions over time
        bucket_expr = self._bucket_sql("purchase_date", filters.group_interval)
        bucket_expr_redemptions = self._bucket_sql("redemption_date", filters.group_interval)
        c.execute(
            f"""
            WITH all_periods AS (
                SELECT DISTINCT {bucket_expr} as period
                FROM purchases
                WHERE {date_where_purchases}
                UNION
                SELECT DISTINCT {bucket_expr_redemptions} as period
                FROM redemptions
                WHERE {date_where_redemptions}
            ),
            purchases_by_period AS (
                SELECT 
                    {bucket_expr} as period,
                    SUM(amount) as total_purchases
                FROM purchases
                WHERE {date_where_purchases}
                GROUP BY period
            ),
            redemptions_by_period AS (
                SELECT 
                    {bucket_expr_redemptions} as period,
                    SUM(amount - COALESCE(fees, 0)) as net_redemptions
                FROM redemptions
                WHERE {date_where_redemptions}
                GROUP BY period
            )
            SELECT 
                a.period,
                COALESCE(p.total_purchases, 0) as purchases,
                COALESCE(r.net_redemptions, 0) as redemptions
            FROM all_periods a
            LEFT JOIN purchases_by_period p ON a.period = p.period
            LEFT JOIN redemptions_by_period r ON a.period = r.period
            ORDER BY a.period
            """,
            params_p + params_r + params_p + params_r,
        )
        purchases_data = []
        redemptions_data = []
        for row in c.fetchall():
            row_dict = self._row_to_dict(row)
            purchases_data.append((row_dict["period"], row_dict["purchases"]))
            redemptions_data.append((row_dict["period"], row_dict["redemptions"]))
        
        series = [
            ReportSeries(name="Purchases", data=purchases_data, color="#E53935"),  # Red
            ReportSeries(name="Redemptions", data=redemptions_data, color="#43A047"),  # Green
        ]
        
        # Top sites table
        c.execute(
            f"""
            WITH site_purchases AS (
                SELECT 
                    site_id,
                    SUM(amount) as total_purchases
                FROM purchases
                WHERE {date_where_purchases}
                GROUP BY site_id
            ),
            site_redemptions AS (
                SELECT 
                    site_id,
                    SUM(amount - COALESCE(fees, 0)) as net_redemptions,
                    SUM(COALESCE(fees, 0)) as total_fees
                FROM redemptions
                WHERE {date_where_redemptions}
                GROUP BY site_id
            )
            SELECT 
                s.name as site_name,
                COALESCE(sp.total_purchases, 0) as total_purchases,
                COALESCE(sr.net_redemptions, 0) as net_redemptions,
                COALESCE(sr.total_fees, 0) as total_fees,
                COALESCE(sr.net_redemptions, 0) - COALESCE(sp.total_purchases, 0) as net_cashflow
            FROM sites s
            LEFT JOIN site_purchases sp ON s.id = sp.site_id
            LEFT JOIN site_redemptions sr ON s.id = sr.site_id
            WHERE sp.total_purchases > 0 OR sr.net_redemptions > 0
            ORDER BY total_purchases DESC
            LIMIT 10
            """,
            params_p + params_r,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        conn.close()
        
        return ReportResult(
            report_id="cashflow_overview",
            title="Cashflow Overview",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_pl_overview(self, filters: ReportFilters) -> ReportResult:
        """P/L Overview: Gameplay performance tracking"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build filter conditions
        date_where_sessions = "1=1"
        date_where_daily = "1=1"
        date_where_realized = "1=1"  # For realized_transactions table
        params_s = []
        params_d = []
        params_r = []
        
        if filters.start_date:
            date_where_sessions += " AND session_date >= ?"
            date_where_daily += " AND session_date >= ?"
            date_where_realized += " AND redemption_date >= ?"
            params_s.append(filters.start_date)
            params_d.append(filters.start_date)
            params_r.append(filters.start_date)
        
        if filters.end_date:
            date_where_sessions += " AND session_date <= ?"
            date_where_daily += " AND session_date <= ?"
            date_where_realized += " AND redemption_date <= ?"
            params_s.append(filters.end_date)
            params_d.append(filters.end_date)
            params_r.append(filters.end_date)
        
        if filters.user_ids:
            placeholders = ",".join("?" * len(filters.user_ids))
            date_where_sessions += f" AND user_id IN ({placeholders})"
            date_where_daily += f" AND user_id IN ({placeholders})"
            date_where_realized += f" AND user_id IN ({placeholders})"
            params_s.extend(filters.user_ids)
            params_d.extend(filters.user_ids)
            params_r.extend(filters.user_ids)
        
        if filters.site_ids:
            placeholders = ",".join("?" * len(filters.site_ids))
            date_where_sessions += f" AND site_id IN ({placeholders})"
            date_where_realized += f" AND site_id IN ({placeholders})"
            params_s.extend(filters.site_ids)
            params_r.extend(filters.site_ids)
        
        # KPIs
        kpis = []
        
        # Session Net P/L (from game_sessions)
        c.execute(
            f"SELECT COALESCE(SUM(net_taxable_pl), 0) FROM game_sessions WHERE {date_where_sessions}",
            params_s,
        )
        session_net_pl = c.fetchone()[0]
        kpis.append(ReportKPI(label="Session Net P/L", value=session_net_pl, format_type="currency"))
        
        # Total Taxable Sessions (from daily_tax_sessions)
        c.execute(
            f"SELECT COUNT(*) FROM daily_tax_sessions WHERE {date_where_daily}",
            params_d,
        )
        total_sessions = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Taxable Sessions", value=total_sessions, format_type="number"))
        
        # Win Rate (winning days / total days)
        c.execute(
            f"SELECT COUNT(*) FROM daily_tax_sessions WHERE {date_where_daily} AND total_session_pnl > 0",
            params_d,
        )
        winning_sessions = c.fetchone()[0]
        win_rate = (winning_sessions / total_sessions * 100) if total_sessions > 0 else 0
        kpis.append(ReportKPI(label="Win Rate", value=win_rate, format_type="percent"))
        
        # Total Game Sessions
        c.execute(
            f"SELECT COUNT(*) FROM game_sessions WHERE {date_where_sessions}",
            params_s,
        )
        total_game_sessions = c.fetchone()[0]
        kpis.append(ReportKPI(label="Total Game Sessions", value=total_game_sessions, format_type="number"))
        
        # Time series: P/L over time
        bucket_expr = self._bucket_sql("session_date", filters.group_interval)
        c.execute(
            f"""
            SELECT 
                {bucket_expr} as period,
                SUM(net_taxable_pl) as total_pl
            FROM game_sessions
            WHERE {date_where_sessions}
            GROUP BY period
            ORDER BY period
            """,
            params_s,
        )
        pl_data = [(self._row_to_dict(row)["period"], self._row_to_dict(row)["total_pl"]) 
                   for row in c.fetchall()]
        
        series = [ReportSeries(name="Net P/L", data=pl_data)]
        
        # Top games table
        c.execute(
            f"""
            SELECT 
                game_name,
                COUNT(*) as session_count,
                COALESCE(SUM(net_taxable_pl), 0) as net_pl,
                COALESCE(AVG(rtp), 0) as avg_rtp
            FROM game_sessions
            WHERE {date_where_sessions} AND game_name IS NOT NULL
            GROUP BY game_name
            ORDER BY net_pl DESC
            LIMIT 10
            """,
            params_s,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        conn.close()
        
        return ReportResult(
            report_id="pl_overview",
            title="Profit & Loss Overview",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_site_summary(self, filters: ReportFilters) -> ReportResult:
        """Site Summary: purchases, redemptions, fees, net by site"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        date_where_purchases = "1=1"
        date_where_redemptions = "1=1"
        params_p = []
        params_r = []
        
        if filters.start_date:
            date_where_purchases += " AND purchase_date >= ?"
            date_where_redemptions += " AND redemption_date >= ?"
            params_p.append(filters.start_date)
            params_r.append(filters.start_date)
        
        if filters.end_date:
            date_where_purchases += " AND purchase_date <= ?"
            date_where_redemptions += " AND redemption_date <= ?"
            params_p.append(filters.end_date)
            params_r.append(filters.end_date)
        
        c.execute(
            f"""
            WITH site_purchases AS (
                SELECT 
                    site_id,
                    SUM(amount) as total_purchases
                FROM purchases
                WHERE {date_where_purchases}
                GROUP BY site_id
            ),
            site_redemptions AS (
                SELECT 
                    site_id,
                    SUM(amount) as total_redemptions,
                    SUM(COALESCE(fees, 0)) as total_fees,
                    SUM(amount - COALESCE(fees, 0)) as net_redemptions
                FROM redemptions
                WHERE {date_where_redemptions}
                GROUP BY site_id
            )
            SELECT 
                s.name as site_name,
                COALESCE(sp.total_purchases, 0) as total_purchases,
                COALESCE(sr.total_redemptions, 0) as total_redemptions,
                COALESCE(sr.total_fees, 0) as total_fees,
                COALESCE(sr.net_redemptions, 0) as net_redemptions,
                COALESCE(sr.net_redemptions, 0) - COALESCE(sp.total_purchases, 0) as net_cashflow
            FROM sites s
            LEFT JOIN site_purchases sp ON s.id = sp.site_id
            LEFT JOIN site_redemptions sr ON s.id = sr.site_id
            WHERE sp.total_purchases > 0 OR sr.total_redemptions > 0
            ORDER BY total_purchases DESC
            """,
            params_p + params_r,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # KPIs
        total_purchases = sum(r["total_purchases"] for r in rows)
        total_redemptions = sum(r["total_redemptions"] for r in rows)
        total_fees = sum(r["total_fees"] for r in rows)
        net_cashflow = sum(r["net_cashflow"] for r in rows)
        
        kpis = [
            ReportKPI(label="Total Purchases", value=total_purchases, format_type="currency"),
            ReportKPI(label="Total Redemptions", value=total_redemptions, format_type="currency"),
            ReportKPI(label="Total Fees", value=total_fees, format_type="currency"),
            ReportKPI(label="Net Cashflow", value=net_cashflow, format_type="currency"),
        ]
        
        # Chart: top 10 sites by net cashflow
        chart_data = [(r["site_name"], r["net_cashflow"]) for r in rows[:10]]
        series = [
            ReportSeries(name="Net Cashflow by Site", data=chart_data, series_type="bar"),
        ]
        
        conn.close()
        
        return ReportResult(
            report_id="site_summary",
            title="Site Summary",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_game_performance(self, filters: ReportFilters) -> ReportResult:
        """Game Performance: sessions, wager, net P/L, RTP by game"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        date_where = "1=1"
        params = []
        
        if filters.start_date:
            date_where += " AND session_date >= ?"
            params.append(filters.start_date)
        
        if filters.end_date:
            date_where += " AND session_date <= ?"
            params.append(filters.end_date)
        
        c.execute(
            f"""
            SELECT 
                COALESCE(gs.game_name, 'Unknown') as game_name,
                COUNT(gs.id) as session_count,
                COALESCE(SUM(gs.wager_amount), 0) as total_wager,
                COALESCE(SUM(gs.net_taxable_pl), 0) as total_net_pl,
                CASE 
                    WHEN SUM(gs.wager_amount) > 0 
                    THEN (SUM(gs.wager_amount) + SUM(gs.net_taxable_pl)) / SUM(gs.wager_amount) * 100
                    ELSE NULL
                END as rtp_percent
            FROM game_sessions gs
            WHERE {date_where}
            GROUP BY gs.game_name
            HAVING session_count > 0
            ORDER BY total_wager DESC
            """,
            params,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # KPIs
        total_sessions = sum(r["session_count"] for r in rows)
        total_wager = sum(r["total_wager"] for r in rows)
        total_net_pl = sum(r["total_net_pl"] for r in rows)
        overall_rtp = ((total_wager + total_net_pl) / total_wager * 100) if total_wager > 0 else 0
        
        kpis = [
            ReportKPI(label="Total Sessions", value=total_sessions, format_type="number"),
            ReportKPI(label="Total Wager", value=total_wager, format_type="currency"),
            ReportKPI(label="Total Net P/L", value=total_net_pl, format_type="currency"),
            ReportKPI(label="Overall RTP", value=overall_rtp, format_type="percent"),
        ]
        
        # Chart: top 10 games by wager
        chart_data = [(r["game_name"], r["total_wager"]) for r in rows[:10]]
        series = [
            ReportSeries(name="Wager by Game", data=chart_data, series_type="bar"),
        ]
        
        conn.close()
        
        return ReportResult(
            report_id="game_performance",
            title="Game Performance",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_session_trend(self, filters: ReportFilters) -> ReportResult:
        """Session Trend: sessions over time with win rate and average net"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        date_where = "1=1"
        params = []
        
        if filters.start_date:
            date_where += " AND gs.session_date >= ?"
            params.append(filters.start_date)
        
        if filters.end_date:
            date_where += " AND gs.session_date <= ?"
            params.append(filters.end_date)
        
        bucket_expr = self._bucket_sql("gs.session_date", filters.group_interval)
        
        c.execute(
            f"""
            SELECT 
                {bucket_expr} as period,
                COUNT(gs.id) as session_count,
                COALESCE(AVG(gs.net_taxable_pl), 0) as avg_net_pl,
                SUM(CASE WHEN gs.net_taxable_pl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(gs.id) as win_rate
            FROM game_sessions gs
            WHERE {date_where}
            GROUP BY period
            ORDER BY period
            """,
            params,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # KPIs
        total_sessions = sum(r["session_count"] for r in rows)
        avg_net_pl = sum(r["avg_net_pl"] * r["session_count"] for r in rows) / total_sessions if total_sessions > 0 else 0
        
        c.execute(
            f"""
            SELECT 
                SUM(CASE WHEN net_taxable_pl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
            FROM game_sessions gs
            WHERE {date_where}
            """,
            params,
        )
        win_rate_row = c.fetchone()
        win_rate = win_rate_row["win_rate"] if win_rate_row else 0
        
        kpis = [
            ReportKPI(label="Total Sessions", value=total_sessions, format_type="number"),
            ReportKPI(label="Avg Net P/L", value=avg_net_pl, format_type="currency"),
            ReportKPI(label="Win Rate", value=win_rate, format_type="percent"),
        ]
        
        # Chart: session count over time
        chart_data = [(r["period"], r["session_count"]) for r in rows]
        series = [
            ReportSeries(name="Sessions Over Time", data=chart_data, series_type="line"),
        ]
        
        conn.close()
        
        return ReportResult(
            report_id="session_trend",
            title="Session Trend",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_redemption_timing(self, filters: ReportFilters) -> ReportResult:
        """Redemption Timing: lag analysis and volume by site/method"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        date_where = "1=1"
        params = []
        
        if filters.start_date:
            date_where += " AND redemption_date >= ?"
            params.append(filters.start_date)
        
        if filters.end_date:
            date_where += " AND redemption_date <= ?"
            params.append(filters.end_date)
        
        # Calculate average lag from redemption_date to receipt_date
        c.execute(
            f"""
            SELECT 
                s.name as site_name,
                rm.name as method_name,
                COUNT(r.id) as redemption_count,
                COALESCE(SUM(r.amount), 0) as total_amount,
                COALESCE(SUM(r.fees), 0) as total_fees,
                AVG(JULIANDAY(r.receipt_date) - JULIANDAY(r.redemption_date)) as avg_lag_days
            FROM redemptions r
            JOIN sites s ON r.site_id = s.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE {date_where}
            GROUP BY s.id, s.name, rm.id, rm.name
            ORDER BY total_amount DESC
            """,
            params,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # KPIs
        total_redemptions = sum(r["redemption_count"] for r in rows)
        total_amount = sum(r["total_amount"] for r in rows)
        total_fees = sum(r["total_fees"] for r in rows)
        weighted_lag = (
            sum(r["avg_lag_days"] * r["redemption_count"] for r in rows if r["avg_lag_days"])
            / total_redemptions
            if total_redemptions > 0
            else 0
        )
        
        kpis = [
            ReportKPI(label="Total Redemptions", value=total_redemptions, format_type="number"),
            ReportKPI(label="Total Amount", value=total_amount, format_type="currency"),
            ReportKPI(label="Total Fees", value=total_fees, format_type="currency"),
            ReportKPI(label="Avg Processing Lag", value=weighted_lag, format_type="number"),
        ]
        
        # Chart: redemptions by method
        method_summary = {}
        for r in rows:
            method = r["method_name"] or "Unknown"
            if method not in method_summary:
                method_summary[method] = 0
            method_summary[method] += r["total_amount"]
        
        chart_data = [(method, amount) for method, amount in sorted(method_summary.items(), key=lambda x: x[1], reverse=True)]
        series = [
            ReportSeries(name="Redemptions by Method", data=chart_data, series_type="bar"),
        ]
        
        conn.close()
        
        return ReportResult(
            report_id="redemption_timing",
            title="Redemption Timing Analysis",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_cashback_summary(self, filters: ReportFilters) -> ReportResult:
        """Cashback Summary: cashback earned by site and card"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        date_where = "1=1"
        params = []
        
        if filters.start_date:
            date_where += " AND purchase_date >= ?"
            params.append(filters.start_date)
        
        if filters.end_date:
            date_where += " AND purchase_date <= ?"
            params.append(filters.end_date)
        
        c.execute(
            f"""
            SELECT 
                s.name as site_name,
                c.name as card_name,
                COUNT(p.id) as purchase_count,
                COALESCE(SUM(p.amount), 0) as total_spent,
                COALESCE(SUM(p.cashback_earned), 0) as total_cashback
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            LEFT JOIN cards c ON p.card_id = c.id
            WHERE {date_where}
            GROUP BY s.id, s.name, c.id, c.name
            HAVING total_cashback > 0
            ORDER BY total_cashback DESC
            """,
            params,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # KPIs
        total_purchases = sum(r["purchase_count"] for r in rows)
        total_spent = sum(r["total_spent"] for r in rows)
        total_cashback = sum(r["total_cashback"] for r in rows)
        cashback_rate = (total_cashback / total_spent * 100) if total_spent > 0 else 0
        
        kpis = [
            ReportKPI(label="Total Purchases", value=total_purchases, format_type="number"),
            ReportKPI(label="Total Spent", value=total_spent, format_type="currency"),
            ReportKPI(label="Total Cashback", value=total_cashback, format_type="currency"),
            ReportKPI(label="Avg Cashback Rate", value=cashback_rate, format_type="percent"),
        ]
        
        # Chart: top 10 cards by cashback
        chart_data = [(r["card_name"] or "Unknown", r["total_cashback"]) for r in rows[:10]]
        series = [
            ReportSeries(name="Cashback by Card", data=chart_data, series_type="bar"),
        ]
        
        conn.close()
        
        return ReportResult(
            report_id="cashback_summary",
            title="Cashback Summary",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )
    
    def _run_tax_winnings_losses(self, filters: ReportFilters) -> ReportResult:
        """Tax Center: Tax Diary - Wins/Losses Summary"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        date_where_sessions = "1=1"
        date_where_expenses = "1=1"
        date_where_redemptions = "1=1"
        params_s = []
        params_e = []
        params_r = []
        
        if filters.start_date:
            date_where_sessions += " AND ts.session_date >= ?"
            date_where_expenses += " AND expense_date >= ?"
            date_where_redemptions += " AND redemption_date >= ?"
            params_s.append(filters.start_date)
            params_e.append(filters.start_date)
            params_r.append(filters.start_date)
        
        if filters.end_date:
            date_where_sessions += " AND ts.session_date <= ?"
            date_where_expenses += " AND expense_date <= ?"
            date_where_redemptions += " AND redemption_date <= ?"
            params_s.append(filters.end_date)
            params_e.append(filters.end_date)
            params_r.append(filters.end_date)
        
        # Calculate total session wins (positive sessions)
        c.execute(
            f"""
            SELECT 
                COUNT(*) as winning_sessions,
                COALESCE(SUM(rt.net_pl), 0) as total_wins
            FROM realized_transactions rt
            WHERE {date_where_redemptions}
              AND rt.net_pl > 0
            """,
            params_r,
        )
        wins_row = c.fetchone()
        winning_sessions = wins_row["winning_sessions"]
        total_wins = wins_row["total_wins"]
        
        # Calculate total session losses (negative sessions)
        c.execute(
            f"""
            SELECT 
                COUNT(*) as losing_sessions,
                COALESCE(SUM(ABS(rt.net_pl)), 0) as total_losses
            FROM realized_transactions rt
            WHERE {date_where_redemptions}
              AND rt.net_pl < 0
            """,
            params_r,
        )
        losses_row = c.fetchone()
        losing_sessions = losses_row["losing_sessions"]
        total_losses = losses_row["total_losses"]
        
        # Net session result
        net_session_result = total_wins - total_losses
        
        # Total business expenses
        c.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) as total_expenses
            FROM expenses
            WHERE {date_where_expenses}
            """,
            params_e,
        )
        total_expenses = c.fetchone()["total_expenses"]
        
        # Total redemption fees
        c.execute(
            f"""
            SELECT COALESCE(SUM(fees), 0) as total_fees
            FROM redemptions
            WHERE {date_where_redemptions}
            """,
            params_r,
        )
        total_fees = c.fetchone()["total_fees"]
        
        # Net after expenses and fees
        net_after_expenses = net_session_result - total_expenses - total_fees
        
        # Total sessions
        total_sessions = winning_sessions + losing_sessions
        win_rate = (winning_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        kpis = [
            ReportKPI(label="Total Session Wins", value=total_wins, format_type="currency"),
            ReportKPI(label="Total Session Losses", value=total_losses, format_type="currency"),
            ReportKPI(label="Net Session Result", value=net_session_result, format_type="currency"),
            ReportKPI(label="Business Expenses", value=total_expenses, format_type="currency"),
            ReportKPI(label="Redemption Fees", value=total_fees, format_type="currency"),
            ReportKPI(label="Net After Expenses", value=net_after_expenses, format_type="currency"),
        ]
        
        # Time series: wins and losses over time
        bucket_expr = self._bucket_sql("rt.redemption_date", filters.group_interval)
        
        c.execute(
            f"""
            SELECT 
                {bucket_expr} as period,
                SUM(CASE WHEN rt.net_pl > 0 THEN rt.net_pl ELSE 0 END) as period_wins,
                SUM(CASE WHEN rt.net_pl < 0 THEN ABS(rt.net_pl) ELSE 0 END) as period_losses,
                SUM(rt.net_pl) as period_net
            FROM realized_transactions rt
            WHERE {date_where_redemptions}
            GROUP BY period
            ORDER BY period
            """,
            params_r,
        )
        time_data = [self._row_to_dict(row) for row in c.fetchall()]
        
        wins_series_data = [(row["period"], row["period_wins"]) for row in time_data]
        losses_series_data = [(row["period"], row["period_losses"]) for row in time_data]
        net_series_data = [(row["period"], row["period_net"]) for row in time_data]
        
        series = [
            ReportSeries(name="Session Wins", data=wins_series_data, series_type="bar"),
            ReportSeries(name="Session Losses", data=losses_series_data, series_type="bar"),
            ReportSeries(name="Net Session Result", data=net_series_data, series_type="line"),
        ]
        
        # Detailed breakdown table by site
        c.execute(
            f"""
            SELECT 
                s.name as site_name,
                COUNT(rt.id) as total_sessions,
                SUM(CASE WHEN rt.net_pl > 0 THEN 1 ELSE 0 END) as winning_sessions,
                SUM(CASE WHEN rt.net_pl < 0 THEN 1 ELSE 0 END) as losing_sessions,
                COALESCE(SUM(CASE WHEN rt.net_pl > 0 THEN rt.net_pl ELSE 0 END), 0) as total_wins,
                COALESCE(SUM(CASE WHEN rt.net_pl < 0 THEN ABS(rt.net_pl) ELSE 0 END), 0) as total_losses,
                COALESCE(SUM(rt.net_pl), 0) as net_result,
                CASE 
                    WHEN COUNT(rt.id) > 0
                    THEN SUM(CASE WHEN rt.net_pl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(rt.id)
                    ELSE 0
                END as win_rate
            FROM sites s
            LEFT JOIN realized_transactions rt ON s.id = rt.site_id AND {date_where_redemptions}
            WHERE rt.id IS NOT NULL
            GROUP BY s.id, s.name
            HAVING total_sessions > 0
            ORDER BY net_result DESC
            """,
            params_r,
        )
        rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # Add expenses breakdown if requested
        c.execute(
            f"""
            SELECT 
                category,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as count
            FROM expenses
            WHERE {date_where_expenses}
            GROUP BY category
            ORDER BY total_amount DESC
            """,
            params_e,
        )
        expense_rows = [self._row_to_dict(row) for row in c.fetchall()]
        
        # Append expense summary to rows
        if expense_rows:
            rows.append({"site_name": "--- EXPENSES BREAKDOWN ---", "total_sessions": "", "winning_sessions": "", "losing_sessions": "", "total_wins": "", "total_losses": "", "net_result": "", "win_rate": ""})
            for exp in expense_rows:
                rows.append({
                    "site_name": f"  {exp['category'] or 'Uncategorized'}",
                    "total_sessions": exp["count"],
                    "winning_sessions": "",
                    "losing_sessions": "",
                    "total_wins": "",
                    "total_losses": exp["total_amount"],
                    "net_result": -exp["total_amount"],
                    "win_rate": ""
                })
        
        conn.close()
        
        return ReportResult(
            report_id="tax_winnings_losses",
            title="Session-Method Winnings/Losses (Tax Diary)",
            kpis=kpis,
            series=series,
            rows=rows,
            filters_applied=filters,
            generated_at=datetime.now(),
        )

