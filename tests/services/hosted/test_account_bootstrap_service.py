from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import HostedBase, get_hosted_session_factory


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_bootstrap_creates_account_and_workspace_for_first_time_user() -> None:
    engine, session_factory = _session_factory()
    service = HostedAccountBootstrapService(session_factory)

    try:
        summary = service.bootstrap_account_workspace(
            supabase_user_id="user-123",
            owner_email="owner@sezzions.com",
        )
    finally:
        engine.dispose()

    assert summary.created_account is True
    assert summary.created_workspace is True
    assert summary.account.supabase_user_id == "user-123"
    assert summary.account.owner_email == "owner@sezzions.com"
    assert summary.account.role == "owner"
    assert summary.account.status == "active"
    assert summary.workspace.account_id == summary.account.id
    assert summary.workspace.name == "owner@sezzions.com Workspace"


def test_bootstrap_is_idempotent_for_existing_user() -> None:
    engine, session_factory = _session_factory()
    service = HostedAccountBootstrapService(session_factory)

    try:
        first = service.bootstrap_account_workspace(
            supabase_user_id="user-123",
            owner_email="owner@sezzions.com",
        )
        second = service.bootstrap_account_workspace(
            supabase_user_id="user-123",
            owner_email="owner@sezzions.com",
        )
    finally:
        engine.dispose()

    assert second.created_account is False
    assert second.created_workspace is False
    assert second.account.id == first.account.id
    assert second.account.role == "owner"
    assert second.account.status == "active"
    assert second.workspace.id == first.workspace.id


def test_bootstrap_updates_owner_email_without_changing_role_or_status() -> None:
    engine, session_factory = _session_factory()
    service = HostedAccountBootstrapService(session_factory)

    try:
        first = service.bootstrap_account_workspace(
            supabase_user_id="user-123",
            owner_email="owner@sezzions.com",
        )
        second = service.bootstrap_account_workspace(
            supabase_user_id="user-123",
            owner_email="updated@sezzions.com",
        )
    finally:
        engine.dispose()

    assert second.account.id == first.account.id
    assert second.account.owner_email == "updated@sezzions.com"
    assert second.account.role == "owner"
    assert second.account.status == "active"


def test_bootstrap_upgrades_legacy_account_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_hosted.db"
    sqlalchemy_url = f"sqlite+pysqlite:///{db_path}"

    legacy_engine = create_engine(sqlalchemy_url, future=True)
    try:
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE hosted_accounts (
                        id VARCHAR(36) PRIMARY KEY,
                        owner_email VARCHAR(255) NOT NULL,
                        supabase_user_id VARCHAR(255) NOT NULL UNIQUE
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE hosted_workspaces (
                        id VARCHAR(36) PRIMARY KEY,
                        account_id VARCHAR(36) NOT NULL UNIQUE,
                        name VARCHAR(255) NOT NULL,
                        source_db_path VARCHAR(1024)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO hosted_accounts (id, owner_email, supabase_user_id)
                    VALUES ('account-123', 'owner@sezzions.com', 'user-123')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO hosted_workspaces (id, account_id, name, source_db_path)
                    VALUES ('workspace-123', 'account-123', 'owner@sezzions.com Workspace', NULL)
                    """
                )
            )
    finally:
        legacy_engine.dispose()

    get_hosted_session_factory.cache_clear()
    session_factory = get_hosted_session_factory(sqlalchemy_url)
    service = HostedAccountBootstrapService(session_factory)

    try:
        summary = service.bootstrap_account_workspace(
            supabase_user_id="user-123",
            owner_email="owner@sezzions.com",
        )
    finally:
        session_factory.kw["bind"].dispose()
        get_hosted_session_factory.cache_clear()

    assert summary.created_account is False
    assert summary.created_workspace is False
    assert summary.account.id == "account-123"
    assert summary.account.role == "owner"
    assert summary.account.status == "active"
    assert summary.workspace.id == "workspace-123"
