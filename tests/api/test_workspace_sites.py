from fastapi.testclient import TestClient

from api.app import app, get_hosted_workspace_site_service
from api.auth import AuthenticatedSession, get_authenticated_session


client = TestClient(app)


def test_workspace_sites_list_endpoint_returns_workspace_sites() -> None:
    class StubWorkspaceSiteService:
        def list_sites_page(self, *, supabase_user_id: str, limit: int, offset: int):
            assert supabase_user_id == "owner-123"
            assert limit == 100
            assert offset == 0
            return {
                "sites": [
                    {
                        "id": "site-1",
                        "workspace_id": "workspace-123",
                        "name": "Lucky Slots",
                        "url": "https://luckyslots.com",
                        "sc_rate": 1.0,
                        "playthrough_requirement": 1.0,
                        "is_active": True,
                        "notes": None,
                    }
                ],
                "offset": 0,
                "limit": 100,
                "next_offset": 1,
                "total_count": 1,
                "has_more": False,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.get("/v1/workspace/sites")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["sites"][0]["name"] == "Lucky Slots"
    assert response.json()["total_count"] == 1


def test_workspace_sites_list_endpoint_accepts_limit_and_offset() -> None:
    class StubWorkspaceSiteService:
        def list_sites_page(self, *, supabase_user_id: str, limit: int, offset: int):
            assert supabase_user_id == "owner-123"
            assert limit == 25
            assert offset == 50
            return {
                "sites": [],
                "offset": offset,
                "limit": limit,
                "next_offset": offset,
                "total_count": 90,
                "has_more": True,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.get("/v1/workspace/sites?limit=25&offset=50")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["limit"] == 25
    assert response.json()["offset"] == 50
    assert response.json()["has_more"] is True


def test_workspace_sites_create_endpoint_returns_created_site() -> None:
    class StubWorkspaceSiteService:
        def create_site(
            self,
            *,
            supabase_user_id: str,
            name: str,
            url: str | None,
            sc_rate: float,
            playthrough_requirement: float,
            notes: str | None,
        ):
            assert supabase_user_id == "owner-123"
            return {
                "id": "site-1",
                "workspace_id": "workspace-123",
                "name": name,
                "url": url,
                "sc_rate": sc_rate,
                "playthrough_requirement": playthrough_requirement,
                "is_active": True,
                "notes": notes,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.post(
            "/v1/workspace/sites",
            json={
                "name": "Lucky Slots",
                "url": "https://luckyslots.com",
                "sc_rate": 2.5,
                "playthrough_requirement": 3.0,
                "notes": "Top site",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Lucky Slots"
    assert response.json()["sc_rate"] == 2.5
    assert response.json()["playthrough_requirement"] == 3.0
    assert response.json()["workspace_id"] == "workspace-123"


def test_workspace_sites_create_endpoint_uses_defaults_for_optional_fields() -> None:
    class StubWorkspaceSiteService:
        def create_site(
            self,
            *,
            supabase_user_id: str,
            name: str,
            url: str | None,
            sc_rate: float,
            playthrough_requirement: float,
            notes: str | None,
        ):
            assert sc_rate == 1.0
            assert playthrough_requirement == 1.0
            assert url is None
            assert notes is None
            return {
                "id": "site-1",
                "workspace_id": "workspace-123",
                "name": name,
                "url": url,
                "sc_rate": sc_rate,
                "playthrough_requirement": playthrough_requirement,
                "is_active": True,
                "notes": notes,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.post("/v1/workspace/sites", json={"name": "Minimal Site"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Minimal Site"
    assert response.json()["sc_rate"] == 1.0


def test_workspace_sites_update_endpoint_returns_updated_site() -> None:
    class StubWorkspaceSiteService:
        def update_site(
            self,
            *,
            supabase_user_id: str,
            site_id: str,
            name: str,
            url: str | None,
            sc_rate: float,
            playthrough_requirement: float,
            notes: str | None,
            is_active: bool,
        ):
            assert supabase_user_id == "owner-123"
            assert site_id == "site-1"
            return {
                "id": site_id,
                "workspace_id": "workspace-123",
                "name": name,
                "url": url,
                "sc_rate": sc_rate,
                "playthrough_requirement": playthrough_requirement,
                "is_active": is_active,
                "notes": notes,
            }

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.patch(
            "/v1/workspace/sites/site-1",
            json={
                "name": "Lucky Slots Updated",
                "url": "https://luckyslots.com/new",
                "sc_rate": 3.0,
                "playthrough_requirement": 2.0,
                "notes": "Updated",
                "is_active": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Lucky Slots Updated"
    assert response.json()["is_active"] is False
    assert response.json()["sc_rate"] == 3.0


def test_workspace_sites_delete_endpoint_returns_204() -> None:
    class StubWorkspaceSiteService:
        def delete_site(self, *, supabase_user_id: str, site_id: str):
            assert supabase_user_id == "owner-123"
            assert site_id == "site-1"

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.delete("/v1/workspace/sites/site-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


def test_workspace_sites_batch_delete_endpoint_returns_deleted_count() -> None:
    class StubWorkspaceSiteService:
        def delete_sites(self, *, supabase_user_id: str, site_ids: list[str]):
            assert supabase_user_id == "owner-123"
            assert site_ids == ["site-1", "site-2", "site-3"]
            return 3

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: StubWorkspaceSiteService()

    try:
        response = client.post(
            "/v1/workspace/sites/batch-delete",
            json={"site_ids": ["site-1", "site-2", "site-3"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"deleted_count": 3}


def test_workspace_sites_endpoints_require_bearer_auth() -> None:
    list_response = client.get("/v1/workspace/sites")
    create_response = client.post("/v1/workspace/sites", json={"name": "Test"})
    update_response = client.patch("/v1/workspace/sites/site-1", json={"name": "Test"})
    delete_response = client.delete("/v1/workspace/sites/site-1")
    batch_delete_response = client.post("/v1/workspace/sites/batch-delete", json={"site_ids": ["site-1"]})

    assert list_response.status_code == 401
    assert create_response.status_code == 401
    assert update_response.status_code == 401
    assert delete_response.status_code == 401
    assert batch_delete_response.status_code == 401


def test_workspace_sites_create_endpoint_returns_400_for_invalid_name() -> None:
    class RejectingWorkspaceSiteService:
        def create_site(
            self,
            *,
            supabase_user_id: str,
            name: str,
            url: str | None,
            sc_rate: float,
            playthrough_requirement: float,
            notes: str | None,
        ):
            raise ValueError("Site name is required")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: RejectingWorkspaceSiteService()

    try:
        response = client.post("/v1/workspace/sites", json={"name": "   "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Site name is required"


def test_workspace_sites_update_endpoint_returns_409_for_missing_workspace_site() -> None:
    class MissingWorkspaceSiteService:
        def update_site(
            self,
            *,
            supabase_user_id: str,
            site_id: str,
            name: str,
            url: str | None,
            sc_rate: float,
            playthrough_requirement: float,
            notes: str | None,
            is_active: bool,
        ):
            raise LookupError("Hosted site was not found in the authenticated workspace.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: MissingWorkspaceSiteService()

    try:
        response = client.patch("/v1/workspace/sites/site-1", json={"name": "Test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Hosted site was not found in the authenticated workspace."


def test_workspace_sites_delete_endpoint_returns_409_for_missing_workspace_site() -> None:
    class MissingWorkspaceSiteService:
        def delete_site(self, *, supabase_user_id: str, site_id: str):
            raise LookupError("Hosted site was not found in the authenticated workspace.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: MissingWorkspaceSiteService()

    try:
        response = client.delete("/v1/workspace/sites/site-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Hosted site was not found in the authenticated workspace."


def test_workspace_sites_batch_delete_endpoint_returns_409_for_missing_workspace_site() -> None:
    class MissingWorkspaceSiteService:
        def delete_sites(self, *, supabase_user_id: str, site_ids: list[str]):
            raise LookupError("One or more hosted sites were not found in the authenticated workspace.")

    app.dependency_overrides[get_authenticated_session] = lambda: AuthenticatedSession(
        user_id="owner-123",
        email="owner@sezzions.com",
        audience="authenticated",
        role="authenticated",
    )
    app.dependency_overrides[get_hosted_workspace_site_service] = lambda: MissingWorkspaceSiteService()

    try:
        response = client.post("/v1/workspace/sites/batch-delete", json={"site_ids": ["site-1", "site-2"]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
