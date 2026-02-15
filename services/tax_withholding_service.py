"""Tax withholding estimates (Issue #29).

Computes an estimated tax set-aside amount per DATE (rollup of all users' game sessions).

Key semantics:
- Tax withholding is calculated at the DATE level (not per user, not per session).
- Daily net P/L = sum of ALL users' net P/L for that local date (based on local end date/time).
- Only positive net is taxed: max(0, sum_of_all_users_pnl) * rate.
- Uses stored rate when present (historical or custom override).
- When enabled and a date has no stored rate yet, uses the global default rate.
- Amount is always `max(0, net_daily_pl) * (rate_pct/100)`.
- Bulk recalculation can retroactively overwrite historical stored values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional


@dataclass(frozen=True)
class TaxWithholdingConfig:
    enabled: bool
    default_rate_pct: Decimal


class TaxWithholdingService:
    def __init__(self, db_manager, settings=None):
        self.db = db_manager
        # settings is intentionally duck-typed: `.get(key, default)`
        self.settings = settings

    def _table_exists(self, table_name: str) -> bool:
        row = self.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return bool(row)

    def _get_timezone_name(self) -> str:
        from tools.timezone_utils import get_configured_timezone_name

        return get_configured_timezone_name(self.settings)

    def _parse_local_date(self, value: str | date_type) -> date_type:
        if isinstance(value, date_type):
            return value
        return date_type.fromisoformat(value)

    def _fetch_closed_sessions_for_local_range(
        self,
        start_date: Optional[date_type],
        end_date: Optional[date_type],
    ) -> list[dict]:
        if not self._table_exists("game_sessions"):
            return []

        query = """
            SELECT
                session_date,
                session_time,
                end_date,
                end_time,
                net_taxable_pl
                        FROM game_sessions
                        WHERE status = 'Closed'
                            AND deleted_at IS NULL
        """
        params: list = []

        if start_date or end_date:
            from tools.timezone_utils import local_date_range_to_utc_bounds

            tz_name = self._get_timezone_name()
            start_value = start_date or end_date
            end_value = end_date or start_date
            if start_value and end_value:
                start_utc, end_utc = local_date_range_to_utc_bounds(start_value, end_value, tz_name)
                query += (
                    " AND (COALESCE(end_date, session_date) > ? OR "
                    "(COALESCE(end_date, session_date) = ? AND COALESCE(end_time, session_time, '00:00:00') >= ?))"
                    " AND (COALESCE(end_date, session_date) < ? OR "
                    "(COALESCE(end_date, session_date) = ? AND COALESCE(end_time, session_time, '00:00:00') <= ?))"
                )
                params.extend([start_utc[0], start_utc[0], start_utc[1], end_utc[0], end_utc[0], end_utc[1]])

        return self.db.fetch_all(query, tuple(params))

    def _iter_local_dates(self, rows: Iterable[dict]) -> Iterable[tuple[date_type, Decimal]]:
        from tools.timezone_utils import utc_date_time_to_local

        tz_name = self._get_timezone_name()
        for row in rows:
            accounting_date = row.get("end_date") or row.get("session_date")
            accounting_time = row.get("end_time") or row.get("session_time") or "00:00:00"
            if not accounting_date:
                continue
            local_date, _ = utc_date_time_to_local(accounting_date, accounting_time, tz_name)
            try:
                net_taxable = Decimal(str(row.get("net_taxable_pl") or 0))
            except Exception:
                net_taxable = Decimal("0")
            yield local_date, net_taxable

    def get_config(self) -> TaxWithholdingConfig:
        settings = self.settings
        if settings is None:
            return TaxWithholdingConfig(enabled=False, default_rate_pct=Decimal("0"))

        enabled = bool(settings.get("tax_withholding_enabled", False))
        default_rate_raw = settings.get("tax_withholding_default_rate_pct", 0)
        try:
            default_rate_pct = Decimal(str(default_rate_raw))
        except Exception:
            default_rate_pct = Decimal("0")

        if default_rate_pct < 0:
            default_rate_pct = Decimal("0")
        if default_rate_pct > 100:
            default_rate_pct = Decimal("100")

        return TaxWithholdingConfig(enabled=enabled, default_rate_pct=default_rate_pct)

    @staticmethod
    def compute_amount(net_taxable_pl: Optional[Decimal], rate_pct: Optional[Decimal]) -> Optional[Decimal]:
        if net_taxable_pl is None or rate_pct is None:
            return None

        try:
            pl = Decimal(str(net_taxable_pl))
            rate = Decimal(str(rate_pct))
        except Exception:
            return None

        if pl <= 0:
            return Decimal("0.00")

        amt = (pl * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amt < 0:
            return Decimal("0.00")
        return amt

    def apply_to_date(
        self,
        session_date: str,
        custom_rate_pct: Optional[Decimal] = None,
    ) -> None:
        """Calculate and store tax withholding for a DATE.
        
        Tax is calculated on the NET P/L across ALL users (winners netted against losers).
        Only positive net P/L is taxed.
        
        Example:
            User 1: +$342.61, User 2: -$205.55 → Net: $137.06 → Tax: $27.41 (at 20%)
        
        Args:
            session_date: Date (YYYY-MM-DD)
            custom_rate_pct: Optional custom rate override (if None, uses default)
        """
        config = self.get_config()
        if not config.enabled:
            # Clear any existing tax data if feature is disabled
            self.db.execute(
                """
                DELETE FROM daily_date_tax WHERE session_date = ?
                """,
                (session_date,),
            )
            return

        # Calculate net P/L across ALL users for this date (sum winners and losers)
        net_daily_pl = self._calculate_date_net_pl(session_date)

        # Determine rate to use.
        # If no custom rate is provided, preserve an existing custom override (if any).
        if custom_rate_pct is not None:
            rate_pct = Decimal(str(custom_rate_pct))
            is_custom = True
        else:
            existing = self.db.fetch_one(
                """
                SELECT tax_withholding_rate_pct, tax_withholding_is_custom
                FROM daily_date_tax
                WHERE session_date = ?
                """,
                (session_date,),
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

        # Compute tax amount (only on positive net P/L)
        amount = self.compute_amount(net_daily_pl, rate_pct)

        # Store in daily_date_tax table
        self.db.execute(
            """
            INSERT OR REPLACE INTO daily_date_tax (
                session_date, 
                net_daily_pnl,
                tax_withholding_rate_pct,
                tax_withholding_is_custom,
                tax_withholding_amount
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_date,
                float(net_daily_pl) if net_daily_pl is not None else 0.0,
                float(rate_pct) if rate_pct is not None else None,
                1 if is_custom else 0,
                float(amount) if amount is not None else None,
            ),
        )

    def _calculate_date_net_pl(self, session_date: str) -> Decimal:
        """Calculate total net P/L for a date across ALL users."""
        target_date = self._parse_local_date(session_date)
        rows = self._fetch_closed_sessions_for_local_range(target_date, target_date)
        total = Decimal("0.00")
        for local_date, net_taxable in self._iter_local_dates(rows):
            if local_date == target_date:
                total += net_taxable
        return total

    def bulk_recalculate(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        overwrite_custom: bool = False,
    ) -> int:
        """Bulk recalculation (retroactive) of withholding fields for dates.

        Recalculates tax withholding for dates (optionally filtered by range) based on current settings.
        Tax is calculated on the NET of ALL users' P/L for each date.
        Respects custom rates unless overwrite_custom=True.

        Args:
            start_date: Optional start date (YYYY-MM-DD) - if None, starts from earliest date
            end_date: Optional end date (YYYY-MM-DD) - if None, goes to latest date
            overwrite_custom: If True, overwrites custom rates; if False, skips them

        Note: Site/user filtering is NOT supported because tax must be calculated
        across ALL users for a date (netting winners against losers).

        Invariants:
        - Updates only withholding columns in daily_date_tax table.
        - Runs atomically in a transaction.

        Returns: number of dates updated.
        """
        config = self.get_config()
        if not config.enabled:
            return 0

        start_local = self._parse_local_date(start_date) if start_date else None
        end_local = self._parse_local_date(end_date) if end_date else None
        rows = self._fetch_closed_sessions_for_local_range(start_local, end_local)

        local_dates = set()
        for local_date, _ in self._iter_local_dates(rows):
            if start_local and local_date < start_local:
                continue
            if end_local and local_date > end_local:
                continue
            local_dates.add(local_date)

        updates = []
        updated_count = 0
        for local_date in sorted(local_dates):
            session_date = local_date.isoformat()
            
            # Check if this date has custom tax (skip if overwrite_custom is False)
            existing = self.db.fetch_one(
                "SELECT tax_withholding_is_custom FROM daily_date_tax WHERE session_date = ?",
                (session_date,)
            )
            if existing and existing.get("tax_withholding_is_custom") and not overwrite_custom:
                continue

            # Calculate net P/L across all users for this date
            net_daily_pl = self._calculate_date_net_pl(session_date)
            
            rate_pct = config.default_rate_pct
            amount = self.compute_amount(net_daily_pl, rate_pct)

            updates.append(
                (
                    session_date,
                    float(net_daily_pl) if net_daily_pl is not None else 0.0,
                    float(rate_pct),
                    0,  # is_custom (reset to default)
                    float(amount) if amount is not None else None,
                )
            )
            updated_count += 1

        if not updates:
            return 0

        with self.db.transaction():
            self.db.executemany_no_commit(
                """
                INSERT OR REPLACE INTO daily_date_tax (
                    session_date,
                    net_daily_pnl,
                    tax_withholding_rate_pct,
                    tax_withholding_is_custom,
                    tax_withholding_amount
                ) VALUES (?, ?, ?, ?, ?)
                """,
                updates,
            )

        return updated_count
