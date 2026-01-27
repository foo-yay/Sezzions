"""Recalculation service - rebuild derived data after edits.

This is the Sezzions OOP equivalent of legacy qt_app.py "Recalculate Everything" and
"scoped rebuild" flows.

Initial implementation focuses on correctness over performance:
- FIFO rebuild: recompute redemption allocations + realized_transactions and refresh purchases.remaining_amount
- Session P/L rebuild: handled elsewhere (GameSessionService)

NOTE: This service intentionally operates directly on the DB for bulk operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from repositories.database import DatabaseManager


def _normalize_time(value: Optional[str]) -> str:
    if not value:
        return "00:00:00"
    value = value.strip()
    if len(value) == 5:
        return f"{value}:00"
    return value


def _to_dt(date_str: str, time_str: Optional[str]) -> datetime:
    return datetime.strptime(f"{date_str} {_normalize_time(time_str)}", "%Y-%m-%d %H:%M:%S")


_CLOSE_BALANCE_RE = re.compile(r"Net Loss:\s*\$([0-9,]+(?:\.[0-9]{1,2})?)")


def _parse_close_balance_loss(notes: Optional[str]) -> Optional[Decimal]:
    if not notes:
        return None
    match = _CLOSE_BALANCE_RE.search(notes)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    try:
        return Decimal(value)
    except Exception:
        return None


@dataclass(frozen=True)
class RebuildResult:
    pairs_processed: int
    redemptions_processed: int
    allocations_written: int
    purchases_updated: int


class RecalculationService:
    """Bulk rebuild operations for derived accounting data."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def iter_pairs(self) -> List[Tuple[int, int]]:
        """Return distinct (user_id, site_id) pairs with any activity."""
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

    def rebuild_fifo_for_pair(self, user_id: int, site_id: int) -> RebuildResult:
        """Rebuild FIFO allocations + realized_transactions for one (user_id, site_id)."""
        conn = self.db._connection
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, amount, purchase_date, COALESCE(purchase_time,'00:00:00') AS pt
            FROM purchases
            WHERE user_id = ? AND site_id = ?
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id),
        )
        purchase_rows = cursor.fetchall()

        purchases: List[Tuple[int, datetime, Decimal]] = []
        remaining: Dict[int, Decimal] = {}
        for r in purchase_rows:
            purchase_id = int(r["id"])
            amt = Decimal(str(r["amount"]))
            dt = _to_dt(r["purchase_date"], r["pt"])
            purchases.append((purchase_id, dt, amt))
            remaining[purchase_id] = amt

        cursor.execute(
            """
                 SELECT id, amount, redemption_date, COALESCE(redemption_time,'00:00:00') AS rt,
                     COALESCE(is_free_sc, 0) AS is_free_sc, COALESCE(more_remaining, 0) AS more_remaining, notes
            FROM redemptions
            WHERE user_id = ? AND site_id = ?
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id),
        )
        redemption_rows = cursor.fetchall()

        redemption_ids = [int(r["id"]) for r in redemption_rows]

        # Clear existing derived records for this pair
        if redemption_ids:
            placeholders = ",".join(["?"] * len(redemption_ids))
            cursor.execute(
                f"DELETE FROM redemption_allocations WHERE redemption_id IN ({placeholders})",
                tuple(redemption_ids),
            )
        cursor.execute(
            "DELETE FROM realized_transactions WHERE user_id = ? AND site_id = ?",
            (user_id, site_id),
        )

        allocations_to_write: List[Tuple[int, int, str]] = []
        realized_to_write: List[Tuple[str, int, int, int, str, str, str]] = []

        # Rebuild chronologically
        for red_row in redemption_rows:
            redemption_id = int(red_row["id"])
            payout = Decimal(str(red_row["amount"]))
            is_free_sc = bool(int(red_row["is_free_sc"] or 0))
            red_dt = _to_dt(red_row["redemption_date"], red_row["rt"])
            notes = red_row["notes"] if "notes" in red_row.keys() else None

            close_balance_loss = _parse_close_balance_loss(notes)
            if payout == 0 and close_balance_loss is not None:
                cost_basis = close_balance_loss
                net_pl = -close_balance_loss
                realized_to_write.append(
                    (
                        red_row["redemption_date"],
                        site_id,
                        user_id,
                        redemption_id,
                        str(cost_basis),
                        str(payout),
                        str(net_pl),
                    )
                )
                continue

            cost_basis = Decimal("0.00")
            if not is_free_sc and payout > 0:
                # Check if this is a Full redemption (more_remaining=False/0)
                more_remaining = bool(int(red_row["more_remaining"] if "more_remaining" in red_row.keys() else 1))
                
                if not more_remaining:
                    # Full redemption: consume ALL remaining basis up to this timestamp
                    remaining_to_allocate = sum(
                        avail for pid, pdt, _pamt in purchases 
                        if pdt <= red_dt and (avail := remaining.get(pid, Decimal("0.00"))) > 0
                    )
                else:
                    # Partial redemption: just allocate the payout amount
                    remaining_to_allocate = payout
                
                for purchase_id, purchase_dt, _purchase_amt in purchases:
                    if remaining_to_allocate <= 0:
                        break
                    if purchase_dt > red_dt:
                        break

                    avail = remaining.get(purchase_id, Decimal("0.00"))
                    if avail <= 0:
                        continue

                    alloc = min(avail, remaining_to_allocate)
                    if alloc <= 0:
                        continue

                    remaining[purchase_id] = avail - alloc
                    remaining_to_allocate -= alloc
                    cost_basis += alloc
                    allocations_to_write.append((redemption_id, purchase_id, str(alloc)))

            net_pl = payout - cost_basis
            realized_to_write.append(
                (
                    red_row["redemption_date"],
                    site_id,
                    user_id,
                    redemption_id,
                    str(cost_basis),
                    str(payout),
                    str(net_pl),
                )
            )

        # Write updated remaining_amount for all purchases in pair
        purchases_updated = 0
        for purchase_id, _dt, _amt in purchases:
            cursor.execute(
                "UPDATE purchases SET remaining_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(remaining[purchase_id]), purchase_id),
            )
            purchases_updated += 1

        if allocations_to_write:
            cursor.executemany(
                """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
                """,
                allocations_to_write,
            )

        if realized_to_write:
            cursor.executemany(
                """
                INSERT INTO realized_transactions
                    (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                realized_to_write,
            )

        conn.commit()

        return RebuildResult(
            pairs_processed=1,
            redemptions_processed=len(redemption_rows),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
        )

    def rebuild_fifo_for_pair_from(
        self,
        user_id: int,
        site_id: int,
        from_date: str,
        from_time: Optional[str] = None,
    ) -> RebuildResult:
        """Scoped FIFO rebuild starting at a boundary redemption timestamp."""
        conn = self.db._connection
        cursor = conn.cursor()
        from_time = _normalize_time(from_time)

        cursor.execute(
            """
            SELECT id, amount, purchase_date, COALESCE(purchase_time,'00:00:00') AS pt
            FROM purchases
            WHERE user_id = ? AND site_id = ?
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id),
        )
        purchase_rows = cursor.fetchall()

        purchases: List[Tuple[int, datetime, Decimal]] = []
        remaining: Dict[int, Decimal] = {}
        for r in purchase_rows:
            purchase_id = int(r["id"])
            amt = Decimal(str(r["amount"]))
            dt = _to_dt(r["purchase_date"], r["pt"])
            purchases.append((purchase_id, dt, amt))
            remaining[purchase_id] = amt

        cursor.execute(
            """
            SELECT ra.purchase_id, ra.allocated_amount
            FROM redemption_allocations ra
            JOIN redemptions r ON ra.redemption_id = r.id
            WHERE r.user_id = ? AND r.site_id = ?
              AND (r.redemption_date < ?
                   OR (r.redemption_date = ? AND COALESCE(r.redemption_time,'00:00:00') < ?))
            """,
            (user_id, site_id, from_date, from_date, from_time),
        )
        allocation_rows = cursor.fetchall()
        for row in allocation_rows:
            purchase_id = int(row["purchase_id"])
            allocated = Decimal(str(row["allocated_amount"]))
            if purchase_id in remaining:
                remaining[purchase_id] = max(Decimal("0.00"), remaining[purchase_id] - allocated)

        cursor.execute(
            """
            SELECT id, amount, redemption_date, COALESCE(redemption_time,'00:00:00') AS rt,
                   COALESCE(is_free_sc, 0) AS is_free_sc, COALESCE(more_remaining, 0) AS more_remaining, notes
            FROM redemptions
            WHERE user_id = ? AND site_id = ?
              AND (redemption_date > ?
                   OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id, from_date, from_date, from_time),
        )
        redemption_rows = cursor.fetchall()

        redemption_ids = [int(r["id"]) for r in redemption_rows]
        if redemption_ids:
            placeholders = ",".join(["?"] * len(redemption_ids))
            cursor.execute(
                f"DELETE FROM redemption_allocations WHERE redemption_id IN ({placeholders})",
                tuple(redemption_ids),
            )
            cursor.execute(
                f"DELETE FROM realized_transactions WHERE redemption_id IN ({placeholders})",
                tuple(redemption_ids),
            )

        allocations_to_write: List[Tuple[int, int, str]] = []
        realized_to_write: List[Tuple[str, int, int, int, str, str, str]] = []

        for red_row in redemption_rows:
            redemption_id = int(red_row["id"])
            payout = Decimal(str(red_row["amount"]))
            is_free_sc = bool(int(red_row["is_free_sc"] or 0))
            red_dt = _to_dt(red_row["redemption_date"], red_row["rt"])
            notes = red_row["notes"] if "notes" in red_row.keys() else None

            close_balance_loss = _parse_close_balance_loss(notes)
            if payout == 0 and close_balance_loss is not None:
                cost_basis = close_balance_loss
                net_pl = -close_balance_loss
                realized_to_write.append(
                    (
                        red_row["redemption_date"],
                        site_id,
                        user_id,
                        redemption_id,
                        str(cost_basis),
                        str(payout),
                        str(net_pl),
                    )
                )
                continue

            cost_basis = Decimal("0.00")
            if not is_free_sc and payout > 0:
                # Check if this is a Full redemption (more_remaining=False/0)
                more_remaining = bool(int(red_row["more_remaining"] if "more_remaining" in red_row.keys() else 1))
                
                if not more_remaining:
                    # Full redemption: consume ALL remaining basis up to this timestamp
                    remaining_to_allocate = sum(
                        avail for pid, pdt, _pamt in purchases 
                        if pdt <= red_dt and (avail := remaining.get(pid, Decimal("0.00"))) > 0
                    )
                else:
                    # Partial redemption: just allocate the payout amount
                    remaining_to_allocate = payout
                
                for purchase_id, purchase_dt, _purchase_amt in purchases:
                    if remaining_to_allocate <= 0:
                        break
                    if purchase_dt > red_dt:
                        break

                    avail = remaining.get(purchase_id, Decimal("0.00"))
                    if avail <= 0:
                        continue

                    alloc = min(avail, remaining_to_allocate)
                    if alloc <= 0:
                        continue

                    remaining[purchase_id] = avail - alloc
                    remaining_to_allocate -= alloc
                    cost_basis += alloc
                    allocations_to_write.append((redemption_id, purchase_id, str(alloc)))

            net_pl = payout - cost_basis
            realized_to_write.append(
                (
                    red_row["redemption_date"],
                    site_id,
                    user_id,
                    redemption_id,
                    str(cost_basis),
                    str(payout),
                    str(net_pl),
                )
            )

        purchases_updated = 0
        for purchase_id, _dt, _amt in purchases:
            cursor.execute(
                "UPDATE purchases SET remaining_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(remaining[purchase_id]), purchase_id),
            )
            purchases_updated += 1

        if allocations_to_write:
            cursor.executemany(
                """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
                """,
                allocations_to_write,
            )

        if realized_to_write:
            cursor.executemany(
                """
                INSERT INTO realized_transactions
                    (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                realized_to_write,
            )

        conn.commit()

        return RebuildResult(
            pairs_processed=1,
            redemptions_processed=len(redemption_rows),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
        )

    def rebuild_fifo_all(self) -> RebuildResult:
        pairs = self.iter_pairs()
        redemptions_processed = 0
        allocations_written = 0
        purchases_updated = 0

        for user_id, site_id in pairs:
            result = self.rebuild_fifo_for_pair(user_id, site_id)
            redemptions_processed += result.redemptions_processed
            allocations_written += result.allocations_written
            purchases_updated += result.purchases_updated

        return RebuildResult(
            pairs_processed=len(pairs),
            redemptions_processed=redemptions_processed,
            allocations_written=allocations_written,
            purchases_updated=purchases_updated,
        )
