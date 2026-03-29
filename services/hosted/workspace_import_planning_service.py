"""Hosted workspace import-planning flow for authenticated users."""

from __future__ import annotations

from dataclasses import dataclass

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.models import HostedWorkspace
from services.hosted.sqlite_migration_inventory_service import (
    SQLiteMigrationInventory,
    SQLiteMigrationInventoryService,
)


@dataclass(frozen=True)
class HostedWorkspaceImportPlanningSummary:
    workspace: HostedWorkspace
    status: str
    detail: str
    source_db_configured: bool
    source_db_accessible: bool
    inventory: SQLiteMigrationInventory | None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "detail": self.detail,
            "source_db_configured": self.source_db_configured,
            "source_db_accessible": self.source_db_accessible,
            "workspace": {
                "id": self.workspace.id,
                "account_id": self.workspace.account_id,
                "name": self.workspace.name,
                "source_db_path": self.workspace.source_db_path,
            },
            "inventory": self.inventory.to_dict() if self.inventory else None,
        }


class HostedWorkspaceImportPlanningService:
    def __init__(self, session_factory, *, inventory_service: SQLiteMigrationInventoryService | None = None) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.inventory_service = inventory_service or SQLiteMigrationInventoryService()

    def plan_import(self, *, supabase_user_id: str) -> HostedWorkspaceImportPlanningSummary:
        with self.session_factory() as session:
            account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
            if account is None:
                raise LookupError("Hosted workspace bootstrap must complete before import planning.")

            workspace = self.workspace_repository.get_by_account_id(session, account.id)
            if workspace is None:
                raise LookupError("Hosted workspace bootstrap must complete before import planning.")

        source_db_path = (workspace.source_db_path or "").strip() if workspace.source_db_path else ""
        if not source_db_path:
            return HostedWorkspaceImportPlanningSummary(
                workspace=workspace,
                status="source-db-path-missing",
                detail="No source SQLite database path is recorded for this hosted workspace yet.",
                source_db_configured=False,
                source_db_accessible=False,
                inventory=None,
            )

        try:
            inventory = self.inventory_service.inspect_database(source_db_path)
        except FileNotFoundError:
            return HostedWorkspaceImportPlanningSummary(
                workspace=workspace,
                status="source-db-not-found",
                detail="The recorded source SQLite database path is not accessible to this API deployment.",
                source_db_configured=True,
                source_db_accessible=False,
                inventory=None,
            )
        except Exception:
            return HostedWorkspaceImportPlanningSummary(
                workspace=workspace,
                status="inspection-failed",
                detail="SQLite import planning failed during inspection. Hosted state was not changed.",
                source_db_configured=True,
                source_db_accessible=False,
                inventory=None,
            )

        return HostedWorkspaceImportPlanningSummary(
            workspace=workspace,
            status="ready",
            detail="Workspace import planning inventory is ready.",
            source_db_configured=True,
            source_db_accessible=True,
            inventory=inventory,
        )