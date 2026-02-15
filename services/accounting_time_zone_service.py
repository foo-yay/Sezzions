"""Accounting time zone history utilities (Issue #117)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, date as date_type
from decimal import Decimal
from bisect import bisect_right
from typing import Iterable, Optional

from repositories.database import DatabaseManager
from tools.timezone_utils import (
    get_accounting_timezone_name,
    local_date_time_to_utc,
    utc_date_time_to_local,
)
from services.tax_withholding_service import TaxWithholdingService


@dataclass(frozen=True)
class AccountingTimeZoneEntry:
    effective_utc: datetime
    tz_name: str


class AccountingTimeZoneResolver:
    """Resolve the accounting time zone in effect for a UTC timestamp."""

    def __init__(self, db: DatabaseManager, settings=None):
        self.db = db
        self.settings = settings
        self._entries = self._load_entries()

    def _load_entries(self) -> list[AccountingTimeZoneEntry]:
        try:
            rows = self.db.fetch_all(
                """
                SELECT effective_utc_timestamp, accounting_time_zone
                FROM accounting_time_zone_history
                ORDER BY effective_utc_timestamp ASC
                """,
                (),
            )
        except Exception:
            rows = []

        entries: list[AccountingTimeZoneEntry] = []
        for row in rows or []:
            ts = row.get("effective_utc_timestamp") if row else None
            tz_name = row.get("accounting_time_zone") if row else None
            if not ts or not tz_name:
                continue
            try:
                parsed = datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            entries.append(AccountingTimeZoneEntry(effective_utc=parsed, tz_name=str(tz_name)))

        if not entries:
            fallback = get_accounting_timezone_name(self.settings)
            entries.append(
                AccountingTimeZoneEntry(
                    effective_utc=datetime(1970, 1, 1, tzinfo=timezone.utc),
                    tz_name=fallback,
                )
            )
        return entries

    def resolve_timezone(self, utc_date: date_type | str, utc_time: Optional[str]) -> str:
        utc_dt = _parse_utc_timestamp(utc_date, utc_time)
        effective_times = [entry.effective_utc for entry in self._entries]
        idx = bisect_right(effective_times, utc_dt) - 1
        if idx < 0:
            return self._entries[0].tz_name
        return self._entries[idx].tz_name

    def utc_to_accounting_local(self, utc_date: date_type | str, utc_time: Optional[str]) -> tuple[date_type, str]:
        tz_name = self.resolve_timezone(utc_date, utc_time)
        return utc_date_time_to_local(utc_date, utc_time, tz_name)


class AccountingTimeZoneService:
    """Manage Accounting TZ history and recompute derived tables."""

    def __init__(self, db: DatabaseManager, settings=None):
        self.db = db
        self.settings = settings

    def ensure_history_seeded(self) -> None:
        """Seed accounting_time_zone_history if empty."""
        try:
            row = self.db.fetch_one(
                "SELECT COUNT(1) as cnt FROM accounting_time_zone_history",
                (),
            )
            if row and row.get("cnt", 0) > 0:
                return
        except Exception:
            return

        tz_name = get_accounting_timezone_name(self.settings)
        self.db.execute(
            """
            INSERT INTO accounting_time_zone_history (effective_utc_timestamp, accounting_time_zone)
            VALUES (?, ?)
            """,
            ("1970-01-01 00:00:00", tz_name),
        )
        if self.settings is not None:
            try:
                self.settings.set("accounting_time_zone_history_seeded", True)
            except Exception:
                pass

    def add_history_entry(
        self,
        new_time_zone: str,
        effective_date: date_type | str,
        effective_time: str,
        reason: Optional[str] = None,
    ) -> str:
        """Insert a new accounting time zone history entry, returning UTC timestamp string."""
        utc_date, utc_time = local_date_time_to_utc(effective_date, effective_time, new_time_zone)
        effective_utc_ts = f"{utc_date} {utc_time}"
        self.db.execute(
            """
            INSERT INTO accounting_time_zone_history (effective_utc_timestamp, accounting_time_zone, reason)
            VALUES (?, ?, ?)
            """,
            (effective_utc_ts, new_time_zone, reason),
        )
        return effective_utc_ts

    def change_accounting_time_zone(
        self,
        new_time_zone: str,
        effective_date: date_type | str,
        effective_time: str,
        reason: Optional[str] = None,
    ) -> str:
        """Change Accounting TZ with rollback if recompute fails."""
        self.ensure_history_seeded()
        effective_utc_ts = self.add_history_entry(new_time_zone, effective_date, effective_time, reason)
        try:
            self.recompute_from_utc(effective_utc_ts)
        except Exception:
            try:
                self.db.execute(
                    "DELETE FROM accounting_time_zone_history WHERE effective_utc_timestamp = ? AND accounting_time_zone = ?",
                    (effective_utc_ts, new_time_zone),
                )
            except Exception:
                pass
            raise
        return effective_utc_ts

    def recompute_from_utc(self, effective_utc_timestamp: str) -> None:
        """Recompute daily_sessions and daily_date_tax from an effective UTC timestamp."""
        resolver = AccountingTimeZoneResolver(self.db, self.settings)
        try:
            effective_dt = datetime.strptime(effective_utc_timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            effective_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

        rows = self.db.fetch_all(
            """
            SELECT user_id, end_date, COALESCE(end_time, session_time, '00:00:00') as end_time,
                   net_taxable_pl
            FROM game_sessions
            WHERE status = 'Closed'
              AND deleted_at IS NULL
              AND end_date IS NOT NULL
              AND (
                    end_date > ? OR
                    (end_date = ? AND COALESCE(end_time, session_time, '00:00:00') >= ?)
                  )
            """,
            (
                effective_dt.date().isoformat(),
                effective_dt.date().isoformat(),
                effective_dt.strftime("%H:%M:%S"),
            ),
        )

        user_date_totals: dict[tuple[str, int], dict[str, Decimal]] = {}
        date_totals: dict[str, Decimal] = {}
        date_counts: dict[tuple[str, int], int] = {}

        for row in rows:
            end_date = row.get("end_date")
            end_time = row.get("end_time") or "00:00:00"
            local_date, _ = resolver.utc_to_accounting_local(end_date, end_time)
            date_key = local_date.isoformat()
            user_id = row.get("user_id")
            try:
                net_taxable = Decimal(str(row.get("net_taxable_pl") or 0))
            except Exception:
                net_taxable = Decimal("0")

            user_key = (date_key, user_id)
            if user_key not in user_date_totals:
                user_date_totals[user_key] = {"net": Decimal("0")}
                date_counts[user_key] = 0
            user_date_totals[user_key]["net"] += net_taxable
            date_counts[user_key] += 1

            date_totals[date_key] = date_totals.get(date_key, Decimal("0")) + net_taxable

        affected_dates = sorted(date_totals.keys())
        if not affected_dates:
            return

        with self.db.transaction():
            # Clear existing daily_sessions rows for affected dates
            for date_key in affected_dates:
                self.db.execute_no_commit(
                    "DELETE FROM daily_sessions WHERE session_date = ?",
                    (date_key,),
                )

            # Insert rebuilt daily_sessions rows
            for (date_key, user_id), totals in user_date_totals.items():
                self.db.execute_no_commit(
                    """
                    INSERT OR REPLACE INTO daily_sessions (
                        session_date, user_id, net_daily_pnl, num_game_sessions
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        date_key,
                        user_id,
                        float(totals["net"]),
                        date_counts.get((date_key, user_id), 0),
                    ),
                )

            tax_service = TaxWithholdingService(self.db, self.settings)
            config = tax_service.get_config()
            for date_key in affected_dates:
                if not config.enabled:
                    self.db.execute_no_commit(
                        "DELETE FROM daily_date_tax WHERE session_date = ?",
                        (date_key,),
                    )
                    continue

                existing = self.db.fetch_one(
                    """
                    SELECT tax_withholding_rate_pct, tax_withholding_is_custom
                    FROM daily_date_tax
                    WHERE session_date = ?
                    """,
                    (date_key,),
                )
                if existing and existing.get("tax_withholding_is_custom"):
                    try:
                        rate_pct = Decimal(str(existing.get("tax_withholding_rate_pct")))
                    except Exception:
                        rate_pct = config.default_rate_pct
                    is_custom = True
                else:
                    rate_pct = config.default_rate_pct
                    is_custom = False

                amount = tax_service.compute_amount(date_totals.get(date_key, Decimal("0")), rate_pct)
                if existing:
                    self.db.execute_no_commit(
                        """
                        UPDATE daily_date_tax
                        SET net_daily_pnl = ?,
                            tax_withholding_rate_pct = ?,
                            tax_withholding_is_custom = ?,
                            tax_withholding_amount = ?
                        WHERE session_date = ?
                        """,
                        (
                            float(date_totals.get(date_key, Decimal("0"))),
                            float(rate_pct) if rate_pct is not None else None,
                            1 if is_custom else 0,
                            float(amount) if amount is not None else None,
                            date_key,
                        ),
                    )
                else:
                    self.db.execute_no_commit(
                        """
                        INSERT INTO daily_date_tax (
                            session_date, net_daily_pnl,
                            tax_withholding_rate_pct, tax_withholding_is_custom,
                            tax_withholding_amount
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            date_key,
                            float(date_totals.get(date_key, Decimal("0"))),
                            float(rate_pct) if rate_pct is not None else None,
                            1 if is_custom else 0,
                            float(amount) if amount is not None else None,
                        ),
                    )


def _parse_utc_timestamp(utc_date: date_type | str, utc_time: Optional[str]) -> datetime:
    if isinstance(utc_date, date_type):
        date_value = utc_date
    else:
        date_value = datetime.strptime(str(utc_date), "%Y-%m-%d").date()
    time_value = utc_time or "00:00:00"
    if len(time_value) == 5:
        time_value = f"{time_value}:00"
    dt = datetime.combine(date_value, datetime.strptime(time_value, "%H:%M:%S").time())
    return dt.replace(tzinfo=timezone.utc)
