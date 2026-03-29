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


def test_list_users_page_returns_sorted_page_metadata() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )

        service.create_user(supabase_user_id="owner-123", name="Charlie")
        service.create_user(supabase_user_id="owner-123", name="Alice")
        service.create_user(supabase_user_id="owner-123", name="Bravo")

        page = service.list_users_page(supabase_user_id="owner-123", limit=2, offset=1)
    finally:
        engine.dispose()

    assert [user.name for user in page["users"]] == ["Bravo", "Charlie"]
    assert page["offset"] == 1
    assert page["limit"] == 2
    assert page["next_offset"] == 3
    assert page["total_count"] == 3
    assert page["has_more"] is False


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


def test_update_user_updates_workspace_owned_business_user() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_user = service.create_user(supabase_user_id="owner-123", name="Alice")

        updated_user = service.update_user(
            supabase_user_id="owner-123",
            user_id=created_user.id,
            name="Alice Updated",
            email="alice@sezzions.com",
            notes="Updated notes",
            is_active=False,
        )
    finally:
        engine.dispose()

    assert updated_user.id == created_user.id
    assert updated_user.name == "Alice Updated"
    assert updated_user.email == "alice@sezzions.com"
    assert updated_user.notes == "Updated notes"
    assert updated_user.is_active is False


def test_update_user_rejects_cross_workspace_access() -> None:
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
        created_user = service.create_user(supabase_user_id="owner-456", name="Other Workspace User")

        try:
            service.update_user(
                supabase_user_id="owner-123",
                user_id=created_user.id,
                name="Should Fail",
                email=None,
                notes=None,
                is_active=True,
            )
        except LookupError as exc:
            assert str(exc) == "Hosted user was not found in the authenticated workspace."
        else:
            raise AssertionError("Expected cross-workspace update to fail")
    finally:
        engine.dispose()


def test_delete_user_removes_workspace_owned_business_user() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_user = service.create_user(supabase_user_id="owner-123", name="Delete Me")

        service.delete_user(
            supabase_user_id="owner-123",
            user_id=created_user.id,
        )

        users = service.list_users(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert users == []


def test_delete_user_rejects_cross_workspace_access() -> None:
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
        created_user = service.create_user(supabase_user_id="owner-456", name="Other Workspace User")

        try:
            service.delete_user(
                supabase_user_id="owner-123",
                user_id=created_user.id,
            )
        except LookupError as exc:
            assert str(exc) == "Hosted user was not found in the authenticated workspace."
        else:
            raise AssertionError("Expected cross-workspace delete to fail")
    finally:
        engine.dispose()


def test_delete_users_removes_multiple_workspace_owned_business_users() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceUserService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_one = service.create_user(supabase_user_id="owner-123", name="Delete Me 1")
        created_two = service.create_user(supabase_user_id="owner-123", name="Delete Me 2")
        service.create_user(supabase_user_id="owner-123", name="Keep Me")

        deleted_count = service.delete_users(
            supabase_user_id="owner-123",
            user_ids=[created_one.id, created_two.id],
        )

        users = service.list_users(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert deleted_count == 2
    assert [user.name for user in users] == ["Keep Me"]


def test_delete_users_rejects_missing_or_cross_workspace_ids_atomically() -> None:
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
        own_user = service.create_user(supabase_user_id="owner-123", name="Own User")
        other_user = service.create_user(supabase_user_id="owner-456", name="Other Workspace User")

        try:
            service.delete_users(
                supabase_user_id="owner-123",
                user_ids=[own_user.id, other_user.id],
            )
        except LookupError as exc:
            assert str(exc) == "One or more hosted users were not found in the authenticated workspace."
        else:
            raise AssertionError("Expected mixed-workspace batch delete to fail")

        users = service.list_users(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert [user.name for user in users] == ["Own User"]