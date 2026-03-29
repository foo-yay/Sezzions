from fastapi.testclient import TestClient

from api.auth import AuthenticatedSession, get_authenticated_session
from api.app import app, get_hosted_account_bootstrap_service


client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_foundation_reports_unconfigured_without_env() -> None:
    response = client.get("/v1/foundation")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["auth_provider"] == "supabase-google"


def test_session_endpoint_requires_bearer_auth() -> None:
    response = client.get("/v1/session")

    assert response.status_code == 401


def test_session_endpoint_returns_authenticated_session() -> None:
    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="user-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )

    try:
        response = client.get("/v1/session")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user_id": "user-123",
        "email": "owner@sezzions.com",
        "audience": "authenticated",
        "role": "authenticated",
    }


def test_session_endpoint_allows_cors_preflight_from_dev_site() -> None:
    response = client.options(
        "/v1/session",
        headers={
            "Origin": "https://dev.sezzions.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://dev.sezzions.com"


def test_account_bootstrap_endpoint_returns_hosted_summary() -> None:
    class StubBootstrapService:
        def bootstrap_account_workspace(self, *, supabase_user_id: str, owner_email: str | None):
            return type(
                "Summary",
                (),
                {
                    "as_dict": lambda self: {
                        "created_account": True,
                        "created_workspace": True,
                        "account": {
                            "id": "account-123",
                            "supabase_user_id": supabase_user_id,
                            "owner_email": owner_email,
                            "auth_provider": "google",
                        },
                        "workspace": {
                            "id": "workspace-123",
                            "account_id": "account-123",
                            "name": "owner@sezzions.com Workspace",
                            "source_db_path": None,
                        },
                    }
                },
            )()

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="user-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_account_bootstrap_service] = lambda: StubBootstrapService()

    try:
        response = client.post("/v1/account/bootstrap")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "created_account": True,
        "created_workspace": True,
        "account": {
            "id": "account-123",
            "supabase_user_id": "user-123",
            "owner_email": "owner@sezzions.com",
            "auth_provider": "google",
        },
        "workspace": {
            "id": "workspace-123",
            "account_id": "account-123",
            "name": "owner@sezzions.com Workspace",
            "source_db_path": None,
        },
    }


def test_account_bootstrap_endpoint_requires_bearer_auth() -> None:
    response = client.post("/v1/account/bootstrap")

    assert response.status_code == 401
