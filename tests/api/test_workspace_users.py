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


def test_workspace_users_update_endpoint_returns_updated_user() -> None:
    class StubWorkspaceUserService:
        def update_user(
            self,
            *,
            supabase_user_id: str,
            user_id: str,
            name: str,
            email: str | None,
            notes: str | None,
            is_active: bool,
        ):
            assert supabase_user_id == "owner-123"
            assert user_id == "user-1"
            return {
                "id": user_id,
                "workspace_id": "workspace-123",
                "name": name,
                "email": email,
                "notes": notes,
                "is_active": is_active,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: StubWorkspaceUserService()

    try:
        response = client.patch(
            "/v1/workspace/users/user-1",
            json={"name": "Alice Updated", "email": "alice@sezzions.com", "notes": "VIP", "is_active": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Alice Updated"
    assert response.json()["is_active"] is False


def test_workspace_users_delete_endpoint_returns_204() -> None:
    class StubWorkspaceUserService:
        def delete_user(self, *, supabase_user_id: str, user_id: str):
            assert supabase_user_id == "owner-123"
            assert user_id == "user-1"

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: StubWorkspaceUserService()

    try:
        response = client.delete("/v1/workspace/users/user-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


def test_workspace_users_endpoints_require_bearer_auth() -> None:
    list_response = client.get("/v1/workspace/users")
    create_response = client.post("/v1/workspace/users", json={"name": "Alice"})
    update_response = client.patch("/v1/workspace/users/user-1", json={"name": "Alice"})
    delete_response = client.delete("/v1/workspace/users/user-1")

    assert list_response.status_code == 401
    assert create_response.status_code == 401
    assert update_response.status_code == 401
    assert delete_response.status_code == 401


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


def test_workspace_users_update_endpoint_returns_409_for_missing_workspace_user() -> None:
    class MissingWorkspaceUserService:
        def update_user(
            self,
            *,
            supabase_user_id: str,
            user_id: str,
            name: str,
            email: str | None,
            notes: str | None,
            is_active: bool,
        ):
            raise LookupError("Hosted user was not found in the authenticated workspace.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: MissingWorkspaceUserService()

    try:
        response = client.patch("/v1/workspace/users/user-1", json={"name": "Alice"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Hosted user was not found in the authenticated workspace."


def test_workspace_users_delete_endpoint_returns_409_for_missing_workspace_user() -> None:
    class MissingWorkspaceUserService:
        def delete_user(self, *, supabase_user_id: str, user_id: str):
            raise LookupError("Hosted user was not found in the authenticated workspace.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_user_service] = lambda: MissingWorkspaceUserService()

    try:
        response = client.delete("/v1/workspace/users/user-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Hosted user was not found in the authenticated workspace."