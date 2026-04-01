"""Hosted workspace-managed redemption method types service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_redemption_method_type_repository import HostedRedemptionMethodTypeRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedRedemptionMethodType, HostedWorkspace


class HostedWorkspaceRedemptionMethodTypeService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.method_type_repository = HostedRedemptionMethodTypeRepository()

    def list_method_types_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.method_type_repository.count_by_workspace_id(session, workspace.id)
            method_types = self.method_type_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(method_types)
            has_more = next_offset < total_count
            return {
                "redemption_method_types": method_types,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_method_type(
        self,
        *,
        supabase_user_id: str,
        name: str,
        notes: str | None = None,
    ) -> HostedRedemptionMethodType:
        candidate = HostedRedemptionMethodType(name=name, notes=notes)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created = self.method_type_repository.create(
                session,
                workspace_id=workspace.id,
                name=candidate.name,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created

    def update_method_type(
        self,
        *,
        supabase_user_id: str,
        method_type_id: str,
        name: str,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedRedemptionMethodType:
        candidate = HostedRedemptionMethodType(name=name, notes=notes, is_active=is_active)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated = self.method_type_repository.update(
                session,
                method_type_id=method_type_id,
                workspace_id=workspace.id,
                name=candidate.name,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated is None:
                raise LookupError("Hosted redemption method type was not found in the authenticated workspace.")

            session.commit()
            return updated

    def delete_method_type(
        self,
        *,
        supabase_user_id: str,
        method_type_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.method_type_repository.delete(
                session,
                method_type_id=method_type_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted redemption method type was not found in the authenticated workspace.")

            session.commit()

    def delete_method_types(
        self,
        *,
        supabase_user_id: str,
        method_type_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(method_type_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted redemption method type id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.method_type_repository.delete_many(
                session,
                method_type_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted redemption method types were not found in the authenticated workspace."
                )

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing redemption method types."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing redemption method types."
            )

        return workspace
