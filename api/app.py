"""FastAPI entrypoint for the hosted Sezzions foundation."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from api.auth import AuthenticatedSession, get_authenticated_session
from api.config import HostedConfigurationError, load_hosted_backend_config
from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import get_hosted_session_factory


app = FastAPI(title="Sezzions Hosted API", version="0.1.0")

cors_config = load_hosted_backend_config(required=False, require_db_password=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_config.cors_allowed_origins) if cors_config else [
        "https://dev.sezzions.com",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def get_hosted_account_bootstrap_service() -> HostedAccountBootstrapService:
    try:
        config = load_hosted_backend_config(require_db_password=True)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session_factory = get_hosted_session_factory(config.sqlalchemy_url)
    return HostedAccountBootstrapService(session_factory)


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
