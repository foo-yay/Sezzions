"""Timezone migration service for UTC storage."""
from __future__ import annotations

from typing import Dict

from repositories.database import DatabaseManager
from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc


class TimezoneMigrationService:
    """Migrate existing local timestamps to UTC storage once."""

    def __init__(self, db: DatabaseManager, settings):
        self.db = db
        self.settings = settings

    def migrate_local_timestamps_to_utc(self) -> Dict[str, int]:
        """Convert existing local date/time fields to UTC in-place.

        Returns a dict with row counts per table.
        """
        if self.settings.get("timezone_storage_migrated", False):
            return {}

        tz_name = get_configured_timezone_name(self.settings)
        counts = {
            "purchases": 0,
            "redemptions": 0,
            "expenses": 0,
            "game_sessions": 0,
            "account_adjustments": 0,
        }

        with self.db.transaction():
            counts["purchases"] = self._migrate_table(
                table="purchases",
                id_column="id",
                date_column="purchase_date",
                time_column="purchase_time",
                tz_name=tz_name,
            )
            counts["redemptions"] = self._migrate_table(
                table="redemptions",
                id_column="id",
                date_column="redemption_date",
                time_column="redemption_time",
                tz_name=tz_name,
            )
            counts["expenses"] = self._migrate_table(
                table="expenses",
                id_column="id",
                date_column="expense_date",
                time_column="expense_time",
                tz_name=tz_name,
            )
            counts["account_adjustments"] = self._migrate_table(
                table="account_adjustments",
                id_column="id",
                date_column="effective_date",
                time_column="effective_time",
                tz_name=tz_name,
            )
            counts["game_sessions"] = self._migrate_game_sessions(tz_name)

        self.settings.set("timezone_storage_migrated", True)
        return counts

    def _migrate_table(
        self,
        *,
        table: str,
        id_column: str,
        date_column: str,
        time_column: str,
        tz_name: str,
    ) -> int:
        rows = self.db.fetch_all(
            f"SELECT {id_column}, {date_column}, {time_column} FROM {table}",
            (),
        )
        updated = 0
        for row in rows:
            row_id = row[id_column]
            date_value = row[date_column]
            time_value = row[time_column]
            if not date_value:
                continue
            utc_date, utc_time = local_date_time_to_utc(date_value, time_value, tz_name)
            if str(date_value) != utc_date or (time_value or "00:00:00") != utc_time:
                self.db.execute_no_commit(
                    f"UPDATE {table} SET {date_column} = ?, {time_column} = ? WHERE {id_column} = ?",
                    (utc_date, utc_time, row_id),
                )
                updated += 1
        return updated

    def _migrate_game_sessions(self, tz_name: str) -> int:
        rows = self.db.fetch_all(
            """
            SELECT id, session_date, session_time, end_date, end_time
            FROM game_sessions
            """,
            (),
        )
        updated = 0
        for row in rows:
            session_date = row["session_date"]
            session_time = row["session_time"]
            if not session_date:
                continue
            session_date_utc, session_time_utc = local_date_time_to_utc(
                session_date,
                session_time,
                tz_name,
            )
            end_date_utc = None
            end_time_utc = None
            if row["end_date"]:
                end_date_utc, end_time_utc = local_date_time_to_utc(
                    row["end_date"],
                    row["end_time"],
                    tz_name,
                )
            self.db.execute_no_commit(
                """
                UPDATE game_sessions
                SET session_date = ?, session_time = ?, end_date = ?, end_time = ?
                WHERE id = ?
                """,
                (
                    session_date_utc,
                    session_time_utc,
                    end_date_utc,
                    end_time_utc,
                    row["id"],
                ),
            )
            updated += 1
        return updated
