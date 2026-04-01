"""FastAPI entrypoint for the hosted Sezzions foundation."""

from __future__ import annotations

from fastapi import Body, Depends, FastAPI, File, HTTPException, Path, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.auth import AuthenticatedSession, get_authenticated_session
from api.config import HostedConfigurationError, load_hosted_backend_config
from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import get_hosted_session_factory
from services.hosted.uploaded_sqlite_inspection_service import (
    HostedUploadedSQLiteInspectionService,
)
from services.hosted.workspace_card_service import HostedWorkspaceCardService
from services.hosted.workspace_site_service import HostedWorkspaceSiteService
from services.hosted.workspace_user_service import HostedWorkspaceUserService
from services.hosted.workspace_import_planning_service import (
    HostedWorkspaceImportPlanningService,
)


app = FastAPI(title="Sezzions Hosted API", version="0.1.0")


class HostedWorkspaceUserCreateRequest(BaseModel):
    name: str
    email: str | None = None
    notes: str | None = None


class HostedWorkspaceUserUpdateRequest(BaseModel):
    name: str
    email: str | None = None
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceUserBatchDeleteRequest(BaseModel):
    user_ids: list[str]


class HostedWorkspaceSiteCreateRequest(BaseModel):
    name: str
    url: str | None = None
    sc_rate: float = 1.0
    playthrough_requirement: float = 1.0
    notes: str | None = None


class HostedWorkspaceSiteUpdateRequest(BaseModel):
    name: str
    url: str | None = None
    sc_rate: float = 1.0
    playthrough_requirement: float = 1.0
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceSiteBatchDeleteRequest(BaseModel):
    site_ids: list[str]


class HostedWorkspaceCardCreateRequest(BaseModel):
    name: str
    user_id: str
    last_four: str | None = None
    cashback_rate: float = 0.0
    notes: str | None = None


class HostedWorkspaceCardUpdateRequest(BaseModel):
    name: str
    user_id: str
    last_four: str | None = None
    cashback_rate: float = 0.0
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceCardBatchDeleteRequest(BaseModel):
    card_ids: list[str]


cors_config = load_hosted_backend_config(required=False, require_db_password=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_config.cors_allowed_origins) if cors_config else [
        "https://dev.sezzions.com",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def get_hosted_account_bootstrap_service() -> HostedAccountBootstrapService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedAccountBootstrapService(session_factory)


def get_hosted_workspace_import_planning_service() -> HostedWorkspaceImportPlanningService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceImportPlanningService(session_factory)


def get_hosted_workspace_user_service() -> HostedWorkspaceUserService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceUserService(session_factory)


def get_hosted_workspace_site_service() -> HostedWorkspaceSiteService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceSiteService(session_factory)


def get_hosted_workspace_card_service() -> HostedWorkspaceCardService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceCardService(session_factory)


def get_hosted_uploaded_sqlite_inspection_service() -> HostedUploadedSQLiteInspectionService:
    return HostedUploadedSQLiteInspectionService()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/foundation")
def foundation() -> dict[str, object]:
    config = load_hosted_backend_config(required=False, require_db_password=False)
    return {
        "auth_provider": "supabase-google",
        "configured": config is not None,
        "supabase_url": config.supabase_url if config else None,
        "google_auth_enabled": config.google_auth_enabled if config else False,
        "project_ref": config.project_ref if config else None,
    }


@app.get("/v1/session")
def session_summary(
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> dict[str, object]:
    return {
        "authenticated": True,
        "user_id": session.user_id,
        "email": session.email,
        "audience": session.audience,
        "role": session.role,
    }


@app.post("/v1/account/bootstrap")
def account_bootstrap(
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedAccountBootstrapService = Depends(get_hosted_account_bootstrap_service),
) -> dict[str, object]:
    summary = service.bootstrap_account_workspace(
        supabase_user_id=session.user_id,
        owner_email=session.email,
    )
    return summary.as_dict() if hasattr(summary, "as_dict") else summary


@app.get("/v1/workspace/users")
def workspace_users_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceUserService = Depends(get_hosted_workspace_user_service),
) -> dict[str, object]:
    try:
        page = service.list_users_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "users": [user.as_dict() if hasattr(user, "as_dict") else user for user in page["users"]],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/users")
def workspace_users_create(
    payload: HostedWorkspaceUserCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceUserService = Depends(get_hosted_workspace_user_service),
) -> dict[str, object]:
    try:
        user = service.create_user(
            supabase_user_id=session.user_id,
            name=payload.name,
            email=payload.email,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return user.as_dict() if hasattr(user, "as_dict") else user


@app.patch("/v1/workspace/users/{user_id}")
def workspace_users_update(
    user_id: str = Path(...),
    payload: HostedWorkspaceUserUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceUserService = Depends(get_hosted_workspace_user_service),
) -> dict[str, object]:
    try:
        user = service.update_user(
            supabase_user_id=session.user_id,
            user_id=user_id,
            name=payload.name,
            email=payload.email,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return user.as_dict() if hasattr(user, "as_dict") else user


@app.delete("/v1/workspace/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def workspace_users_delete(
    user_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceUserService = Depends(get_hosted_workspace_user_service),
) -> Response:
    try:
        service.delete_user(
            supabase_user_id=session.user_id,
            user_id=user_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/users/batch-delete")
def workspace_users_batch_delete(
    payload: HostedWorkspaceUserBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceUserService = Depends(get_hosted_workspace_user_service),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_users(
            supabase_user_id=session.user_id,
            user_ids=payload.user_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


# ── Sites ──────────────────────────────────────────────────────


@app.get("/v1/workspace/sites")
def workspace_sites_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceSiteService = Depends(get_hosted_workspace_site_service),
) -> dict[str, object]:
    try:
        page = service.list_sites_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "sites": [site.as_dict() if hasattr(site, "as_dict") else site for site in page["sites"]],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/sites")
def workspace_sites_create(
    payload: HostedWorkspaceSiteCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceSiteService = Depends(get_hosted_workspace_site_service),
) -> dict[str, object]:
    try:
        site = service.create_site(
            supabase_user_id=session.user_id,
            name=payload.name,
            url=payload.url,
            sc_rate=payload.sc_rate,
            playthrough_requirement=payload.playthrough_requirement,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return site.as_dict() if hasattr(site, "as_dict") else site


@app.patch("/v1/workspace/sites/{site_id}")
def workspace_sites_update(
    site_id: str = Path(...),
    payload: HostedWorkspaceSiteUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceSiteService = Depends(get_hosted_workspace_site_service),
) -> dict[str, object]:
    try:
        site = service.update_site(
            supabase_user_id=session.user_id,
            site_id=site_id,
            name=payload.name,
            url=payload.url,
            sc_rate=payload.sc_rate,
            playthrough_requirement=payload.playthrough_requirement,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return site.as_dict() if hasattr(site, "as_dict") else site


@app.delete("/v1/workspace/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
def workspace_sites_delete(
    site_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceSiteService = Depends(get_hosted_workspace_site_service),
) -> Response:
    try:
        service.delete_site(
            supabase_user_id=session.user_id,
            site_id=site_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/sites/batch-delete")
def workspace_sites_batch_delete(
    payload: HostedWorkspaceSiteBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceSiteService = Depends(get_hosted_workspace_site_service),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_sites(
            supabase_user_id=session.user_id,
            site_ids=payload.site_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


# ── Cards ────────────────────────────────────────────────────────────────

@app.get("/v1/workspace/cards")
def workspace_cards_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceCardService = Depends(get_hosted_workspace_card_service),
) -> dict[str, object]:
    try:
        page = service.list_cards_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "cards": [card.as_dict() if hasattr(card, "as_dict") else card for card in page["cards"]],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/cards")
def workspace_cards_create(
    payload: HostedWorkspaceCardCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceCardService = Depends(get_hosted_workspace_card_service),
) -> dict[str, object]:
    try:
        card = service.create_card(
            supabase_user_id=session.user_id,
            name=payload.name,
            user_id=payload.user_id,
            last_four=payload.last_four,
            cashback_rate=payload.cashback_rate,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return card.as_dict() if hasattr(card, "as_dict") else card


@app.patch("/v1/workspace/cards/{card_id}")
def workspace_cards_update(
    card_id: str = Path(...),
    payload: HostedWorkspaceCardUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceCardService = Depends(get_hosted_workspace_card_service),
) -> dict[str, object]:
    try:
        card = service.update_card(
            supabase_user_id=session.user_id,
            card_id=card_id,
            name=payload.name,
            user_id=payload.user_id,
            last_four=payload.last_four,
            cashback_rate=payload.cashback_rate,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return card.as_dict() if hasattr(card, "as_dict") else card


@app.delete("/v1/workspace/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def workspace_cards_delete(
    card_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceCardService = Depends(get_hosted_workspace_card_service),
) -> Response:
    try:
        service.delete_card(
            supabase_user_id=session.user_id,
            card_id=card_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/cards/batch-delete")
def workspace_cards_batch_delete(
    payload: HostedWorkspaceCardBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceCardService = Depends(get_hosted_workspace_card_service),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_cards(
            supabase_user_id=session.user_id,
            card_ids=payload.card_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


@app.get("/v1/workspace/import-plan")
def workspace_import_plan(
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceImportPlanningService = Depends(get_hosted_workspace_import_planning_service),
) -> dict[str, object]:
    try:
        summary = service.plan_import(supabase_user_id=session.user_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return summary.as_dict() if hasattr(summary, "as_dict") else summary


@app.post("/v1/workspace/import-upload-plan")
async def workspace_import_upload_plan(
    session: AuthenticatedSession = Depends(get_authenticated_session),
    sqlite_db: UploadFile = File(...),
    service: HostedUploadedSQLiteInspectionService = Depends(get_hosted_uploaded_sqlite_inspection_service),
) -> dict[str, object]:
    del session
    try:
        summary = service.inspect_upload(
            filename=sqlite_db.filename or "uploaded.sqlite",
            fileobj=sqlite_db.file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await sqlite_db.close()

    return summary.as_dict() if hasattr(summary, "as_dict") else summary
