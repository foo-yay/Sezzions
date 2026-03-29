from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import HostedBase


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
    assert second.workspace.id == first.workspace.id
