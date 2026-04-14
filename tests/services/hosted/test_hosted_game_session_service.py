"""Tests for HostedWorkspaceGameSessionService — CRUD, active guard, side effects."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import HostedBase, HostedPurchaseRecord
from services.hosted.workspace_game_session_service import HostedWorkspaceGameSessionService
from services.hosted.workspace_game_service import HostedWorkspaceGameService
from services.hosted.workspace_game_type_service import HostedWorkspaceGameTypeService
from services.hosted.workspace_site_service import HostedWorkspaceSiteService
from services.hosted.workspace_user_service import HostedWorkspaceUserService


OWNER = "owner-123"


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _bootstrap(session_factory):
    """Bootstrap account + workspace + create user + site + game + game_type."""
    bootstrap = HostedAccountBootstrapService(session_factory)
    bootstrap.bootstrap_account_workspace(
        supabase_user_id=OWNER,
        owner_email="owner@sezzions.com",
    )

    user_service = HostedWorkspaceUserService(session_factory)
    user = user_service.create_user(supabase_user_id=OWNER, name="Alice")

    site_service = HostedWorkspaceSiteService(session_factory)
    site = site_service.create_site(supabase_user_id=OWNER, name="CasinoA")

    game_type_service = HostedWorkspaceGameTypeService(session_factory)
    game_type = game_type_service.create_game_type(supabase_user_id=OWNER, name="Video Slots")

    game_service = HostedWorkspaceGameService(session_factory)
    game = game_service.create_game(supabase_user_id=OWNER, name="Lucky Slots", game_type_id=game_type.id)

    return user, site, game, game_type


# ── Happy path ───────────────────────────────────────────────────────────────


def test_create_basic():
    engine, sf = _session_factory()
    user, site, game, game_type = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="14:00:00",
            game_id=game.id,
            game_type_id=game_type.id,
            starting_balance="100.00",
            notes="First session",
        )
    finally:
        engine.dispose()

    assert gs is not None
    assert gs.id is not None
    assert gs.user_id == user.id
    assert gs.site_id == site.id
    assert gs.session_date == "2026-01-15"
    assert gs.starting_balance == "100.00"
    assert gs.status == "Active"
    assert gs.user_name == "Alice"
    assert gs.site_name == "CasinoA"
    assert gs.game_name == "Lucky Slots"
    assert gs.game_type_name == "Video Slots"
    assert gs.notes == "First session"


def test_create_without_optional_fields():
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
        )
    finally:
        engine.dispose()

    assert gs.game_id is None
    assert gs.game_type_id is None
    assert gs.end_date is None
    assert gs.notes is None


def test_list_page():
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        for i in range(3):
            service.create_game_session(
                supabase_user_id=OWNER,
                user_id=user.id,
                site_id=site.id,
                session_date=f"2026-01-{10 + i:02d}",
                status_value="Closed",
            )

        page = service.list_game_sessions_page(
            supabase_user_id=OWNER, limit=2, offset=0,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 3
    assert len(page["game_sessions"]) == 2
    assert page["has_more"] is True
    assert page["next_offset"] == 2


def test_update_session():
    engine, sf = _session_factory()
    user, site, game, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            starting_balance="100.00",
        )

        updated = service.update_game_session(
            supabase_user_id=OWNER,
            game_session_id=gs.id,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            starting_balance="200.00",
            ending_balance="350.00",
            status_value="Closed",
            end_date="2026-01-15",
            end_time="18:00:00",
            game_id=game.id,
        )
    finally:
        engine.dispose()

    assert updated.starting_balance == "200.00"
    assert updated.ending_balance == "350.00"
    assert updated.status == "Closed"
    assert updated.end_date == "2026-01-15"
    assert updated.game_id == game.id


def test_delete_session():
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
        )
        service.delete_game_session(
            supabase_user_id=OWNER,
            game_session_id=gs.id,
        )

        page = service.list_game_sessions_page(
            supabase_user_id=OWNER, limit=100,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 0


def test_batch_delete():
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs1 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            status_value="Closed",
        )
        gs2 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-12",
            status_value="Closed",
        )
        gs3 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            status_value="Closed",
        )

        count = service.delete_game_sessions(
            supabase_user_id=OWNER,
            game_session_ids=[gs1.id, gs3.id],
        )

        page = service.list_game_sessions_page(
            supabase_user_id=OWNER, limit=100,
        )
    finally:
        engine.dispose()

    assert count == 2
    assert page["total_count"] == 1
    assert page["game_sessions"][0].id == gs2.id


# ── Active session guard ─────────────────────────────────────────────────────


def test_active_session_guard_on_create():
    """Cannot create a second active session for the same user+site."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            status_value="Active",
        )

        with pytest.raises(ValueError, match="active session already exists"):
            service.create_game_session(
                supabase_user_id=OWNER,
                user_id=user.id,
                site_id=site.id,
                session_date="2026-01-16",
                status_value="Active",
            )
    finally:
        engine.dispose()


def test_active_session_guard_allows_closed():
    """Creating a Closed session should not trigger active session guard."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            status_value="Active",
        )

        gs2 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            status_value="Closed",
            end_date="2026-01-10",
            end_time="18:00:00",
        )
    finally:
        engine.dispose()

    assert gs2.status == "Closed"


def test_active_session_guard_on_update():
    """Cannot re-activate a session if another is already active."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            status_value="Active",
        )

        gs2 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            status_value="Closed",
            end_date="2026-01-10",
            end_time="18:00:00",
        )

        with pytest.raises(ValueError, match="active session already exists"):
            service.update_game_session(
                supabase_user_id=OWNER,
                game_session_id=gs2.id,
                user_id=user.id,
                site_id=site.id,
                session_date="2026-01-10",
                status_value="Active",
            )
    finally:
        engine.dispose()


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_delete_nonexistent_raises():
    engine, sf = _session_factory()
    _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(LookupError, match="not found"):
            service.delete_game_session(
                supabase_user_id=OWNER,
                game_session_id="nonexistent-id",
            )
    finally:
        engine.dispose()


def test_update_nonexistent_raises():
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(LookupError, match="not found"):
            service.update_game_session(
                supabase_user_id=OWNER,
                game_session_id="nonexistent-id",
                user_id=user.id,
                site_id=site.id,
                session_date="2026-01-15",
            )
    finally:
        engine.dispose()


def test_batch_delete_empty_raises():
    engine, sf = _session_factory()
    _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(ValueError, match="At least one"):
            service.delete_game_sessions(
                supabase_user_id=OWNER,
                game_session_ids=[],
            )
    finally:
        engine.dispose()


def test_batch_delete_nonexistent_raises():
    engine, sf = _session_factory()
    _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(LookupError, match="not found"):
            service.delete_game_sessions(
                supabase_user_id=OWNER,
                game_session_ids=["nonexistent-id"],
            )
    finally:
        engine.dispose()


def test_no_workspace_raises():
    engine, sf = _session_factory()
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(LookupError, match="bootstrap"):
            service.list_game_sessions_page(
                supabase_user_id="no-such-user",
                limit=10,
            )
    finally:
        engine.dispose()


# ── Timestamp dedup ──────────────────────────────────────────────────────────


def test_timestamp_dedup_on_create():
    """Two sessions with the same start timestamp should get deduplicated."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs1 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="14:00:00",
            status_value="Closed",
            end_date="2026-01-15",
            end_time="16:00:00",
        )

        gs2 = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="14:00:00",
            status_value="Closed",
            end_date="2026-01-15",
            end_time="18:00:00",
        )
    finally:
        engine.dispose()

    # At least one should have been adjusted
    timestamps = {
        (gs1.session_date, gs1.session_time),
        (gs2.session_date, gs2.session_time),
    }
    assert len(timestamps) == 2  # both must be unique


# ── UTC end > start validation ───────────────────────────────────────────────


def test_create_end_before_start_raises():
    """Creating a session whose end datetime is before/equal to start should fail."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(ValueError, match="end.*before.*start"):
            service.create_game_session(
                supabase_user_id=OWNER,
                user_id=user.id,
                site_id=site.id,
                session_date="2026-01-15",
                session_time="14:00:00",
                end_date="2026-01-15",
                end_time="12:00:00",
                status_value="Closed",
            )
    finally:
        engine.dispose()


def test_update_end_before_start_raises():
    """Updating a session so end datetime is before start should fail."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="14:00:00",
        )

        with pytest.raises(ValueError, match="end.*before.*start"):
            service.update_game_session(
                supabase_user_id=OWNER,
                game_session_id=gs.id,
                user_id=user.id,
                site_id=site.id,
                session_date="2026-01-15",
                session_time="14:00:00",
                end_date="2026-01-15",
                end_time="12:00:00",
                status_value="Closed",
            )
    finally:
        engine.dispose()


def test_create_end_equals_start_raises():
    """End time equal to start time should also be rejected."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        with pytest.raises(ValueError, match="end.*before.*start"):
            service.create_game_session(
                supabase_user_id=OWNER,
                user_id=user.id,
                site_id=site.id,
                session_date="2026-01-15",
                session_time="14:00:00",
                end_date="2026-01-15",
                end_time="14:00:00",
                status_value="Closed",
            )
    finally:
        engine.dispose()


def test_create_end_after_start_succeeds():
    """End datetime after start datetime should succeed."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        gs = service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="14:00:00",
            end_date="2026-01-15",
            end_time="18:00:00",
            status_value="Closed",
        )
    finally:
        engine.dispose()

    assert gs.status == "Closed"
    assert gs.end_time == "18:00:00"


# ── Dormant purchase reactivation ────────────────────────────────────────────


def _get_workspace_id(sf):
    """Get the workspace ID from the bootstrapped environment."""
    from services.hosted.persistence import HostedWorkspaceRecord
    with sf() as s:
        ws = s.query(HostedWorkspaceRecord).first()
        return ws.id if ws else None


def test_dormant_purchases_reactivated_on_active_session():
    """Creating an Active session reactivates dormant purchases for that user+site."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)
    workspace_id = _get_workspace_id(sf)

    try:
        # Insert a dormant purchase directly
        from uuid import uuid4
        purchase_id = str(uuid4())
        with sf() as s:
            s.add(HostedPurchaseRecord(
                id=purchase_id,
                workspace_id=workspace_id,
                user_id=user.id,
                site_id=site.id,
                amount="50.00",
                sc_received="50.00",
                remaining_amount="50.00",
                purchase_date="2026-01-10",
                purchase_time="12:00:00",
                status="dormant",
            ))
            s.commit()

        # Create an Active session
        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
            status_value="Active",
        )

        # Verify the purchase is now active
        with sf() as s:
            p = s.query(HostedPurchaseRecord).filter_by(id=purchase_id).one()
            assert p.status == "active"
    finally:
        engine.dispose()


def test_dormant_purchases_not_reactivated_on_closed_session():
    """Creating a Closed session should NOT reactivate dormant purchases."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)
    workspace_id = _get_workspace_id(sf)

    try:
        from uuid import uuid4
        purchase_id = str(uuid4())
        with sf() as s:
            s.add(HostedPurchaseRecord(
                id=purchase_id,
                workspace_id=workspace_id,
                user_id=user.id,
                site_id=site.id,
                amount="50.00",
                sc_received="50.00",
                remaining_amount="50.00",
                purchase_date="2026-01-10",
                purchase_time="12:00:00",
                status="dormant",
            ))
            s.commit()

        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
            status_value="Closed",
            end_date="2026-01-15",
            end_time="14:00:00",
        )

        with sf() as s:
            p = s.query(HostedPurchaseRecord).filter_by(id=purchase_id).one()
            assert p.status == "dormant"
    finally:
        engine.dispose()


# ── Low-balance close ─────────────────────────────────────────────────────────


def test_low_balance_prompt_returns_data_when_below_threshold():
    """Balance < $1 should return prompt data."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        result = service.get_low_balance_close_prompt_data(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            ending_total_sc="0.50",
        )
    finally:
        engine.dispose()

    assert result is not None
    assert result["current_sc"] == "0.50"
    assert result["user_id"] == user.id


def test_low_balance_prompt_returns_none_when_above_threshold():
    """Balance >= $1 should return None."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        result = service.get_low_balance_close_prompt_data(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            ending_total_sc="5.00",
        )
    finally:
        engine.dispose()

    assert result is None


def test_low_balance_prompt_returns_none_if_active_session():
    """Active session present → no prompt."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            status_value="Active",
        )

        result = service.get_low_balance_close_prompt_data(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            ending_total_sc="0.00",
        )
    finally:
        engine.dispose()

    assert result is None


def test_close_unrealized_position_creates_redemption():
    """close_unrealized_position creates a $0 redemption with Net Loss notes."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        result = service.close_unrealized_position(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            current_sc="0.50",
            current_value="0.50",
            total_basis="0.00",
        )
    finally:
        engine.dispose()

    assert result["redemption_id"] is not None
    assert "Net Loss" in result["notes"]


def test_close_unrealized_position_marks_purchases_dormant():
    """When basis > 0, fully consumed purchases become dormant after close."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)
    workspace_id = _get_workspace_id(sf)

    try:
        from uuid import uuid4
        purchase_id = str(uuid4())
        with sf() as s:
            s.add(HostedPurchaseRecord(
                id=purchase_id,
                workspace_id=workspace_id,
                user_id=user.id,
                site_id=site.id,
                amount="50.00",
                sc_received="50.00",
                remaining_amount="50.00",
                purchase_date="2026-01-10",
                purchase_time="12:00:00",
                status="active",
            ))
            s.commit()

        result = service.close_unrealized_position(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            current_sc="0.50",
            current_value="0.50",
            total_basis="50.00",
        )

        with sf() as s:
            p = s.query(HostedPurchaseRecord).filter_by(id=purchase_id).one()
            # After FIFO consumes all basis, remaining → 0, status → dormant
            assert Decimal(p.remaining_amount) == 0
            assert p.status == "dormant"
    finally:
        engine.dispose()


def test_close_unrealized_position_blocked_by_active_session():
    """Cannot close position while an active session exists."""
    engine, sf = _session_factory()
    user, site, _, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)

    try:
        service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            status_value="Active",
        )

        with pytest.raises(ValueError, match="active session"):
            service.close_unrealized_position(
                supabase_user_id=OWNER,
                user_id=user.id,
                site_id=site.id,
                current_sc="0.00",
                current_value="0.00",
                total_basis="0.00",
            )
    finally:
        engine.dispose()
