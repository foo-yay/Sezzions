"""
Repository for GameSession database operations
"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from models.game_session import GameSession
from tools.timezone_utils import (
    get_configured_timezone_name,
    local_date_time_to_utc,
    utc_date_time_to_local,
)


class GameSessionRepository:
    """Handles database operations for game sessions"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def _row_to_model(self, row) -> GameSession:
        """Convert database row to GameSession model"""
        def safe_decimal(value, default="0.00"):
            if value is None:
                return Decimal(default) if default is not None else None
            return Decimal(value)

        def row_value(key, default=None):
            val = row[key] if key in row.keys() else default
            # If value exists but is None, use default
            return val if val is not None else default
        
        session_date = row["session_date"]
        if isinstance(session_date, str):
            session_date = datetime.strptime(session_date, "%Y-%m-%d").date()
        end_date = row_value("end_date")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        tz_name = get_configured_timezone_name()
        session_date, session_time = utc_date_time_to_local(
            session_date,
            row["session_time"] or "00:00:00",
            tz_name,
        )
        end_time_value = row_value("end_time")
        end_date_local = None
        end_time_local = None
        if end_date:
            end_date_local, end_time_local = utc_date_time_to_local(
                end_date,
                end_time_value or "00:00:00",
                tz_name,
            )

        return GameSession(
            id=row["id"],
            user_id=row["user_id"],
            site_id=row["site_id"],
            game_id=row["game_id"],
            game_type_id=row_value("game_type_id"),
            session_date=session_date,
            end_date=end_date_local,
            end_time=end_time_local,
            session_time=session_time or "00:00:00",
            starting_balance=Decimal(row["starting_balance"]),
            ending_balance=safe_decimal(row_value("ending_balance"), "0.00"),
            starting_redeemable=safe_decimal(row_value("starting_redeemable"), "0.00"),
            ending_redeemable=safe_decimal(row_value("ending_redeemable"), "0.00"),
            purchases_during=safe_decimal(row_value("purchases_during"), "0.00"),
            redemptions_during=safe_decimal(row_value("redemptions_during"), "0.00"),
            wager_amount=safe_decimal(row_value("wager_amount"), "0.00"),
            rtp=row_value("rtp"),
            expected_start_total=safe_decimal(row_value("expected_start_total")),
            expected_start_redeemable=safe_decimal(row_value("expected_start_redeemable")),
            discoverable_sc=safe_decimal(row_value("discoverable_sc")),
            delta_total=safe_decimal(row_value("delta_total")),
            delta_redeem=safe_decimal(row_value("delta_redeem")),
            session_basis=safe_decimal(row_value("session_basis")),
            basis_consumed=safe_decimal(row_value("basis_consumed")),
            net_taxable_pl=safe_decimal(row_value("net_taxable_pl")),
            tax_withholding_rate_pct=None,
            tax_withholding_is_custom=False,
            tax_withholding_amount=None,
            status=row_value("status", "Active"),
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        )
    
    def get_by_id(self, session_id: int) -> Optional[GameSession]:
        """Get session by ID (excludes soft-deleted)"""
        query = "SELECT * FROM game_sessions WHERE id = ? AND deleted_at IS NULL"
        row = self.db.fetch_one(query, (session_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self, status: Optional[str] = None) -> List[GameSession]:
        """Get all sessions, optionally filtered by status (excludes soft-deleted)"""
        query = "SELECT * FROM game_sessions WHERE deleted_at IS NULL"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY session_date DESC, session_time DESC"
        rows = self.db.fetch_all(query, tuple(params) if params else ())
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user(self, user_id: int) -> List[GameSession]:
        """Get all sessions for a user (excludes soft-deleted)"""
        query = """
            SELECT * FROM game_sessions 
            WHERE user_id = ? AND deleted_at IS NULL
            ORDER BY session_date DESC, session_time DESC
        """
        rows = self.db.fetch_all(query, (user_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_site(self, site_id: int) -> List[GameSession]:
        """Get all sessions for a site (excludes soft-deleted)"""
        query = """
            SELECT * FROM game_sessions 
            WHERE site_id = ? AND deleted_at IS NULL
            ORDER BY session_date DESC, session_time DESC
        """
        rows = self.db.fetch_all(query, (site_id,))
        return [self._row_to_model(row) for row in rows]

    def get_active_session(self, user_id: int, site_id: int) -> Optional[GameSession]:
        """Get the active session for a user/site, if any (excludes soft-deleted)"""
        query = """
            SELECT * FROM game_sessions
            WHERE user_id = ? AND site_id = ? AND status = 'Active' AND deleted_at IS NULL
            ORDER BY session_date DESC, session_time DESC
            LIMIT 1
        """
        row = self.db.fetch_one(query, (user_id, site_id))
        return self._row_to_model(row) if row else None
    
    def get_by_user_and_site(self, user_id: int, site_id: int) -> List[GameSession]:
        """Get sessions for specific user/site combination (excludes soft-deleted)"""
        query = """
            SELECT * FROM game_sessions 
            WHERE user_id = ? AND site_id = ? AND deleted_at IS NULL
            ORDER BY session_date DESC, session_time DESC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def get_chronological(self, user_id: int, site_id: int) -> List[GameSession]:
        """Get sessions in chronological order (for P/L calculation, excludes soft-deleted)"""
        query = """
            SELECT * FROM game_sessions 
            WHERE user_id = ? AND site_id = ? AND deleted_at IS NULL
            ORDER BY COALESCE(end_date, session_date) ASC, COALESCE(end_time, session_time) ASC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def create(self, session: GameSession) -> GameSession:
        """Create a new session"""
        tz_name = get_configured_timezone_name()
        utc_session_date, utc_session_time = local_date_time_to_utc(
            session.session_date,
            session.session_time,
            tz_name,
        )
        utc_end_date = None
        utc_end_time = None
        if session.end_date:
            utc_end_date, utc_end_time = local_date_time_to_utc(
                session.end_date,
                session.end_time,
                tz_name,
            )
        query = """
            INSERT INTO game_sessions (
                user_id, site_id, game_id, game_type_id, session_date, session_time, end_date, end_time,
                starting_balance, ending_balance, starting_redeemable, ending_redeemable,
                purchases_during, redemptions_during, wager_amount, rtp,
                expected_start_total, expected_start_redeemable,
                discoverable_sc, delta_total, delta_redeem,
                session_basis, basis_consumed, net_taxable_pl,
                status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        def str_or_none(val):
            return str(val) if val is not None else None
        
        session_id = self.db.execute(
            query,
            (
                session.user_id, session.site_id, session.game_id, session.game_type_id,
                utc_session_date, utc_session_time,
                utc_end_date,
                utc_end_time,
                str(session.starting_balance), str(session.ending_balance),
                str(session.starting_redeemable), str(session.ending_redeemable),
                str(session.purchases_during), str(session.redemptions_during),
                str(session.wager_amount), session.rtp,
                str_or_none(session.expected_start_total),
                str_or_none(session.expected_start_redeemable),
                str_or_none(session.discoverable_sc),
                str_or_none(session.delta_total),
                str_or_none(session.delta_redeem),
                str_or_none(session.session_basis),
                str_or_none(session.basis_consumed),
                str_or_none(session.net_taxable_pl),
                session.status, session.notes
            )
        )
        session.id = session_id
        return session
    
    def update(self, session: GameSession) -> GameSession:
        """Update an existing session"""
        tz_name = get_configured_timezone_name()
        utc_session_date, utc_session_time = local_date_time_to_utc(
            session.session_date,
            session.session_time,
            tz_name,
        )
        utc_end_date = None
        utc_end_time = None
        if session.end_date:
            utc_end_date, utc_end_time = local_date_time_to_utc(
                session.end_date,
                session.end_time,
                tz_name,
            )
        query = """
            UPDATE game_sessions SET
                user_id = ?, site_id = ?, game_id = ?, game_type_id = ?, session_date = ?, session_time = ?, end_date = ?, end_time = ?,
                starting_balance = ?, ending_balance = ?, starting_redeemable = ?, ending_redeemable = ?,
                purchases_during = ?, redemptions_during = ?, wager_amount = ?, rtp = ?,
                expected_start_total = ?, expected_start_redeemable = ?,
                discoverable_sc = ?, delta_total = ?, delta_redeem = ?,
                session_basis = ?, basis_consumed = ?, net_taxable_pl = ?,
                status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        def str_or_none(val):
            return str(val) if val is not None else None
        
        self.db.execute(
            query,
            (
                session.user_id, session.site_id, session.game_id, session.game_type_id,
                utc_session_date, utc_session_time,
                utc_end_date,
                utc_end_time,
                str(session.starting_balance), str(session.ending_balance),
                str(session.starting_redeemable), str(session.ending_redeemable),
                str(session.purchases_during), str(session.redemptions_during),
                str(session.wager_amount), session.rtp,
                str_or_none(session.expected_start_total),
                str_or_none(session.expected_start_redeemable),
                str_or_none(session.discoverable_sc),
                str_or_none(session.delta_total),
                str_or_none(session.delta_redeem),
                str_or_none(session.session_basis),
                str_or_none(session.basis_consumed),
                str_or_none(session.net_taxable_pl),
                session.status, session.notes, session.id
            )
        )
        return session
    
    def delete(self, session_id: int) -> None:
        """Soft delete a session by setting deleted_at timestamp"""
        query = "UPDATE game_sessions SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?"
        self.db.execute(query, (session_id,))
    
    def restore(self, session_id: int) -> None:
        """Restore a soft-deleted session by clearing deleted_at"""
        query = "UPDATE game_sessions SET deleted_at = NULL WHERE id = ?"
        self.db.execute(query, (session_id,))
