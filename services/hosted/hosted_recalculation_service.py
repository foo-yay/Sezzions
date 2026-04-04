"""Hosted recalculation service — bulk FIFO + realized-transaction rebuilds.

Ported from the desktop ``RecalculationService``.  Key differences:
- SQLAlchemy ORM instead of raw SQL / DatabaseManager
- String UUIDs instead of integer IDs
- Monetary values stored/compared as strings (Decimal in Python)
- No timezone conversion (hosted stores dates as-is)
- Adjustment support is optional (injected)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import asc, func, or_, and_
from sqlalchemy.orm import Session

from services.hosted.persistence import (
    HostedAccountAdjustmentRecord,
    HostedGameSessionRecord,
    HostedPurchaseRecord,
    HostedRedemptionAllocationRecord,
    HostedRedemptionRecord,
    HostedRealizedTransactionRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    m = _CLOSE_BALANCE_RE.search(notes)
    if not m:
        return None
    try:
        return Decimal(m.group(1).replace(",", ""))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HostedRebuildResult:
    pairs_processed: int
    redemptions_processed: int
    allocations_written: int
    purchases_updated: int
    game_sessions_processed: int = 0
    errors: List[str] = field(default_factory=list)
    operation: Optional[str] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HostedRecalculationService:
    """Bulk FIFO + realized-transaction rebuild for a hosted workspace."""

    def iter_pairs(
        self,
        session: Session,
        workspace_id: str,
    ) -> List[Tuple[str, str]]:
        """Return distinct (user_id, site_id) pairs with any activity."""
        from sqlalchemy import union_all, select, literal_column

        purchases_q = (
            select(
                HostedPurchaseRecord.user_id,
                HostedPurchaseRecord.site_id,
            )
            .where(
                HostedPurchaseRecord.workspace_id == workspace_id,
                HostedPurchaseRecord.deleted_at.is_(None),
            )
            .distinct()
        )
        redemptions_q = (
            select(
                HostedRedemptionRecord.user_id,
                HostedRedemptionRecord.site_id,
            )
            .where(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.deleted_at.is_(None),
            )
            .distinct()
        )
        sessions_q = (
            select(
                HostedGameSessionRecord.user_id,
                HostedGameSessionRecord.site_id,
            )
            .where(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
            .distinct()
        )
        adjustments_q = (
            select(
                HostedAccountAdjustmentRecord.user_id,
                HostedAccountAdjustmentRecord.site_id,
            )
            .where(
                HostedAccountAdjustmentRecord.workspace_id == workspace_id,
                HostedAccountAdjustmentRecord.deleted_at.is_(None),
            )
            .distinct()
        )

        combined = union_all(purchases_q, redemptions_q, sessions_q, adjustments_q).subquery()
        rows = session.execute(
            select(combined.c.user_id, combined.c.site_id).distinct()
        ).all()

        pairs = [
            (r.user_id, r.site_id)
            for r in rows
            if r.user_id is not None and r.site_id is not None
        ]
        pairs.sort()
        return pairs

    # ------------------------------------------------------------------
    # Full pair rebuild
    # ------------------------------------------------------------------

    def rebuild_fifo_for_pair(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
    ) -> HostedRebuildResult:
        """Full FIFO + realized-transaction rebuild for one (user, site) pair."""

        # --- Fetch purchases (chronological) ---
        purchase_rows = (
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

        # Build in-memory FIFO state: (id, datetime, original_amount)
        # remaining dict tracks current remaining for each lot
        purchases: List[Tuple[str, datetime, Decimal]] = []
        remaining: Dict[str, Decimal] = {}
        for p in purchase_rows:
            pid = p.id
            amt = Decimal(str(p.amount))
            dt = _to_dt(p.purchase_date, p.purchase_time)
            purchases.append((pid, dt, amt))
            remaining[pid] = amt

        # --- Merge basis adjustments as synthetic lots ---
        adj_rows = (
            session.query(HostedAccountAdjustmentRecord)
            .filter(
                HostedAccountAdjustmentRecord.workspace_id == workspace_id,
                HostedAccountAdjustmentRecord.user_id == user_id,
                HostedAccountAdjustmentRecord.site_id == site_id,
                HostedAccountAdjustmentRecord.deleted_at.is_(None),
                HostedAccountAdjustmentRecord.type == "BASIS_USD_CORRECTION",
            )
            .all()
        )
        for adj in adj_rows:
            synthetic_id = f"adj-{adj.id}"
            dt = _to_dt(adj.effective_date, adj.effective_time)
            delta = Decimal(str(adj.delta_basis_usd or "0.00"))
            purchases.append((synthetic_id, dt, delta))
            remaining[synthetic_id] = delta

        # Re-sort chronologically
        purchases.sort(key=lambda x: (x[1], x[0]))

        # --- Fetch redemptions (chronological, non-deleted, non-canceled) ---
        redemption_rows = (
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

        # --- Clear existing derived records for this pair ---
        self._clear_derived_for_pair(session, workspace_id, user_id, site_id)

        # --- Allocate ---
        allocations_to_write: List[Tuple[str, str, Decimal]] = []  # (redemption_id, purchase_id, amount)
        realized_to_write: List[dict] = []

        for red in redemption_rows:
            payout = Decimal(str(red.amount))
            is_free_sc = bool(red.is_free_sc)
            red_dt = _to_dt(red.redemption_date, red.redemption_time)

            # --- Close-balance (Net Loss) special case ---
            close_loss = _parse_close_balance_loss(red.notes)
            if payout == 0 and close_loss is not None:
                cost_basis = self._allocate_fifo(
                    purchases, remaining, red_dt, close_loss,
                    allocations_to_write, red.id,
                )
                net_pl = payout - cost_basis
                realized_to_write.append(self._realized_dict(
                    workspace_id, red.redemption_date, user_id, site_id,
                    red.id, cost_basis, payout, net_pl,
                ))
                continue

            cost_basis = Decimal("0.00")
            if not is_free_sc and payout > 0:
                more_remaining = bool(red.more_remaining)
                if not more_remaining:
                    # Full redemption: consume ALL basis up to timestamp
                    total_avail = sum(
                        avail
                        for pid, pdt, _ in purchases
                        if pdt <= red_dt and (avail := remaining.get(pid, Decimal("0.00"))) > 0
                    )
                    amount_to_consume = total_avail
                else:
                    amount_to_consume = payout

                cost_basis = self._allocate_fifo(
                    purchases, remaining, red_dt, amount_to_consume,
                    allocations_to_write, red.id,
                )

            net_pl = payout - cost_basis
            realized_to_write.append(self._realized_dict(
                workspace_id, red.redemption_date, user_id, site_id,
                red.id, cost_basis, payout, net_pl,
            ))

        # --- Write updated remaining_amount for real purchases ---
        purchases_updated = 0
        for p in purchase_rows:
            new_remaining = str(remaining[p.id])
            if p.remaining_amount != new_remaining:
                p.remaining_amount = new_remaining
            purchases_updated += 1

        # --- Write allocations ---
        for red_id, purch_id, alloc_amt in allocations_to_write:
            session.add(HostedRedemptionAllocationRecord(
                id=str(uuid4()),
                workspace_id=workspace_id,
                redemption_id=red_id,
                purchase_id=purch_id,
                allocated_amount=str(alloc_amt),
            ))

        # --- Write realized transactions ---
        for rt in realized_to_write:
            session.add(HostedRealizedTransactionRecord(
                id=str(uuid4()),
                **rt,
            ))

        session.flush()

        return HostedRebuildResult(
            pairs_processed=1,
            redemptions_processed=len(redemption_rows),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
        )

    # ------------------------------------------------------------------
    # Scoped rebuild (from a boundary timestamp)
    # ------------------------------------------------------------------

    def rebuild_fifo_for_pair_from(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        from_date: str,
        from_time: Optional[str] = None,
    ) -> HostedRebuildResult:
        """Scoped FIFO rebuild starting at a boundary timestamp."""
        from_time = _normalize_time(from_time)

        # --- Fetch ALL purchases for pair ---
        purchase_rows = (
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

        purchases: List[Tuple[str, datetime, Decimal]] = []
        remaining: Dict[str, Decimal] = {}
        for p in purchase_rows:
            amt = Decimal(str(p.amount))
            dt = _to_dt(p.purchase_date, p.purchase_time)
            purchases.append((p.id, dt, amt))
            remaining[p.id] = amt

        # Merge adjustments
        adj_rows = (
            session.query(HostedAccountAdjustmentRecord)
            .filter(
                HostedAccountAdjustmentRecord.workspace_id == workspace_id,
                HostedAccountAdjustmentRecord.user_id == user_id,
                HostedAccountAdjustmentRecord.site_id == site_id,
                HostedAccountAdjustmentRecord.deleted_at.is_(None),
                HostedAccountAdjustmentRecord.type == "BASIS_USD_CORRECTION",
            )
            .all()
        )
        for adj in adj_rows:
            synthetic_id = f"adj-{adj.id}"
            dt = _to_dt(adj.effective_date, adj.effective_time)
            delta = Decimal(str(adj.delta_basis_usd or "0.00"))
            purchases.append((synthetic_id, dt, delta))
            remaining[synthetic_id] = delta

        purchases.sort(key=lambda x: (x[1], x[0]))

        # --- Prime remaining from prior allocations (before boundary) ---
        prior_allocs = (
            session.query(
                HostedRedemptionAllocationRecord.purchase_id,
                HostedRedemptionAllocationRecord.allocated_amount,
            )
            .join(
                HostedRedemptionRecord,
                HostedRedemptionAllocationRecord.redemption_id == HostedRedemptionRecord.id,
            )
            .filter(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.user_id == user_id,
                HostedRedemptionRecord.site_id == site_id,
                HostedRedemptionRecord.deleted_at.is_(None),
                HostedRedemptionRecord.status.notin_(["CANCELED", "PENDING_CANCEL"]),
                or_(
                    HostedRedemptionRecord.redemption_date < from_date,
                    and_(
                        HostedRedemptionRecord.redemption_date == from_date,
                        func.coalesce(HostedRedemptionRecord.redemption_time, "00:00:00") < from_time,
                    ),
                ),
            )
            .all()
        )
        for purchase_id, allocated_str in prior_allocs:
            allocated = Decimal(str(allocated_str))
            if purchase_id in remaining:
                remaining[purchase_id] = max(Decimal("0.00"), remaining[purchase_id] - allocated)

        # --- Fetch suffix redemptions ---
        suffix_redemptions = (
            session.query(HostedRedemptionRecord)
            .filter(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.user_id == user_id,
                HostedRedemptionRecord.site_id == site_id,
                HostedRedemptionRecord.deleted_at.is_(None),
                HostedRedemptionRecord.status.notin_(["CANCELED", "PENDING_CANCEL"]),
                or_(
                    HostedRedemptionRecord.redemption_date > from_date,
                    and_(
                        HostedRedemptionRecord.redemption_date == from_date,
                        func.coalesce(HostedRedemptionRecord.redemption_time, "00:00:00") >= from_time,
                    ),
                ),
            )
            .order_by(
                asc(HostedRedemptionRecord.redemption_date),
                asc(func.coalesce(HostedRedemptionRecord.redemption_time, "00:00:00")),
                asc(HostedRedemptionRecord.id),
            )
            .all()
        )

        suffix_ids = [r.id for r in suffix_redemptions]

        # --- Delete existing allocations/realized for suffix ---
        if suffix_ids:
            session.query(HostedRedemptionAllocationRecord).filter(
                HostedRedemptionAllocationRecord.redemption_id.in_(suffix_ids),
            ).delete(synchronize_session="fetch")

            session.query(HostedRealizedTransactionRecord).filter(
                HostedRealizedTransactionRecord.redemption_id.in_(suffix_ids),
            ).delete(synchronize_session="fetch")

        # --- Allocate suffix ---
        allocations_to_write: List[Tuple[str, str, Decimal]] = []
        realized_to_write: List[dict] = []

        for red in suffix_redemptions:
            payout = Decimal(str(red.amount))
            is_free_sc = bool(red.is_free_sc)
            red_dt = _to_dt(red.redemption_date, red.redemption_time)

            close_loss = _parse_close_balance_loss(red.notes)
            if payout == 0 and close_loss is not None:
                cost_basis = self._allocate_fifo(
                    purchases, remaining, red_dt, close_loss,
                    allocations_to_write, red.id,
                )
                net_pl = payout - cost_basis
                realized_to_write.append(self._realized_dict(
                    workspace_id, red.redemption_date, user_id, site_id,
                    red.id, cost_basis, payout, net_pl,
                ))
                continue

            cost_basis = Decimal("0.00")
            if not is_free_sc and payout > 0:
                more_remaining = bool(red.more_remaining)
                if not more_remaining:
                    total_avail = sum(
                        avail
                        for pid, pdt, _ in purchases
                        if pdt <= red_dt and (avail := remaining.get(pid, Decimal("0.00"))) > 0
                    )
                    amount_to_consume = total_avail
                else:
                    amount_to_consume = payout

                cost_basis = self._allocate_fifo(
                    purchases, remaining, red_dt, amount_to_consume,
                    allocations_to_write, red.id,
                )

            net_pl = payout - cost_basis
            realized_to_write.append(self._realized_dict(
                workspace_id, red.redemption_date, user_id, site_id,
                red.id, cost_basis, payout, net_pl,
            ))

        # --- Update purchase remaining amounts ---
        purchases_updated = 0
        for p in purchase_rows:
            new_remaining = str(remaining[p.id])
            if p.remaining_amount != new_remaining:
                p.remaining_amount = new_remaining
            purchases_updated += 1

        # --- Write allocations ---
        for red_id, purch_id, alloc_amt in allocations_to_write:
            session.add(HostedRedemptionAllocationRecord(
                id=str(uuid4()),
                workspace_id=workspace_id,
                redemption_id=red_id,
                purchase_id=purch_id,
                allocated_amount=str(alloc_amt),
            ))

        # --- Write realized transactions ---
        for rt in realized_to_write:
            session.add(HostedRealizedTransactionRecord(
                id=str(uuid4()),
                **rt,
            ))

        session.flush()

        return HostedRebuildResult(
            pairs_processed=1,
            redemptions_processed=len(suffix_redemptions),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
        )

    # ------------------------------------------------------------------
    # Full workspace rebuild
    # ------------------------------------------------------------------

    def rebuild_all(
        self,
        session: Session,
        *,
        workspace_id: str,
    ) -> HostedRebuildResult:
        """Rebuild FIFO + realized transactions for all pairs in a workspace."""
        pairs = self.iter_pairs(session, workspace_id)

        totals = {
            "redemptions_processed": 0,
            "allocations_written": 0,
            "purchases_updated": 0,
        }

        for user_id, site_id in pairs:
            result = self.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace_id,
                user_id=user_id,
                site_id=site_id,
            )
            totals["redemptions_processed"] += result.redemptions_processed
            totals["allocations_written"] += result.allocations_written
            totals["purchases_updated"] += result.purchases_updated

        return HostedRebuildResult(
            pairs_processed=len(pairs),
            operation="all",
            **totals,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clear_derived_for_pair(
        self,
        session: Session,
        workspace_id: str,
        user_id: str,
        site_id: str,
    ) -> None:
        """Delete all allocations + realized transactions for a (user, site) pair."""
        # Get redemption IDs for this pair
        red_ids = [
            r.id
            for r in session.query(HostedRedemptionRecord.id)
            .filter(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.user_id == user_id,
                HostedRedemptionRecord.site_id == site_id,
            )
            .all()
        ]
        if red_ids:
            session.query(HostedRedemptionAllocationRecord).filter(
                HostedRedemptionAllocationRecord.redemption_id.in_(red_ids),
            ).delete(synchronize_session="fetch")

        session.query(HostedRealizedTransactionRecord).filter(
            HostedRealizedTransactionRecord.workspace_id == workspace_id,
            HostedRealizedTransactionRecord.user_id == user_id,
            HostedRealizedTransactionRecord.site_id == site_id,
        ).delete(synchronize_session="fetch")

    @staticmethod
    def _allocate_fifo(
        purchases: List[Tuple[str, datetime, Decimal]],
        remaining: Dict[str, Decimal],
        red_dt: datetime,
        amount_to_consume: Decimal,
        allocations_out: List[Tuple[str, str, Decimal]],
        redemption_id: str,
    ) -> Decimal:
        """Walk purchases in FIFO order and allocate up to *amount_to_consume*.

        Writes to *allocations_out* (only for real purchase IDs, not synthetic).
        Returns total cost basis consumed.
        """
        cost_basis = Decimal("0.00")
        left = amount_to_consume

        for purchase_id, purchase_dt, _ in purchases:
            if left <= 0:
                break
            if purchase_dt > red_dt:
                break

            avail = remaining.get(purchase_id, Decimal("0.00"))
            if avail <= 0:
                continue

            alloc = min(avail, left)
            remaining[purchase_id] = avail - alloc
            left -= alloc
            cost_basis += alloc

            # Synthetic adjustment IDs start with "adj-"; skip writing to allocations table
            if not purchase_id.startswith("adj-"):
                allocations_out.append((redemption_id, purchase_id, alloc))

        return cost_basis

    @staticmethod
    def _realized_dict(
        workspace_id: str,
        redemption_date: str,
        user_id: str,
        site_id: str,
        redemption_id: str,
        cost_basis: Decimal,
        payout: Decimal,
        net_pl: Decimal,
    ) -> dict:
        return {
            "workspace_id": workspace_id,
            "redemption_date": redemption_date,
            "user_id": user_id,
            "site_id": site_id,
            "redemption_id": redemption_id,
            "cost_basis": str(cost_basis),
            "payout": str(payout),
            "net_pl": str(net_pl),
        }
