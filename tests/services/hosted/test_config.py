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
    assert config.sqlalchemy_url.endswith("?sslmode=require")


def test_load_hosted_backend_config_allows_sslmode_override() -> None:
    config = load_hosted_backend_config(
        {
            "SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co",
            "SUPABASE_DB_PASSWORD": "secret",
            "SUPABASE_DB_SSLMODE": "verify-full",
        }
    )

    assert config.db_sslmode == "verify-full"
    assert config.sqlalchemy_url.endswith("?sslmode=verify-full")


def test_load_hosted_backend_config_allows_sqlalchemy_url_override() -> None:
    config = load_hosted_backend_config(
        {
            "SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co",
            "DATABASE_URL": "postgresql+psycopg2://postgres.nztovvajnrokzsetliwz:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require",
        }
    )

    assert config.sqlalchemy_url_override is not None
    assert config.sqlalchemy_url == (
        "postgresql+psycopg2://postgres.nztovvajnrokzsetliwz:secret@"
        "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )


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
    assert config.cors_allowed_origins == (
        "https://dev.sezzions.com",
        "http://localhost:5173",
    )


def test_load_hosted_backend_config_parses_cors_allowed_origins() -> None:
    config = load_hosted_backend_config(
        {
            "SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co",
            "CORS_ALLOWED_ORIGINS": "https://dev.sezzions.com, https://sezzions.com ,http://localhost:5173",
        },
        require_db_password=False,
    )

    assert config is not None
    assert config.cors_allowed_origins == (
        "https://dev.sezzions.com",
        "https://sezzions.com",
        "http://localhost:5173",
    )


def test_load_hosted_backend_config_reads_publishable_key_variants() -> None:
    config = load_hosted_backend_config(
        {
            "SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key-123",
        },
        require_db_password=False,
    )

    assert config is not None
    assert config.supabase_publishable_key == "publishable-key-123"

    fallback_config = load_hosted_backend_config(
        {
            "SUPABASE_URL": "https://nztovvajnrokzsetliwz.supabase.co",
            "SUPABASE_ANON_KEY": "anon-key-123",
        },
        require_db_password=False,
    )

    assert fallback_config is not None
    assert fallback_config.supabase_publishable_key == "anon-key-123"
