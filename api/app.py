"""FastAPI entrypoint for the hosted Sezzions foundation."""

from __future__ import annotations

from fastapi import FastAPI

from api.config import load_hosted_backend_config


app = FastAPI(title="Sezzions Hosted API", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/foundation")
def foundation() -> dict[str, object]:
    config = load_hosted_backend_config(required=False)
    return {
        "auth_provider": "supabase-google",
        "configured": config is not None,
        "supabase_url": config.supabase_url if config else None,
        "google_auth_enabled": config.google_auth_enabled if config else False,
        "project_ref": config.project_ref if config else None,
    }
