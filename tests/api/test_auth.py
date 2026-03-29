import jwt
import pytest

from api.auth import fetch_supabase_user, get_authenticated_session
from api.config import HostedBackendConfig


def _request(headers: dict[str, str] | None = None):
    return type("Request", (), {"headers": headers or {}})()


def test_get_authenticated_session_falls_back_to_supabase_user_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.auth.load_hosted_backend_config",
        lambda require_db_password=False: object(),
    )
    monkeypatch.setattr(
        "api.auth.decode_supabase_access_token",
        lambda token, config: (_ for _ in ()).throw(jwt.InvalidTokenError("bad token")),
    )
    monkeypatch.setattr(
        "api.auth.fetch_supabase_user",
        lambda token, config, *, api_key=None: {
            "id": "user-123",
            "email": "owner@sezzions.com",
            "aud": "authenticated",
            "role": "authenticated",
        },
    )

    session = get_authenticated_session(
        credentials=type(
            "Creds",
            (),
            {"scheme": "Bearer", "credentials": "token-123"},
        )(),
        request=_request(),
    )

    assert session.user_id == "user-123"
    assert session.email == "owner@sezzions.com"
    assert session.audience == "authenticated"
    assert session.role == "authenticated"


def test_get_authenticated_session_raises_unauthorized_when_fallback_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.auth.load_hosted_backend_config",
        lambda require_db_password=False: object(),
    )
    monkeypatch.setattr(
        "api.auth.decode_supabase_access_token",
        lambda token, config: (_ for _ in ()).throw(jwt.InvalidTokenError("bad token")),
    )
    monkeypatch.setattr(
        "api.auth.fetch_supabase_user",
        lambda token, config, *, api_key=None: (_ for _ in ()).throw(RuntimeError("no user")),
    )

    with pytest.raises(Exception) as exc_info:
        get_authenticated_session(
            credentials=type(
                "Creds",
                (),
                {"scheme": "Bearer", "credentials": "token-123"},
            )(),
            request=_request(),
        )

    assert getattr(exc_info.value, "status_code", None) == 401


def test_get_authenticated_session_uses_request_apikey_for_fallback(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "api.auth.load_hosted_backend_config",
        lambda require_db_password=False: type(
            "Config",
            (),
            {"supabase_publishable_key": "stale-render-key"},
        )(),
    )
    monkeypatch.setattr(
        "api.auth.decode_supabase_access_token",
        lambda token, config: (_ for _ in ()).throw(jwt.InvalidTokenError("bad token")),
    )

    def fake_fetch(token, config, *, api_key=None):
        captured["api_key"] = api_key
        return {
            "id": "user-123",
            "email": "owner@sezzions.com",
            "aud": "authenticated",
            "role": "authenticated",
        }

    monkeypatch.setattr("api.auth.fetch_supabase_user", fake_fetch)

    session = get_authenticated_session(
        credentials=type(
            "Creds",
            (),
            {"scheme": "Bearer", "credentials": "token-123"},
        )(),
        request=type(
            "Request",
            (),
            {"headers": {"apikey": "publishable-key-123"}},
        )(),
    )

    assert session.user_id == "user-123"
    assert captured["api_key"] == "publishable-key-123"


def test_get_authenticated_session_retries_fallback_keys_in_order(monkeypatch) -> None:
    attempted_keys = []

    monkeypatch.setattr(
        "api.auth.load_hosted_backend_config",
        lambda require_db_password=False: type(
            "Config",
            (),
            {"supabase_publishable_key": "render-config-key"},
        )(),
    )
    monkeypatch.setattr(
        "api.auth.decode_supabase_access_token",
        lambda token, config: (_ for _ in ()).throw(jwt.InvalidTokenError("bad token")),
    )

    def fake_fetch(token, config, *, api_key=None):
        attempted_keys.append(api_key)
        if api_key == "request-key":
            raise RuntimeError("request key rejected")
        return {
            "id": "user-123",
            "email": "owner@sezzions.com",
            "aud": "authenticated",
            "role": "authenticated",
        }

    monkeypatch.setattr("api.auth.fetch_supabase_user", fake_fetch)

    session = get_authenticated_session(
        credentials=type(
            "Creds",
            (),
            {"scheme": "Bearer", "credentials": "token-123"},
        )(),
        request=type(
            "Request",
            (),
            {"headers": {"apikey": "request-key", "x-supabase-apikey": "secondary-request-key"}},
        )(),
    )

    assert session.user_id == "user-123"
    assert attempted_keys == [
        "request-key",
        "secondary-request-key",
    ]


def test_fetch_supabase_user_sends_apikey_header(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"id": "user-123"}

    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("api.auth.httpx.get", fake_get)

    config = HostedBackendConfig(
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="publishable-key-123",
    )

    user = fetch_supabase_user("token-123", config)

    assert user == {"id": "user-123"}
    assert captured["url"] == "https://example.supabase.co/auth/v1/user"
    assert captured["headers"] == {
        "Authorization": "Bearer token-123",
        "apikey": "publishable-key-123",
    }
    assert captured["timeout"] == 10.0