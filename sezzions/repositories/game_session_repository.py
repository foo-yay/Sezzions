"""
Repository for GameSession database operations
"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from models.game_session import GameSession


class GameSessionRepository:
    """Handles database operations for game sessions"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def _row_to_model(self, row) -> GameSession:
        """Convert database row to GameSession model"""
        def safe_decimal(value):
            return Decimal(value) if value is not None else None

        def row_value(key, default=None):
            return row[key] if key in row.keys() else default
        
        return GameSession(
            id=row["id"],
            user_id=row["user_id"],
            site_id=row["site_id"],
            game_id=row["game_id"],
            session_date=row["session_date"],
            end_date=row_value("end_date"),
            end_time=row_value("end_time"),
            session_time=row["session_time"] or "00:00:00",
            starting_balance=Decimal(row["starting_balance"]),
            ending_balance=Decimal(row["ending_balance"]),
            starting_redeemable=Decimal(row_value("starting_redeemable", "0.00")),
            ending_redeemable=Decimal(row_value("ending_redeemable", "0.00")),
            purchases_during=Decimal(row["purchases_during"]),
            redemptions_during=Decimal(row["redemptions_during"]),
            expected_start_total=safe_decimal(row_value("expected_start_total")),
            expected_start_redeemable=safe_decimal(row_value("expected_start_redeemable")),
            discoverable_sc=safe_decimal(row_value("discoverable_sc")),
            delta_total=safe_decimal(row_value("delta_total")),
            delta_redeem=safe_decimal(row_value("delta_redeem")),
            session_basis=safe_decimal(row_value("session_basis")),
            basis_consumed=safe_decimal(row_value("basis_consumed")),
            net_taxable_pl=safe_decimal(row_value("net_taxable_pl")),
            status=row_value("status", "Active"),
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        )
    
    def get_by_id(self, session_id: int) -> Optional[GameSession]:
        """Get session by ID"""
        query = "SELECT * FROM game_sessions WHERE id = ?"
        row = self.db.fetch_one(query, (session_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self, status: Optional[str] = None) -> List[GameSession]:
        """Get all sessions, optionally filtered by status"""
        query = "SELECT * FROM game_sessions"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY session_date DESC, session_time DESC"
        rows = self.db.fetch_all(query, tuple(params) if params else ())
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user(self, user_id: int) -> List[GameSession]:
        """Get all sessions for a user"""
        query = """
            SELECT * FROM game_sessions 
            WHERE user_id = ? 
            ORDER BY session_date DESC, session_time DESC
        """
        rows = self.db.fetch_all(query, (user_id,))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_site(self, site_id: int) -> List[GameSession]:
        """Get all sessions for a site"""
        query = """
            SELECT * FROM game_sessions 
            WHERE site_id = ? 
            ORDER BY session_date DESC, session_time DESC
        """
        rows = self.db.fetch_all(query, (site_id,))
        return [self._row_to_model(row) for row in rows]

    def get_active_session(self, user_id: int, site_id: int) -> Optional[GameSession]:
        """Get the active session for a user/site, if any"""
        query = """
            SELECT * FROM game_sessions
            WHERE user_id = ? AND site_id = ? AND status = 'Active'
            ORDER BY session_date DESC, session_time DESC
            LIMIT 1
        """
        row = self.db.fetch_one(query, (user_id, site_id))
        return self._row_to_model(row) if row else None
    
    def get_by_user_and_site(self, user_id: int, site_id: int) -> List[GameSession]:
        """Get sessions for specific user/site combination"""
        query = """
            SELECT * FROM game_sessions 
            WHERE user_id = ? AND site_id = ? 
            ORDER BY session_date DESC, session_time DESC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def get_chronological(self, user_id: int, site_id: int) -> List[GameSession]:
        """Get sessions in chronological order (for P/L calculation)"""
        query = """
            SELECT * FROM game_sessions 
            WHERE user_id = ? AND site_id = ? 
            ORDER BY COALESCE(end_date, session_date) ASC, COALESCE(end_time, session_time) ASC
        """
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]
    
    def create(self, session: GameSession) -> GameSession:
        """Create a new session"""
        query = """
            INSERT INTO game_sessions (
                user_id, site_id, game_id, session_date, session_time, end_date, end_time,
                starting_balance, ending_balance, starting_redeemable, ending_redeemable,
                purchases_during, redemptions_during,
                expected_start_total, expected_start_redeemable,
                discoverable_sc, delta_total, delta_redeem,
                session_basis, basis_consumed, net_taxable_pl,
                status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        def str_or_none(val):
            return str(val) if val is not None else None
        
        session_id = self.db.execute(
            query,
            (
                session.user_id, session.site_id, session.game_id,
                session.session_date.isoformat(), session.session_time,
                session.end_date.isoformat() if session.end_date else None,
                session.end_time,
                str(session.starting_balance), str(session.ending_balance),
                str(session.starting_redeemable), str(session.ending_redeemable),
                str(session.purchases_during), str(session.redemptions_during),
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
        query = """
            UPDATE game_sessions SET
                user_id = ?, site_id = ?, game_id = ?, session_date = ?, session_time = ?, end_date = ?, end_time = ?,
                starting_balance = ?, ending_balance = ?, starting_redeemable = ?, ending_redeemable = ?,
                purchases_during = ?, redemptions_during = ?,
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
                session.user_id, session.site_id, session.game_id,
                session.session_date.isoformat(), session.session_time,
                session.end_date.isoformat() if session.end_date else None,
                session.end_time,
                str(session.starting_balance), str(session.ending_balance),
                str(session.starting_redeemable), str(session.ending_redeemable),
                str(session.purchases_during), str(session.redemptions_during),
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
        """Delete a session"""
        query = "DELETE FROM game_sessions WHERE id = ?"
        self.db.execute(query, (session_id,))
