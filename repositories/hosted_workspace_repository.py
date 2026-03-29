"""Persistence helpers for hosted product workspaces."""

from __future__ import annotations

from sqlalchemy import select

from services.hosted.models import HostedWorkspace
from services.hosted.persistence import HostedWorkspaceRecord


class HostedWorkspaceRepository:
    def get_by_account_id(self, session, account_id: str) -> HostedWorkspace | None:
        record = session.scalar(
            select(HostedWorkspaceRecord).where(HostedWorkspaceRecord.account_id == account_id)
        )
        if record is None:
            return None
        return HostedWorkspace(
            id=record.id,
            account_id=record.account_id,
            name=record.name,
            source_db_path=record.source_db_path,
        )

    def create(
        self,
        session,
        *,
        account_id: str,
        name: str,
        source_db_path: str | None = None,
    ) -> HostedWorkspace:
        record = HostedWorkspaceRecord(
            account_id=account_id,
            name=name,
            source_db_path=source_db_path,
        )
        session.add(record)
        session.flush()
        return HostedWorkspace(
            id=record.id,
            account_id=record.account_id,
            name=record.name,
            source_db_path=record.source_db_path,
        )