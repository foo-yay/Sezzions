"""Supabase access-token verification for protected API endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import HostedBackendConfig, HostedConfigurationError, load_hosted_backend_config


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedSession:
    user_id: str
    email: str | None
    audience: str | list[str] | None
    role: str | None


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url)


def decode_supabase_access_token(token: str, config: HostedBackendConfig) -> dict[str, Any]:
    signing_key = _jwks_client(config.supabase_jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=config.jwt_audience,
        issuer=config.supabase_issuer,
    )


def fetch_supabase_user(token: str, config: HostedBackendConfig) -> dict[str, Any]:
    response = httpx.get(
        f"{config.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_authenticated_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedSession:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Bearer token is required.")

    try:
        config = load_hosted_backend_config(require_db_password=False)
    except HostedConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    try:
        claims = decode_supabase_access_token(credentials.credentials, config)
    except jwt.InvalidTokenError:
        try:
            claims = fetch_supabase_user(credentials.credentials, config)
        except Exception as exc:
            raise _unauthorized("Invalid bearer token.") from exc

    user_id = str(claims.get("sub") or claims.get("id") or "")
    if not user_id:
        raise _unauthorized("Bearer token is missing subject.")

    return AuthenticatedSession(
        user_id=user_id,
        email=claims.get("email"),
        audience=claims.get("aud"),
        role=claims.get("role"),
    )
