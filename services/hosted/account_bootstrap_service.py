"""Hosted account/workspace bootstrap flow for authenticated users."""

from __future__ import annotations

from dataclasses import dataclass

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedAccount, HostedWorkspace


@dataclass(frozen=True)
class HostedBootstrapSummary:
    account: HostedAccount
    workspace: HostedWorkspace
    created_account: bool
    created_workspace: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "created_account": self.created_account,
            "created_workspace": self.created_workspace,
            "account": {
                "id": self.account.id,
                "owner_email": self.account.owner_email,
                "auth_provider": self.account.auth_provider,
                "supabase_user_id": self.account.supabase_user_id,
            },
            "workspace": {
                "id": self.workspace.id,
                "account_id": self.workspace.account_id,
                "name": self.workspace.name,
                "source_db_path": self.workspace.source_db_path,
            },
        }


class HostedAccountBootstrapService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()

    def bootstrap_account_workspace(
        self,
        *,
        supabase_user_id: str,
        owner_email: str | None,
    ) -> HostedBootstrapSummary:
        normalized_email = self._normalized_owner_email(owner_email, supabase_user_id)

        with self.session_factory() as session:
            created_account = False
            created_workspace = False

            account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
            if account is None:
                account = self.account_repository.create(
                    session,
                    owner_email=normalized_email,
                    supabase_user_id=supabase_user_id,
                )
                created_account = True
            elif account.owner_email != normalized_email:
                account = self.account_repository.update_owner_email(
                    session,
                    supabase_user_id=supabase_user_id,
                    owner_email=normalized_email,
                )

            workspace = self.workspace_repository.get_by_account_id(session, account.id)
            if workspace is None:
                workspace = self.workspace_repository.create(
                    session,
                    account_id=account.id,
                    name=f"{account.owner_email} Workspace",
                )
                created_workspace = True

            session.commit()

        return HostedBootstrapSummary(
            account=account,
            workspace=workspace,
            created_account=created_account,
            created_workspace=created_workspace,
        )

    @staticmethod
    def _normalized_owner_email(owner_email: str | None, supabase_user_id: str) -> str:
        if owner_email and owner_email.strip():
            return owner_email.strip().lower()
        return f"{supabase_user_id}@users.sezzions.local"