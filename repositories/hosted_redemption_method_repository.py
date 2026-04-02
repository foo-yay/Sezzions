"""Persistence helpers for hosted workspace-owned redemption methods."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from services.hosted.models import HostedRedemptionMethod
from services.hosted.persistence import (
    HostedRedemptionMethodRecord,
    HostedRedemptionMethodTypeRecord,
    HostedUserRecord,
)


class HostedRedemptionMethodRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedRedemptionMethod]:
        user_alias = aliased(HostedUserRecord)
        type_alias = aliased(HostedRedemptionMethodTypeRecord)
        query = (
            select(
                HostedRedemptionMethodRecord,
                user_alias.name.label("user_name"),
                type_alias.name.label("method_type_name"),
            )
            .join(user_alias, HostedRedemptionMethodRecord.user_id == user_alias.id)
            .join(type_alias, HostedRedemptionMethodRecord.method_type_id == type_alias.id)
            .where(HostedRedemptionMethodRecord.workspace_id == workspace_id)
            .order_by(HostedRedemptionMethodRecord.name.asc(), HostedRedemptionMethodRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedRedemptionMethodRecord)
            .where(HostedRedemptionMethodRecord.workspace_id == workspace_id)
        ) or 0

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        method_id: str,
        workspace_id: str,
    ) -> HostedRedemptionMethod | None:
        user_alias = aliased(HostedUserRecord)
        type_alias = aliased(HostedRedemptionMethodTypeRecord)
        row = session.execute(
            select(
                HostedRedemptionMethodRecord,
                user_alias.name.label("user_name"),
                type_alias.name.label("method_type_name"),
            )
            .join(user_alias, HostedRedemptionMethodRecord.user_id == user_alias.id)
            .join(type_alias, HostedRedemptionMethodRecord.method_type_id == type_alias.id)
            .where(
                HostedRedemptionMethodRecord.id == method_id,
                HostedRedemptionMethodRecord.workspace_id == workspace_id,
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
        name: str,
        method_type_id: str,
        user_id: str,
        is_active: bool = True,
        notes: str | None = None,
    ) -> HostedRedemptionMethod:
        record = HostedRedemptionMethodRecord(
            workspace_id=workspace_id,
            name=name,
            method_type_id=method_type_id,
            user_id=user_id,
            is_active=is_active,
            notes=notes,
        )
        session.add(record)
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, method_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        method_id: str,
        workspace_id: str,
        name: str,
        method_type_id: str,
        user_id: str,
        is_active: bool,
        notes: str | None,
    ) -> HostedRedemptionMethod | None:
        record = session.scalar(
            select(HostedRedemptionMethodRecord).where(
                HostedRedemptionMethodRecord.id == method_id,
                HostedRedemptionMethodRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.name = name
        record.method_type_id = method_type_id
        record.user_id = user_id
        record.is_active = is_active
        record.notes = notes
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, method_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, method_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedRedemptionMethodRecord).where(
                HostedRedemptionMethodRecord.id == method_id,
                HostedRedemptionMethodRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, method_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(method_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedRedemptionMethodRecord).where(
                HostedRedemptionMethodRecord.workspace_id == workspace_id,
                HostedRedemptionMethodRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _row_to_model(row) -> HostedRedemptionMethod:
        record = row[0] if hasattr(row, "__getitem__") else row
        user_name = row.user_name if hasattr(row, "user_name") else None
        method_type_name = row.method_type_name if hasattr(row, "method_type_name") else None
        return HostedRedemptionMethod(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            method_type_id=record.method_type_id,
            user_id=record.user_id,
            is_active=record.is_active,
            notes=record.notes,
            user_name=user_name,
            method_type_name=method_type_name,
        )
