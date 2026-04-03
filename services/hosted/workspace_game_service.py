"""Hosted workspace-managed games service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_game_repository import HostedGameRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedGame, HostedWorkspace


class HostedWorkspaceGameService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.game_repository = HostedGameRepository()

    def list_games_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.game_repository.count_by_workspace_id(session, workspace.id)
            games = self.game_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(games)
            has_more = next_offset < total_count
            return {
                "games": games,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_game(
        self,
        *,
        supabase_user_id: str,
        name: str,
        game_type_id: str,
        rtp: float | None = None,
        notes: str | None = None,
    ) -> HostedGame:
        candidate = HostedGame(name=name, game_type_id=game_type_id, rtp=rtp, notes=notes)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created = self.game_repository.create(
                session,
                workspace_id=workspace.id,
                name=candidate.name,
                game_type_id=candidate.game_type_id,
                rtp=candidate.rtp,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created

    def update_game(
        self,
        *,
        supabase_user_id: str,
        game_id: str,
        name: str,
        game_type_id: str,
        rtp: float | None = None,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedGame:
        candidate = HostedGame(
            name=name, game_type_id=game_type_id, rtp=rtp, notes=notes, is_active=is_active
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated = self.game_repository.update(
                session,
                game_id=game_id,
                workspace_id=workspace.id,
                name=candidate.name,
                game_type_id=candidate.game_type_id,
                rtp=candidate.rtp,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated is None:
                raise LookupError("Hosted game was not found in the authenticated workspace.")

            session.commit()
            return updated

    def delete_game(
        self,
        *,
        supabase_user_id: str,
        game_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.game_repository.delete(
                session,
                game_id=game_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted game was not found in the authenticated workspace.")

            session.commit()

    def delete_games(
        self,
        *,
        supabase_user_id: str,
        game_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(game_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted game id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.game_repository.delete_many(
                session,
                game_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted games were not found in the authenticated workspace."
                )

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing games."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing games."
            )

        return workspace
