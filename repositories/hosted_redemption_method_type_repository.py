"""Persistence helpers for hosted workspace-owned redemption method types."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from services.hosted.models import HostedRedemptionMethodType
from services.hosted.persistence import HostedRedemptionMethodTypeRecord


class HostedRedemptionMethodTypeRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedRedemptionMethodType]:
        query = (
            select(HostedRedemptionMethodTypeRecord)
            .where(HostedRedemptionMethodTypeRecord.workspace_id == workspace_id)
            .order_by(HostedRedemptionMethodTypeRecord.name.asc(), HostedRedemptionMethodTypeRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        records = session.scalars(query).all()
        return [self._record_to_model(record) for record in records]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedRedemptionMethodTypeRecord)
            .where(HostedRedemptionMethodTypeRecord.workspace_id == workspace_id)
        ) or 0

    def create(
        self,
        session,
        *,
        workspace_id: str,
        name: str,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedRedemptionMethodType:
        record = HostedRedemptionMethodTypeRecord(
            workspace_id=workspace_id,
            name=name,
            notes=notes,
            is_active=is_active,
        )
        session.add(record)
        session.flush()
        return self._record_to_model(record)

    def update(
        self,
        session,
        *,
        method_type_id: str,
        workspace_id: str,
        name: str,
        notes: str | None,
        is_active: bool,
    ) -> HostedRedemptionMethodType | None:
        record = session.scalar(
            select(HostedRedemptionMethodTypeRecord).where(
                HostedRedemptionMethodTypeRecord.id == method_type_id,
                HostedRedemptionMethodTypeRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.name = name
        record.notes = notes
        record.is_active = is_active
        session.flush()
        return self._record_to_model(record)

    def delete(self, session, *, method_type_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedRedemptionMethodTypeRecord).where(
                HostedRedemptionMethodTypeRecord.id == method_type_id,
                HostedRedemptionMethodTypeRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, method_type_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(method_type_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedRedemptionMethodTypeRecord).where(
                HostedRedemptionMethodTypeRecord.workspace_id == workspace_id,
                HostedRedemptionMethodTypeRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _record_to_model(record: HostedRedemptionMethodTypeRecord) -> HostedRedemptionMethodType:
        return HostedRedemptionMethodType(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            is_active=record.is_active,
            notes=record.notes,
        )
