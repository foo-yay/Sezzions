from fastapi.testclient import TestClient

from api.app import app, get_hosted_uploaded_sqlite_inspection_service
from api.auth import AuthenticatedSession, get_authenticated_session


client = TestClient(app)


def test_workspace_import_upload_endpoint_returns_inventory_summary() -> None:
    class StubUploadService:
        def inspect_upload(self, *, filename: str, fileobj):
            return {
                "status": "ready",
                "detail": "Uploaded SQLite inventory is ready.",
                "uploaded_filename": filename,
                "inventory": {
                    "db_path": "/tmp/upload.db",
                    "db_size_bytes": 1024,
                    "schema_version_count": 1,
                    "tables": [{"table_name": "users", "row_count": 1}],
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
    app.dependency_overrides[get_hosted_uploaded_sqlite_inspection_service] = lambda: StubUploadService()

    try:
        response = client.post(
            "/v1/workspace/import-upload-plan",
            files={"sqlite_db": ("sezzions.db", b"sqlite-bytes", "application/octet-stream")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["uploaded_filename"] == "sezzions.db"


def test_workspace_import_upload_endpoint_requires_bearer_auth() -> None:
    response = client.post(
        "/v1/workspace/import-upload-plan",
        files={"sqlite_db": ("sezzions.db", b"sqlite-bytes", "application/octet-stream")},
    )

    assert response.status_code == 401


def test_workspace_import_upload_endpoint_returns_400_for_invalid_upload() -> None:
    class RejectingUploadService:
        def inspect_upload(self, *, filename: str, fileobj):
            raise ValueError("Uploaded file is not a readable SQLite database.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="user-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_uploaded_sqlite_inspection_service] = lambda: RejectingUploadService()

    try:
        response = client.post(
            "/v1/workspace/import-upload-plan",
            files={"sqlite_db": ("bad.db", b"bad-bytes", "application/octet-stream")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is not a readable SQLite database."