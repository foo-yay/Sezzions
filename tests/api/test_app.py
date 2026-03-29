from fastapi.testclient import TestClient

from api.auth import AuthenticatedSession, get_authenticated_session
from api.app import app


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
