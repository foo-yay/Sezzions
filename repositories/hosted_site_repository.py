"""Persistence helpers for hosted workspace-owned business sites."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from services.hosted.models import HostedSite
from services.hosted.persistence import HostedSiteRecord


class HostedSiteRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedSite]:
        query = (
            select(HostedSiteRecord)
            .where(HostedSiteRecord.workspace_id == workspace_id)
            .order_by(HostedSiteRecord.name.asc(), HostedSiteRecord.id.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        records = session.scalars(query).all()
        return [self._record_to_model(record) for record in records]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedSiteRecord)
            .where(HostedSiteRecord.workspace_id == workspace_id)
        ) or 0

    def create(
        self,
        session,
        *,
        workspace_id: str,
        name: str,
        url: str | None = None,
        sc_rate: float = 1.0,
        playthrough_requirement: float = 1.0,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedSite:
        record = HostedSiteRecord(
            workspace_id=workspace_id,
            name=name,
            url=url,
            sc_rate=sc_rate,
            playthrough_requirement=playthrough_requirement,
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
        site_id: str,
        workspace_id: str,
        name: str,
        url: str | None,
        sc_rate: float,
        playthrough_requirement: float,
        notes: str | None,
        is_active: bool,
    ) -> HostedSite | None:
        record = session.scalar(
            select(HostedSiteRecord).where(
                HostedSiteRecord.id == site_id,
                HostedSiteRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.name = name
        record.url = url
        record.sc_rate = sc_rate
        record.playthrough_requirement = playthrough_requirement
        record.notes = notes
        record.is_active = is_active
        session.flush()
        return self._record_to_model(record)

    def delete(self, session, *, site_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedSiteRecord).where(
                HostedSiteRecord.id == site_id,
                HostedSiteRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, site_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(site_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedSiteRecord).where(
                HostedSiteRecord.workspace_id == workspace_id,
                HostedSiteRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _record_to_model(record: HostedSiteRecord) -> HostedSite:
        return HostedSite(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            url=record.url,
            sc_rate=record.sc_rate,
            playthrough_requirement=record.playthrough_requirement,
            is_active=record.is_active,
            notes=record.notes,
        )
