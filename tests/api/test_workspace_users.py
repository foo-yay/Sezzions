from fastapi.testclient import TestClient

from api.app import app, get_hosted_workspace_user_service
from api.auth import AuthenticatedSession, get_authenticated_session


client = TestClient(app)


def test_workspace_users_list_endpoint_returns_workspace_users() -> None:
    class StubWorkspaceUserService:
        def list_users(self, *, supabase_user_id: str):
            assert supabase_user_id == "owner-123"
            return [
                {
                    "id": "user-1",
                    "workspace_id": "workspace-123",
                    "name": "Alice",
                    "email": "alice@sezzions.com",
                    "notes": None,
                    "is_active": True,
                }
            ]

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: StubWorkspaceUserService()

    try:
        response = client.get("/v1/workspace/users")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["users"][0]["name"] == "Alice"


def test_workspace_users_create_endpoint_returns_created_user() -> None:
    class StubWorkspaceUserService:
        def create_user(self, *, supabase_user_id: str, name: str, email: str | None, notes: str | None):
            assert supabase_user_id == "owner-123"
            return {
                "id": "user-1",
                "workspace_id": "workspace-123",
                "name": name,
                "email": email,
                "notes": notes,
                "is_active": True,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: StubWorkspaceUserService()

    try:
        response = client.post(
            "/v1/workspace/users",
            json={"name": "Alice", "email": "alice@sezzions.com", "notes": "VIP"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Alice"
    assert response.json()["workspace_id"] == "workspace-123"


def test_workspace_users_endpoints_require_bearer_auth() -> None:
    list_response = client.get("/v1/workspace/users")
    create_response = client.post("/v1/workspace/users", json={"name": "Alice"})

    assert list_response.status_code == 401
    assert create_response.status_code == 401


def test_workspace_users_create_endpoint_returns_400_for_invalid_name() -> None:
    class RejectingWorkspaceUserService:
        def create_user(self, *, supabase_user_id: str, name: str, email: str | None, notes: str | None):
            raise ValueError("User name is required")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: RejectingWorkspaceUserService()

    try:
        response = client.post("/v1/workspace/users", json={"name": "   "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "User name is required"