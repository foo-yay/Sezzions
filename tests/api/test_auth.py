import jwt
import pytest

from api.auth import get_authenticated_session


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
        lambda token, config: {
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
        )()
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
        lambda token, config: (_ for _ in ()).throw(RuntimeError("no user")),
    )

    with pytest.raises(Exception) as exc_info:
        get_authenticated_session(
            credentials=type(
                "Creds",
                (),
                {"scheme": "Bearer", "credentials": "token-123"},
            )()
        )

    assert getattr(exc_info.value, "status_code", None) == 401