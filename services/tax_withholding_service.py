"""Tax withholding estimates (Issue #29).

Computes an estimated tax set-aside amount per daily session (rollup of game sessions).

Key semantics:
- Tax withholding is calculated at the DAILY level, not per game session.
- Daily net P/L = sum of all game session net P/L for that (date, user).
- Uses stored rate when present (historical or custom override).
- When enabled and a daily session has no stored rate yet, uses the global default rate.
- Amount is always `max(0, net_daily_pl) * (rate_pct/100)`.
- Bulk recalculation can retroactively overwrite historical stored values.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass(frozen=True)
class TaxWithholdingConfig:
    enabled: bool
    default_rate_pct: Decimal


class TaxWithholdingService:
    def __init__(self, db_manager, settings=None):
        self.db = db_manager
        # settings is intentionally duck-typed: `.get(key, default)`
        self.settings = settings

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

    def apply_to_daily_session(
        self,
        session_date: str,
        user_id: int,
        net_daily_pl: Optional[Decimal],
        custom_rate_pct: Optional[Decimal] = None,
    ) -> None:
        """Calculate and store tax withholding for a daily session.

        Args:
            session_date: Date of the daily session (YYYY-MM-DD)
            user_id: User ID
            net_daily_pl: Net profit/loss for the day (sum of game sessions)
            custom_rate_pct: Optional custom rate override (if None, uses default)
        """
        config = self.get_config()
        if not config.enabled:
            # Clear any existing tax data if feature is disabled
            self.db.execute(
                """
                UPDATE daily_sessions
                SET tax_withholding_rate_pct = NULL,
                    tax_withholding_is_custom = 0,
                    tax_withholding_amount = NULL
                WHERE session_date = ? AND user_id = ?
                """,
                (session_date, user_id),
            )
            return

        # Determine rate to use
        if custom_rate_pct is not None:
            rate_pct = Decimal(str(custom_rate_pct))
            is_custom = True
        else:
            rate_pct = config.default_rate_pct
            is_custom = False

        # Compute amount
        amount = self.compute_amount(net_daily_pl, rate_pct)

        # Store in daily_sessions table
        self.db.execute_write(
            """
            UPDATE daily_sessions
            SET tax_withholding_rate_pct = ?,
                tax_withholding_is_custom = ?,
                tax_withholding_amount = ?
            WHERE session_date = ? AND user_id = ?
            """,
            (
                float(rate_pct) if rate_pct is not None else None,
                1 if is_custom else 0,
                str(amount) if amount is not None else None,
                session_date,
                user_id,
            ),
        )

    def bulk_recalculate(
        self,
        *,
        site_id: Optional[int] = None,
        user_id: Optional[int] = None,
        overwrite_custom: bool = False,
    ) -> int:
        """Bulk recalculation (retroactive) of withholding fields for daily sessions.

        Recalculates tax withholding for all daily sessions based on current settings.
        Respects custom rates unless overwrite_custom=True.

        Invariants:
        - Updates only withholding columns in daily_sessions table.
        - Runs atomically in a transaction.

        Returns: number of daily sessions updated.
        """
        config = self.get_config()
        if not config.enabled:
            return 0

        # Build WHERE clause for filtering
        where_parts = []
        params = []
        if site_id is not None:
            # Filter by site_id via game sessions
            where_parts.append(
                """
                EXISTS (
                    SELECT 1 FROM game_sessions gs
                    WHERE gs.session_date = daily_sessions.session_date
                      AND gs.user_id = daily_sessions.user_id
                      AND gs.site_id = ?
                )
                """
            )
            params.append(site_id)
        if user_id is not None:
            where_parts.append("user_id = ?")
            params.append(user_id)

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"

        # Fetch all daily sessions that need updating
        rows = self.db.fetch_all(
            f"""
            SELECT session_date, user_id, net_daily_pnl,
                   tax_withholding_is_custom
            FROM daily_sessions
            WHERE {where_sql}
            ORDER BY session_date ASC
            """,
            tuple(params),
        )

        updates = []
        updated_count = 0
        for row in rows:
            is_custom = bool(row.get("tax_withholding_is_custom") or 0)
            if is_custom and not overwrite_custom:
                continue

            net_daily_pl = row.get("net_daily_pnl")
            if net_daily_pl is None:
                continue

            rate_pct = config.default_rate_pct
            amount = self.compute_amount(Decimal(str(net_daily_pl)), rate_pct)

            updates.append(
                (
                    float(rate_pct),
                    0,  # is_custom (reset to default)
                    str(amount) if amount is not None else None,
                    row["session_date"],
                    row["user_id"],
                )
            )
            updated_count += 1

        if not updates:
            return 0

        with self.db.transaction():
            self.db.executemany_no_commit(
                """
                UPDATE daily_sessions
                SET tax_withholding_rate_pct = ?,
                    tax_withholding_is_custom = ?,
                    tax_withholding_amount = ?
                WHERE session_date = ? AND user_id = ?
                """,
                updates,
            )

        return updated_count
