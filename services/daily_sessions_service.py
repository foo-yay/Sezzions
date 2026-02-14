"""
Daily sessions service - aggregates closed game sessions by date/user
"""
from datetime import date as date_type
from typing import Iterable, List, Dict, Optional, Tuple


class DailySessionsService:
    def __init__(self, db_manager, daily_session_repo=None):
        self.db = db_manager
        self.daily_session_repo = daily_session_repo

    def _table_exists(self, table_name: str) -> bool:
        row = self.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return bool(row)

    def fetch_sessions(
        self,
        selected_users: Optional[Iterable[str]] = None,
        selected_sites: Optional[Iterable[str]] = None,
        active_date_filter: Tuple[Optional[date_type], Optional[date_type]] = (None, None),
    ) -> List[Dict]:
        query = """
            SELECT
                gs.session_date,
                gs.user_id,
                u.name as user_name,
                gs.site_id,
                s.name as site_name,
                gs.id,
                gs.status,
                gt.name as game_type,
                g.name as game_name,
                gs.starting_balance as starting_sc_balance,
                gs.ending_balance as ending_sc_balance,
                COALESCE(gs.session_time, '00:00:00') as start_time,
                gs.end_date as end_date,
                COALESCE(gs.end_time, '') as end_time,
                COALESCE(gs.delta_total, gs.ending_balance - gs.starting_balance, 0) as delta_total,
                gs.delta_redeem,
                COALESCE(gs.starting_redeemable, gs.starting_balance) as starting_redeem,
                COALESCE(gs.ending_redeemable, gs.ending_balance) as ending_redeem,
                COALESCE(gs.basis_consumed, gs.session_basis) as basis_consumed,
                COALESCE(gs.net_taxable_pl, 0) as total_taxable,
                gs.notes
            FROM game_sessions gs
            JOIN users u ON gs.user_id = u.id
            JOIN sites s ON gs.site_id = s.id
            LEFT JOIN games g ON gs.game_id = g.id
            LEFT JOIN game_types gt ON g.game_type_id = gt.id
            WHERE gs.status = 'Closed' AND gs.deleted_at IS NULL
        """
        params: List = []

        if selected_users:
            users = sorted({name for name in selected_users if name})
            if users:
                placeholders = ",".join("?" * len(users))
                query += f" AND u.name IN ({placeholders})"
                params.extend(users)

        if selected_sites:
            sites = sorted({name for name in selected_sites if name})
            if sites:
                placeholders = ",".join("?" * len(sites))
                query += f" AND s.name IN ({placeholders})"
                params.extend(sites)

        start_date, end_date = active_date_filter
        from tools.timezone_utils import get_configured_timezone_name, local_date_range_to_utc_bounds
        tz_name = get_configured_timezone_name()

        if not start_date and not end_date:
            start_date = date_type(date_type.today().year, 1, 1)
            end_date = date_type.today()

        if start_date:
            start_utc, _ = local_date_range_to_utc_bounds(start_date, start_date, tz_name)
            query += " AND (COALESCE(gs.end_date, gs.session_date) > ? OR (COALESCE(gs.end_date, gs.session_date) = ? AND COALESCE(gs.end_time, gs.session_time, '00:00:00') >= ?))"
            params.extend([start_utc[0], start_utc[0], start_utc[1]])

        if end_date:
            _, end_utc = local_date_range_to_utc_bounds(end_date, end_date, tz_name)
            query += " AND (COALESCE(gs.end_date, gs.session_date) < ? OR (COALESCE(gs.end_date, gs.session_date) = ? AND COALESCE(gs.end_time, gs.session_time, '00:00:00') <= ?))"
            params.extend([end_utc[0], end_utc[0], end_utc[1]])

        query += " ORDER BY gs.session_date DESC, u.name, s.name, gs.session_time"
        rows = self.db.fetch_all(query, tuple(params))

        sessions: List[Dict] = []
        from tools.timezone_utils import utc_date_time_to_local
        for row in rows:
            session_date = row["session_date"]
            start_time = row["start_time"] or "00:00:00"
            session_date, start_time = utc_date_time_to_local(session_date, start_time, tz_name)

            end_date = row["end_date"]
            end_time = row["end_time"] or ""
            if end_date:
                end_date, end_time = utc_date_time_to_local(end_date, end_time or "00:00:00", tz_name)
            delta_total = float(row["delta_total"] or 0.0)
            delta_redeem = row["delta_redeem"]
            if delta_redeem is None:
                start_redeem = row["starting_redeem"]
                end_redeem = row["ending_redeem"]
                if start_redeem is not None and end_redeem is not None:
                    delta_redeem = float(end_redeem) - float(start_redeem)
            if delta_redeem is not None:
                delta_redeem = float(delta_redeem)

            basis_consumed = row["basis_consumed"]
            if basis_consumed is not None:
                basis_consumed = float(basis_consumed)

            total_taxable = float(row["total_taxable"] or 0.0)
            notes = row["notes"] or ""
            game_type = row["game_type"] or ""
            game_name = row["game_name"] or ""

            start_total = row["starting_sc_balance"]
            end_total = row["ending_sc_balance"]
            start_redeem = row["starting_redeem"]
            end_redeem = row["ending_redeem"]

            search_blob = " ".join(
                str(value).lower()
                for value in (
                    session_date,
                    row["user_name"],
                    row["site_name"],
                    game_type,
                    game_name,
                    f"{float(start_total):.2f}" if start_total is not None else "",
                    f"{float(end_total):.2f}" if end_total is not None else "",
                    f"{float(start_redeem):.2f}" if start_redeem is not None else "",
                    f"{float(end_redeem):.2f}" if end_redeem is not None else "",
                    f"{delta_total:.2f}",
                    f"{delta_redeem:.2f}" if delta_redeem is not None else "",
                    f"{basis_consumed:.2f}" if basis_consumed is not None else "",
                    f"{total_taxable:.2f}",
                    notes,
                )
                if value is not None
            )

            sessions.append(
                {
                    "id": row["id"],
                    "session_date": session_date,
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "site_id": row["site_id"],
                    "site_name": row["site_name"],
                    "status": row["status"] or "",
                    "game_type": game_type,
                    "game_name": game_name,
                    "start_total": start_total,
                    "end_total": end_total,
                    "start_redeem": start_redeem,
                    "end_redeem": end_redeem,
                    "start_time": start_time or "",
                    "end_date": end_date,
                    "end_time": end_time or "",
                    "delta_total": delta_total,
                    "delta_redeem": delta_redeem,
                    "basis_consumed": basis_consumed,
                    "total_taxable": total_taxable,
                    "notes": notes,
                    "search_blob": search_blob,
                }
            )

        return sessions

    def fetch_daily_tax_data(
        self,
        selected_users: Optional[Iterable[str]] = None,
        selected_sites: Optional[Iterable[str]] = None,
        active_date_filter: Tuple[Optional[date_type], Optional[date_type]] = (None, None),
    ) -> Dict[str, Dict]:
        """
        Fetch tax withholding data from daily_date_tax table.
        Returns dict keyed by session_date with tax data.
        Note: Tax is now date-level, not per-user.
        """
        if not self._table_exists("daily_date_tax"):
            return {}

        query = """
            SELECT
                session_date,
                net_daily_pnl,
                tax_withholding_rate_pct,
                tax_withholding_is_custom,
                tax_withholding_amount
            FROM daily_date_tax
            WHERE 1=1
        """
        params = []

        start_date, end_date = active_date_filter
        if start_date:
            query += " AND session_date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND session_date <= ?"
            params.append(end_date.isoformat())

        rows = self.db.fetch_all(query, tuple(params))

        result = {}
        for row in rows:
            result[row["session_date"]] = {
                "net_daily_pnl": float(row["net_daily_pnl"] or 0.0),
                "tax_withholding_rate_pct": float(row["tax_withholding_rate_pct"] or 0.0) if row["tax_withholding_rate_pct"] is not None else None,
                "tax_withholding_is_custom": bool(row["tax_withholding_is_custom"]) if row["tax_withholding_is_custom"] is not None else False,
                "tax_withholding_amount": float(row["tax_withholding_amount"] or 0.0),
            }

        return result

    def fetch_notes_for_dates(self, dates: Iterable[str]) -> Dict[str, str]:
        dates = list(dates)
        if not dates:
            return {}
        if self.daily_session_repo is not None:
            return self.daily_session_repo.get_notes_by_dates(dates)
        if not self._table_exists("daily_sessions"):
            return {}
        placeholders = ",".join("?" * len(dates))
        query = f"""
            SELECT session_date, MAX(notes) as notes
            FROM daily_sessions
            WHERE session_date IN ({placeholders})
            GROUP BY session_date
        """
        rows = self.db.fetch_all(query, tuple(dates))
        return {row["session_date"]: row["notes"] or "" for row in rows}

    def get_note_for_date(self, session_date: str) -> str:
        """Get date-level notes from daily_date_tax table."""
        if self.daily_session_repo is not None:
            return self.daily_session_repo.get_note_for_date(session_date)
        if not self._table_exists("daily_date_tax"):
            return ""
        row = self.db.fetch_one(
            "SELECT notes FROM daily_date_tax WHERE session_date = ?",
            (session_date,),
        )
        return row["notes"] if row and row["notes"] else ""

    def set_notes_for_date(self, session_date: str, user_ids: Iterable[int], notes: str) -> None:
        """Set date-level notes in daily_date_tax table."""
        if self.daily_session_repo is not None:
            self.daily_session_repo.upsert_notes_for_date(session_date, user_ids, notes)
            return
        if not self._table_exists("daily_date_tax"):
            return
        # Store notes at date level in daily_date_tax (not duplicated per user)
        self.db.execute(
            """
            INSERT INTO daily_date_tax (session_date, notes)
            VALUES (?, ?)
            ON CONFLICT(session_date) DO UPDATE SET notes = excluded.notes
            """,
            (notes if notes else None, session_date),
        )

    def group_sessions(self, sessions: List[Dict], daily_tax_data: Optional[Dict] = None) -> List[Dict]:
        from collections import defaultdict

        if daily_tax_data is None:
            daily_tax_data = {}

        dates = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for sess in sessions:
            # Group by end_date (or session_date if no end_date) for proper tax accounting
            accounting_date = sess.get("end_date") or sess["session_date"]
            dates[accounting_date][sess["user_id"]][sess["site_id"]].append(sess)

        notes_by_date = self.fetch_notes_for_dates(dates.keys())
        data: List[Dict] = []
        for session_date in sorted(dates.keys(), reverse=True):
            users_data = dates[session_date]
            
            # Get date-level tax data (keyed by session_date only)
            date_tax_info = daily_tax_data.get(session_date, {})
            date_tax_withholding = date_tax_info.get("tax_withholding_amount", 0.0)
            
            users = []
            for user_id in sorted(
                users_data.keys(),
                key=lambda uid: list(list(users_data[uid].values())[0])[0]["user_name"].lower(),
            ):
                sites_data = users_data[user_id]
                # Get all sessions for this user across all sites
                all_user_sessions = [sess for site_sessions in sites_data.values() for sess in site_sessions]
                user_gameplay = sum(sess["delta_total"] for sess in all_user_sessions)
                user_delta_redeem = sum(sess["delta_redeem"] or 0.0 for sess in all_user_sessions)
                user_basis = sum(sess["basis_consumed"] or 0.0 for sess in all_user_sessions)
                user_total = sum(sess["total_taxable"] for sess in all_user_sessions)
                
                # Tax withholding is date-level (net of all users), don't show per-user
                user_tax_withholding = 0.0
                
                # Build sites list with grouped sessions
                sites = []
                for site_id in sorted(sites_data.keys(), key=lambda sid: sites_data[sid][0]["site_name"].lower()):
                    site_sessions = list(sites_data[site_id])
                    site_sessions.sort(key=lambda s: s["start_time"] or "")
                    site_gameplay = sum(sess["delta_total"] for sess in site_sessions)
                    site_delta_redeem = sum(sess["delta_redeem"] or 0.0 for sess in site_sessions)
                    site_basis = sum(sess["basis_consumed"] or 0.0 for sess in site_sessions)
                    site_total = sum(sess["total_taxable"] for sess in site_sessions)
                    # Tax withholding is at user+date level, not site level (removed site_tax_withholding)
                    sites.append(
                        {
                            "site_id": site_id,
                            "site_name": site_sessions[0]["site_name"],
                            "gameplay": site_gameplay,
                            "delta_redeem": site_delta_redeem,
                            "basis": site_basis,
                            "total": site_total,
                            "status": "Win" if site_total >= 0 else "Loss",
                            "sessions": site_sessions,
                        }
                    )
                
                users.append(
                    {
                        "user_id": user_id,
                        "user_name": all_user_sessions[0]["user_name"],
                        "gameplay": user_gameplay,
                        "delta_redeem": user_delta_redeem,
                        "basis": user_basis,
                        "total": user_total,
                        "tax_withholding": user_tax_withholding,
                        "status": "Win" if user_total >= 0 else "Loss",
                        "sites": sites,
                    }
                )

            date_gameplay = sum(user["gameplay"] for user in users)
            date_delta_redeem = sum(user["delta_redeem"] for user in users)
            date_basis = sum(user["basis"] for user in users)
            date_total = sum(user["total"] for user in users)
            # Use date-level tax from daily_date_tax table (net of all users)
            # date_tax_withholding already fetched from daily_tax_data on line 283
            total_sessions = sum(len(site["sessions"]) for user in users for site in user["sites"])
            data.append(
                {
                    "date": session_date,
                    "date_gameplay": date_gameplay,
                    "date_delta_redeem": date_delta_redeem,
                    "date_basis": date_basis,
                    "date_total": date_total,
                    "date_tax_withholding": date_tax_withholding,
                    "status": "Win" if date_total >= 0 else "Loss",
                    "users": users,
                    "user_count": len(users),
                    "session_count": total_sessions,
                    "notes": notes_by_date.get(session_date, ""),
                }
            )

        return data
