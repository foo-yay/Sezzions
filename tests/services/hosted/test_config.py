import pytest

from api.config import HostedConfigurationError, load_hosted_backend_config


def test_load_hosted_backend_config_builds_supabase_db_connection_values() -> None:
    config = load_hosted_backend_config(
        {
            "SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co",
            "SUPABASE_DB_PASSWORD": "secret with spaces",
            "SUPABASE_GOOGLE_AUTH_ENABLED": "true",
        }
    )

    assert config.project_ref == "nztovvajnrokzsetliwz"
    assert config.db_host == "db.nztovvajnrokzsetliwz.supabase.co"
    assert config.google_auth_enabled is True
    assert "secret+with+spaces" in config.sqlalchemy_url


def test_load_hosted_backend_config_can_skip_when_not_required() -> None:
    config = load_hosted_backend_config({}, required=False)

    assert config is None


def test_load_hosted_backend_config_requires_url_and_password() -> None:
    with pytest.raises(HostedConfigurationError):
        load_hosted_backend_config({"SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co"})


def test_load_hosted_backend_config_can_load_auth_only_settings() -> None:
    config = load_hosted_backend_config(
        {"SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co"},
        require_db_password=False,
    )

    assert config is not None
    assert config.supabase_db_password is None
    assert config.supabase_issuer == "https://nztovvajnrokzsetliwz.supabase.co/auth/v1"
    assert config.supabase_jwks_url.endswith("/.well-known/jwks.json")
