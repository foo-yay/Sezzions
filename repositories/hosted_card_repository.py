"""Persistence helpers for hosted workspace-owned business cards."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from services.hosted.models import HostedCard
from services.hosted.persistence import HostedCardRecord, HostedUserRecord


class HostedCardRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedCard]:
        user_alias = aliased(HostedUserRecord)
        query = (
            select(HostedCardRecord, user_alias.name.label("user_name"))
            .outerjoin(user_alias, HostedCardRecord.user_id == user_alias.id)
            .where(HostedCardRecord.workspace_id == workspace_id)
            .order_by(HostedCardRecord.name.asc(), HostedCardRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedCardRecord)
            .where(HostedCardRecord.workspace_id == workspace_id)
        ) or 0

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        card_id: str,
        workspace_id: str,
    ) -> HostedCard | None:
        user_alias = aliased(HostedUserRecord)
        row = session.execute(
            select(HostedCardRecord, user_alias.name.label("user_name"))
            .outerjoin(user_alias, HostedCardRecord.user_id == user_alias.id)
            .where(
                HostedCardRecord.id == card_id,
                HostedCardRecord.workspace_id == workspace_id,
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
        name: str,
        last_four: str | None = None,
        cashback_rate: float = 0.0,
        is_active: bool = True,
        notes: str | None = None,
    ) -> HostedCard:
        record = HostedCardRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            last_four=last_four,
            cashback_rate=cashback_rate,
            is_active=is_active,
            notes=notes,
        )
        session.add(record)
        session.flush()
        # Re-query to get joined user_name
        return self.get_by_id_and_workspace_id(
            session, card_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        card_id: str,
        workspace_id: str,
        user_id: str,
        name: str,
        last_four: str | None,
        cashback_rate: float,
        is_active: bool,
        notes: str | None,
    ) -> HostedCard | None:
        record = session.scalar(
            select(HostedCardRecord).where(
                HostedCardRecord.id == card_id,
                HostedCardRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.user_id = user_id
        record.name = name
        record.last_four = last_four
        record.cashback_rate = cashback_rate
        record.is_active = is_active
        record.notes = notes
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, card_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, card_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedCardRecord).where(
                HostedCardRecord.id == card_id,
                HostedCardRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, card_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(card_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedCardRecord).where(
                HostedCardRecord.workspace_id == workspace_id,
                HostedCardRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _row_to_model(row) -> HostedCard:
        record = row[0] if hasattr(row, "__getitem__") else row
        user_name = row.user_name if hasattr(row, "user_name") else None
        return HostedCard(
            id=record.id,
            workspace_id=record.workspace_id,
            user_id=record.user_id,
            name=record.name,
            last_four=record.last_four,
            cashback_rate=record.cashback_rate,
            is_active=record.is_active,
            notes=record.notes,
            user_name=user_name,
        )
