"""Hosted FIFO service — cost basis calculation using First-In-First-Out.

Operates on hosted persistence records via SQLAlchemy sessions.
All monetary values use ``Decimal`` (stored as strings in the DB).
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from services.hosted.persistence import HostedPurchaseRecord


class HostedFIFOService:
    """FIFO cost-basis calculation for the hosted (web) layer."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_cost_basis(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        redemption_amount: Decimal,
        redemption_date: str,
        redemption_time: str = "23:59:59",
    ) -> Tuple[Decimal, Decimal, List[Tuple[str, Decimal]]]:
        """Calculate cost basis for a single redemption using FIFO.

        Returns
        -------
        (cost_basis, taxable_profit, allocations)
            allocations is a list of ``(purchase_id, allocated_amount)``
        """
        available = self._get_available_purchases(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            site_id=site_id,
            as_of_date=redemption_date,
            as_of_time=redemption_time,
        )

        remaining_to_allocate = redemption_amount
        cost_basis = Decimal("0.00")
        allocations: List[Tuple[str, Decimal]] = []

        for purchase in available:
            if remaining_to_allocate <= 0:
                break

            avail = Decimal(str(purchase.remaining_amount))
            if avail <= 0:
                continue

            alloc = min(remaining_to_allocate, avail)
            allocations.append((purchase.id, alloc))
            cost_basis += alloc
            remaining_to_allocate -= alloc

        taxable_profit = redemption_amount - cost_basis
        return cost_basis, taxable_profit, allocations

    def apply_allocation(
        self,
        session: Session,
        allocations: List[Tuple[str, Decimal]],
    ) -> None:
        """Reduce ``remaining_amount`` on each purchase by the allocated amount."""
        for purchase_id, amount_allocated in allocations:
            purchase = session.get(HostedPurchaseRecord, purchase_id)
            if purchase is None:
                raise ValueError(f"Purchase {purchase_id} not found")

            current = Decimal(str(purchase.remaining_amount))
            new_remaining = current - amount_allocated
            if new_remaining < 0:
                raise ValueError(
                    f"Cannot allocate ${amount_allocated} from purchase {purchase_id}. "
                    f"Only ${current} remaining."
                )
            purchase.remaining_amount = str(new_remaining)

    def reverse_allocation(
        self,
        session: Session,
        allocations: List[Tuple[str, Decimal]],
    ) -> None:
        """Restore ``remaining_amount`` on each purchase (undo)."""
        for purchase_id, amount_allocated in allocations:
            purchase = session.get(HostedPurchaseRecord, purchase_id)
            if purchase is None:
                raise ValueError(f"Purchase {purchase_id} not found")

            current = Decimal(str(purchase.remaining_amount))
            original = Decimal(str(purchase.amount))
            new_remaining = current + amount_allocated
            if new_remaining > original:
                raise ValueError(
                    f"Cannot restore ${amount_allocated} to purchase {purchase_id}. "
                    f"Would exceed original amount ${original}."
                )
            purchase.remaining_amount = str(new_remaining)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_available_purchases(
        self,
        session: Session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        as_of_date: str,
        as_of_time: str,
    ) -> List[HostedPurchaseRecord]:
        """Fetch purchases eligible for FIFO in chronological order.

        Only includes non-deleted purchases with remaining_amount > '0'
        whose timestamp is on or before the given date/time.
        Ordered: purchase_date ASC, purchase_time ASC, id ASC.
        """
        from sqlalchemy import or_, and_

        time_norm = as_of_time or "23:59:59"

        return (
            session.query(HostedPurchaseRecord)
            .filter(
                HostedPurchaseRecord.workspace_id == workspace_id,
                HostedPurchaseRecord.user_id == user_id,
                HostedPurchaseRecord.site_id == site_id,
                HostedPurchaseRecord.deleted_at.is_(None),
                HostedPurchaseRecord.remaining_amount > "0",
                # Strictly: remaining_amount is a string column, but Postgres
                # string comparison of well-formatted decimals works for > "0"
                # since "0.00" < "0.01" etc.  For robustness we also exclude "0.00".
                HostedPurchaseRecord.remaining_amount != "0.00",
                HostedPurchaseRecord.remaining_amount != "0",
                or_(
                    HostedPurchaseRecord.purchase_date < as_of_date,
                    and_(
                        HostedPurchaseRecord.purchase_date == as_of_date,
                        func.coalesce(HostedPurchaseRecord.purchase_time, "00:00:00")
                        <= time_norm,
                    ),
                ),
            )
            .order_by(
                asc(HostedPurchaseRecord.purchase_date),
                asc(func.coalesce(HostedPurchaseRecord.purchase_time, "00:00:00")),
                asc(HostedPurchaseRecord.id),
            )
            .all()
        )
