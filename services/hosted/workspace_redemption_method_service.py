"""Hosted workspace-managed redemption methods service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_redemption_method_repository import HostedRedemptionMethodRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedRedemptionMethod, HostedWorkspace


class HostedWorkspaceRedemptionMethodService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.method_repository = HostedRedemptionMethodRepository()

    def list_methods_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.method_repository.count_by_workspace_id(session, workspace.id)
            methods = self.method_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(methods)
            has_more = next_offset < total_count
            return {
                "redemption_methods": methods,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_method(
        self,
        *,
        supabase_user_id: str,
        name: str,
        method_type_id: str,
        user_id: str,
        notes: str | None = None,
    ) -> HostedRedemptionMethod:
        candidate = HostedRedemptionMethod(
            name=name,
            method_type_id=method_type_id,
            user_id=user_id,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created = self.method_repository.create(
                session,
                workspace_id=workspace.id,
                name=candidate.name,
                method_type_id=candidate.method_type_id,
                user_id=candidate.user_id,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created

    def update_method(
        self,
        *,
        supabase_user_id: str,
        method_id: str,
        name: str,
        method_type_id: str,
        user_id: str,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedRedemptionMethod:
        candidate = HostedRedemptionMethod(
            name=name,
            method_type_id=method_type_id,
            user_id=user_id,
            notes=notes,
            is_active=is_active,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated = self.method_repository.update(
                session,
                method_id=method_id,
                workspace_id=workspace.id,
                name=candidate.name,
                method_type_id=candidate.method_type_id,
                user_id=candidate.user_id,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated is None:
                raise LookupError("Hosted redemption method was not found in the authenticated workspace.")

            session.commit()
            return updated

    def delete_method(
        self,
        *,
        supabase_user_id: str,
        method_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.method_repository.delete(
                session,
                method_id=method_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted redemption method was not found in the authenticated workspace.")

            session.commit()

    def delete_methods(
        self,
        *,
        supabase_user_id: str,
        method_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(method_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted redemption method id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.method_repository.delete_many(
                session,
                method_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted redemption methods were not found in the authenticated workspace."
                )

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing redemption methods."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing redemption methods."
            )

        return workspace
