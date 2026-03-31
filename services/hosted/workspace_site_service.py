"""Hosted workspace-managed site/casino directory service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_site_repository import HostedSiteRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedSite, HostedWorkspace


class HostedWorkspaceSiteService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.site_repository = HostedSiteRepository()

    def list_sites(self, *, supabase_user_id: str) -> list[HostedSite]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            return self.site_repository.list_by_workspace_id(session, workspace.id)

    def list_sites_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.site_repository.count_by_workspace_id(session, workspace.id)
            sites = self.site_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(sites)
            has_more = next_offset < total_count
            return {
                "sites": sites,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_site(
        self,
        *,
        supabase_user_id: str,
        name: str,
        url: str | None = None,
        sc_rate: float = 1.0,
        playthrough_requirement: float = 1.0,
        notes: str | None = None,
    ) -> HostedSite:
        candidate = HostedSite(
            name=name,
            url=url,
            sc_rate=sc_rate,
            playthrough_requirement=playthrough_requirement,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created_site = self.site_repository.create(
                session,
                workspace_id=workspace.id,
                name=candidate.name,
                url=candidate.url,
                sc_rate=candidate.sc_rate,
                playthrough_requirement=candidate.playthrough_requirement,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created_site

    def update_site(
        self,
        *,
        supabase_user_id: str,
        site_id: str,
        name: str,
        url: str | None = None,
        sc_rate: float = 1.0,
        playthrough_requirement: float = 1.0,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedSite:
        candidate = HostedSite(
            name=name,
            url=url,
            sc_rate=sc_rate,
            playthrough_requirement=playthrough_requirement,
            notes=notes,
            is_active=is_active,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated_site = self.site_repository.update(
                session,
                site_id=site_id,
                workspace_id=workspace.id,
                name=candidate.name,
                url=candidate.url,
                sc_rate=candidate.sc_rate,
                playthrough_requirement=candidate.playthrough_requirement,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated_site is None:
                raise LookupError("Hosted site was not found in the authenticated workspace.")

            session.commit()
            return updated_site

    def delete_site(
        self,
        *,
        supabase_user_id: str,
        site_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.site_repository.delete(
                session,
                site_id=site_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted site was not found in the authenticated workspace.")

            session.commit()

    def delete_sites(
        self,
        *,
        supabase_user_id: str,
        site_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(site_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted site id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.site_repository.delete_many(
                session,
                site_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError("One or more hosted sites were not found in the authenticated workspace.")

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError("Hosted workspace bootstrap must complete before managing workspace sites.")

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError("Hosted workspace bootstrap must complete before managing workspace sites.")

        return workspace
