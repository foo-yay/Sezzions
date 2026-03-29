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
    supabase_db_password: str
    db_user: str = "postgres"
    db_name: str = "postgres"
    db_port: int = 5432
    jwt_audience: str = "authenticated"
    google_auth_enabled: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.supabase_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise HostedConfigurationError(
                "SUPABASE_URL must be a valid https URL."
            )
        if not self.supabase_db_password:
            raise HostedConfigurationError(
                "SUPABASE_DB_PASSWORD is required for hosted database access."
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
    def sqlalchemy_url(self) -> str:
        encoded_password = quote_plus(self.supabase_db_password)
        return (
            "postgresql+psycopg2://"
            f"{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def load_hosted_backend_config(
    env: Optional[Mapping[str, str]] = None,
    *,
    required: bool = True,
) -> Optional[HostedBackendConfig]:
    """Build hosted configuration from environment variables.

    Required environment variables:
    - SUPABASE_URL
    - SUPABASE_DB_PASSWORD

    Optional:
    - SUPABASE_DB_USER
    - SUPABASE_DB_NAME
    - SUPABASE_DB_PORT
    - SUPABASE_JWT_AUDIENCE
    - SUPABASE_GOOGLE_AUTH_ENABLED
    """

    env_map = env or os.environ
    supabase_url = env_map.get("SUPABASE_URL", "").strip()
    db_password = env_map.get("SUPABASE_DB_PASSWORD", "").strip()

    if not supabase_url and not db_password and not required:
        return None

    if not supabase_url or not db_password:
        if required:
            raise HostedConfigurationError(
                "SUPABASE_URL and SUPABASE_DB_PASSWORD must both be set."
            )
        return None

    db_user = env_map.get("SUPABASE_DB_USER", "postgres").strip() or "postgres"
    db_name = env_map.get("SUPABASE_DB_NAME", "postgres").strip() or "postgres"
    db_port_raw = env_map.get("SUPABASE_DB_PORT", "5432").strip() or "5432"
    jwt_audience = env_map.get("SUPABASE_JWT_AUDIENCE", "authenticated").strip() or "authenticated"
    google_auth_enabled = env_map.get("SUPABASE_GOOGLE_AUTH_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    try:
        db_port = int(db_port_raw)
    except ValueError as exc:
        raise HostedConfigurationError("SUPABASE_DB_PORT must be an integer.") from exc

    return HostedBackendConfig(
        supabase_url=supabase_url,
        supabase_db_password=db_password,
        db_user=db_user,
        db_name=db_name,
        db_port=db_port,
        jwt_audience=jwt_audience,
        google_auth_enabled=google_auth_enabled,
    )
