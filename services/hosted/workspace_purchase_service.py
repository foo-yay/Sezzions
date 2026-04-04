"""Hosted workspace-managed purchases service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_purchase_repository import HostedPurchaseRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedPurchase, HostedWorkspace


class HostedWorkspacePurchaseService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.purchase_repository = HostedPurchaseRepository()

    def list_purchases_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.purchase_repository.count_by_workspace_id(session, workspace.id)
            purchases = self.purchase_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(purchases)
            has_more = next_offset < total_count
            return {
                "purchases": purchases,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_purchase(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        purchase_date: str,
        purchase_time: str | None = None,
        sc_received: str | None = None,
        starting_sc_balance: str = "0.00",
        cashback_earned: str = "0.00",
        cashback_is_manual: bool = False,
        card_id: str | None = None,
        notes: str | None = None,
    ) -> HostedPurchase:
        candidate = HostedPurchase(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            purchase_date=purchase_date,
            purchase_time=purchase_time,
            sc_received=sc_received,
            starting_sc_balance=starting_sc_balance,
            cashback_earned=cashback_earned,
            cashback_is_manual=cashback_is_manual,
            card_id=card_id,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            created = self.purchase_repository.create(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                amount=candidate.amount,
                purchase_date=candidate.purchase_date,
                purchase_time=candidate.purchase_time,
                sc_received=candidate.sc_received,
                starting_sc_balance=candidate.starting_sc_balance,
                cashback_earned=candidate.cashback_earned,
                cashback_is_manual=candidate.cashback_is_manual,
                card_id=candidate.card_id,
                remaining_amount=candidate.remaining_amount,
                notes=candidate.notes,
            )
            session.commit()
            return created

    def update_purchase(
        self,
        *,
        supabase_user_id: str,
        purchase_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        purchase_date: str,
        purchase_time: str | None = None,
        sc_received: str | None = None,
        starting_sc_balance: str = "0.00",
        cashback_earned: str = "0.00",
        cashback_is_manual: bool = False,
        card_id: str | None = None,
        status: str = "active",
        notes: str | None = None,
    ) -> HostedPurchase:
        candidate = HostedPurchase(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            purchase_date=purchase_date,
            purchase_time=purchase_time,
            sc_received=sc_received,
            starting_sc_balance=starting_sc_balance,
            cashback_earned=cashback_earned,
            cashback_is_manual=cashback_is_manual,
            card_id=card_id,
            status=status,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            updated = self.purchase_repository.update(
                session,
                purchase_id=purchase_id,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                amount=candidate.amount,
                purchase_date=candidate.purchase_date,
                purchase_time=candidate.purchase_time,
                sc_received=candidate.sc_received,
                starting_sc_balance=candidate.starting_sc_balance,
                cashback_earned=candidate.cashback_earned,
                cashback_is_manual=candidate.cashback_is_manual,
                card_id=candidate.card_id,
                remaining_amount=candidate.remaining_amount,
                status=candidate.status,
                notes=candidate.notes,
            )
            if updated is None:
                raise LookupError("Hosted purchase was not found in the authenticated workspace.")

            session.commit()
            return updated

    def delete_purchase(
        self,
        *,
        supabase_user_id: str,
        purchase_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted = self.purchase_repository.delete(
                session,
                purchase_id=purchase_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted purchase was not found in the authenticated workspace.")

            session.commit()

    def delete_purchases(
        self,
        *,
        supabase_user_id: str,
        purchase_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(purchase_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted purchase id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            deleted_count = self.purchase_repository.delete_many(
                session,
                purchase_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted purchases were not found in the authenticated workspace."
                )

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing purchases."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing purchases."
            )

        return workspace
