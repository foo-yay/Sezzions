from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import HostedBase
from services.hosted.workspace_site_service import HostedWorkspaceSiteService


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_create_site_creates_workspace_owned_business_site() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap = bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_site = service.create_site(
            supabase_user_id="owner-123",
            name="Lucky Slots",
            url="https://luckyslots.com",
            sc_rate=2.5,
            playthrough_requirement=3.0,
            notes="Top sweepstakes site.",
        )
    finally:
        engine.dispose()

    assert created_site.workspace_id == bootstrap.workspace.id
    assert created_site.name == "Lucky Slots"
    assert created_site.url == "https://luckyslots.com"
    assert created_site.sc_rate == 2.5
    assert created_site.playthrough_requirement == 3.0
    assert created_site.notes == "Top sweepstakes site."
    assert created_site.is_active is True


def test_create_site_uses_default_sc_rate_and_playthrough() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_site = service.create_site(
            supabase_user_id="owner-123",
            name="Minimal Site",
        )
    finally:
        engine.dispose()

    assert created_site.sc_rate == 1.0
    assert created_site.playthrough_requirement == 1.0
    assert created_site.url is None
    assert created_site.notes is None


def test_list_sites_returns_only_sites_for_authenticated_users_workspace() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-456",
            owner_email="owner2@sezzions.com",
        )

        service.create_site(supabase_user_id="owner-123", name="Charlie Casino")
        service.create_site(supabase_user_id="owner-123", name="Alpha Slots")
        service.create_site(supabase_user_id="owner-456", name="Other Workspace Site")

        sites = service.list_sites(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert [site.name for site in sites] == ["Alpha Slots", "Charlie Casino"]


def test_list_sites_page_returns_sorted_page_metadata() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )

        service.create_site(supabase_user_id="owner-123", name="Charlie Casino")
        service.create_site(supabase_user_id="owner-123", name="Alpha Slots")
        service.create_site(supabase_user_id="owner-123", name="Bravo Bets")

        page = service.list_sites_page(supabase_user_id="owner-123", limit=2, offset=1)
    finally:
        engine.dispose()

    assert [site.name for site in page["sites"]] == ["Bravo Bets", "Charlie Casino"]
    assert page["offset"] == 1
    assert page["limit"] == 2
    assert page["next_offset"] == 3
    assert page["total_count"] == 3
    assert page["has_more"] is False


def test_create_site_rejects_blank_name_without_persisting_record() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )

        try:
            service.create_site(supabase_user_id="owner-123", name="   ")
        except ValueError as exc:
            assert str(exc) == "Site name is required"
        else:
            raise AssertionError("Expected blank site name to fail validation")

        sites = service.list_sites(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert sites == []


def test_create_site_rejects_negative_sc_rate() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )

        try:
            service.create_site(supabase_user_id="owner-123", name="Bad Site", sc_rate=-1.0)
        except ValueError as exc:
            assert str(exc) == "SC rate must be non-negative"
        else:
            raise AssertionError("Expected negative SC rate to fail validation")
    finally:
        engine.dispose()


def test_create_site_rejects_negative_playthrough_requirement() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )

        try:
            service.create_site(supabase_user_id="owner-123", name="Bad Site", playthrough_requirement=-0.5)
        except ValueError as exc:
            assert str(exc) == "Playthrough requirement must be non-negative"
        else:
            raise AssertionError("Expected negative playthrough requirement to fail validation")
    finally:
        engine.dispose()


def test_update_site_updates_workspace_owned_business_site() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_site = service.create_site(supabase_user_id="owner-123", name="Alpha Slots")

        updated_site = service.update_site(
            supabase_user_id="owner-123",
            site_id=created_site.id,
            name="Alpha Slots Updated",
            url="https://alphaslots.com",
            sc_rate=5.0,
            playthrough_requirement=2.0,
            notes="Updated notes",
            is_active=False,
        )
    finally:
        engine.dispose()

    assert updated_site.id == created_site.id
    assert updated_site.name == "Alpha Slots Updated"
    assert updated_site.url == "https://alphaslots.com"
    assert updated_site.sc_rate == 5.0
    assert updated_site.playthrough_requirement == 2.0
    assert updated_site.notes == "Updated notes"
    assert updated_site.is_active is False


def test_update_site_rejects_cross_workspace_access() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-456",
            owner_email="owner2@sezzions.com",
        )
        created_site = service.create_site(supabase_user_id="owner-456", name="Other Workspace Site")

        try:
            service.update_site(
                supabase_user_id="owner-123",
                site_id=created_site.id,
                name="Should Fail",
                url=None,
                sc_rate=1.0,
                playthrough_requirement=1.0,
                notes=None,
                is_active=True,
            )
        except LookupError as exc:
            assert str(exc) == "Hosted site was not found in the authenticated workspace."
        else:
            raise AssertionError("Expected cross-workspace update to fail")
    finally:
        engine.dispose()


def test_delete_site_removes_workspace_owned_business_site() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_site = service.create_site(supabase_user_id="owner-123", name="Delete Me")

        service.delete_site(
            supabase_user_id="owner-123",
            site_id=created_site.id,
        )

        sites = service.list_sites(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert sites == []


def test_delete_site_rejects_cross_workspace_access() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-456",
            owner_email="owner2@sezzions.com",
        )
        created_site = service.create_site(supabase_user_id="owner-456", name="Other Workspace Site")

        try:
            service.delete_site(
                supabase_user_id="owner-123",
                site_id=created_site.id,
            )
        except LookupError as exc:
            assert str(exc) == "Hosted site was not found in the authenticated workspace."
        else:
            raise AssertionError("Expected cross-workspace delete to fail")
    finally:
        engine.dispose()


def test_delete_sites_removes_multiple_workspace_owned_business_sites() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner@sezzions.com",
        )
        created_one = service.create_site(supabase_user_id="owner-123", name="Delete Me 1")
        created_two = service.create_site(supabase_user_id="owner-123", name="Delete Me 2")
        service.create_site(supabase_user_id="owner-123", name="Keep Me")

        deleted_count = service.delete_sites(
            supabase_user_id="owner-123",
            site_ids=[created_one.id, created_two.id],
        )

        sites = service.list_sites(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert deleted_count == 2
    assert [site.name for site in sites] == ["Keep Me"]


def test_delete_sites_rejects_missing_or_cross_workspace_ids_atomically() -> None:
    engine, session_factory = _session_factory()
    bootstrap_service = HostedAccountBootstrapService(session_factory)
    service = HostedWorkspaceSiteService(session_factory)

    try:
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-123",
            owner_email="owner1@sezzions.com",
        )
        bootstrap_service.bootstrap_account_workspace(
            supabase_user_id="owner-456",
            owner_email="owner2@sezzions.com",
        )
        own_site = service.create_site(supabase_user_id="owner-123", name="Own Site")
        other_site = service.create_site(supabase_user_id="owner-456", name="Other Workspace Site")

        try:
            service.delete_sites(
                supabase_user_id="owner-123",
                site_ids=[own_site.id, other_site.id],
            )
        except LookupError as exc:
            assert str(exc) == "One or more hosted sites were not found in the authenticated workspace."
        else:
            raise AssertionError("Expected mixed-workspace batch delete to fail")

        sites = service.list_sites(supabase_user_id="owner-123")
    finally:
        engine.dispose()

    assert [site.name for site in sites] == ["Own Site"]
