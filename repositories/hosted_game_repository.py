"""Persistence helpers for hosted workspace-owned games."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from services.hosted.models import HostedGame
from services.hosted.persistence import (
    HostedGameRecord,
    HostedGameTypeRecord,
)


class HostedGameRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedGame]:
        type_alias = aliased(HostedGameTypeRecord)
        query = (
            select(
                HostedGameRecord,
                type_alias.name.label("game_type_name"),
            )
            .join(type_alias, HostedGameRecord.game_type_id == type_alias.id)
            .where(HostedGameRecord.workspace_id == workspace_id)
            .order_by(HostedGameRecord.name.asc(), HostedGameRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedGameRecord)
            .where(HostedGameRecord.workspace_id == workspace_id)
        ) or 0

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        game_id: str,
        workspace_id: str,
    ) -> HostedGame | None:
        type_alias = aliased(HostedGameTypeRecord)
        row = session.execute(
            select(
                HostedGameRecord,
                type_alias.name.label("game_type_name"),
            )
            .join(type_alias, HostedGameRecord.game_type_id == type_alias.id)
            .where(
                HostedGameRecord.id == game_id,
                HostedGameRecord.workspace_id == workspace_id,
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
        game_type_id: str,
        rtp: float | None = None,
        is_active: bool = True,
        notes: str | None = None,
    ) -> HostedGame:
        record = HostedGameRecord(
            workspace_id=workspace_id,
            name=name,
            game_type_id=game_type_id,
            rtp=rtp,
            is_active=is_active,
            notes=notes,
        )
        session.add(record)
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, game_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        game_id: str,
        workspace_id: str,
        name: str,
        game_type_id: str,
        rtp: float | None,
        is_active: bool,
        notes: str | None,
    ) -> HostedGame | None:
        record = session.scalar(
            select(HostedGameRecord).where(
                HostedGameRecord.id == game_id,
                HostedGameRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.name = name
        record.game_type_id = game_type_id
        record.rtp = rtp
        record.is_active = is_active
        record.notes = notes
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, game_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, game_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedGameRecord).where(
                HostedGameRecord.id == game_id,
                HostedGameRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, game_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(game_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedGameRecord).where(
                HostedGameRecord.workspace_id == workspace_id,
                HostedGameRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _row_to_model(row) -> HostedGame:
        record = row[0] if hasattr(row, "__getitem__") else row
        game_type_name = row.game_type_name if hasattr(row, "game_type_name") else None
        return HostedGame(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            game_type_id=record.game_type_id,
            rtp=record.rtp,
            actual_rtp=record.actual_rtp,
            is_active=record.is_active,
            notes=record.notes,
            game_type_name=game_type_name,
        )
