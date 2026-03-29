from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import HostedBase
from services.hosted.workspace_user_service import HostedWorkspaceUserService


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_create_user_creates_workspace_owned_business_user() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap = bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_user = service.create_user(
            supabase_user_id="owner-123",
            name="Mrs. FooYay",
            email="mrs@sezzions.com",
            notes="Managed by account owner.",
        )
    finally:
        engine.dispose()

    assert created_user.workspace_id == bootstrap.workspace.id
    assert created_user.name == "Mrs. FooYay"
    assert created_user.email == "mrs@sezzions.com"
    assert created_user.notes == "Managed by account owner."
    assert created_user.is_active is True


def test_list_users_returns_only_users_for_authenticated_users_workspace() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-456",
            owner_email="owner2@sezzions.com",
        )

        service.create_user(supabase_user_id="owner-123", name="Charlie")
        service.create_user(supabase_user_id="owner-123", name="Alice")
        service.create_user(supabase_user_id="owner-456", name="Other Workspace User")

        users = service.list_users(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert [user.name for user in users] == ["Alice", "Charlie"]


def test_create_user_rejects_blank_name_without_persisting_record() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )

        try:
            service.create_user(supabase_user_id="owner-123", name="   ")
        except ValueError as exc:
            assert str(exc) == "User name is required"
        else:
            raise AssertionError("Expected blank user name to fail validation")

        users = service.list_users(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert users == []