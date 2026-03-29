"""Persistence helpers for hosted workspace-owned business users."""

from __future__ import annotations

from sqlalchemy import select

from services.hosted.models import HostedUser
from services.hosted.persistence import HostedUserRecord


class HostedUserRepository:
    def list_by_workspace_id(self, session, workspace_id: str) -> list[HostedUser]:
        records = session.scalars(
            select(HostedUserRecord)
            .where(HostedUserRecord.workspace_id == workspace_id)
            .order_by(HostedUserRecord.name.asc(), HostedUserRecord.id.asc())
        ).all()
        return [self._record_to_model(record) for record in records]

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