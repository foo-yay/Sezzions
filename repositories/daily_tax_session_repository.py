"""Repository for daily_tax_sessions table"""
from typing import Dict, Iterable, List, Optional


class DailyTaxSessionRepository:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_notes_by_dates(self, dates: Iterable[str]) -> Dict[str, str]:
        dates = list(dates)
        if not dates:
            return {}
        placeholders = ",".join("?" * len(dates))
        query = f"""
            SELECT session_date, MAX(notes) as notes
            FROM daily_tax_sessions
            WHERE session_date IN ({placeholders})
            GROUP BY session_date
        """
        rows = self.db.fetch_all(query, tuple(dates))
        return {row["session_date"]: row["notes"] or "" for row in rows}

    def get_note_for_date(self, session_date: str) -> str:
        row = self.db.fetch_one(
            "SELECT MAX(notes) as notes FROM daily_tax_sessions WHERE session_date = ?",
            (session_date,),
        )
        return row["notes"] if row and row["notes"] else ""

    def upsert_notes_for_date(self, session_date: str, user_ids: Iterable[int], notes: Optional[str]) -> None:
        user_ids = [uid for uid in set(user_ids) if uid is not None]
        if not user_ids:
            return

        for user_id in user_ids:
            self.db.execute(
                """
                INSERT OR IGNORE INTO daily_tax_sessions (
                    session_date, user_id,
                    total_other_income, total_session_pnl, net_daily_pnl,
                    status, num_game_sessions, num_other_income_items, notes
                ) VALUES (?, ?, 0.0, 0.0, 0.0, '', 0, 0, ?)
                """,
                (session_date, user_id, notes),
            )

        self.db.execute(
            "UPDATE daily_tax_sessions SET notes = ? WHERE session_date = ?",
            (notes if notes else None, session_date),
        )
