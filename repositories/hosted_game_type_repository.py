"""Persistence helpers for hosted workspace-owned game types."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from services.hosted.models import HostedGameType
from services.hosted.persistence import HostedGameTypeRecord


class HostedGameTypeRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedGameType]:
        query = (
            select(HostedGameTypeRecord)
            .where(HostedGameTypeRecord.workspace_id == workspace_id)
            .order_by(HostedGameTypeRecord.name.asc(), HostedGameTypeRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        records = session.scalars(query).all()
        return [self._record_to_model(record) for record in records]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedGameTypeRecord)
            .where(HostedGameTypeRecord.workspace_id == workspace_id)
        ) or 0

    def create(
        self,
        session,
        *,
        workspace_id: str,
        name: str,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedGameType:
        record = HostedGameTypeRecord(
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
        game_type_id: str,
        workspace_id: str,
        name: str,
        notes: str | None,
        is_active: bool,
    ) -> HostedGameType | None:
        record = session.scalar(
            select(HostedGameTypeRecord).where(
                HostedGameTypeRecord.id == game_type_id,
                HostedGameTypeRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.name = name
        record.notes = notes
        record.is_active = is_active
        session.flush()
        return self._record_to_model(record)

    def delete(self, session, *, game_type_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedGameTypeRecord).where(
                HostedGameTypeRecord.id == game_type_id,
                HostedGameTypeRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, game_type_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(game_type_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedGameTypeRecord).where(
                HostedGameTypeRecord.workspace_id == workspace_id,
                HostedGameTypeRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _record_to_model(record: HostedGameTypeRecord) -> HostedGameType:
        return HostedGameType(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            is_active=record.is_active,
            notes=record.notes,
        )
