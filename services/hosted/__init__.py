"""Hosted backend and migration helpers."""

__all__ = [
	"HostedAccountBootstrapService",
	"HostedBootstrapSummary",
	"HostedUploadedSQLiteInspectionService",
	"HostedUploadedSQLiteInspectionSummary",
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
	if name in {"HostedUploadedSQLiteInspectionService", "HostedUploadedSQLiteInspectionSummary"}:
		from services.hosted.uploaded_sqlite_inspection_service import (
			HostedUploadedSQLiteInspectionService,
			HostedUploadedSQLiteInspectionSummary,
		)

		return {
			"HostedUploadedSQLiteInspectionService": HostedUploadedSQLiteInspectionService,
			"HostedUploadedSQLiteInspectionSummary": HostedUploadedSQLiteInspectionSummary,
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
