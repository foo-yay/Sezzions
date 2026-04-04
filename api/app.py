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
from services.hosted.workspace_redemption_method_service import (
    HostedWorkspaceRedemptionMethodService,
)
from services.hosted.workspace_redemption_method_type_service import (
    HostedWorkspaceRedemptionMethodTypeService,
)
from services.hosted.workspace_site_service import HostedWorkspaceSiteService
from services.hosted.workspace_user_service import HostedWorkspaceUserService
from services.hosted.workspace_game_type_service import (
    HostedWorkspaceGameTypeService,
)
from services.hosted.workspace_game_service import (
    HostedWorkspaceGameService,
)
from services.hosted.workspace_import_planning_service import (
    HostedWorkspaceImportPlanningService,
)
from services.hosted.workspace_purchase_service import (
    HostedWorkspacePurchaseService,
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


class HostedWorkspaceRedemptionMethodTypeCreateRequest(BaseModel):
    name: str
    notes: str | None = None


class HostedWorkspaceRedemptionMethodTypeUpdateRequest(BaseModel):
    name: str
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceRedemptionMethodTypeBatchDeleteRequest(BaseModel):
    redemption_method_type_ids: list[str]


class HostedWorkspaceRedemptionMethodCreateRequest(BaseModel):
    name: str
    method_type_id: str
    user_id: str
    notes: str | None = None


class HostedWorkspaceRedemptionMethodUpdateRequest(BaseModel):
    name: str
    method_type_id: str
    user_id: str
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceRedemptionMethodBatchDeleteRequest(BaseModel):
    redemption_method_ids: list[str]


class HostedWorkspaceGameTypeCreateRequest(BaseModel):
    name: str
    notes: str | None = None


class HostedWorkspaceGameTypeUpdateRequest(BaseModel):
    name: str
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceGameTypeBatchDeleteRequest(BaseModel):
    game_type_ids: list[str]


class HostedWorkspaceGameCreateRequest(BaseModel):
    name: str
    game_type_id: str
    rtp: float | None = None
    notes: str | None = None


class HostedWorkspaceGameUpdateRequest(BaseModel):
    name: str
    game_type_id: str
    rtp: float | None = None
    notes: str | None = None
    is_active: bool = True


class HostedWorkspaceGameBatchDeleteRequest(BaseModel):
    game_ids: list[str]


class HostedWorkspacePurchaseCreateRequest(BaseModel):
    user_id: str
    site_id: str
    amount: str
    purchase_date: str
    purchase_time: str | None = None
    sc_received: str | None = None
    starting_sc_balance: str = "0.00"
    cashback_earned: str = "0.00"
    cashback_is_manual: bool = False
    card_id: str | None = None
    notes: str | None = None


class HostedWorkspacePurchaseUpdateRequest(BaseModel):
    user_id: str
    site_id: str
    amount: str
    purchase_date: str
    purchase_time: str | None = None
    sc_received: str | None = None
    starting_sc_balance: str = "0.00"
    cashback_earned: str = "0.00"
    cashback_is_manual: bool = False
    card_id: str | None = None
    status: str = "active"
    notes: str | None = None


class HostedWorkspacePurchaseBatchDeleteRequest(BaseModel):
    purchase_ids: list[str]


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


def get_hosted_workspace_redemption_method_type_service() -> HostedWorkspaceRedemptionMethodTypeService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceRedemptionMethodTypeService(session_factory)


def get_hosted_workspace_redemption_method_service() -> HostedWorkspaceRedemptionMethodService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceRedemptionMethodService(session_factory)


def get_hosted_workspace_game_type_service() -> HostedWorkspaceGameTypeService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceGameTypeService(session_factory)


def get_hosted_workspace_game_service() -> HostedWorkspaceGameService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspaceGameService(session_factory)


def get_hosted_workspace_purchase_service() -> HostedWorkspacePurchaseService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedWorkspacePurchaseService(session_factory)


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


# ── Redemption Method Types ──────────────────────────────────────────────


@app.get("/v1/workspace/redemption-method-types")
def workspace_redemption_method_types_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodTypeService = Depends(
        get_hosted_workspace_redemption_method_type_service
    ),
) -> dict[str, object]:
    try:
        page = service.list_method_types_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "redemption_method_types": [
            mt.as_dict() if hasattr(mt, "as_dict") else mt
            for mt in page["redemption_method_types"]
        ],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/redemption-method-types")
def workspace_redemption_method_types_create(
    payload: HostedWorkspaceRedemptionMethodTypeCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodTypeService = Depends(
        get_hosted_workspace_redemption_method_type_service
    ),
) -> dict[str, object]:
    try:
        method_type = service.create_method_type(
            supabase_user_id=session.user_id,
            name=payload.name,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return method_type.as_dict() if hasattr(method_type, "as_dict") else method_type


@app.patch("/v1/workspace/redemption-method-types/{method_type_id}")
def workspace_redemption_method_types_update(
    method_type_id: str = Path(...),
    payload: HostedWorkspaceRedemptionMethodTypeUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodTypeService = Depends(
        get_hosted_workspace_redemption_method_type_service
    ),
) -> dict[str, object]:
    try:
        method_type = service.update_method_type(
            supabase_user_id=session.user_id,
            method_type_id=method_type_id,
            name=payload.name,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return method_type.as_dict() if hasattr(method_type, "as_dict") else method_type


@app.delete(
    "/v1/workspace/redemption-method-types/{method_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def workspace_redemption_method_types_delete(
    method_type_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodTypeService = Depends(
        get_hosted_workspace_redemption_method_type_service
    ),
) -> Response:
    try:
        service.delete_method_type(
            supabase_user_id=session.user_id,
            method_type_id=method_type_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/redemption-method-types/batch-delete")
def workspace_redemption_method_types_batch_delete(
    payload: HostedWorkspaceRedemptionMethodTypeBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodTypeService = Depends(
        get_hosted_workspace_redemption_method_type_service
    ),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_method_types(
            supabase_user_id=session.user_id,
            method_type_ids=payload.redemption_method_type_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


# ── Redemption Methods ───────────────────────────────────────────────────


@app.get("/v1/workspace/redemption-methods")
def workspace_redemption_methods_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodService = Depends(
        get_hosted_workspace_redemption_method_service
    ),
) -> dict[str, object]:
    try:
        page = service.list_methods_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "redemption_methods": [
            m.as_dict() if hasattr(m, "as_dict") else m
            for m in page["redemption_methods"]
        ],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/redemption-methods")
def workspace_redemption_methods_create(
    payload: HostedWorkspaceRedemptionMethodCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodService = Depends(
        get_hosted_workspace_redemption_method_service
    ),
) -> dict[str, object]:
    try:
        method = service.create_method(
            supabase_user_id=session.user_id,
            name=payload.name,
            method_type_id=payload.method_type_id,
            user_id=payload.user_id,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return method.as_dict() if hasattr(method, "as_dict") else method


@app.patch("/v1/workspace/redemption-methods/{method_id}")
def workspace_redemption_methods_update(
    method_id: str = Path(...),
    payload: HostedWorkspaceRedemptionMethodUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodService = Depends(
        get_hosted_workspace_redemption_method_service
    ),
) -> dict[str, object]:
    try:
        method = service.update_method(
            supabase_user_id=session.user_id,
            method_id=method_id,
            name=payload.name,
            method_type_id=payload.method_type_id,
            user_id=payload.user_id,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return method.as_dict() if hasattr(method, "as_dict") else method


@app.delete(
    "/v1/workspace/redemption-methods/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def workspace_redemption_methods_delete(
    method_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodService = Depends(
        get_hosted_workspace_redemption_method_service
    ),
) -> Response:
    try:
        service.delete_method(
            supabase_user_id=session.user_id,
            method_id=method_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/redemption-methods/batch-delete")
def workspace_redemption_methods_batch_delete(
    payload: HostedWorkspaceRedemptionMethodBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceRedemptionMethodService = Depends(
        get_hosted_workspace_redemption_method_service
    ),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_methods(
            supabase_user_id=session.user_id,
            method_ids=payload.redemption_method_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


# ── Game Types ───────────────────────────────────────────────────────────


@app.get("/v1/workspace/game-types")
def workspace_game_types_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameTypeService = Depends(
        get_hosted_workspace_game_type_service
    ),
) -> dict[str, object]:
    try:
        page = service.list_game_types_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "game_types": [
            gt.as_dict() if hasattr(gt, "as_dict") else gt
            for gt in page["game_types"]
        ],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/game-types")
def workspace_game_types_create(
    payload: HostedWorkspaceGameTypeCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameTypeService = Depends(
        get_hosted_workspace_game_type_service
    ),
) -> dict[str, object]:
    try:
        game_type = service.create_game_type(
            supabase_user_id=session.user_id,
            name=payload.name,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return game_type.as_dict() if hasattr(game_type, "as_dict") else game_type


@app.patch("/v1/workspace/game-types/{game_type_id}")
def workspace_game_types_update(
    game_type_id: str = Path(...),
    payload: HostedWorkspaceGameTypeUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameTypeService = Depends(
        get_hosted_workspace_game_type_service
    ),
) -> dict[str, object]:
    try:
        game_type = service.update_game_type(
            supabase_user_id=session.user_id,
            game_type_id=game_type_id,
            name=payload.name,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return game_type.as_dict() if hasattr(game_type, "as_dict") else game_type


@app.delete(
    "/v1/workspace/game-types/{game_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def workspace_game_types_delete(
    game_type_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameTypeService = Depends(
        get_hosted_workspace_game_type_service
    ),
) -> Response:
    try:
        service.delete_game_type(
            supabase_user_id=session.user_id,
            game_type_id=game_type_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/game-types/batch-delete")
def workspace_game_types_batch_delete(
    payload: HostedWorkspaceGameTypeBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameTypeService = Depends(
        get_hosted_workspace_game_type_service
    ),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_game_types(
            supabase_user_id=session.user_id,
            game_type_ids=payload.game_type_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


# ── Games ────────────────────────────────────────────────────────────────


@app.get("/v1/workspace/games")
def workspace_games_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameService = Depends(
        get_hosted_workspace_game_service
    ),
) -> dict[str, object]:
    try:
        page = service.list_games_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "games": [
            g.as_dict() if hasattr(g, "as_dict") else g
            for g in page["games"]
        ],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/games")
def workspace_games_create(
    payload: HostedWorkspaceGameCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameService = Depends(
        get_hosted_workspace_game_service
    ),
) -> dict[str, object]:
    try:
        game = service.create_game(
            supabase_user_id=session.user_id,
            name=payload.name,
            game_type_id=payload.game_type_id,
            rtp=payload.rtp,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return game.as_dict() if hasattr(game, "as_dict") else game


@app.patch("/v1/workspace/games/{game_id}")
def workspace_games_update(
    game_id: str = Path(...),
    payload: HostedWorkspaceGameUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameService = Depends(
        get_hosted_workspace_game_service
    ),
) -> dict[str, object]:
    try:
        game = service.update_game(
            supabase_user_id=session.user_id,
            game_id=game_id,
            name=payload.name,
            game_type_id=payload.game_type_id,
            rtp=payload.rtp,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return game.as_dict() if hasattr(game, "as_dict") else game


@app.delete(
    "/v1/workspace/games/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def workspace_games_delete(
    game_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameService = Depends(
        get_hosted_workspace_game_service
    ),
) -> Response:
    try:
        service.delete_game(
            supabase_user_id=session.user_id,
            game_id=game_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/games/batch-delete")
def workspace_games_batch_delete(
    payload: HostedWorkspaceGameBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspaceGameService = Depends(
        get_hosted_workspace_game_service
    ),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_games(
            supabase_user_id=session.user_id,
            game_ids=payload.game_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"deleted_count": deleted_count}


# ── Purchases ────────────────────────────────────────────────────────────────


@app.get("/v1/workspace/purchases")
def workspace_purchases_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspacePurchaseService = Depends(
        get_hosted_workspace_purchase_service
    ),
) -> dict[str, object]:
    try:
        page = service.list_purchases_page(
            supabase_user_id=session.user_id,
            limit=limit,
            offset=offset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "purchases": [
            p.as_dict() if hasattr(p, "as_dict") else p
            for p in page["purchases"]
        ],
        "offset": page["offset"],
        "limit": page["limit"],
        "next_offset": page["next_offset"],
        "total_count": page["total_count"],
        "has_more": page["has_more"],
    }


@app.post("/v1/workspace/purchases")
def workspace_purchases_create(
    payload: HostedWorkspacePurchaseCreateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspacePurchaseService = Depends(
        get_hosted_workspace_purchase_service
    ),
) -> dict[str, object]:
    try:
        purchase = service.create_purchase(
            supabase_user_id=session.user_id,
            user_id=payload.user_id,
            site_id=payload.site_id,
            amount=payload.amount,
            purchase_date=payload.purchase_date,
            purchase_time=payload.purchase_time,
            sc_received=payload.sc_received,
            starting_sc_balance=payload.starting_sc_balance,
            cashback_earned=payload.cashback_earned,
            cashback_is_manual=payload.cashback_is_manual,
            card_id=payload.card_id,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return purchase.as_dict() if hasattr(purchase, "as_dict") else purchase


@app.patch("/v1/workspace/purchases/{purchase_id}")
def workspace_purchases_update(
    purchase_id: str = Path(...),
    payload: HostedWorkspacePurchaseUpdateRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspacePurchaseService = Depends(
        get_hosted_workspace_purchase_service
    ),
) -> dict[str, object]:
    try:
        purchase = service.update_purchase(
            supabase_user_id=session.user_id,
            purchase_id=purchase_id,
            user_id=payload.user_id,
            site_id=payload.site_id,
            amount=payload.amount,
            purchase_date=payload.purchase_date,
            purchase_time=payload.purchase_time,
            sc_received=payload.sc_received,
            starting_sc_balance=payload.starting_sc_balance,
            cashback_earned=payload.cashback_earned,
            cashback_is_manual=payload.cashback_is_manual,
            card_id=payload.card_id,
            status=payload.status,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return purchase.as_dict() if hasattr(purchase, "as_dict") else purchase


@app.delete(
    "/v1/workspace/purchases/{purchase_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def workspace_purchases_delete(
    purchase_id: str = Path(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspacePurchaseService = Depends(
        get_hosted_workspace_purchase_service
    ),
) -> Response:
    try:
        service.delete_purchase(
            supabase_user_id=session.user_id,
            purchase_id=purchase_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/workspace/purchases/batch-delete")
def workspace_purchases_batch_delete(
    payload: HostedWorkspacePurchaseBatchDeleteRequest = Body(...),
    session: AuthenticatedSession = Depends(get_authenticated_session),
    service: HostedWorkspacePurchaseService = Depends(
        get_hosted_workspace_purchase_service
    ),
) -> dict[str, int]:
    try:
        deleted_count = service.delete_purchases(
            supabase_user_id=session.user_id,
            purchase_ids=payload.purchase_ids,
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
