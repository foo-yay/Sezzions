"""Hosted workspace-managed expenses service."""

from __future__ import annotations

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_expense_repository import HostedExpenseRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedExpense, HostedWorkspace


class HostedWorkspaceExpenseService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.expense_repository = HostedExpenseRepository()

    def list_expenses_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.expense_repository.count_by_workspace_id(session, workspace.id)
            expenses = self.expense_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(expenses)
            has_more = next_offset < total_count
            return {
                "expenses": expenses,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    def create_expense(
        self,
        *,
        supabase_user_id: str,
        expense_date: str,
        amount: str,
        vendor: str,
        expense_time: str | None = None,
        expense_entry_time_zone: str | None = None,
        description: str | None = None,
        category: str | None = None,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> HostedExpense:
        # Validate via model
        HostedExpense(
            expense_date=expense_date,
            amount=amount,
            vendor=vendor,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            created = self.expense_repository.create(
                session,
                workspace_id=workspace.id,
                expense_date=expense_date,
                expense_time=expense_time,
                expense_entry_time_zone=expense_entry_time_zone,
                amount=amount,
                vendor=vendor,
                description=description,
                category=category,
                user_id=user_id,
                notes=notes,
            )

            session.commit()
            return created

    def update_expense(
        self,
        *,
        supabase_user_id: str,
        expense_id: str,
        expense_date: str,
        amount: str,
        vendor: str,
        expense_time: str | None = None,
        expense_entry_time_zone: str | None = None,
        description: str | None = None,
        category: str | None = None,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> HostedExpense:
        # Validate via model
        HostedExpense(
            expense_date=expense_date,
            amount=amount,
            vendor=vendor,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            updated = self.expense_repository.update(
                session,
                expense_id=expense_id,
                workspace_id=workspace.id,
                expense_date=expense_date,
                expense_time=expense_time,
                expense_entry_time_zone=expense_entry_time_zone,
                amount=amount,
                vendor=vendor,
                description=description,
                category=category,
                user_id=user_id,
                notes=notes,
            )
            if updated is None:
                raise LookupError("Hosted expense was not found in the authenticated workspace.")

            session.commit()
            return updated

    def delete_expense(
        self,
        *,
        supabase_user_id: str,
        expense_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            deleted = self.expense_repository.delete(
                session,
                expense_id=expense_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError("Hosted expense was not found in the authenticated workspace.")

            session.commit()

    def delete_expenses(
        self,
        *,
        supabase_user_id: str,
        expense_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(expense_ids))
        if not normalized_ids:
            raise ValueError("At least one hosted expense id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            deleted_count = self.expense_repository.delete_many(
                session,
                expense_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more hosted expenses were not found in the authenticated workspace."
                )

            session.commit()
            return deleted_count

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing expenses."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing expenses."
            )

        return workspace
