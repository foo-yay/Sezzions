"""Hosted game-session event-link service.

Classifies purchases and redemptions as BEFORE / DURING / AFTER relative to
game sessions for a given (workspace, user, site) triple.

Ported from the desktop ``GameSessionEventLinkService``.  Key differences:

- SQLAlchemy ORM instead of raw SQL
- String UUIDs instead of integer IDs
- Boundary rule (Issue #90): session start INCLUSIVE (>=), end EXCLUSIVE (<)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import asc, func, or_, and_
from sqlalchemy.orm import Session

from services.hosted.persistence import (
    HostedGameSessionEventLinkRecord,
    HostedGameSessionRecord,
    HostedPurchaseRecord,
    HostedRedemptionRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_time(value: Optional[str], default: str = "00:00:00") -> str:
    if not value:
        return default
    value = value.strip()
    if len(value) == 5:
        return f"{value}:00"
    return value


def _to_dt(date_str: str, time_str: Optional[str]) -> datetime:
    return datetime.strptime(f"{date_str} {_normalize_time(time_str)}", "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HostedEventLinkService:
    """Build temporal links between game sessions and purchase/redemption events."""

    def rebuild_links_for_pair(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
    ) -> None:
        """Full rebuild of event links for one (user, site) pair."""

        # --- Clear existing links for this pair ---
        session_ids_q = (
            session.query(HostedGameSessionRecord.id)
            .filter(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.user_id == user_id,
                HostedGameSessionRecord.site_id == site_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
        )
        session_ids = [r.id for r in session_ids_q.all()]
        if session_ids:
            session.query(HostedGameSessionEventLinkRecord).filter(
                HostedGameSessionEventLinkRecord.game_session_id.in_(session_ids),
            ).delete(synchronize_session="fetch")

        # --- Load sessions (chronological) ---
        game_sessions = (
            session.query(HostedGameSessionRecord)
            .filter(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.user_id == user_id,
                HostedGameSessionRecord.site_id == site_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
            .order_by(
                asc(func.coalesce(HostedGameSessionRecord.end_date, HostedGameSessionRecord.session_date)),
                asc(func.coalesce(HostedGameSessionRecord.end_time, HostedGameSessionRecord.session_time, "00:00:00")),
                asc(HostedGameSessionRecord.id),
            )
            .all()
        )
        if not game_sessions:
            session.flush()
            return

        # --- Load purchases and redemptions ---
        purchases = (
            session.query(HostedPurchaseRecord)
            .filter(
                HostedPurchaseRecord.workspace_id == workspace_id,
                HostedPurchaseRecord.user_id == user_id,
                HostedPurchaseRecord.site_id == site_id,
                HostedPurchaseRecord.deleted_at.is_(None),
            )
            .order_by(
                asc(HostedPurchaseRecord.purchase_date),
                asc(func.coalesce(HostedPurchaseRecord.purchase_time, "00:00:00")),
                asc(HostedPurchaseRecord.id),
            )
            .all()
        )

        redemptions = (
            session.query(HostedRedemptionRecord)
            .filter(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.user_id == user_id,
                HostedRedemptionRecord.site_id == site_id,
                HostedRedemptionRecord.deleted_at.is_(None),
                HostedRedemptionRecord.status.notin_(["CANCELED", "PENDING_CANCEL"]),
            )
            .order_by(
                asc(HostedRedemptionRecord.redemption_date),
                asc(func.coalesce(HostedRedemptionRecord.redemption_time, "00:00:00")),
                asc(HostedRedemptionRecord.id),
            )
            .all()
        )

        # --- Classify and insert ---
        links = self._classify_events(game_sessions, purchases, redemptions, workspace_id)
        for link in links:
            session.add(link)
        session.flush()

    def rebuild_links_all(
        self,
        session: Session,
        *,
        workspace_id: str,
    ) -> None:
        """Rebuild links for every (user, site) pair in the workspace."""
        pairs = self._iter_pairs(session, workspace_id)
        for user_id, site_id in pairs:
            self.rebuild_links_for_pair(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                site_id=site_id,
            )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _iter_pairs(
        self,
        session: Session,
        workspace_id: str,
    ) -> List[Tuple[str, str]]:
        """Distinct (user_id, site_id) pairs with purchases, redemptions, or sessions."""
        from sqlalchemy import union_all, select

        q1 = (
            select(HostedPurchaseRecord.user_id, HostedPurchaseRecord.site_id)
            .where(HostedPurchaseRecord.workspace_id == workspace_id, HostedPurchaseRecord.deleted_at.is_(None))
            .distinct()
        )
        q2 = (
            select(HostedRedemptionRecord.user_id, HostedRedemptionRecord.site_id)
            .where(HostedRedemptionRecord.workspace_id == workspace_id, HostedRedemptionRecord.deleted_at.is_(None))
            .distinct()
        )
        q3 = (
            select(HostedGameSessionRecord.user_id, HostedGameSessionRecord.site_id)
            .where(HostedGameSessionRecord.workspace_id == workspace_id, HostedGameSessionRecord.deleted_at.is_(None))
            .distinct()
        )
        combined = union_all(q1, q2, q3).subquery()
        rows = session.execute(
            select(combined.c.user_id, combined.c.site_id).distinct()
        ).all()
        return sorted(
            [(r.user_id, r.site_id) for r in rows if r.user_id and r.site_id]
        )

    @staticmethod
    def _classify_events(
        game_sessions: list,
        purchases: list,
        redemptions: list,
        workspace_id: str,
    ) -> List[HostedGameSessionEventLinkRecord]:
        """Classify each purchase/redemption as BEFORE/DURING/AFTER each session."""
        seen: set = set()  # deduplicate (session_id, event_type, event_id, relation)
        links: List[HostedGameSessionEventLinkRecord] = []

        for i, gs in enumerate(game_sessions):
            start_dt = _to_dt(gs.session_date, gs.session_time)
            is_active = gs.status == "Active" or gs.end_date is None
            end_dt = None if is_active else _to_dt(gs.end_date, gs.end_time)

            prev_end_dt = None
            if i > 0:
                prev = game_sessions[i - 1]
                if prev.end_date:
                    prev_end_dt = _to_dt(prev.end_date, prev.end_time)

            next_start_dt = None
            if i < len(game_sessions) - 1:
                nxt = game_sessions[i + 1]
                next_start_dt = _to_dt(nxt.session_date, nxt.session_time)

            # --- purchases ---
            for p in purchases:
                p_dt = _to_dt(p.purchase_date, p.purchase_time)
                relation = _classify_timestamp(
                    p_dt, start_dt, end_dt, prev_end_dt, next_start_dt, is_active,
                    link_type="purchase",
                )
                if relation:
                    key = (gs.id, "purchase", p.id, relation)
                    if key not in seen:
                        seen.add(key)
                        links.append(HostedGameSessionEventLinkRecord(
                            id=str(uuid4()),
                            workspace_id=workspace_id,
                            game_session_id=gs.id,
                            event_type="purchase",
                            event_id=p.id,
                            relation=relation,
                        ))

            # --- redemptions (closed sessions only for AFTER links) ---
            for r in redemptions:
                r_dt = _to_dt(r.redemption_date, r.redemption_time)
                relation = _classify_timestamp(
                    r_dt, start_dt, end_dt, prev_end_dt, next_start_dt, is_active,
                    link_type="redemption",
                )
                if relation:
                    key = (gs.id, "redemption", r.id, relation)
                    if key not in seen:
                        seen.add(key)
                        links.append(HostedGameSessionEventLinkRecord(
                            id=str(uuid4()),
                            workspace_id=workspace_id,
                            game_session_id=gs.id,
                            event_type="redemption",
                            event_id=r.id,
                            relation=relation,
                        ))

        return links


# ---------------------------------------------------------------------------
# Pure classification function (stateless, testable)
# ---------------------------------------------------------------------------

def _classify_timestamp(
    event_dt: datetime,
    session_start: datetime,
    session_end: Optional[datetime],
    prev_end: Optional[datetime],
    next_start: Optional[datetime],
    is_active: bool,
    *,
    link_type: str,  # "purchase" or "redemption"
) -> Optional[str]:
    """Return 'BEFORE', 'DURING', 'AFTER', or None.

    Boundary rule (Issue #90): start INCLUSIVE (>=), end EXCLUSIVE (<).
    Redemption AFTER links only apply to closed sessions.
    """
    # --- DURING ---
    if session_end is not None and session_start <= event_dt < session_end:
        return "DURING"
    if is_active and event_dt >= session_start:
        if next_start is None or event_dt < next_start:
            return "DURING"

    # --- BEFORE (purchases only, or all events before session start) ---
    if event_dt < session_start:
        if prev_end is None and event_dt < session_start:
            return "BEFORE"
        if prev_end is not None and prev_end <= event_dt < session_start:
            return "BEFORE"

    # --- AFTER (closed sessions only) ---
    if link_type == "redemption" and session_end is not None and event_dt >= session_end:
        if next_start is None:
            return "AFTER"
        if event_dt < next_start:
            return "AFTER"

    return None
