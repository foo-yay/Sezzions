"""Persistence helpers for hosted workspace-owned redemptions."""

from __future__ import annotations

from sqlalchemy import delete, func, select, update as sa_update
from sqlalchemy.orm import aliased

from services.hosted.models import HostedRedemption
from services.hosted.persistence import (
    HostedRealizedTransactionRecord,
    HostedRedemptionMethodRecord,
    HostedRedemptionRecord,
    HostedSiteRecord,
    HostedUserRecord,
)


class HostedRedemptionRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedRedemption]:
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        method_alias = aliased(HostedRedemptionMethodRecord)
        rt_alias = aliased(HostedRealizedTransactionRecord)
        query = (
            select(
                HostedRedemptionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                method_alias.name.label("method_name"),
                rt_alias.cost_basis.label("cost_basis"),
                rt_alias.net_pl.label("net_pl"),
            )
            .join(user_alias, HostedRedemptionRecord.user_id == user_alias.id)
            .join(site_alias, HostedRedemptionRecord.site_id == site_alias.id)
            .outerjoin(method_alias, HostedRedemptionRecord.redemption_method_id == method_alias.id)
            .outerjoin(
                rt_alias,
                (HostedRedemptionRecord.id == rt_alias.redemption_id)
                & (HostedRedemptionRecord.workspace_id == rt_alias.workspace_id),
            )
            .where(HostedRedemptionRecord.workspace_id == workspace_id)
            .order_by(
                HostedRedemptionRecord.redemption_date.desc(),
                HostedRedemptionRecord.redemption_time.desc(),
                HostedRedemptionRecord.id.desc(),
            )
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def list_by_workspace_user_and_site(
        self,
        session,
        workspace_id: str,
        user_id: str,
        site_id: str,
    ) -> list[HostedRedemption]:
        """Return redemptions for a user+site pair ordered chronologically (ASC)."""
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        method_alias = aliased(HostedRedemptionMethodRecord)
        rt_alias = aliased(HostedRealizedTransactionRecord)
        query = (
            select(
                HostedRedemptionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                method_alias.name.label("method_name"),
                rt_alias.cost_basis.label("cost_basis"),
                rt_alias.net_pl.label("net_pl"),
            )
            .join(user_alias, HostedRedemptionRecord.user_id == user_alias.id)
            .join(site_alias, HostedRedemptionRecord.site_id == site_alias.id)
            .outerjoin(method_alias, HostedRedemptionRecord.redemption_method_id == method_alias.id)
            .outerjoin(
                rt_alias,
                (HostedRedemptionRecord.id == rt_alias.redemption_id)
                & (HostedRedemptionRecord.workspace_id == rt_alias.workspace_id),
            )
            .where(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.user_id == user_id,
                HostedRedemptionRecord.site_id == site_id,
            )
            .order_by(
                HostedRedemptionRecord.redemption_date.asc(),
                HostedRedemptionRecord.redemption_time.asc(),
                HostedRedemptionRecord.id.asc(),
            )
        )
        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedRedemptionRecord)
            .where(HostedRedemptionRecord.workspace_id == workspace_id)
        ) or 0

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        redemption_id: str,
        workspace_id: str,
    ) -> HostedRedemption | None:
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        method_alias = aliased(HostedRedemptionMethodRecord)
        rt_alias = aliased(HostedRealizedTransactionRecord)
        row = session.execute(
            select(
                HostedRedemptionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                method_alias.name.label("method_name"),
                rt_alias.cost_basis.label("cost_basis"),
                rt_alias.net_pl.label("net_pl"),
            )
            .join(user_alias, HostedRedemptionRecord.user_id == user_alias.id)
            .join(site_alias, HostedRedemptionRecord.site_id == site_alias.id)
            .outerjoin(method_alias, HostedRedemptionRecord.redemption_method_id == method_alias.id)
            .outerjoin(
                rt_alias,
                (HostedRedemptionRecord.id == rt_alias.redemption_id)
                & (HostedRedemptionRecord.workspace_id == rt_alias.workspace_id),
            )
            .where(
                HostedRedemptionRecord.id == redemption_id,
                HostedRedemptionRecord.workspace_id == workspace_id,
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
        redemption_date: str,
        redemption_time: str = "00:00:00",
        redemption_entry_time_zone: str | None = None,
        redemption_method_id: str | None = None,
        fees: str = "0.00",
        is_free_sc: bool = False,
        receipt_date: str | None = None,
        processed: bool = False,
        more_remaining: bool = False,
        notes: str | None = None,
        status: str = "PENDING",
    ) -> HostedRedemption:
        record = HostedRedemptionRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            redemption_date=redemption_date,
            redemption_time=redemption_time,
            redemption_entry_time_zone=redemption_entry_time_zone,
            redemption_method_id=redemption_method_id,
            fees=fees,
            is_free_sc=is_free_sc,
            receipt_date=receipt_date,
            processed=processed,
            more_remaining=more_remaining,
            notes=notes,
            status=status,
        )
        session.add(record)
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, redemption_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        redemption_id: str,
        workspace_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        redemption_date: str,
        redemption_time: str = "00:00:00",
        redemption_entry_time_zone: str | None = None,
        redemption_method_id: str | None = None,
        fees: str = "0.00",
        is_free_sc: bool = False,
        receipt_date: str | None = None,
        processed: bool = False,
        more_remaining: bool = False,
        notes: str | None = None,
        status: str = "PENDING",
        canceled_at: str | None = None,
        cancel_reason: str | None = None,
    ) -> HostedRedemption | None:
        record = session.scalar(
            select(HostedRedemptionRecord).where(
                HostedRedemptionRecord.id == redemption_id,
                HostedRedemptionRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.user_id = user_id
        record.site_id = site_id
        record.amount = amount
        record.redemption_date = redemption_date
        record.redemption_time = redemption_time
        record.redemption_entry_time_zone = redemption_entry_time_zone
        record.redemption_method_id = redemption_method_id
        record.fees = fees
        record.is_free_sc = is_free_sc
        record.receipt_date = receipt_date
        record.processed = processed
        record.more_remaining = more_remaining
        record.notes = notes
        record.status = status
        record.canceled_at = canceled_at
        record.cancel_reason = cancel_reason
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, redemption_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, redemption_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedRedemptionRecord).where(
                HostedRedemptionRecord.id == redemption_id,
                HostedRedemptionRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, redemption_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(redemption_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedRedemptionRecord).where(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    def bulk_set_receipt_date(
        self, session, *, redemption_ids: list[str], workspace_id: str, receipt_date: str | None
    ) -> int:
        if not redemption_ids:
            return 0
        result = session.execute(
            sa_update(HostedRedemptionRecord)
            .where(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.id.in_(redemption_ids),
                HostedRedemptionRecord.status == "PENDING",
            )
            .values(receipt_date=receipt_date)
        )
        session.flush()
        return int(result.rowcount or 0)

    def bulk_set_processed(
        self, session, *, redemption_ids: list[str], workspace_id: str, processed: bool = True
    ) -> int:
        if not redemption_ids:
            return 0
        result = session.execute(
            sa_update(HostedRedemptionRecord)
            .where(
                HostedRedemptionRecord.workspace_id == workspace_id,
                HostedRedemptionRecord.id.in_(redemption_ids),
            )
            .values(processed=processed)
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _row_to_model(row) -> HostedRedemption:
        record = row[0] if hasattr(row, "__getitem__") else row
        user_name = row.user_name if hasattr(row, "user_name") else None
        site_name = row.site_name if hasattr(row, "site_name") else None
        method_name = row.method_name if hasattr(row, "method_name") else None
        cost_basis = row.cost_basis if hasattr(row, "cost_basis") else None
        net_pl = row.net_pl if hasattr(row, "net_pl") else None
        return HostedRedemption(
            id=record.id,
            workspace_id=record.workspace_id,
            user_id=record.user_id,
            site_id=record.site_id,
            amount=record.amount,
            fees=record.fees,
            redemption_date=record.redemption_date,
            redemption_time=record.redemption_time,
            redemption_entry_time_zone=record.redemption_entry_time_zone,
            redemption_method_id=record.redemption_method_id,
            is_free_sc=record.is_free_sc,
            receipt_date=record.receipt_date,
            processed=record.processed,
            more_remaining=record.more_remaining,
            notes=record.notes,
            status=record.status,
            canceled_at=record.canceled_at,
            cancel_reason=record.cancel_reason,
            user_name=user_name,
            site_name=site_name,
            method_name=method_name,
            cost_basis=cost_basis,
            net_pl=net_pl,
        )
