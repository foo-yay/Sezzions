"""
Repository for game_session_event_links table operations
"""
from typing import List, Dict, Any


class GameSessionEventLinkRepository:
    """Handles database operations for game_session_event_links"""

    def __init__(self, db_manager):
        self.db = db_manager

    def clear_links_for_pair(self, site_id: int, user_id: int) -> None:
        query = """
            DELETE FROM game_session_event_links
            WHERE game_session_id IN (
                SELECT id FROM game_sessions WHERE site_id = ? AND user_id = ?
            )
        """
        self.db.execute(query, (site_id, user_id))

    def clear_links_for_sessions(self, session_ids: List[int]) -> None:
        if not session_ids:
            return
        placeholders = ",".join(["?"] * len(session_ids))
        query = f"DELETE FROM game_session_event_links WHERE game_session_id IN ({placeholders})"
        self.db.execute(query, tuple(session_ids))

    def insert_links(self, links: List[tuple]) -> None:
        if not links:
            return
        cursor = self.db._connection.cursor()
        cursor.executemany(
            """
            INSERT OR IGNORE INTO game_session_event_links
                (game_session_id, event_type, event_id, relation)
            VALUES (?, ?, ?, ?)
            """,
            links,
        )
        self.db._connection.commit()
        self.db._notify_change()

    def get_session_links_for_purchase(self, purchase_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT gsel.relation, gs.*
            FROM game_session_event_links gsel
            JOIN game_sessions gs ON gs.id = gsel.game_session_id
            WHERE gsel.event_type = 'purchase' AND gsel.event_id = ?
            ORDER BY COALESCE(gs.end_date, gs.session_date) ASC,
                     COALESCE(gs.end_time, gs.session_time, '00:00:00') ASC,
                     gs.id ASC
        """
        return self.db.fetch_all(query, (purchase_id,))

    def get_session_links_for_redemption(self, redemption_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT gsel.relation, gs.*
            FROM game_session_event_links gsel
            JOIN game_sessions gs ON gs.id = gsel.game_session_id
            WHERE gsel.event_type = 'redemption' AND gsel.event_id = ?
            ORDER BY COALESCE(gs.end_date, gs.session_date) ASC,
                     COALESCE(gs.end_time, gs.session_time, '00:00:00') ASC,
                     gs.id ASC
        """
        return self.db.fetch_all(query, (redemption_id,))

    def get_event_links_for_session(self, session_id: int) -> Dict[str, List[Dict[str, Any]]]:
        purchases = self.db.fetch_all(
            """
            SELECT gsel.relation, p.*
            FROM game_session_event_links gsel
            JOIN purchases p ON p.id = gsel.event_id
            WHERE gsel.game_session_id = ? AND gsel.event_type = 'purchase'
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time, '00:00:00') ASC, p.id ASC
            """,
            (session_id,),
        )

        redemptions = self.db.fetch_all(
            """
            SELECT gsel.relation, r.*, rm.name as method_name, rm.method_type as method_type
            FROM game_session_event_links gsel
            JOIN redemptions r ON r.id = gsel.event_id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE gsel.game_session_id = ? AND gsel.event_type = 'redemption'
            ORDER BY r.redemption_date ASC, COALESCE(r.redemption_time, '00:00:00') ASC, r.id ASC
            """,
            (session_id,),
        )

        return {"purchases": purchases, "redemptions": redemptions}
