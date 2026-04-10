"""Tests for compute_expected_balances and get_deletion_impact."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.persistence import HostedBase
from services.hosted.workspace_card_service import HostedWorkspaceCardService
from services.hosted.workspace_game_session_service import HostedWorkspaceGameSessionService
from services.hosted.workspace_purchase_service import HostedWorkspacePurchaseService
from services.hosted.workspace_redemption_service import HostedWorkspaceRedemptionService
from services.hosted.workspace_site_service import HostedWorkspaceSiteService
from services.hosted.workspace_user_service import HostedWorkspaceUserService


OWNER = "owner-balances"


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _bootstrap(sf):
    """Bootstrap account, workspace, user, site, card."""
    HostedAccountBootstrapService(sf).bootstrap_account_workspace(
        supabase_user_id=OWNER, owner_email="owner@test.com",
    )
    user = HostedWorkspaceUserService(sf).create_user(supabase_user_id=OWNER, name="Alice")
    site = HostedWorkspaceSiteService(sf).create_site(supabase_user_id=OWNER, name="CasinoA")
    card = HostedWorkspaceCardService(sf).create_card(
        supabase_user_id=OWNER, name="Visa", user_id=user.id,
    )
    return user, site, card


# ── compute_expected_balances ───────────────────────────────────────────────


def test_zero_baseline_no_data():
    """Priority 3: no sessions or events → (0, 0)."""
    engine, sf = _session_factory()
    user, site, _ = _bootstrap(sf)
    service = HostedWorkspaceGameSessionService(sf)
    try:
        result = service.compute_expected_balances(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-06-01",
            session_time="12:00:00",
        )
    finally:
        engine.dispose()
    assert result["expected_start_total"] == "0.00"
    assert result["expected_start_redeemable"] == "0.00"


def test_anchor_from_closed_session():
    """Priority 2: uses last closed session's ending balances."""
    engine, sf = _session_factory()
    user, site, _ = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    try:
        # Create and close a session
        gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            end_date="2026-01-10",
            end_time="18:00:00",
            starting_balance="0.00",
            ending_balance="250.00",
            starting_redeemable="0.00",
            ending_redeemable="80.00",
            status_value="Closed",
        )

        result = gs_service.compute_expected_balances(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
        )
    finally:
        engine.dispose()
    assert result["expected_start_total"] == "250.00"
    assert result["expected_start_redeemable"] == "80.00"


def test_purchase_after_anchor_updates_total():
    """A purchase between anchor session and cutoff sets expected_total."""
    engine, sf = _session_factory()
    user, site, card = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    purchase_service = HostedWorkspacePurchaseService(sf)
    try:
        # Closed session
        gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            end_date="2026-01-10",
            end_time="18:00:00",
            starting_balance="0.00",
            ending_balance="200.00",
            starting_redeemable="0.00",
            ending_redeemable="50.00",
            status_value="Closed",
        )

        # Purchase after session → starting_sc_balance = 350 (post-purchase snapshot)
        purchase_service.create_purchase(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="150.00",
            purchase_date="2026-01-12",
            purchase_time="09:00:00",
            card_id=card.id,
            starting_sc_balance="350.00",
        )

        result = gs_service.compute_expected_balances(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
        )
    finally:
        engine.dispose()
    assert result["expected_start_total"] == "350.00"
    # Purchase's starting_redeemable_balance defaults to "0.00" (checkpoint),
    # which supersedes the session anchor.
    assert result["expected_start_redeemable"] == "0.00"


def test_redemption_after_anchor_decreases_balances():
    """A pending redemption after anchor reduces both total and redeemable."""
    engine, sf = _session_factory()
    user, site, card = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    purchase_service = HostedWorkspacePurchaseService(sf)
    redemption_service = HostedWorkspaceRedemptionService(sf)
    try:
        # Need a purchase first (for FIFO basis on redemption)
        purchase_service.create_purchase(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="500.00",
            purchase_date="2026-01-01",
            card_id=card.id,
            starting_sc_balance="0.00",
        )

        # Closed session
        gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            end_date="2026-01-10",
            end_time="18:00:00",
            starting_balance="0.00",
            ending_balance="300.00",
            starting_redeemable="0.00",
            ending_redeemable="100.00",
            status_value="Closed",
        )

        # Redemption of $50 (sc_rate=1 → 50 SC)
        redemption_service.create_redemption(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            redemption_date="2026-01-12",
            redemption_time="09:00:00",
        )

        result = gs_service.compute_expected_balances(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
        )
    finally:
        engine.dispose()
    assert result["expected_start_total"] == "250.00"
    assert result["expected_start_redeemable"] == "50.00"


def test_floor_at_zero():
    """Expected balances never go negative."""
    engine, sf = _session_factory()
    user, site, card = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    purchase_service = HostedWorkspacePurchaseService(sf)
    redemption_service = HostedWorkspaceRedemptionService(sf)
    try:
        # Seed a purchase for FIFO
        purchase_service.create_purchase(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="1000.00",
            purchase_date="2025-12-01",
            card_id=card.id,
            starting_sc_balance="0.00",
        )

        # Small session
        gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            end_date="2026-01-10",
            end_time="18:00:00",
            starting_balance="0.00",
            ending_balance="10.00",
            starting_redeemable="0.00",
            ending_redeemable="5.00",
            status_value="Closed",
        )

        # Giant redemption exceeds balances
        redemption_service.create_redemption(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="999.00",
            redemption_date="2026-01-12",
            redemption_time="09:00:00",
        )

        result = gs_service.compute_expected_balances(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
        )
    finally:
        engine.dispose()
    assert result["expected_start_total"] == "0.00"
    assert result["expected_start_redeemable"] == "0.00"


def test_ignores_active_sessions():
    """Active sessions do NOT serve as anchors."""
    engine, sf = _session_factory()
    user, site, _ = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    try:
        gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            starting_balance="500.00",
            ending_balance="500.00",
            status_value="Active",
        )

        result = gs_service.compute_expected_balances(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-15",
            session_time="10:00:00",
        )
    finally:
        engine.dispose()
    # Active sessions ignored → falls through to zero baseline
    assert result["expected_start_total"] == "0.00"
    assert result["expected_start_redeemable"] == "0.00"


# ── get_deletion_impact ─────────────────────────────────────────────────────


def test_no_impact_for_active_session():
    """Active sessions have no deletion impact."""
    engine, sf = _session_factory()
    user, site, _ = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    try:
        gs = gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            status_value="Active",
        )
        result = gs_service.get_deletion_impact(
            supabase_user_id=OWNER,
            game_session_id=gs.id,
        )
    finally:
        engine.dispose()
    assert result["has_impact"] is False


def test_no_impact_when_no_subsequent_redemptions():
    """Closed session with no redemptions after it → no impact."""
    engine, sf = _session_factory()
    user, site, _ = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    try:
        gs = gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            end_date="2026-01-10",
            end_time="18:00:00",
            ending_balance="200.00",
            status_value="Closed",
        )
        result = gs_service.get_deletion_impact(
            supabase_user_id=OWNER,
            game_session_id=gs.id,
        )
    finally:
        engine.dispose()
    assert result["has_impact"] is False


def test_impact_when_subsequent_redemptions_exist():
    """Closed session with redemptions after it → returns impact message."""
    engine, sf = _session_factory()
    user, site, card = _bootstrap(sf)
    gs_service = HostedWorkspaceGameSessionService(sf)
    purchase_service = HostedWorkspacePurchaseService(sf)
    redemption_service = HostedWorkspaceRedemptionService(sf)
    try:
        # Need a purchase for FIFO
        purchase_service.create_purchase(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="500.00",
            purchase_date="2025-12-01",
            card_id=card.id,
            starting_sc_balance="0.00",
        )

        gs = gs_service.create_game_session(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            session_date="2026-01-10",
            session_time="10:00:00",
            end_date="2026-01-10",
            end_time="18:00:00",
            ending_balance="200.00",
            status_value="Closed",
        )

        # Redemption AFTER the session ends
        redemption_service.create_redemption(
            supabase_user_id=OWNER,
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2026-01-15",
            redemption_time="09:00:00",
        )

        result = gs_service.get_deletion_impact(
            supabase_user_id=OWNER,
            game_session_id=gs.id,
        )
    finally:
        engine.dispose()
    assert result["has_impact"] is True
    assert "1 redemption(s)" in result["message"]
    assert "$100.00" in result["message"]
