"""Hosted workspace-managed game types service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_game_type_repository import HostedGameTypeRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedGameType, HostedWorkspace


class HostedWorkspaceGameTypeService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.game_type_repository = HostedGameTypeRepository()

    def list_game_types_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.game_type_repository.count_by_workspace_id(session, workspace.id)
            game_types = self.game_type_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(game_types)
            has_more = next_offset < total_count
            return {
                "game_types": game_types,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_game_type(
        self,
        *,
        supabase_user_id: str,
        name: str,
        notes: str | None = None,
    ) -> HostedGameType:
        candidate = HostedGameType(name=name, notes=notes)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created = self.game_type_repository.create(
                session,
                workspace_id=workspace.id,
                name=candidate.name,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created

    def update_game_type(
        self,
        *,
        supabase_user_id: str,
        game_type_id: str,
        name: str,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedGameType:
        candidate = HostedGameType(name=name, notes=notes, is_active=is_active)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated = self.game_type_repository.update(
                session,
                game_type_id=game_type_id,
                workspace_id=workspace.id,
                name=candidate.name,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated is None:
                raise LookupError("Hosted game type was not found in the authenticated workspace.")

            session.commit()
            return updated

    def delete_game_type(
        self,
        *,
        supabase_user_id: str,
        game_type_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.game_type_repository.delete(
                session,
                game_type_id=game_type_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted game type was not found in the authenticated workspace.")

            session.commit()

    def delete_game_types(
        self,
        *,
        supabase_user_id: str,
        game_type_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(game_type_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted game type id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.game_type_repository.delete_many(
                session,
                game_type_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted game types were not found in the authenticated workspace."
                )

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing game types."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing game types."
            )

        return workspace
