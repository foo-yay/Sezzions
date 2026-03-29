"""Configuration helpers for the hosted Sezzions foundation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping, Optional
from urllib.parse import quote_plus, urlparse


class HostedConfigurationError(ValueError):
    """Raised when hosted environment configuration is incomplete or invalid."""


@dataclass(frozen=True)
class HostedBackendConfig:
    """Resolved hosted backend configuration derived from Supabase inputs."""

    supabase_url: str
    supabase_db_password: Optional[str] = None
    sqlalchemy_url_override: Optional[str] = None
    supabase_publishable_key: Optional[str] = None
    db_user: str = "postgres"
    db_name: str = "postgres"
    db_port: int = 5432
    db_sslmode: str = "require"
    jwt_audience: str = "authenticated"
    google_auth_enabled: bool = False
    cors_allowed_origins: tuple[str, ...] = (
        "https://dev.sezzions.com",
        "http://localhost:5173",
    )

    def __post_init__(self) -> None:
        parsed = urlparse(self.supabase_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise HostedConfigurationError(
                "SUPABASE_URL must be a valid https URL."
            )
    @property
    def project_ref(self) -> str:
        hostname = urlparse(self.supabase_url).hostname or ""
        project_ref = hostname.split(".", 1)[0]
        if not project_ref:
            raise HostedConfigurationError(
                "Could not derive Supabase project ref from SUPABASE_URL."
            )
        return project_ref

    @property
    def db_host(self) -> str:
        return f"db.{self.project_ref}.supabase.co"

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"

    @property
    def sqlalchemy_url(self) -> str:
        if self.sqlalchemy_url_override:
            return self.sqlalchemy_url_override
        if not self.supabase_db_password:
            raise HostedConfigurationError(
                "SUPABASE_DB_PASSWORD is required for hosted database access."
            )
        encoded_password = quote_plus(self.supabase_db_password)
        return (
            "postgresql+psycopg2://"
            f"{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?sslmode={quote_plus(self.db_sslmode)}"
        )


def load_hosted_backend_config(
    env: Optional[Mapping[str, str]] = None,
    *,
    required: bool = True,
    require_db_password: bool = True,
) -> Optional[HostedBackendConfig]:
    """Build hosted configuration from environment variables.

    Required environment variables:
    - SUPABASE_URL
    - SUPABASE_DB_PASSWORD or SUPABASE_SQLALCHEMY_URL / DATABASE_URL

    Optional:
    - SUPABASE_SQLALCHEMY_URL
    - DATABASE_URL
    - SUPABASE_DB_USER
    - SUPABASE_DB_NAME
    - SUPABASE_DB_PORT
    - SUPABASE_DB_SSLMODE
    - SUPABASE_PUBLISHABLE_KEY
    - SUPABASE_ANON_KEY
    - SUPABASE_JWT_AUDIENCE
    - SUPABASE_GOOGLE_AUTH_ENABLED
    """

    env_map = env or os.environ
    supabase_url = env_map.get("SUPABASE_URL", "").strip()
    db_password = env_map.get("SUPABASE_DB_PASSWORD", "").strip()
    sqlalchemy_url_override = (
        env_map.get("SUPABASE_SQLALCHEMY_URL", "").strip()
        or env_map.get("DATABASE_URL", "").strip()
        or None
    )

    if not supabase_url and not db_password and not sqlalchemy_url_override and not required:
        return None

    if not supabase_url or (require_db_password and not db_password and not sqlalchemy_url_override):
        if required:
            raise HostedConfigurationError(
                "SUPABASE_URL and either SUPABASE_DB_PASSWORD or SUPABASE_SQLALCHEMY_URL / DATABASE_URL must be set."
            )
        return None

    db_user = env_map.get("SUPABASE_DB_USER", "postgres").strip() or "postgres"
    db_name = env_map.get("SUPABASE_DB_NAME", "postgres").strip() or "postgres"
    db_port_raw = env_map.get("SUPABASE_DB_PORT", "5432").strip() or "5432"
    db_sslmode = env_map.get("SUPABASE_DB_SSLMODE", "require").strip() or "require"
    supabase_publishable_key = (
        env_map.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or env_map.get("SUPABASE_ANON_KEY", "").strip()
        or env_map.get("VITE_SUPABASE_ANON_KEY", "").strip()
        or None
    )
    jwt_audience = env_map.get("SUPABASE_JWT_AUDIENCE", "authenticated").strip() or "authenticated"
    google_auth_enabled = env_map.get("SUPABASE_GOOGLE_AUTH_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    cors_allowed_origins = tuple(
        origin.strip()
        for origin in env_map.get(
            "CORS_ALLOWED_ORIGINS",
            "https://dev.sezzions.com,http://localhost:5173",
        ).split(",")
        if origin.strip()
    )

    try:
        db_port = int(db_port_raw)
    except ValueError as exc:
        raise HostedConfigurationError("SUPABASE_DB_PORT must be an integer.") from exc

    return HostedBackendConfig(
        supabase_url=supabase_url,
        supabase_db_password=db_password or None,
        sqlalchemy_url_override=sqlalchemy_url_override,
        supabase_publishable_key=supabase_publishable_key,
        db_user=db_user,
        db_name=db_name,
        db_port=db_port,
        db_sslmode=db_sslmode,
        jwt_audience=jwt_audience,
        google_auth_enabled=google_auth_enabled,
        cors_allowed_origins=cors_allowed_origins,
    )
