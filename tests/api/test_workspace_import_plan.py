from fastapi.testclient import TestClient

from api.app import app, get_hosted_workspace_import_planning_service
from api.auth import AuthenticatedSession, get_authenticated_session


client = TestClient(app)


def test_workspace_import_plan_endpoint_returns_readiness_summary() -> None:
    class StubPlanningService:
        def plan_import(self, *, supabase_user_id: str):
            return {
                "status": "ready",
                "detail": "Workspace import planning inventory is ready.",
                "source_db_configured": True,
                "source_db_accessible": True,
                "workspace": {
                    "id": "workspace-123",
                    "account_id": "account-123",
                    "name": "owner@sezzions.com Workspace",
                    "source_db_path": "/tmp/sezzions.db",
                },
                "inventory": {
                    "db_path": "/tmp/sezzions.db",
                    "db_size_bytes": 1024,
                    "schema_version_count": 1,
                    "tables": [{"table_name": "users", "row_count": 4}],
                    "active_user_names": ["Elliot"],
                    "site_names": ["Stake"],
                },
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="user-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_import_planning_service] = (
        lambda: StubPlanningService()
    )

    try:
        response = client.get("/v1/workspace/import-plan")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["inventory"]["active_user_names"] == ["Elliot"]


def test_workspace_import_plan_endpoint_requires_bearer_auth() -> None:
    response = client.get("/v1/workspace/import-plan")

    assert response.status_code == 401


def test_workspace_import_plan_endpoint_requires_existing_workspace() -> None:
    class MissingWorkspacePlanningService:
        def plan_import(self, *, supabase_user_id: str):
            raise LookupError("Hosted workspace bootstrap must complete before import planning.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="user-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_import_planning_service] = (
        lambda: MissingWorkspacePlanningService()
    )

    try:
        response = client.get("/v1/workspace/import-plan")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Hosted workspace bootstrap must complete before import planning."