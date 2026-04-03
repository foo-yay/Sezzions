"""Hosted timestamp uniqueness enforcement service.

Ensures no two events (purchases, redemptions, sessions) for a given
(workspace, user, site) triple share the exact same stored timestamp.
Auto-increments by 1 second on conflict (up to 3600 attempts).

Hosted adaptation notes vs desktop:
- Uses SQLAlchemy ORM queries instead of raw SQL
- IDs are string UUIDs, not integers
- No timezone conversion layer: hosted stores dates/times as-is from the API
  (the caller is responsible for any timezone handling before calling this service)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from services.hosted.persistence import (
    HostedGameSessionRecord,
    HostedPurchaseRecord,
    HostedRedemptionRecord,
)


def _normalize_time(value: Optional[str]) -> str:
    if not value:
        return "00:00:00"
    value = value.strip()
    if len(value) == 5:
        return f"{value}:00"
    return value


class HostedTimestampService:
    """Enforce timestamp uniqueness across event types for a workspace."""

    MAX_ATTEMPTS = 3600  # 1 hour window

    def ensure_unique_timestamp(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        date_str: str,
        time_str: str,
        exclude_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        """Return (date, time, was_adjusted) with a conflict-free timestamp.

        Parameters
        ----------
        session : SQLAlchemy session (must be within a transaction)
        workspace_id, user_id, site_id : scope identifiers
        date_str : ISO date  e.g. "2026-01-15"
        time_str : time      e.g. "14:30:00"
        exclude_id : skip this record id during conflict check (for edits)
        event_type : 'purchase' | 'redemption' | 'session_start' | 'session_end'
        """
        time_str = _normalize_time(time_str)

        try:
            current_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return (date_str, time_str, False)

        original_dt = current_dt

        for _ in range(self.MAX_ATTEMPTS):
            cur_date = current_dt.strftime("%Y-%m-%d")
            cur_time = current_dt.strftime("%H:%M:%S")

            if not self._has_conflict(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                site_id=site_id,
                date_str=cur_date,
                time_str=cur_time,
                exclude_id=exclude_id,
                event_type=event_type,
            ):
                was_adjusted = current_dt != original_dt
                return (cur_date, cur_time, was_adjusted)

            current_dt += timedelta(seconds=1)

        # Fallback (should never happen in practice)
        return (date_str, time_str, False)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _has_conflict(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        date_str: str,
        time_str: str,
        exclude_id: Optional[str],
        event_type: Optional[str],
    ) -> bool:
        """Return True if *any* event occupies this timestamp slot."""

        # --- purchases ---
        q = session.query(func.count(HostedPurchaseRecord.id)).filter(
            HostedPurchaseRecord.workspace_id == workspace_id,
            HostedPurchaseRecord.user_id == user_id,
            HostedPurchaseRecord.site_id == site_id,
            HostedPurchaseRecord.purchase_date == date_str,
            HostedPurchaseRecord.purchase_time == time_str,
            HostedPurchaseRecord.deleted_at.is_(None),
        )
        if exclude_id and event_type == "purchase":
            q = q.filter(HostedPurchaseRecord.id != exclude_id)
        if q.scalar() > 0:
            return True

        # --- redemptions ---
        q = session.query(func.count(HostedRedemptionRecord.id)).filter(
            HostedRedemptionRecord.workspace_id == workspace_id,
            HostedRedemptionRecord.user_id == user_id,
            HostedRedemptionRecord.site_id == site_id,
            HostedRedemptionRecord.redemption_date == date_str,
            HostedRedemptionRecord.redemption_time == time_str,
            HostedRedemptionRecord.deleted_at.is_(None),
        )
        if exclude_id and event_type == "redemption":
            q = q.filter(HostedRedemptionRecord.id != exclude_id)
        if q.scalar() > 0:
            return True

        # --- session start times ---
        q = session.query(func.count(HostedGameSessionRecord.id)).filter(
            HostedGameSessionRecord.workspace_id == workspace_id,
            HostedGameSessionRecord.user_id == user_id,
            HostedGameSessionRecord.site_id == site_id,
            HostedGameSessionRecord.session_date == date_str,
            HostedGameSessionRecord.session_time == time_str,
            HostedGameSessionRecord.deleted_at.is_(None),
        )
        if exclude_id and event_type == "session_start":
            q = q.filter(HostedGameSessionRecord.id != exclude_id)
        if q.scalar() > 0:
            return True

        # --- session end times (closed sessions only) ---
        q = session.query(func.count(HostedGameSessionRecord.id)).filter(
            HostedGameSessionRecord.workspace_id == workspace_id,
            HostedGameSessionRecord.user_id == user_id,
            HostedGameSessionRecord.site_id == site_id,
            HostedGameSessionRecord.end_date == date_str,
            HostedGameSessionRecord.end_time == time_str,
            HostedGameSessionRecord.status == "Closed",
            HostedGameSessionRecord.deleted_at.is_(None),
        )
        if exclude_id and event_type == "session_end":
            q = q.filter(HostedGameSessionRecord.id != exclude_id)
        if q.scalar() > 0:
            return True

        return False
