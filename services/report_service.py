"""
Report service for aggregating and analyzing data
"""
from collections import defaultdict
import re
from typing import Any, List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import date
from dataclasses import dataclass

from tools.timezone_utils import (
    get_configured_timezone_name,
    local_date_range_to_utc_bounds,
    utc_date_time_to_accounting_local,
)


_CLOSE_BALANCE_LOSS_RE = re.compile(r"Net Loss:\s*\$([0-9,]+(?:\.[0-9]{1,2})?)")
_DORMANT_SC_RE = re.compile(r"\((?:\$)?([0-9,]+(?:\.[0-9]{1,2})?)\s+SC marked dormant\)")


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

    def get_bridge_reconciliation_report(self) -> Dict[str, Any]:
        """Summarize basis roll-forward and economic-vs-session bridge figures by user/site pair."""
        from repositories.unrealized_position_repository import UnrealizedPositionRepository

        purchase_rows = self.db.fetch_all(
            """
            SELECT
                user_id,
                site_id,
                COALESCE(SUM(CAST(amount AS REAL)), 0) as total_purchases,
                COALESCE(SUM(CAST(remaining_amount AS REAL)), 0) as open_basis,
                COALESCE(SUM(CASE WHEN status = 'dormant' THEN CAST(remaining_amount AS REAL) ELSE 0 END), 0) as dormant_basis,
                COALESCE(SUM(CASE WHEN status IS NULL OR status = 'active' THEN CAST(remaining_amount AS REAL) ELSE 0 END), 0) as active_open_basis
            FROM purchases
            WHERE deleted_at IS NULL
            GROUP BY user_id, site_id
            """
        )
        realized_rows = self.db.fetch_all(
            """
            SELECT
                user_id,
                site_id,
                COALESCE(SUM(CAST(cost_basis AS REAL)), 0) as redeemed_basis,
                COALESCE(SUM(CAST(net_pl AS REAL)), 0) as realized_pl
            FROM realized_transactions
            GROUP BY user_id, site_id
            """
        )
        session_rows = self.db.fetch_all(
            """
            SELECT
                user_id,
                site_id,
                COALESCE(SUM(CAST(net_taxable_pl AS REAL)), 0) as session_pl
            FROM game_sessions
            WHERE deleted_at IS NULL AND net_taxable_pl IS NOT NULL
            GROUP BY user_id, site_id
            """
        )
        active_session_rows = self.db.fetch_all(
            """
            SELECT
                user_id,
                site_id,
                COUNT(*) as active_sessions
            FROM game_sessions
            WHERE deleted_at IS NULL AND status = 'Active'
            GROUP BY user_id, site_id
            """
        )
        pending_redemption_rows = self.db.fetch_all(
            """
            SELECT
                r.user_id,
                r.site_id,
                COUNT(*) as pending_redemptions,
                COALESCE(SUM(CAST(r.amount AS REAL)), 0) as pending_redemption_amount
            FROM redemptions r
            LEFT JOIN realized_transactions rt ON rt.redemption_id = r.id
            WHERE r.deleted_at IS NULL
              AND r.status IN ('PENDING', 'PENDING_CANCEL')
              AND rt.id IS NULL
            GROUP BY r.user_id, r.site_id
            """
        )
        close_marker_event_rows = self.db.fetch_all(
            """
            SELECT
                r.user_id,
                r.site_id,
                r.id as redemption_id,
                r.redemption_date,
                COALESCE(r.redemption_time, '00:00:00') as redemption_time,
                r.notes,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM realized_transactions rt
                    WHERE rt.redemption_id = r.id
                ) THEN 1 ELSE 0 END as has_realized_row
            FROM redemptions r
            WHERE r.deleted_at IS NULL
              AND r.notes LIKE 'Balance Closed - Net Loss:%'
            ORDER BY r.site_id, r.user_id, r.redemption_date, COALESCE(r.redemption_time, '00:00:00'), r.id
            """
        )
        realized_event_rows = self.db.fetch_all(
            """
            SELECT
                rt.user_id,
                rt.site_id,
                rt.redemption_date,
                COALESCE(r.redemption_time, '00:00:00') as redemption_time,
                COALESCE(CAST(rt.net_pl AS REAL), 0) as net_pl,
                COALESCE(CAST(r.amount AS REAL), 0) as redemption_amount,
                COALESCE(r.more_remaining, 1) as more_remaining,
                r.notes
            FROM realized_transactions rt
            LEFT JOIN redemptions r ON r.id = rt.redemption_id
            ORDER BY rt.site_id, rt.user_id, rt.redemption_date, COALESCE(r.redemption_time, '00:00:00'), rt.redemption_id
            """
        )
        session_event_rows = self.db.fetch_all(
            """
            SELECT
                user_id,
                site_id,
                session_date,
                COALESCE(session_time, '00:00:00') as session_time,
                COALESCE(CAST(delta_redeem AS REAL), 0) as delta_redeem,
                COALESCE(CAST(ending_redeemable AS REAL), 0) as ending_redeemable,
                COALESCE(CAST(net_taxable_pl AS REAL), 0) as net_taxable_pl
            FROM game_sessions
            WHERE deleted_at IS NULL AND net_taxable_pl IS NOT NULL
            ORDER BY site_id, user_id, session_date, COALESCE(session_time, '00:00:00'), id
            """
        )
        user_rows = self.db.fetch_all("SELECT id, name FROM users")
        site_rows = self.db.fetch_all("SELECT id, name FROM sites")

        user_names = {row["id"]: row["name"] for row in user_rows}
        site_names = {row["id"]: row["name"] for row in site_rows}

        purchases_by_pair: Dict[Tuple[int, int], Dict[str, Decimal]] = {}
        for row in purchase_rows:
            purchases_by_pair[(row["user_id"], row["site_id"])] = {
                "total_purchases": Decimal(str(row["total_purchases"])),
                "open_basis": Decimal(str(row["open_basis"])),
                "dormant_basis": Decimal(str(row["dormant_basis"])),
                "active_open_basis": Decimal(str(row["active_open_basis"])),
            }

        realized_by_pair: Dict[Tuple[int, int], Dict[str, Decimal]] = {}
        for row in realized_rows:
            realized_by_pair[(row["user_id"], row["site_id"])] = {
                "redeemed_basis": Decimal(str(row["redeemed_basis"])),
                "realized_pl": Decimal(str(row["realized_pl"])),
            }

        session_by_pair: Dict[Tuple[int, int], Decimal] = {}
        for row in session_rows:
            session_by_pair[(row["user_id"], row["site_id"])] = Decimal(str(row["session_pl"]))

        active_sessions_by_pair: Dict[Tuple[int, int], int] = {}
        for row in active_session_rows:
            active_sessions_by_pair[(row["user_id"], row["site_id"])] = int(row["active_sessions"])

        pending_redemptions_by_pair: Dict[Tuple[int, int], Dict[str, Decimal | int]] = {}
        for row in pending_redemption_rows:
            pending_redemptions_by_pair[(row["user_id"], row["site_id"])] = {
                "count": int(row["pending_redemptions"]),
                "amount": Decimal(str(row["pending_redemption_amount"])),
            }

        unrealized_positions = UnrealizedPositionRepository(self.db).get_all_positions()
        unrealized_by_pair: Dict[Tuple[int, int], Dict[str, Decimal | int]] = defaultdict(
            lambda: {
                "pairs": 0,
                "basis": Decimal("0.00"),
                "value": Decimal("0.00"),
                "unrealized_pl": Decimal("0.00"),
            }
        )
        for position in unrealized_positions:
            bucket = unrealized_by_pair[(position.user_id, position.site_id)]
            bucket["pairs"] += 1
            bucket["basis"] += Decimal(str(position.purchase_basis))
            bucket["value"] += Decimal(str(position.current_value))
            bucket["unrealized_pl"] += Decimal(str(position.unrealized_pl))

        bridge_components_by_pair, unmatched_sessions_by_pair = self._build_bridge_components_by_pair(
            realized_event_rows,
            session_event_rows,
        )
        close_marker_events_by_pair = self._build_close_marker_events_by_pair(close_marker_event_rows)
        latest_session_dt_by_pair = self._build_latest_session_dt_by_pair(session_event_rows)

        pair_keys = (
            set(purchases_by_pair)
            | set(realized_by_pair)
            | set(session_by_pair)
            | set(active_sessions_by_pair)
            | set(pending_redemptions_by_pair)
        )

        totals = {
            "total_purchases": Decimal("0.00"),
            "redeemed_basis": Decimal("0.00"),
            "open_basis": Decimal("0.00"),
            "basis_delta": Decimal("0.00"),
            "realized_pl": Decimal("0.00"),
            "economic_pl": Decimal("0.00"),
            "session_pl": Decimal("0.00"),
            "bridge_gap": Decimal("0.00"),
        }
        report_rows = []

        for user_id, site_id in sorted(
            pair_keys,
            key=lambda value: (
                site_names.get(value[1], f"Site {value[1]}").lower(),
                user_names.get(value[0], f"User {value[0]}").lower(),
            ),
        ):
            pair_key = (user_id, site_id)
            purchase_data = purchases_by_pair.get(
                pair_key,
                {
                    "total_purchases": Decimal("0.00"),
                    "open_basis": Decimal("0.00"),
                    "dormant_basis": Decimal("0.00"),
                    "active_open_basis": Decimal("0.00"),
                },
            )
            realized_data = realized_by_pair.get(
                pair_key,
                {"redeemed_basis": Decimal("0.00"), "realized_pl": Decimal("0.00")},
            )
            session_pl = session_by_pair.get(pair_key, Decimal("0.00"))
            active_sessions = active_sessions_by_pair.get(pair_key, 0)
            pending_redemptions = pending_redemptions_by_pair.get(
                pair_key,
                {"count": 0, "amount": Decimal("0.00")},
            )
            unrealized_summary = unrealized_by_pair.get(
                pair_key,
                {
                    "pairs": 0,
                    "basis": Decimal("0.00"),
                    "value": Decimal("0.00"),
                    "unrealized_pl": Decimal("0.00"),
                },
            )
            bridge_components = bridge_components_by_pair.get(pair_key, [])
            unmatched_sessions = unmatched_sessions_by_pair.get(pair_key, [])
            close_marker_events = close_marker_events_by_pair.get(pair_key, [])

            basis_delta = (
                purchase_data["total_purchases"]
                - realized_data["redeemed_basis"]
                - purchase_data["open_basis"]
            )
            economic_pl = realized_data["realized_pl"]
            raw_bridge_gap = (economic_pl - session_pl).quantize(Decimal("0.01"))
            actionable_bridge_components, historical_bridge_components = self._split_bridge_components_for_current_state(
                bridge_components,
                latest_session_dt_by_pair.get(pair_key),
            )
            bridge_gap = (
                sum(
                    (Decimal(str(component.get("current_state_diff", component["diff"]))) for component in actionable_bridge_components),
                    Decimal("0.00"),
                )
                + sum(
                    (Decimal("0.00") - Decimal(str(session["net_taxable_pl"])) for session in unmatched_sessions),
                    Decimal("0.00"),
                )
            ).quantize(Decimal("0.01"))
            bridge_gap_explanation, bridge_gap_detail = self._build_bridge_gap_explanation(
                bridge_gap=bridge_gap,
                raw_bridge_gap=raw_bridge_gap,
                open_basis=purchase_data["open_basis"],
                dormant_basis=purchase_data["dormant_basis"],
                active_open_basis=purchase_data["active_open_basis"],
                active_sessions=active_sessions,
                pending_redemptions=int(pending_redemptions["count"]),
                pending_redemption_amount=Decimal(str(pending_redemptions["amount"])),
                bridge_components=actionable_bridge_components,
                suppressed_bridge_components=historical_bridge_components,
                unmatched_sessions=unmatched_sessions,
                close_marker_events=close_marker_events,
                unrealized_pairs=int(unrealized_summary["pairs"]),
                unrealized_basis=Decimal(str(unrealized_summary["basis"])),
                unrealized_value=Decimal(str(unrealized_summary["value"])),
                unrealized_pl=Decimal(str(unrealized_summary["unrealized_pl"])),
                realized_pl=realized_data["realized_pl"],
                session_pl=session_pl,
            )

            row = {
                "user_id": user_id,
                "site_id": site_id,
                "user_name": user_names.get(user_id, f"User {user_id}"),
                "site_name": site_names.get(site_id, f"Site {site_id}"),
                "total_purchases": purchase_data["total_purchases"],
                "redeemed_basis": realized_data["redeemed_basis"],
                "open_basis": purchase_data["open_basis"],
                "basis_delta": basis_delta,
                "realized_pl": realized_data["realized_pl"],
                "economic_pl": economic_pl,
                "session_pl": session_pl,
                "bridge_gap": bridge_gap,
                "raw_bridge_gap": raw_bridge_gap,
                "bridge_gap_explanation": bridge_gap_explanation,
                "bridge_gap_detail": bridge_gap_detail,
            }
            report_rows.append(row)

            for key in totals:
                totals[key] += row[key]

        return {
            "site_rows": report_rows,
            "totals": totals,
        }

    @staticmethod
    def _build_bridge_gap_explanation(
        bridge_gap: Decimal,
        raw_bridge_gap: Decimal,
        open_basis: Decimal,
        dormant_basis: Decimal,
        active_open_basis: Decimal,
        active_sessions: int,
        pending_redemptions: int,
        pending_redemption_amount: Decimal,
        bridge_components: List[Dict[str, Any]],
        suppressed_bridge_components: List[Dict[str, Any]],
        unmatched_sessions: List[Dict[str, Any]],
        close_marker_events: List[Dict[str, Any]],
        unrealized_pairs: int,
        unrealized_basis: Decimal,
        unrealized_value: Decimal,
        unrealized_pl: Decimal,
        realized_pl: Decimal,
        session_pl: Decimal,
    ) -> Tuple[str, str]:
        """Return a concise additive summary plus a human-readable audit detail."""
        additive_summaries: List[str] = []
        additive_details: List[str] = []
        context_lines: List[str] = []
        generic_redemption_components = [
            component
            for component in bridge_components
            if not component.get("is_close_balance") and not component.get("is_full_redemption_rounding_remainder")
        ]
        should_group_generic_redemptions = len(generic_redemption_components) > 3

        if should_group_generic_redemptions:
            generic_net = sum(
                (Decimal(str(component["diff"])) for component in generic_redemption_components),
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))
            if abs(generic_net) >= Decimal("0.005"):
                first_date = generic_redemption_components[0]["date"]
                last_date = generic_redemption_components[-1]["date"]
                additive_summaries.append(
                    f"{ReportService._format_currency(generic_net)} across {len(generic_redemption_components)} redemption timing differences"
                )
                additive_details.append(
                    f"{ReportService._format_currency(generic_net)} across {len(generic_redemption_components)} redemption timing differences from {first_date} to {last_date}. These redemption/session timing items offset each other except for the net amount shown here."
                )

        for component in bridge_components:
            if should_group_generic_redemptions and not component.get("is_close_balance") and not component.get("is_full_redemption_rounding_remainder"):
                continue
            if component.get("is_close_balance"):
                if component.get("is_close_balance_redeemable_remainder"):
                    additive_summaries.append(
                        f"{ReportService._format_currency(component['diff'])} on {component['date']} close left dormant redeemable on site"
                    )
                    additive_details.append(
                        f"{ReportService._format_currency(component['diff'])} on {component['display_label']}: the latest closed session ended with {ReportService._format_currency(component['normalized_ending_redeemable'])} still redeemable on site, and the subsequent close marker parked that amount dormant."
                    )
                else:
                    additive_summaries.append(
                        f"{ReportService._format_currency(component['diff'])} on {component['date']} close marker vs sessions"
                    )
                    additive_details.append(
                        f"{ReportService._format_currency(component['diff'])} on {component['display_label']}: close marker realized {ReportService._format_currency(component['net_pl'])} while closed sessions since the prior redemption total {ReportService._format_currency(component['session_sum'])}."
                    )
            elif component.get("is_partial_redemption_remainder"):
                additive_summaries.append(
                    f"{ReportService._format_currency(component['current_state_diff'])} on {component['date']} partial redemption left redeemable on site"
                )
                additive_details.append(
                    f"{ReportService._format_currency(component['current_state_diff'])} on {component['display_label']}: partial redemption paid {ReportService._format_currency(component['redemption_amount'])} while {ReportService._format_currency(component['ending_redeemable'])} was still redeemable on site at close, leaving {ReportService._format_currency(component['total_remainder'])} still on site for a later redemption."
                )
            elif component.get("is_full_redemption_rounding_remainder"):
                additive_summaries.append(
                    f"{ReportService._format_currency(component['current_state_diff'])} on {component['date']} full redemption left dormant SC on site"
                )
                additive_details.append(
                    f"{ReportService._format_currency(component['current_state_diff'])} on {component['display_label']}: full redemption paid {ReportService._format_currency(component['redemption_amount'])} against {ReportService._format_currency(component['ending_redeemable'])} redeemable on site at close, leaving {ReportService._format_currency(component['total_remainder'])} parked on site as dormant SC."
                )
            else:
                additive_summaries.append(
                    f"{ReportService._format_currency(component['diff'])} on {component['date']} redemption timing difference"
                )
                additive_details.append(
                    f"{ReportService._format_currency(component['diff'])} on {component['display_label']}: redemption realized {ReportService._format_currency(component['net_pl'])} while closed sessions since the prior redemption total {ReportService._format_currency(component['session_sum'])}."
                )

        for session in unmatched_sessions:
            unmatched_amount = Decimal("0.00") - Decimal(str(session["net_taxable_pl"]))
            additive_summaries.append(
                f"{ReportService._format_currency(unmatched_amount)} on {session['date']} closed session not yet redeemed"
            )
            additive_details.append(
                f"{ReportService._format_currency(unmatched_amount)} on {session['display_label']}: closed session P/L was {ReportService._format_currency(session['net_taxable_pl'])} but there is no later redemption tied to it."
            )

        zero_basis_close_markers = [
            marker for marker in close_marker_events if not marker.get("has_realized_row")
        ]
        for marker in zero_basis_close_markers:
            dormant_sc = Decimal(str(marker["dormant_sc"]))
            net_loss = Decimal(str(marker["net_loss"]))
            if dormant_sc > Decimal("0.005") or net_loss > Decimal("0.005"):
                context_lines.append(
                    f"{marker['display_label']} close marker parked {dormant_sc:,.2f} SC dormant with no realized row."
                )

        if unmatched_sessions and not zero_basis_close_markers:
            context_lines.append(
                "No later redemption or close marker was found after the unmatched closed session activity."
            )

        if dormant_basis > Decimal("0.005"):
            context_lines.append(
                f"Dormant purchase basis still parked: {ReportService._format_currency(dormant_basis)}."
            )

        if unrealized_pairs > 0:
            context_lines.append(
                "Unrealized still shows "
                f"{unrealized_pairs} pair(s), basis {ReportService._format_currency(unrealized_basis)}, "
                f"est value {ReportService._format_currency(unrealized_value)}, unrealized P/L {ReportService._format_currency(unrealized_pl)}."
            )

        if pending_redemptions > 0:
            context_lines.append(
                f"Pending redemptions without realized rows: {pending_redemptions} for {ReportService._format_currency(pending_redemption_amount)}."
            )

        if not additive_summaries and (active_open_basis > Decimal("0.005") or (open_basis > Decimal("0.005") and active_sessions > 0)):
            open_balance = active_open_basis if active_open_basis > Decimal("0.005") else open_basis
            context_lines.append(
                f"Active open basis still on site: {ReportService._format_currency(open_balance)}."
            )

        if not additive_summaries:
            if abs(bridge_gap) < Decimal("0.005"):
                additive_details.append(
                    "No current actionable gap remains."
                )
            elif abs(session_pl) < Decimal("0.005") and abs(realized_pl) >= Decimal("0.005"):
                additive_summaries.append(
                    f"{ReportService._format_currency(bridge_gap)} realized activity without matching session P/L"
                )
                additive_details.append(
                    f"{ReportService._format_currency(bridge_gap)} remains because realized activity totals {ReportService._format_currency(realized_pl)} while session P/L is {ReportService._format_currency(session_pl)}."
                )
            elif abs(realized_pl) < Decimal("0.005") and abs(session_pl) >= Decimal("0.005"):
                additive_summaries.append(
                    f"{ReportService._format_currency(bridge_gap)} session activity without matching realized row"
                )
                additive_details.append(
                    f"{ReportService._format_currency(bridge_gap)} remains because session P/L totals {ReportService._format_currency(session_pl)} while realized activity is {ReportService._format_currency(realized_pl)}."
                )
            else:
                additive_summaries.append(
                    f"{ReportService._format_currency(bridge_gap)} needs manual audit"
                )
                additive_details.append(
                    f"{ReportService._format_currency(bridge_gap)} could not be tied to a specific redemption or unmatched closed session with the current audit rules."
                )

        if abs(bridge_gap) < Decimal("0.005"):
            additive_summaries = []
            additive_details = ["No current actionable gap remains."]

        detail_lines = [f"Current actionable gap: {ReportService._format_currency(bridge_gap)}"]
        detail_lines.extend([
            "",
            "Audit items that add up to the current actionable gap:",
        ])
        detail_lines.extend(f"- {line}" for line in additive_details)
        if context_lines:
            detail_lines.extend([
                "",
                "Context:",
            ])
            detail_lines.extend(f"- {line}" for line in context_lines)

        return "; ".join(additive_summaries), "\n".join(detail_lines)

    def _build_bridge_components_by_pair(self, realized_event_rows, session_event_rows):
        sessions_by_pair: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
        for row in session_event_rows:
            local_date, local_time = utc_date_time_to_accounting_local(
                self.db,
                row["session_date"],
                row["session_time"],
            )
            sessions_by_pair[(row["user_id"], row["site_id"])].append(
                {
                    "dt": ReportService._dt_key(row["session_date"], row["session_time"]),
                    "date": local_date.isoformat(),
                    "display_label": f"{local_date.isoformat()} {local_time}",
                    "delta_redeem": Decimal(str(row["delta_redeem"])),
                    "ending_redeemable": Decimal(str(row["ending_redeemable"])),
                    "net_taxable_pl": Decimal(str(row["net_taxable_pl"])),
                }
            )

        realized_by_pair: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
        for row in realized_event_rows:
            local_date, local_time = utc_date_time_to_accounting_local(
                self.db,
                row["redemption_date"],
                row["redemption_time"],
            )
            realized_by_pair[(row["user_id"], row["site_id"])].append(
                {
                    "dt": ReportService._dt_key(row["redemption_date"], row["redemption_time"]),
                    "date": local_date.isoformat(),
                    "display_label": f"{local_date.isoformat()} {local_time}",
                    "net_pl": Decimal(str(row["net_pl"])),
                    "redemption_amount": Decimal(str(row["redemption_amount"])),
                    "more_remaining": bool(row["more_remaining"]),
                    "notes": row.get("notes") or "",
                }
            )

        bridge_components_by_pair: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        unmatched_sessions_by_pair: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        pair_keys = set(sessions_by_pair) | set(realized_by_pair)

        for pair_key in pair_keys:
            components: List[Dict[str, Any]] = []
            sessions = sessions_by_pair.get(pair_key, [])
            realized = realized_by_pair.get(pair_key, [])
            session_index = 0
            previous_dt = None

            for event in realized:
                session_sum = Decimal("0.00")
                redeemable_sum = Decimal("0.00")
                last_session_ending_redeemable = Decimal("0.00")
                while session_index < len(sessions):
                    session = sessions[session_index]
                    if previous_dt is not None and session["dt"] <= previous_dt:
                        session_index += 1
                        continue
                    if session["dt"] > event["dt"]:
                        break
                    session_sum += session["net_taxable_pl"]
                    redeemable_sum += session["delta_redeem"]
                    last_session_ending_redeemable = session["ending_redeemable"]
                    session_index += 1

                diff = event["net_pl"] - session_sum
                if abs(diff) >= Decimal("0.005"):
                    normalized_redeemable_sum = ReportService._normalize_redeemable_amount(
                        redeemable_sum,
                        event["redemption_amount"],
                    )
                    normalized_ending_redeemable = ReportService._normalize_redeemable_amount(
                        last_session_ending_redeemable,
                        event["redemption_amount"],
                    )
                    rounding_remainder = (normalized_redeemable_sum - event["redemption_amount"]).quantize(Decimal("0.01"))
                    total_remainder = (normalized_ending_redeemable - event["redemption_amount"]).quantize(Decimal("0.01"))
                    is_close_balance_redeemable_remainder = (
                        bool(event["notes"].startswith("Balance Closed - Net Loss:"))
                        and normalized_ending_redeemable > Decimal("0.00")
                        and abs(abs(diff) - normalized_ending_redeemable) < Decimal("0.005")
                    )
                    is_partial_redemption_remainder = (
                        event["more_remaining"]
                        and normalized_ending_redeemable > event["redemption_amount"]
                        and total_remainder > Decimal("0.00")
                    )
                    is_whole_dollar_full_redemption = (
                        not event["notes"].startswith("Balance Closed - Net Loss:")
                        and not event["more_remaining"]
                        and event["redemption_amount"] == event["redemption_amount"].quantize(Decimal("1"))
                        and total_remainder > Decimal("0.00")
                        and total_remainder < Decimal("1.00")
                        and normalized_ending_redeemable > Decimal("0.00")
                    )
                    components.append(
                        {
                            "dt": event["dt"],
                            "date": event["date"],
                            "display_label": event["display_label"],
                            "diff": diff,
                            "current_state_diff": (
                                Decimal("0.00") - total_remainder
                                if (is_whole_dollar_full_redemption or is_partial_redemption_remainder)
                                else diff
                            ),
                            "net_pl": event["net_pl"],
                            "session_sum": session_sum,
                            "redeemable_sum": normalized_redeemable_sum,
                            "ending_redeemable": normalized_ending_redeemable,
                            "normalized_ending_redeemable": normalized_ending_redeemable,
                            "redemption_amount": event["redemption_amount"],
                            "rounding_remainder": rounding_remainder,
                            "total_remainder": total_remainder,
                            "is_full_redemption_rounding_remainder": is_whole_dollar_full_redemption,
                            "is_partial_redemption_remainder": is_partial_redemption_remainder,
                            "is_close_balance_redeemable_remainder": is_close_balance_redeemable_remainder,
                            "is_close_balance": bool(event["notes"].startswith("Balance Closed - Net Loss:")),
                        }
                    )
                previous_dt = event["dt"]

            unmatched_sessions: List[Dict[str, Any]] = []
            while session_index < len(sessions):
                session = sessions[session_index]
                if abs(session["net_taxable_pl"]) >= Decimal("0.005"):
                    unmatched_sessions.append(
                        {
                            "date": session["date"],
                            "display_label": session["display_label"],
                            "net_taxable_pl": session["net_taxable_pl"],
                        }
                    )
                session_index += 1

            bridge_components_by_pair[pair_key] = components
            unmatched_sessions_by_pair[pair_key] = unmatched_sessions

        return bridge_components_by_pair, unmatched_sessions_by_pair

    @staticmethod
    def _build_latest_session_dt_by_pair(session_event_rows):
        latest_session_dt_by_pair: Dict[Tuple[int, int], str] = {}
        for row in session_event_rows:
            dt = ReportService._dt_key(row["session_date"], row["session_time"])
            pair_key = (row["user_id"], row["site_id"])
            if dt > latest_session_dt_by_pair.get(pair_key, ""):
                latest_session_dt_by_pair[pair_key] = dt
        return latest_session_dt_by_pair

    @staticmethod
    def _split_bridge_components_for_current_state(bridge_components, latest_session_dt):
        latest_actionable_remainder_component = None
        latest_component_dt = max((component.get("dt", "") for component in bridge_components), default="")
        for component in bridge_components:
            is_current_state_remainder = (
                component.get("is_full_redemption_rounding_remainder")
                or component.get("is_partial_redemption_remainder")
                or component.get("is_close_balance_redeemable_remainder")
            )
            component_dt = component.get("dt", "")
            has_later_session = bool(component_dt and latest_session_dt and latest_session_dt > component_dt)
            has_later_realized_component = bool(component_dt and latest_component_dt and latest_component_dt > component_dt)
            if is_current_state_remainder and not has_later_session and not has_later_realized_component:
                if latest_actionable_remainder_component is None or component.get("dt", "") > latest_actionable_remainder_component.get("dt", ""):
                    latest_actionable_remainder_component = component

        if latest_actionable_remainder_component is not None:
            actionable_components = [latest_actionable_remainder_component]
            historical_components = [
                component
                for component in bridge_components
                if component is not latest_actionable_remainder_component
            ]
            return actionable_components, historical_components

        actionable_components: List[Dict[str, Any]] = []
        historical_components: List[Dict[str, Any]] = []

        for component in bridge_components:
            component_dt = component.get("dt", "")
            has_later_session = bool(component_dt and latest_session_dt and latest_session_dt > component_dt)
            has_later_realized_component = bool(component_dt and latest_component_dt and latest_component_dt > component_dt)
            is_remainder_component = (
                component.get("is_full_redemption_rounding_remainder")
                or component.get("is_partial_redemption_remainder")
                or component.get("is_close_balance_redeemable_remainder")
            )

            if is_remainder_component and (has_later_session or has_later_realized_component):
                historical_components.append(component)
                continue

            if component.get("is_close_balance") and has_later_session:
                historical_components.append(component)
                continue
            actionable_components.append(component)

        resolved_partial_remainders = [
            component
            for component in historical_components
            if component.get("is_partial_redemption_remainder")
        ]
        if resolved_partial_remainders:
            remaining_actionable_components: List[Dict[str, Any]] = []
            for component in actionable_components:
                component_dt = component.get("dt", "")
                matched_resolved_partial = next(
                    (
                        partial_component
                        for partial_component in resolved_partial_remainders
                        if component_dt > partial_component.get("dt", "")
                        and not component.get("is_close_balance")
                        and not component.get("is_full_redemption_rounding_remainder")
                        and not component.get("is_partial_redemption_remainder")
                        and abs(
                            Decimal(str(component.get("redemption_amount", Decimal("0.00"))))
                            - Decimal(str(partial_component.get("total_remainder", Decimal("0.00"))))
                        )
                        < Decimal("0.01")
                    ),
                    None,
                )
                if matched_resolved_partial is not None:
                    historical_components.append(component)
                    resolved_partial_remainders.remove(matched_resolved_partial)
                    continue
                remaining_actionable_components.append(component)
            actionable_components = remaining_actionable_components

        close_marker_carryover = sum(
            (
                Decimal(str(component.get("current_state_diff", component["diff"])))
                for component in historical_components
                if component.get("is_close_balance")
            ),
            Decimal("0.00"),
        )

        if abs(close_marker_carryover) < Decimal("0.005"):
            return actionable_components, historical_components

        adjusted_actionable_components: List[Dict[str, Any]] = []
        for component in actionable_components:
            component_diff = Decimal(str(component.get("current_state_diff", component["diff"])))
            is_generic_realized_component = (
                not component.get("is_close_balance")
                and not component.get("is_full_redemption_rounding_remainder")
            )
            if is_generic_realized_component and component_diff * close_marker_carryover < 0:
                if abs(component_diff) <= abs(close_marker_carryover) + Decimal("0.0001"):
                    close_marker_carryover += component_diff
                    historical_components.append(component)
                    continue
                adjusted_component = dict(component)
                if component_diff > 0:
                    adjusted_component["current_state_diff"] = (component_diff + close_marker_carryover).quantize(Decimal("0.01"))
                else:
                    adjusted_component["current_state_diff"] = (component_diff + close_marker_carryover).quantize(Decimal("0.01"))
                close_marker_carryover = Decimal("0.00")
                adjusted_actionable_components.append(adjusted_component)
                continue

            adjusted_actionable_components.append(component)

        return adjusted_actionable_components, historical_components

    def _build_close_marker_events_by_pair(self, close_marker_event_rows):
        close_marker_events_by_pair: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
        for row in close_marker_event_rows:
            local_date, local_time = utc_date_time_to_accounting_local(
                self.db,
                row["redemption_date"],
                row["redemption_time"],
            )
            close_marker_events_by_pair[(row["user_id"], row["site_id"])].append(
                {
                    "date": local_date.isoformat(),
                    "display_label": f"{local_date.isoformat()} {local_time}",
                    "dt": ReportService._dt_key(row["redemption_date"], row["redemption_time"]),
                    "has_realized_row": bool(row["has_realized_row"]),
                    "net_loss": ReportService._parse_close_balance_loss(row.get("notes")),
                    "dormant_sc": ReportService._parse_dormant_sc(row.get("notes")),
                    "notes": row.get("notes") or "",
                }
            )
        return close_marker_events_by_pair

    @staticmethod
    def _dt_key(date_value: str, time_value: str) -> str:
        return f"{date_value} {time_value or '00:00:00'}"

    @staticmethod
    def _parse_close_balance_loss(notes: Optional[str]) -> Decimal:
        if not notes:
            return Decimal("0.00")
        match = _CLOSE_BALANCE_LOSS_RE.search(notes)
        if not match:
            return Decimal("0.00")
        return Decimal(match.group(1).replace(",", ""))

    @staticmethod
    def _parse_dormant_sc(notes: Optional[str]) -> Decimal:
        if not notes:
            return Decimal("0.00")
        match = _DORMANT_SC_RE.search(notes)
        if not match:
            return Decimal("0.00")
        return Decimal(match.group(1).replace(",", ""))

    @staticmethod
    def _format_currency(value: Decimal) -> str:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if abs(amount) < Decimal("0.005"):
            amount = Decimal("0.00")
        sign = "-" if amount < 0 else ""
        return f"{sign}${abs(amount):,.2f}"

    @staticmethod
    def _normalize_redeemable_amount(raw_amount: Decimal, reference_amount: Decimal) -> Decimal:
        amount = raw_amount if isinstance(raw_amount, Decimal) else Decimal(str(raw_amount))
        reference = reference_amount if isinstance(reference_amount, Decimal) else Decimal(str(reference_amount))
        if amount == Decimal("0.00"):
            return Decimal("0.00")

        candidates = [amount]
        if amount.copy_abs() >= Decimal("1.00"):
            candidates.append((amount / Decimal("100")).quantize(Decimal("0.01")))

        target = reference.copy_abs()
        best = min(candidates, key=lambda candidate: abs(candidate.copy_abs() - target))
        return best.quantize(Decimal("0.01"))
