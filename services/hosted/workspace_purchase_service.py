"""Hosted workspace-managed purchases service."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_card_repository import HostedCardRepository
from repositories.hosted_purchase_repository import HostedPurchaseRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.hosted_recalculation_service import HostedRecalculationService
from services.hosted.models import HostedPurchase, HostedWorkspace


class HostedWorkspacePurchaseService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.purchase_repository = HostedPurchaseRepository()
        self.card_repository = HostedCardRepository()
        self.recalculation_service = HostedRecalculationService()

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
        card_id: str,
        starting_sc_balance: str,
        purchase_time: str | None = None,
        sc_received: str | None = None,
        cashback_earned: str = "0.00",
        cashback_is_manual: bool = False,
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

            # Auto-calculate cashback if not manually set
            if not cashback_is_manual:
                computed = self._calculate_cashback(
                    session, workspace.id, candidate.amount, candidate.card_id
                )
                candidate.cashback_earned = computed

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

            # Rebuild FIFO for this (user, site) pair
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )

            session.commit()

            # Re-fetch to get updated remaining_amount after FIFO rebuild
            return self.purchase_repository.get_by_id_and_workspace_id(
                session, purchase_id=created.id, workspace_id=workspace.id
            ) or created

    def update_purchase(
        self,
        *,
        supabase_user_id: str,
        purchase_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        purchase_date: str,
        card_id: str,
        starting_sc_balance: str,
        purchase_time: str | None = None,
        sc_received: str | None = None,
        cashback_earned: str = "0.00",
        cashback_is_manual: bool = False,
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

            # Fetch existing purchase for consumed-amount checks
            existing = self.purchase_repository.get_by_id_and_workspace_id(
                session, purchase_id=purchase_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError("Hosted purchase was not found in the authenticated workspace.")

            old_amount = Decimal(str(existing.amount))
            old_remaining = Decimal(str(existing.remaining_amount or existing.amount))
            consumed = old_amount - old_remaining

            # Consumed protection: prevent amount / date changes if purchase has been consumed
            new_amount = Decimal(str(candidate.amount))
            if consumed > 0:
                if new_amount != old_amount:
                    raise ValueError(
                        "Cannot change amount on a purchase that has been partially or fully consumed by redemptions."
                    )
                if candidate.purchase_date != existing.purchase_date:
                    raise ValueError(
                        "Cannot change date on a purchase that has been partially or fully consumed by redemptions."
                    )

            # Proportional remaining_amount adjustment when amount changes
            if new_amount != old_amount and old_amount > 0:
                ratio = old_remaining / old_amount
                candidate.remaining_amount = str(
                    (new_amount * ratio).quantize(Decimal("0.01"))
                )
            else:
                candidate.remaining_amount = str(old_remaining)

            # Auto-calculate cashback if not manually set
            if not cashback_is_manual:
                computed = self._calculate_cashback(
                    session, workspace.id, candidate.amount, candidate.card_id
                )
                candidate.cashback_earned = computed

            # Track whether (user, site) pair changed for FIFO rebuild
            old_user_id = existing.user_id
            old_site_id = existing.site_id

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

            # Rebuild FIFO for affected (user, site) pair(s)
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )
            # If (user, site) changed, also rebuild the old pair
            if old_user_id != candidate.user_id or old_site_id != candidate.site_id:
                self.recalculation_service.rebuild_fifo_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=old_user_id,
                    site_id=old_site_id,
                )

            session.commit()

            # Re-fetch to get updated remaining_amount after FIFO rebuild
            return self.purchase_repository.get_by_id_and_workspace_id(
                session, purchase_id=purchase_id, workspace_id=workspace.id
            ) or updated

    def delete_purchase(
        self,
        *,
        supabase_user_id: str,
        purchase_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            # Fetch existing purchase for consumed-amount checks
            existing = self.purchase_repository.get_by_id_and_workspace_id(
                session, purchase_id=purchase_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError("Hosted purchase was not found in the authenticated workspace.")

            old_amount = Decimal(str(existing.amount))
            old_remaining = Decimal(str(existing.remaining_amount or existing.amount))
            consumed = old_amount - old_remaining
            if consumed > 0:
                raise ValueError(
                    "Cannot delete a purchase that has been partially or fully consumed by redemptions."
                )

            deleted = self.purchase_repository.delete(
                session,
                purchase_id=purchase_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted purchase was not found in the authenticated workspace.")

            # Rebuild FIFO for affected (user, site) pair
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
            )

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

            # Check consumed protection for each purchase in the batch
            affected_pairs: set[tuple[str, str]] = set()
            for pid in normalized_ids:
                existing = self.purchase_repository.get_by_id_and_workspace_id(
                    session, purchase_id=pid, workspace_id=workspace.id
                )
                if existing is None:
                    raise LookupError(
                        "One or more hosted purchases were not found in the authenticated workspace."
                    )
                old_amount = Decimal(str(existing.amount))
                old_remaining = Decimal(str(existing.remaining_amount or existing.amount))
                consumed = old_amount - old_remaining
                if consumed > 0:
                    raise ValueError(
                        "Cannot delete a purchase that has been partially or fully consumed by redemptions."
                    )
                affected_pairs.add((existing.user_id, existing.site_id))

            deleted_count = self.purchase_repository.delete_many(
                session,
                purchase_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted purchases were not found in the authenticated workspace."
                )

            # Rebuild FIFO for all affected (user, site) pairs
            for user_id, site_id in affected_pairs:
                self.recalculation_service.rebuild_fifo_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=user_id,
                    site_id=site_id,
                )

            session.commit()
            return deleted_count

    def _calculate_cashback(
        self, session, workspace_id: str, amount: str, card_id: str | None
    ) -> str:
        if not card_id:
            return "0.00"
        card = self.card_repository.get_by_id_and_workspace_id(
            session, card_id=card_id, workspace_id=workspace_id
        )
        if card is None or card.cashback_rate is None or float(card.cashback_rate) <= 0:
            return "0.00"
        amt = Decimal(str(amount))
        rate = Decimal(str(card.cashback_rate))
        cashback = (amt * rate / Decimal("100")).quantize(Decimal("0.01"))
        return str(cashback)

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

    def compute_expected_balance(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
        site_id: str,
        purchase_date: str,
        purchase_time: str | None = None,
        exclude_purchase_id: str | None = None,
    ) -> dict[str, str]:
        """Compute expected pre-purchase SC balance at a given timestamp.

        Walks all purchases for the user+site chronologically and returns the
        ``starting_sc_balance`` of the most recent purchase strictly before the
        cutoff.  When game sessions, redemptions, and adjustments are ported,
        this method should be expanded to include those anchors (matching the
        desktop ``GameSessionService.compute_expected_balances`` algorithm).
        """
        cutoff_time = purchase_time or "00:00:00"
        if len(cutoff_time) == 5:
            cutoff_time = f"{cutoff_time}:00"
        cutoff = (purchase_date, cutoff_time)

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            purchases = self.purchase_repository.list_by_workspace_user_and_site(
                session, workspace.id, user_id, site_id,
            )

        expected_total = Decimal("0.00")
        for p in purchases:
            p_time = p.purchase_time or "00:00:00"
            if len(p_time) == 5:
                p_time = f"{p_time}:00"
            p_key = (p.purchase_date, p_time, p.id or "")

            # Only consider purchases strictly before the cutoff (date, time, id).
            if (p.purchase_date, p_time) > cutoff:
                continue
            if (p.purchase_date, p_time) == cutoff:
                # Same timestamp: include only those with id < exclude id
                if exclude_purchase_id is not None and p.id and p.id >= exclude_purchase_id:
                    continue
                if exclude_purchase_id is None:
                    continue

            if exclude_purchase_id is not None and p.id == exclude_purchase_id:
                continue

            # Each purchase is authoritative: its starting_sc_balance is the
            # known post-purchase total.
            expected_total = Decimal(str(p.starting_sc_balance))

        return {"expected_total": str(expected_total)}
