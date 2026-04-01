"""Hosted workspace-managed card directory service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_card_repository import HostedCardRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedCard, HostedWorkspace


class HostedWorkspaceCardService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.card_repository = HostedCardRepository()

    def list_cards(self, *, supabase_user_id: str) -> list[HostedCard]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            return self.card_repository.list_by_workspace_id(session, workspace.id)

    def list_cards_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.card_repository.count_by_workspace_id(session, workspace.id)
            cards = self.card_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(cards)
            has_more = next_offset < total_count
            return {
                "cards": cards,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_card(
        self,
        *,
        supabase_user_id: str,
        name: str,
        user_id: str,
        last_four: str | None = None,
        cashback_rate: float = 0.0,
        notes: str | None = None,
    ) -> HostedCard:
        candidate = HostedCard(
            name=name,
            user_id=user_id,
            last_four=last_four,
            cashback_rate=cashback_rate,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created_card = self.card_repository.create(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                name=candidate.name,
                last_four=candidate.last_four,
                cashback_rate=candidate.cashback_rate,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            session.commit()
            return created_card

    def update_card(
        self,
        *,
        supabase_user_id: str,
        card_id: str,
        name: str,
        user_id: str,
        last_four: str | None = None,
        cashback_rate: float = 0.0,
        notes: str | None = None,
        is_active: bool = True,
    ) -> HostedCard:
        candidate = HostedCard(
            name=name,
            user_id=user_id,
            last_four=last_four,
            cashback_rate=cashback_rate,
            notes=notes,
            is_active=is_active,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated_card = self.card_repository.update(
                session,
                card_id=card_id,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                name=candidate.name,
                last_four=candidate.last_four,
                cashback_rate=candidate.cashback_rate,
                notes=candidate.notes,
                is_active=candidate.is_active,
            )
            if updated_card is None:
                raise LookupError("Hosted card was not found in the authenticated workspace.")

            session.commit()
            return updated_card

    def delete_card(
        self,
        *,
        supabase_user_id: str,
        card_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.card_repository.delete(
                session,
                card_id=card_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted card was not found in the authenticated workspace.")

            session.commit()

    def delete_cards(
        self,
        *,
        supabase_user_id: str,
        card_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(card_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted card id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.card_repository.delete_many(
                session,
                card_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError("One or more hosted cards were not found in the authenticated workspace.")

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError("Hosted workspace bootstrap must complete before managing workspace cards.")

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError("Hosted workspace bootstrap must complete before managing workspace cards.")

        return workspace
