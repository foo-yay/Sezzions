"""Tax withholding estimates (Issue #29).

Computes an estimated tax set-aside amount per closed game session.

Key semantics:
- Uses per-session stored rate when present (historical).
- When enabled and a closed session has no stored rate yet, captures the current
  global default rate and marks `tax_withholding_is_custom = 0`.
- Amount is always `max(0, net_taxable_pl) * (rate_pct/100)`.
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

    def apply_to_session_model(self, session) -> None:
        """Mutates a GameSession model in-place (used during session recalculation).

        Only acts for closed sessions.
        """
        if session is None or getattr(session, "status", None) != "Closed":
            return

        config = self.get_config()
        if not config.enabled:
            return

        # Capture default rate at close time if not already stored.
        if getattr(session, "tax_withholding_rate_pct", None) is None:
            session.tax_withholding_rate_pct = config.default_rate_pct
            session.tax_withholding_is_custom = False

        session.tax_withholding_amount = self.compute_amount(
            getattr(session, "net_taxable_pl", None),
            getattr(session, "tax_withholding_rate_pct", None),
        )

    def bulk_recalculate(
        self,
        *,
        site_id: Optional[int] = None,
        user_id: Optional[int] = None,
        overwrite_custom: bool = False,
    ) -> int:
        """Bulk recalculation (retroactive) of withholding fields.

        Invariants:
        - Updates only withholding columns.
        - Runs atomically in a transaction.

        Returns: number of sessions updated.
        """
        config = self.get_config()
        if not config.enabled:
            return 0

        where = ["status = 'Closed'", "net_taxable_pl IS NOT NULL"]
        params = []
        if site_id is not None:
            where.append("site_id = ?")
            params.append(site_id)
        if user_id is not None:
            where.append("user_id = ?")
            params.append(user_id)

        where_sql = " AND ".join(where)
        rows = self.db.fetch_all(
            f"""
            SELECT id, net_taxable_pl, tax_withholding_rate_pct, tax_withholding_is_custom
            FROM game_sessions
            WHERE {where_sql}
            ORDER BY COALESCE(end_date, session_date) ASC, COALESCE(end_time, session_time) ASC
            """,
            tuple(params),
        )

        updates = []
        updated_count = 0
        for row in rows:
            is_custom = bool(row.get("tax_withholding_is_custom") or 0)
            if is_custom and not overwrite_custom:
                continue

            rate_pct = config.default_rate_pct
            amount = self.compute_amount(Decimal(str(row["net_taxable_pl"])), rate_pct)

            updates.append(
                (
                    float(rate_pct),
                    0,  # is_custom
                    str(amount) if amount is not None else None,
                    row["id"],
                )
            )
            updated_count += 1

        if not updates:
            return 0

        with self.db.transaction():
            self.db.executemany_no_commit(
                """
                UPDATE game_sessions
                SET tax_withholding_rate_pct = ?,
                    tax_withholding_is_custom = ?,
                    tax_withholding_amount = ?
                WHERE id = ?
                """,
                updates,
            )

        return updated_count
