"""Hosted workspace-managed business users/player directory service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_user_repository import HostedUserRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedUser, HostedWorkspace


class HostedWorkspaceUserService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.user_repository = HostedUserRepository()

    def list_users(self, *, supabase_user_id: str) -> list[HostedUser]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            return self.user_repository.list_by_workspace_id(session, workspace.id)

    def list_users_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.user_repository.count_by_workspace_id(session, workspace.id)
            users = self.user_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(users)
            has_more = next_offset < total_count
            return {
                "users": users,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_user(
        self,
        *,
        supabase_user_id: str,
        name: str,
        email: str | None = None,
        notes: str | None = None,
    ) -> HostedUser:
        candidate = HostedUser(name=name, email=email, notes=notes)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created_user = self.user_repository.create(
                session,
                workspace_id=workspace.id,
                name=candidate.name,
                email=candidate.email,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created_user

    def update_user(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
        name: str,
        email: str | None = None,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedUser:
        candidate = HostedUser(name=name, email=email, notes=notes, is_active=is_active)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated_user = self.user_repository.update(
                session,
                user_id=user_id,
                workspace_id=workspace.id,
                name=candidate.name,
                email=candidate.email,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated_user is None:
                raise LookupError("Hosted user was not found in the authenticated workspace.")

            session.commit()
            return updated_user

    def delete_user(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.user_repository.delete(
                session,
                user_id=user_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted user was not found in the authenticated workspace.")

            session.commit()

    def delete_users(
        self,
        *,
        supabase_user_id: str,
        user_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(user_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted user id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.user_repository.delete_many(
                session,
                user_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError("One or more hosted users were not found in the authenticated workspace.")

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError("Hosted workspace bootstrap must complete before managing workspace users.")

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError("Hosted workspace bootstrap must complete before managing workspace users.")

        return workspace