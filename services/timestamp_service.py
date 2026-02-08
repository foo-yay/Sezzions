"""
Timestamp uniqueness enforcement service.

Ensures no two events (purchases, redemptions, sessions) for a given user/site
share the exact same timestamp. Auto-increments by 1 second until a unique
timestamp is found.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from repositories.database import DatabaseManager


class TimestampService:
    """Service for enforcing timestamp uniqueness across events."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def ensure_unique_timestamp(
        self,
        user_id: int,
        site_id: int,
        date_val,
        time_str: str,
        exclude_id: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        """
        Ensure timestamp is unique for this user/site pair across all events.

        Args:
            user_id: User ID
            site_id: Site ID
            date_val: Date value (date object or string)
            time_str: Time string (HH:MM:SS format)
            exclude_id: Optional ID to exclude from conflict check (for edits)
            event_type: Optional event type to check only ('purchase', 'redemption', 'session_start', 'session_end')

        Returns:
            Tuple of (adjusted_date_str, adjusted_time_str, was_adjusted)
        """
        from datetime import date as date_type

        # Convert date to string format
        if isinstance(date_val, date_type):
            date_str = date_val.isoformat()
        else:
            date_str = str(date_val)

        # Parse initial datetime
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # If parsing fails, return original
            return (date_str, time_str, False)

        original_dt = dt
        max_attempts = 3600  # Maximum 1 hour of incrementing
        attempt = 0

        while attempt < max_attempts:
            current_date_str = dt.date().isoformat()
            current_time_str = dt.time().strftime("%H:%M:%S")

            # Check if this timestamp conflicts with any existing event
            has_conflict = self._check_timestamp_conflict(
                user_id, site_id, current_date_str, current_time_str, exclude_id, event_type
            )

            if not has_conflict:
                # Found a unique timestamp
                was_adjusted = (dt != original_dt)
                return (current_date_str, current_time_str, was_adjusted)

            # Increment by 1 second and try again
            dt += timedelta(seconds=1)
            attempt += 1

        # Fallback: return original if we couldn't find a slot
        # (This should never happen in practice)
        return (date_str, time_str, False)

    def _check_timestamp_conflict(
        self,
        user_id: int,
        site_id: int,
        date_str: str,
        time_str: str,
        exclude_id: Optional[int],
        event_type: Optional[str],
    ) -> bool:
        """
        Check if timestamp conflicts with any existing event.

        Returns True if conflict exists, False if timestamp is unique.
        """
        # Check purchases
        if event_type is None or event_type == "purchase":
            query = """
                SELECT COUNT(*) as cnt FROM purchases
                WHERE user_id = ? AND site_id = ?
                  AND purchase_date = ? AND purchase_time = ?
            """
            params = [user_id, site_id, date_str, time_str]
            if exclude_id and event_type == "purchase":
                query += " AND id != ?"
                params.append(exclude_id)

            result = self.db.fetch_one(query, tuple(params))
            if result and result["cnt"] > 0:
                return True

        # Check redemptions
        if event_type is None or event_type == "redemption":
            query = """
                SELECT COUNT(*) as cnt FROM redemptions
                WHERE user_id = ? AND site_id = ?
                  AND redemption_date = ? AND redemption_time = ?
            """
            params = [user_id, site_id, date_str, time_str]
            if exclude_id and event_type == "redemption":
                query += " AND id != ?"
                params.append(exclude_id)

            result = self.db.fetch_one(query, tuple(params))
            if result and result["cnt"] > 0:
                return True

        # Check session start times
        if event_type is None or event_type == "session_start":
            query = """
                SELECT COUNT(*) as cnt FROM game_sessions
                WHERE user_id = ? AND site_id = ?
                  AND session_date = ? AND session_time = ?
            """
            params = [user_id, site_id, date_str, time_str]
            if exclude_id and event_type == "session_start":
                query += " AND id != ?"
                params.append(exclude_id)

            result = self.db.fetch_one(query, tuple(params))
            if result and result["cnt"] > 0:
                return True

        # Check session end times
        if event_type is None or event_type == "session_end":
            query = """
                SELECT COUNT(*) as cnt FROM game_sessions
                WHERE user_id = ? AND site_id = ?
                  AND end_date = ? AND end_time = ?
                  AND status = 'Closed'
            """
            params = [user_id, site_id, date_str, time_str]
            if exclude_id and event_type == "session_end":
                query += " AND id != ?"
                params.append(exclude_id)

            result = self.db.fetch_one(query, tuple(params))
            if result and result["cnt"] > 0:
                return True

        return False
