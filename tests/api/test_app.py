from fastapi.testclient import TestClient

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
