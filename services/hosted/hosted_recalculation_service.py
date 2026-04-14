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
    HostedGameSessionEventLinkRecord,
    HostedGameSessionRecord,
    HostedPurchaseRecord,
    HostedRedemptionAllocationRecord,
    HostedRedemptionRecord,
    HostedRealizedTransactionRecord,
    HostedSiteRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TWO_PLACES = Decimal("0.01")


def _fmt(val: Decimal) -> str:
    """Format a Decimal to 2 decimal places."""
    return str(val.quantize(_TWO_PLACES))


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

        # --- Session P/L recalc ---
        gs_count = self.rebuild_sessions_for_pair(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            site_id=site_id,
        )

        return HostedRebuildResult(
            pairs_processed=1,
            redemptions_processed=len(redemption_rows),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
            game_sessions_processed=gs_count,
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

        # --- Session P/L recalc ---
        gs_count = self.rebuild_sessions_for_pair(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            site_id=site_id,
        )

        return HostedRebuildResult(
            pairs_processed=1,
            redemptions_processed=len(suffix_redemptions),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
            game_sessions_processed=gs_count,
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
    # Session P/L recalculation
    # ------------------------------------------------------------------

    def rebuild_sessions_for_pair(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
    ) -> int:
        """Recalculate P/L fields for all closed sessions of a (user, site) pair.

        Walks sessions in chronological order, computing expected start
        balances, discoverable SC, basis consumed, and net taxable P/L
        for each closed session.  Active sessions are skipped.

        Returns the number of sessions processed.
        """
        # --- sc_rate ---
        site = session.query(HostedSiteRecord).filter(
            HostedSiteRecord.id == site_id,
            HostedSiteRecord.workspace_id == workspace_id,
        ).first()
        sc_rate = Decimal(str(site.sc_rate)) if site else Decimal("1.00")

        # --- Load all sessions (chronological) ---
        all_sessions = (
            session.query(HostedGameSessionRecord)
            .filter(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.user_id == user_id,
                HostedGameSessionRecord.site_id == site_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
            .order_by(
                asc(HostedGameSessionRecord.session_date),
                asc(func.coalesce(HostedGameSessionRecord.session_time, "00:00:00")),
                asc(HostedGameSessionRecord.id),
            )
            .all()
        )

        # --- Load all purchases for the pair ---
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
            )
            .all()
        )
        # (datetime, cash_amount, sc_amount)
        purchases = [
            (_to_dt(p.purchase_date, p.purchase_time), Decimal(str(p.amount)), Decimal(str(p.sc_received)))
            for p in purchase_rows
        ]

        # --- Load non-canceled redemptions ---
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
            )
            .all()
        )
        # Convert redemption dollar amounts to SC: amount_sc = dollars / sc_rate
        redemptions = [
            (_to_dt(r.redemption_date, r.redemption_time), Decimal(str(r.amount)) / sc_rate)
            for r in redemption_rows
        ]

        # --- Walk sessions ---
        last_end_total = Decimal("0.00")
        last_end_redeem = Decimal("0.00")
        checkpoint_end_dt = None
        pending_basis_pool = Decimal("0.00")
        count = 0

        def _in_window(dt, start_exclusive, end_exclusive):
            if dt is None:
                return False
            if start_exclusive is not None and dt <= start_exclusive:
                return False
            if end_exclusive is not None and dt >= end_exclusive:
                return False
            return True

        for sess in all_sessions:
            if sess.status != "Closed":
                continue

            start_dt = _to_dt(sess.session_date, sess.session_time)
            end_dt = _to_dt(
                sess.end_date or sess.session_date,
                sess.end_time or sess.session_time,
            )
            if end_dt is None:
                end_dt = start_dt

            # Events between checkpoint and this session's start / end
            red_between = sum(
                (amt for dt, amt in redemptions if _in_window(dt, checkpoint_end_dt, start_dt)),
                Decimal("0.00"),
            )
            pur_sc_to_start = sum(
                (sc for dt, cash, sc in purchases if _in_window(dt, checkpoint_end_dt, start_dt)),
                Decimal("0.00"),
            )
            pur_cash_to_end = sum(
                (cash for dt, cash, sc in purchases if _in_window(dt, checkpoint_end_dt, end_dt)),
                Decimal("0.00"),
            )

            expected_start_total = max(Decimal("0.00"), (last_end_total - red_between) + pur_sc_to_start)
            expected_start_redeem = max(Decimal("0.00"), last_end_redeem - red_between)

            start_total = Decimal(str(sess.starting_balance))
            end_total = Decimal(str(sess.ending_balance))
            start_red = Decimal(str(sess.starting_redeemable))
            end_red = Decimal(str(sess.ending_redeemable))

            delta_total = end_total - start_total
            delta_redeem = end_red - start_red

            # session_basis = all purchases (cash) from checkpoint to session end
            session_basis = pur_cash_to_end
            pending_basis_pool += session_basis
            if pending_basis_pool < 0:
                pending_basis_pool = Decimal("0.00")

            discoverable_sc = max(Decimal("0.00"), start_red - expected_start_redeem)
            locked_start = max(Decimal("0.00"), start_total - start_red)
            locked_end = max(Decimal("0.00"), end_total - end_red)

            # DURING-linked purchases (SC) and redemptions (dollars)
            purchases_during_sc = self._sum_linked_purchases_during_sc(session, sess.id)
            redemptions_during_total = self._sum_linked_redemptions_during_total(session, sess.id)

            locked_processed_sc = max(Decimal("0.00"), locked_start + purchases_during_sc - locked_end)
            locked_processed_value = locked_processed_sc * sc_rate
            basis_consumed = min(pending_basis_pool, locked_processed_value)
            pending_basis_pool = max(Decimal("0.00"), pending_basis_pool - basis_consumed)

            net_taxable_pl = ((discoverable_sc + delta_redeem) * sc_rate) - basis_consumed

            # Write all P/L fields
            sess.expected_start_total = _fmt(expected_start_total)
            sess.expected_start_redeemable = _fmt(expected_start_redeem)
            sess.discoverable_sc = _fmt(discoverable_sc)
            sess.delta_total = _fmt(delta_total)
            sess.delta_redeem = _fmt(delta_redeem)
            sess.session_basis = _fmt(session_basis)
            sess.basis_consumed = _fmt(basis_consumed)
            sess.net_taxable_pl = _fmt(net_taxable_pl)
            sess.purchases_during = _fmt(purchases_during_sc)
            sess.redemptions_during = _fmt(redemptions_during_total)

            last_end_total = end_total
            last_end_redeem = end_red
            checkpoint_end_dt = end_dt
            count += 1

        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sum_linked_purchases_during_sc(
        self,
        session: Session,
        game_session_id: str,
    ) -> Decimal:
        """Sum sc_received from purchases linked as DURING to this session."""
        row = (
            session.query(func.coalesce(func.sum(HostedPurchaseRecord.sc_received), "0"))
            .join(
                HostedGameSessionEventLinkRecord,
                HostedPurchaseRecord.id == HostedGameSessionEventLinkRecord.event_id,
            )
            .filter(
                HostedGameSessionEventLinkRecord.game_session_id == game_session_id,
                HostedGameSessionEventLinkRecord.event_type == "purchase",
                HostedGameSessionEventLinkRecord.relation == "DURING",
                HostedPurchaseRecord.deleted_at.is_(None),
            )
            .scalar()
        )
        return Decimal(str(row)) if row else Decimal("0.00")

    def _sum_linked_redemptions_during_total(
        self,
        session: Session,
        game_session_id: str,
    ) -> Decimal:
        """Sum amounts from redemptions linked as DURING to this session."""
        row = (
            session.query(func.coalesce(func.sum(HostedRedemptionRecord.amount), "0"))
            .join(
                HostedGameSessionEventLinkRecord,
                HostedRedemptionRecord.id == HostedGameSessionEventLinkRecord.event_id,
            )
            .filter(
                HostedGameSessionEventLinkRecord.game_session_id == game_session_id,
                HostedGameSessionEventLinkRecord.event_type == "redemption",
                HostedGameSessionEventLinkRecord.relation == "DURING",
                HostedRedemptionRecord.deleted_at.is_(None),
                HostedRedemptionRecord.status.notin_(["CANCELED", "PENDING_CANCEL"]),
            )
            .scalar()
        )
        return Decimal(str(row)) if row else Decimal("0.00")

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
