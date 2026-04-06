"""Hosted workspace-managed redemptions service."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_redemption_repository import HostedRedemptionRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.hosted_recalculation_service import HostedRecalculationService
from services.hosted.models import HostedRedemption, HostedWorkspace


class HostedWorkspaceRedemptionService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.redemption_repository = HostedRedemptionRepository()
        self.recalculation_service = HostedRecalculationService()

    def list_redemptions_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.redemption_repository.count_by_workspace_id(session, workspace.id)
            redemptions = self.redemption_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(redemptions)
            has_more = next_offset < total_count
            return {
                "redemptions": redemptions,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_redemption(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        redemption_date: str,
        redemption_time: str | None = None,
        redemption_method_id: str | None = None,
        fees: str = "0.00",
        is_free_sc: bool = False,
        receipt_date: str | None = None,
        processed: bool = False,
        more_remaining: bool = False,
        notes: str | None = None,
    ) -> HostedRedemption:
        candidate = HostedRedemption(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            redemption_date=redemption_date,
            redemption_time=redemption_time or "00:00:00",
            redemption_method_id=redemption_method_id,
            fees=fees,
            is_free_sc=is_free_sc,
            receipt_date=receipt_date,
            processed=processed,
            more_remaining=more_remaining,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            created = self.redemption_repository.create(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                amount=candidate.amount,
                redemption_date=candidate.redemption_date,
                redemption_time=candidate.redemption_time,
                redemption_method_id=candidate.redemption_method_id,
                fees=candidate.fees,
                is_free_sc=candidate.is_free_sc,
                receipt_date=candidate.receipt_date,
                processed=candidate.processed,
                more_remaining=candidate.more_remaining,
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

            # Re-fetch to get updated accounting fields after FIFO rebuild
            return self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=created.id, workspace_id=workspace.id
            ) or created

    def update_redemption(
        self,
        *,
        supabase_user_id: str,
        redemption_id: str,
        user_id: str,
        site_id: str,
        amount: str,
        redemption_date: str,
        redemption_time: str | None = None,
        redemption_method_id: str | None = None,
        fees: str = "0.00",
        is_free_sc: bool = False,
        receipt_date: str | None = None,
        processed: bool = False,
        more_remaining: bool = False,
        notes: str | None = None,
        status: str = "PENDING",
    ) -> HostedRedemption:
        candidate = HostedRedemption(
            user_id=user_id,
            site_id=site_id,
            amount=amount,
            redemption_date=redemption_date,
            redemption_time=redemption_time or "00:00:00",
            redemption_method_id=redemption_method_id,
            fees=fees,
            is_free_sc=is_free_sc,
            receipt_date=receipt_date,
            processed=processed,
            more_remaining=more_remaining,
            notes=notes,
            status=status,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            existing = self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            if existing.status in ("CANCELED",):
                raise ValueError("Cannot update a canceled redemption.")

            # Track whether (user, site) pair changed for FIFO rebuild
            old_user_id = existing.user_id
            old_site_id = existing.site_id

            updated = self.redemption_repository.update(
                session,
                redemption_id=redemption_id,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                amount=candidate.amount,
                redemption_date=candidate.redemption_date,
                redemption_time=candidate.redemption_time,
                redemption_method_id=candidate.redemption_method_id,
                fees=candidate.fees,
                is_free_sc=candidate.is_free_sc,
                receipt_date=candidate.receipt_date,
                processed=candidate.processed,
                more_remaining=candidate.more_remaining,
                notes=candidate.notes,
                status=candidate.status,
                canceled_at=existing.canceled_at,
                cancel_reason=existing.cancel_reason,
            )
            if updated is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            # Rebuild FIFO for affected (user, site) pair(s)
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )
            if old_user_id != candidate.user_id or old_site_id != candidate.site_id:
                self.recalculation_service.rebuild_fifo_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=old_user_id,
                    site_id=old_site_id,
                )

            session.commit()

            return self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            ) or updated

    def delete_redemption(
        self,
        *,
        supabase_user_id: str,
        redemption_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            existing = self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            deleted = self.redemption_repository.delete(
                session,
                redemption_id=redemption_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            # Rebuild FIFO for affected (user, site) pair
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
            )

            session.commit()

    def delete_redemptions(
        self,
        *,
        supabase_user_id: str,
        redemption_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(redemption_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted redemption id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            affected_pairs: set[tuple[str, str]] = set()
            for rid in normalized_ids:
                existing = self.redemption_repository.get_by_id_and_workspace_id(
                    session, redemption_id=rid, workspace_id=workspace.id
                )
                if existing is None:
                    raise LookupError(
                        "One or more hosted redemptions were not found in the authenticated workspace."
                    )
                affected_pairs.add((existing.user_id, existing.site_id))

            deleted_count = self.redemption_repository.delete_many(
                session,
                redemption_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted redemptions were not found in the authenticated workspace."
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

    def cancel_redemption(
        self,
        *,
        supabase_user_id: str,
        redemption_id: str,
        reason: str | None = None,
    ) -> HostedRedemption:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            existing = self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            if existing.status != "PENDING":
                raise ValueError(f"Only PENDING redemptions can be canceled (current: {existing.status}).")

            now_utc = datetime.now(timezone.utc).isoformat()

            updated = self.redemption_repository.update(
                session,
                redemption_id=redemption_id,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
                amount=existing.amount,
                redemption_date=existing.redemption_date,
                redemption_time=existing.redemption_time,
                redemption_method_id=existing.redemption_method_id,
                fees=existing.fees,
                is_free_sc=existing.is_free_sc,
                receipt_date=existing.receipt_date,
                processed=existing.processed,
                more_remaining=existing.more_remaining,
                notes=existing.notes,
                status="CANCELED",
                canceled_at=now_utc,
                cancel_reason=reason,
            )
            if updated is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            # Rebuild FIFO — canceling removes the allocation
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
            )

            session.commit()

            return self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            ) or updated

    def uncancel_redemption(
        self,
        *,
        supabase_user_id: str,
        redemption_id: str,
    ) -> HostedRedemption:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            existing = self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            if existing.status not in ("CANCELED", "PENDING_CANCEL"):
                raise ValueError(f"Only canceled redemptions can be uncanceled (current: {existing.status}).")

            updated = self.redemption_repository.update(
                session,
                redemption_id=redemption_id,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
                amount=existing.amount,
                redemption_date=existing.redemption_date,
                redemption_time=existing.redemption_time,
                redemption_method_id=existing.redemption_method_id,
                fees=existing.fees,
                is_free_sc=existing.is_free_sc,
                receipt_date=existing.receipt_date,
                processed=existing.processed,
                more_remaining=existing.more_remaining,
                notes=existing.notes,
                status="PENDING",
                canceled_at=None,
                cancel_reason=None,
            )
            if updated is None:
                raise LookupError("Hosted redemption was not found in the authenticated workspace.")

            # Rebuild FIFO — uncanceling restores the allocation
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
            )

            session.commit()

            return self.redemption_repository.get_by_id_and_workspace_id(
                session, redemption_id=redemption_id, workspace_id=workspace.id
            ) or updated

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing redemptions."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing redemptions."
            )

        return workspace
