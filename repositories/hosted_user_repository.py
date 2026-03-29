"""Persistence helpers for hosted workspace-owned business users."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from services.hosted.models import HostedUser
from services.hosted.persistence import HostedUserRecord


class HostedUserRepository:
    def get_by_id_and_workspace_id(self, session, *, user_id: str, workspace_id: str) -> HostedUser | None:
        record = session.scalar(
            select(HostedUserRecord).where(
                HostedUserRecord.id == user_id,
                HostedUserRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None
        return self._record_to_model(record)

    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedUser]:
        query = (
            select(HostedUserRecord)
            .where(HostedUserRecord.workspace_id == workspace_id)
            .order_by(HostedUserRecord.name.asc(), HostedUserRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        records = session.scalars(query).all()
        return [self._record_to_model(record) for record in records]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedUserRecord)
            .where(HostedUserRecord.workspace_id == workspace_id)
        ) or 0

    def create(
        self,
        session,
        *,
        workspace_id: str,
        name: str,
        email: str | None = None,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedUser:
        record = HostedUserRecord(
            workspace_id=workspace_id,
            name=name,
            email=email,
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
        user_id: str,
        workspace_id: str,
        name: str,
        email: str | None,
        notes: str | None,
        is_active: bool,
    ) -> HostedUser | None:
        record = session.scalar(
            select(HostedUserRecord).where(
                HostedUserRecord.id == user_id,
                HostedUserRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.name = name
        record.email = email
        record.notes = notes
        record.is_active = is_active
        session.flush()
        return self._record_to_model(record)

    def delete(self, session, *, user_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedUserRecord).where(
                HostedUserRecord.id == user_id,
                HostedUserRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, user_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(user_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedUserRecord).where(
                HostedUserRecord.workspace_id == workspace_id,
                HostedUserRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _record_to_model(record: HostedUserRecord) -> HostedUser:
        return HostedUser(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            email=record.email,
            notes=record.notes,
            is_active=record.is_active,
        )