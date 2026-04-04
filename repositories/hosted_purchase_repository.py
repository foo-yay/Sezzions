"""Persistence helpers for hosted workspace-owned purchases."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from services.hosted.models import HostedPurchase
from services.hosted.persistence import (
    HostedCardRecord,
    HostedPurchaseRecord,
    HostedSiteRecord,
    HostedUserRecord,
)


class HostedPurchaseRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedPurchase]:
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        card_alias = aliased(HostedCardRecord)
        query = (
            select(
                HostedPurchaseRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                card_alias.name.label("card_name"),
            )
            .join(user_alias, HostedPurchaseRecord.user_id == user_alias.id)
            .join(site_alias, HostedPurchaseRecord.site_id == site_alias.id)
            .outerjoin(card_alias, HostedPurchaseRecord.card_id == card_alias.id)
            .where(HostedPurchaseRecord.workspace_id == workspace_id)
            .order_by(
                HostedPurchaseRecord.purchase_date.desc(),
                HostedPurchaseRecord.purchase_time.desc(),
                HostedPurchaseRecord.id.desc(),
            )
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedPurchaseRecord)
            .where(HostedPurchaseRecord.workspace_id == workspace_id)
        ) or 0

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        purchase_id: str,
        workspace_id: str,
    ) -> HostedPurchase | None:
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        card_alias = aliased(HostedCardRecord)
        row = session.execute(
            select(
                HostedPurchaseRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                card_alias.name.label("card_name"),
            )
            .join(user_alias, HostedPurchaseRecord.user_id == user_alias.id)
            .join(site_alias, HostedPurchaseRecord.site_id == site_alias.id)
            .outerjoin(card_alias, HostedPurchaseRecord.card_id == card_alias.id)
            .where(
                HostedPurchaseRecord.id == purchase_id,
                HostedPurchaseRecord.workspace_id == workspace_id,
            )
        ).first()
        if row is None:
            return None
        return self._row_to_model(row)

    def create(
        self,
        session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        purchase_date: str,
        purchase_time: str | None = None,
        sc_received: str = "0.00",
        starting_sc_balance: str = "0.00",
        starting_redeemable_balance: str = "0.00",
        cashback_earned: str = "0.00",
        cashback_is_manual: bool = False,
        card_id: str | None = None,
        remaining_amount: str | None = None,
        status: str = "active",
        notes: str | None = None,
    ) -> HostedPurchase:
        record = HostedPurchaseRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            purchase_date=purchase_date,
            purchase_time=purchase_time,
            sc_received=sc_received,
            starting_sc_balance=starting_sc_balance,
            starting_redeemable_balance=starting_redeemable_balance,
            cashback_earned=cashback_earned,
            cashback_is_manual=cashback_is_manual,
            card_id=card_id,
            remaining_amount=remaining_amount if remaining_amount is not None else amount,
            status=status,
            notes=notes,
        )
        session.add(record)
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, purchase_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        purchase_id: str,
        workspace_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        purchase_date: str,
        purchase_time: str | None = None,
        sc_received: str = "0.00",
        starting_sc_balance: str = "0.00",
        starting_redeemable_balance: str = "0.00",
        cashback_earned: str = "0.00",
        cashback_is_manual: bool = False,
        card_id: str | None = None,
        remaining_amount: str | None = None,
        status: str = "active",
        notes: str | None = None,
    ) -> HostedPurchase | None:
        record = session.scalar(
            select(HostedPurchaseRecord).where(
                HostedPurchaseRecord.id == purchase_id,
                HostedPurchaseRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.user_id = user_id
        record.site_id = site_id
        record.amount = amount
        record.purchase_date = purchase_date
        record.purchase_time = purchase_time
        record.sc_received = sc_received
        record.starting_sc_balance = starting_sc_balance
        record.starting_redeemable_balance = starting_redeemable_balance
        record.cashback_earned = cashback_earned
        record.cashback_is_manual = cashback_is_manual
        record.card_id = card_id
        record.remaining_amount = remaining_amount if remaining_amount is not None else amount
        record.status = status
        record.notes = notes
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, purchase_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, purchase_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedPurchaseRecord).where(
                HostedPurchaseRecord.id == purchase_id,
                HostedPurchaseRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, purchase_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(purchase_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedPurchaseRecord).where(
                HostedPurchaseRecord.workspace_id == workspace_id,
                HostedPurchaseRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _row_to_model(row) -> HostedPurchase:
        record = row[0] if hasattr(row, "__getitem__") else row
        user_name = row.user_name if hasattr(row, "user_name") else None
        site_name = row.site_name if hasattr(row, "site_name") else None
        card_name = row.card_name if hasattr(row, "card_name") else None
        return HostedPurchase(
            id=record.id,
            workspace_id=record.workspace_id,
            user_id=record.user_id,
            site_id=record.site_id,
            amount=record.amount,
            purchase_date=record.purchase_date,
            purchase_time=record.purchase_time,
            sc_received=record.sc_received,
            starting_sc_balance=record.starting_sc_balance,
            starting_redeemable_balance=record.starting_redeemable_balance,
            cashback_earned=record.cashback_earned,
            cashback_is_manual=record.cashback_is_manual,
            card_id=record.card_id,
            remaining_amount=record.remaining_amount,
            status=record.status,
            notes=record.notes,
            user_name=user_name,
            site_name=site_name,
            card_name=card_name,
        )
