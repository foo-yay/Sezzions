"""
Service layer for explicit game session event linking (legacy parity).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from repositories.game_session_event_link_repository import GameSessionEventLinkRepository
from repositories.game_session_repository import GameSessionRepository
from repositories.purchase_repository import PurchaseRepository
from repositories.redemption_repository import RedemptionRepository


def _normalize_time(value: Optional[str], default: str = "00:00:00") -> str:
    if not value:
        return default
    value = value.strip()
    if len(value) == 5:
        return f"{value}:00"
    return value


def _to_dt(date_value: str, time_value: Optional[str]) -> datetime:
    return datetime.strptime(f"{date_value} {_normalize_time(time_value)}", "%Y-%m-%d %H:%M:%S")


class GameSessionEventLinkService:
    """Business logic for session-event links."""

    def __init__(
        self,
        repo: GameSessionEventLinkRepository,
        session_repo: GameSessionRepository,
        purchase_repo: PurchaseRepository,
        redemption_repo: RedemptionRepository,
        db_manager,
    ):
        self.repo = repo
        self.session_repo = session_repo
        self.purchase_repo = purchase_repo
        self.redemption_repo = redemption_repo
        self.db = db_manager

    def rebuild_links_for_pair(self, site_id: int, user_id: int) -> None:
        """Full rebuild of game_session_event_links for a site/user pair."""
        conn = self.db._connection
        cursor = conn.cursor()

        # Clear existing links for this pair
        cursor.execute(
            """
            DELETE FROM game_session_event_links
            WHERE game_session_id IN (
                SELECT id FROM game_sessions WHERE site_id = ? AND user_id = ?
            )
            """,
            (site_id, user_id),
        )

        # Load sessions in chronological order (active included)
        cursor.execute(
            """
            SELECT id, session_date,
                   COALESCE(session_time, '00:00:00') as start_time,
                   end_date, COALESCE(end_time, '23:59:59') as end_time,
                   status
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
            ORDER BY
                COALESCE(end_date, session_date) ASC,
                COALESCE(end_time, session_time, '00:00:00') ASC,
                id ASC
            """,
            (site_id, user_id),
        )
        sessions = cursor.fetchall()

        if not sessions:
            conn.commit()
            return

        # Load all purchases and redemptions for this pair
        cursor.execute(
            """
            SELECT id, purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND purchase_date IS NOT NULL
            ORDER BY purchase_date ASC, COALESCE(purchase_time, '00:00:00') ASC, id ASC
            """,
            (site_id, user_id),
        )
        purchases = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, redemption_date, COALESCE(redemption_time, '00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND redemption_date IS NOT NULL
            ORDER BY redemption_date ASC, COALESCE(redemption_time, '00:00:00') ASC, id ASC
            """,
            (site_id, user_id),
        )
        redemptions = cursor.fetchall()

        links_to_insert: List[Tuple[int, str, int, str]] = []

        for i, session in enumerate(sessions):
            session_id = session["id"]
            start_dt = _to_dt(session["session_date"], session["start_time"])

            if session["status"] == "Active" or session["end_date"] is None:
                end_dt = None
            else:
                end_dt = _to_dt(session["end_date"], session["end_time"])

            prev_end_dt = None
            if i > 0:
                prev_session = sessions[i - 1]
                if prev_session["end_date"]:
                    prev_end_dt = _to_dt(prev_session["end_date"], prev_session["end_time"])

            next_start_dt = None
            if i < len(sessions) - 1:
                next_session = sessions[i + 1]
                next_start_dt = _to_dt(next_session["session_date"], next_session["start_time"])

            # Link purchases
            for p in purchases:
                p_dt = _to_dt(p["purchase_date"], p["purchase_time"])

                if end_dt and start_dt <= p_dt <= end_dt:
                    links_to_insert.append((session_id, "purchase", p["id"], "DURING"))
                elif prev_end_dt is None or (prev_end_dt < p_dt < start_dt):
                    if prev_end_dt is None and p_dt < start_dt:
                        links_to_insert.append((session_id, "purchase", p["id"], "BEFORE"))
                    elif prev_end_dt is not None and prev_end_dt < p_dt < start_dt:
                        links_to_insert.append((session_id, "purchase", p["id"], "BEFORE"))

            # Link redemptions (closed sessions only)
            if end_dt:
                for r in redemptions:
                    r_dt = _to_dt(r["redemption_date"], r["redemption_time"])

                    if start_dt <= r_dt <= end_dt:
                        links_to_insert.append((session_id, "redemption", r["id"], "DURING"))
                    elif next_start_dt is None or (end_dt < r_dt < next_start_dt):
                        if next_start_dt is None and r_dt > end_dt:
                            links_to_insert.append((session_id, "redemption", r["id"], "AFTER"))
                        elif next_start_dt is not None and end_dt < r_dt < next_start_dt:
                            links_to_insert.append((session_id, "redemption", r["id"], "AFTER"))

        if links_to_insert:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO game_session_event_links
                    (game_session_id, event_type, event_id, relation)
                VALUES (?, ?, ?, ?)
                """,
                links_to_insert,
            )

        conn.commit()

    def rebuild_links_for_pair_from(self, site_id: int, user_id: int, from_date: str, from_time: str = "00:00:00") -> None:
        """Scoped rebuild of game_session_event_links starting from a boundary date/time."""
        conn = self.db._connection
        cursor = conn.cursor()

        boundary_dt = _to_dt(from_date, from_time or "00:00:00")

        cursor.execute(
            """
            SELECT id, session_date,
                   COALESCE(session_time, '00:00:00') as start_time,
                   end_date, COALESCE(end_time, '23:59:59') as end_time,
                   status
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND (
                  (status = 'Closed' AND end_date IS NOT NULL
                   AND (end_date > ? OR (end_date = ? AND COALESCE(end_time, '00:00:00') >= ?)))
                  OR
                  (status = 'Active'
                   AND (session_date > ? OR (session_date = ? AND COALESCE(session_time, '00:00:00') >= ?)))
              )
            ORDER BY
                COALESCE(end_date, session_date) ASC,
                COALESCE(end_time, session_time, '00:00:00') ASC,
                id ASC
            """,
            (site_id, user_id, from_date, from_date, from_time, from_date, from_date, from_time),
        )
        suffix_sessions = cursor.fetchall()

        if not suffix_sessions:
            conn.commit()
            return

        suffix_session_ids = [s["id"] for s in suffix_sessions]
        placeholders = ",".join(["?"] * len(suffix_session_ids))
        cursor.execute(
            f"DELETE FROM game_session_event_links WHERE game_session_id IN ({placeholders})",
            tuple(suffix_session_ids),
        )

        cursor.execute(
            """
            SELECT id, end_date, end_time
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Closed'
              AND (session_date < ? OR (session_date = ? AND COALESCE(session_time,'00:00:00') < ?))
            ORDER BY
              COALESCE(end_date, session_date) DESC,
              COALESCE(end_time, '00:00:00') DESC
            LIMIT 1
            """,
            (site_id, user_id, from_date, from_date, from_time),
        )
        checkpoint_session = cursor.fetchone()

        prev_end_dt = None
        if checkpoint_session and checkpoint_session["end_date"]:
            prev_end_dt = _to_dt(
                checkpoint_session["end_date"],
                checkpoint_session["end_time"] if checkpoint_session["end_time"] else "23:59:59",
            )

        if prev_end_dt:
            prev_date = prev_end_dt.strftime("%Y-%m-%d")
            prev_time = prev_end_dt.strftime("%H:%M:%S")
        else:
            prev_date = "1900-01-01"
            prev_time = "00:00:00"

        cursor.execute(
            """
            SELECT id, purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND purchase_date IS NOT NULL
              AND (purchase_date > ? OR (purchase_date = ? AND COALESCE(purchase_time, '00:00:00') > ?))
            ORDER BY purchase_date ASC, COALESCE(purchase_time, '00:00:00') ASC, id ASC
            """,
            (site_id, user_id, prev_date, prev_date, prev_time),
        )
        purchases = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, redemption_date, COALESCE(redemption_time, '00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND redemption_date IS NOT NULL
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time, '00:00:00') > ?))
            ORDER BY redemption_date ASC, COALESCE(redemption_time, '00:00:00') ASC, id ASC
            """,
            (site_id, user_id, prev_date, prev_date, prev_time),
        )
        redemptions = cursor.fetchall()

        links_to_insert: List[Tuple[int, str, int, str]] = []

        for i, session in enumerate(suffix_sessions):
            session_id = session["id"]
            start_dt = _to_dt(session["session_date"], session["start_time"])

            if session["status"] == "Active" or session["end_date"] is None:
                end_dt = None
            else:
                end_dt = _to_dt(session["end_date"], session["end_time"])

            if i == 0:
                current_prev_end_dt = prev_end_dt
            else:
                prev_session = suffix_sessions[i - 1]
                if prev_session["end_date"]:
                    current_prev_end_dt = _to_dt(prev_session["end_date"], prev_session["end_time"])
                else:
                    current_prev_end_dt = None

            next_start_dt = None
            if i < len(suffix_sessions) - 1:
                next_session = suffix_sessions[i + 1]
                next_start_dt = _to_dt(next_session["session_date"], next_session["start_time"])

            for p in purchases:
                p_dt = _to_dt(p["purchase_date"], p["purchase_time"])

                if end_dt and start_dt <= p_dt <= end_dt:
                    links_to_insert.append((session_id, "purchase", p["id"], "DURING"))
                elif current_prev_end_dt is None or (current_prev_end_dt < p_dt < start_dt):
                    if current_prev_end_dt is None and p_dt < start_dt:
                        links_to_insert.append((session_id, "purchase", p["id"], "BEFORE"))
                    elif current_prev_end_dt is not None and current_prev_end_dt < p_dt < start_dt:
                        links_to_insert.append((session_id, "purchase", p["id"], "BEFORE"))

            if end_dt:
                for r in redemptions:
                    r_dt = _to_dt(r["redemption_date"], r["redemption_time"])

                    if start_dt <= r_dt <= end_dt:
                        links_to_insert.append((session_id, "redemption", r["id"], "DURING"))
                    elif next_start_dt is None or (end_dt < r_dt < next_start_dt):
                        if next_start_dt is None and r_dt > end_dt:
                            links_to_insert.append((session_id, "redemption", r["id"], "AFTER"))
                        elif next_start_dt is not None and end_dt < r_dt < next_start_dt:
                            links_to_insert.append((session_id, "redemption", r["id"], "AFTER"))

        if links_to_insert:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO game_session_event_links
                    (game_session_id, event_type, event_id, relation)
                VALUES (?, ?, ?, ?)
                """,
                links_to_insert,
            )

        conn.commit()

    def rebuild_links_all(self) -> None:
        pairs = self._iter_pairs()
        for user_id, site_id in pairs:
            self.rebuild_links_for_pair(site_id, user_id)

    def _iter_pairs(self) -> List[Tuple[int, int]]:
        rows = self.db.fetch_all(
            """
            SELECT DISTINCT user_id, site_id FROM purchases
            UNION
            SELECT DISTINCT user_id, site_id FROM redemptions
            UNION
            SELECT DISTINCT user_id, site_id FROM game_sessions
            """
        )
        pairs: List[Tuple[int, int]] = []
        for r in rows:
            if r.get("user_id") is None or r.get("site_id") is None:
                continue
            pairs.append((int(r["user_id"]), int(r["site_id"])))
        pairs.sort()
        return pairs

    def get_sessions_for_purchase(self, purchase_id: int):
        rows = self.repo.get_session_links_for_purchase(purchase_id)
        sessions = []
        for row in rows:
            session = self.session_repo._row_to_model(row)
            if "relation" in row:
                setattr(session, "link_relation", row["relation"])
            sessions.append(session)
        return sessions

    def get_sessions_for_redemption(self, redemption_id: int):
        rows = self.repo.get_session_links_for_redemption(redemption_id)
        sessions = []
        for row in rows:
            session = self.session_repo._row_to_model(row)
            if "relation" in row:
                setattr(session, "link_relation", row["relation"])
            sessions.append(session)
        return sessions

    def get_events_for_session(self, session_id: int) -> Dict[str, list]:
        rows = self.repo.get_event_links_for_session(session_id)
        purchases = []
        for row in rows["purchases"]:
            purchase = self.purchase_repo._row_to_model(row)
            if "relation" in row:
                setattr(purchase, "link_relation", row["relation"])
            purchases.append(purchase)

        redemptions = []
        for row in rows["redemptions"]:
            redemption = self.redemption_repo._row_to_model(row)
            if "relation" in row:
                setattr(redemption, "link_relation", row["relation"])
            redemptions.append(redemption)

        return {"purchases": purchases, "redemptions": redemptions}
