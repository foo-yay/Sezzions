"""Hosted backend and migration helpers."""

__all__ = [
	"HostedAccountBootstrapService",
	"HostedBootstrapSummary",
	"HostedWorkspaceImportPlanningService",
	"HostedWorkspaceImportPlanningSummary",
]


def __getattr__(name: str):
	if name in {"HostedAccountBootstrapService", "HostedBootstrapSummary"}:
		from services.hosted.account_bootstrap_service import (
			HostedAccountBootstrapService,
			HostedBootstrapSummary,
		)

		return {
			"HostedAccountBootstrapService": HostedAccountBootstrapService,
			"HostedBootstrapSummary": HostedBootstrapSummary,
		}[name]
	if name in {"HostedWorkspaceImportPlanningService", "HostedWorkspaceImportPlanningSummary"}:
		from services.hosted.workspace_import_planning_service import (
			HostedWorkspaceImportPlanningService,
			HostedWorkspaceImportPlanningSummary,
		)

		return {
			"HostedWorkspaceImportPlanningService": HostedWorkspaceImportPlanningService,
			"HostedWorkspaceImportPlanningSummary": HostedWorkspaceImportPlanningSummary,
		}[name]
	raise AttributeError(name)
