from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.models import HostedRedemption
from services.hosted.persistence import HostedBase
from services.hosted.workspace_purchase_service import HostedWorkspacePurchaseService
from services.hosted.workspace_redemption_service import HostedWorkspaceRedemptionService
from services.hosted.workspace_card_service import HostedWorkspaceCardService
from services.hosted.workspace_site_service import HostedWorkspaceSiteService
from services.hosted.workspace_user_service import HostedWorkspaceUserService


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _bootstrap(session_factory):
    """Bootstrap account + workspace + user + site + card + purchase for FK refs."""
    bootstrap = HostedAccountBootstrapService(session_factory)
    result = bootstrap.bootstrap_account_workspace(
        supabase_user_id="owner-123",
        owner_email="owner@sezzions.com",
    )

    user_service = HostedWorkspaceUserService(session_factory)
    user = user_service.create_user(
        supabase_user_id="owner-123",
        name="Test User",
    )

    site_service = HostedWorkspaceSiteService(session_factory)
    site = site_service.create_site(
        supabase_user_id="owner-123",
        name="Test Site",
    )

    card_service = HostedWorkspaceCardService(session_factory)
    card = card_service.create_card(
        supabase_user_id="owner-123",
        name="Default Card",
        user_id=user.id,
        last_four="0000",
        cashback_rate=2.0,
    )

    # Create a purchase so FIFO has basis to allocate
    purchase_service = HostedWorkspacePurchaseService(session_factory)
    purchase = purchase_service.create_purchase(
        supabase_user_id="owner-123",
        user_id=user.id,
        site_id=site.id,
        amount="500.00",
        purchase_date="2025-01-01",
        card_id=card.id,
        starting_sc_balance="0.00",
    )

    return result, user, site, card, purchase


# ── Happy path ───────────────────────────────────────────────────────────────


def test_create_redemption_basic() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        redemption = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
            redemption_time="10:30:00",
            notes="Test redemption",
        )
    finally:
        engine.dispose()

    assert redemption.user_id == user.id
    assert redemption.site_id == site.id
    assert redemption.amount == "100.00"
    assert redemption.redemption_date == "2025-01-15"
    assert redemption.redemption_time == "10:30:00"
    assert redemption.notes == "Test redemption"
    assert redemption.status == "PENDING"
    assert redemption.user_name == "Test User"
    assert redemption.site_name == "Test Site"
    assert redemption.fees == "0.00"
    assert redemption.is_free_sc is False
    assert redemption.more_remaining is False


def test_create_redemption_triggers_fifo() -> None:
    """Verify that creating a non-free redemption creates a realized transaction with cost basis."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        redemption = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
    finally:
        engine.dispose()

    # Full redemption (more_remaining=False) consumes all available basis
    assert redemption.cost_basis is not None
    assert redemption.net_pl is not None


def test_create_partial_redemption() -> None:
    """Partial redemption only consumes up to the redemption amount."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        redemption = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
            more_remaining=True,
        )
    finally:
        engine.dispose()

    assert redemption.more_remaining is True
    assert redemption.cost_basis is not None
    cost = Decimal(str(redemption.cost_basis))
    # Partial: cost_basis <= redemption amount
    assert cost <= Decimal("100.00")


def test_create_free_sc_redemption_no_fifo() -> None:
    """Free SC redemptions don't consume cost basis."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        redemption = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            redemption_date="2025-01-15",
            is_free_sc=True,
        )
    finally:
        engine.dispose()

    assert redemption.is_free_sc is True
    # Free SC: cost_basis should be 0 and net_pl = payout
    if redemption.cost_basis is not None:
        assert Decimal(str(redemption.cost_basis)) == Decimal("0.00")


def test_list_redemptions_page() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            redemption_date="2025-01-10",
        )
        service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="75.00",
            redemption_date="2025-01-20",
            more_remaining=True,
        )
        page = service.list_redemptions_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 2
    assert len(page["redemptions"]) == 2
    assert page["has_more"] is False


def test_update_redemption() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        updated = service.update_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
            user_id=user.id,
            site_id=site.id,
            amount="150.00",
            redemption_date="2025-01-16",
            fees="5.00",
            notes="Updated notes",
        )
    finally:
        engine.dispose()

    assert updated.amount == "150.00"
    assert updated.fees == "5.00"
    assert updated.notes == "Updated notes"


def test_delete_redemption() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        service.delete_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
        )
        page = service.list_redemptions_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 0


def test_batch_delete_redemptions() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        r1 = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            redemption_date="2025-01-10",
        )
        r2 = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="75.00",
            redemption_date="2025-01-11",
            more_remaining=True,
        )
        deleted = service.delete_redemptions(
            supabase_user_id="owner-123",
            redemption_ids=[r1.id, r2.id],
        )
        page = service.list_redemptions_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert deleted == 2
    assert page["total_count"] == 0


# ── Cancel / Uncancel ────────────────────────────────────────────────────────


def test_cancel_redemption() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        canceled = service.cancel_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
            reason="Changed my mind",
        )
    finally:
        engine.dispose()

    assert canceled.status == "CANCELED"
    assert canceled.cancel_reason == "Changed my mind"
    assert canceled.canceled_at is not None


def test_cancel_non_pending_raises() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        service.cancel_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
        )
        with pytest.raises(ValueError, match="Only PENDING"):
            service.cancel_redemption(
                supabase_user_id="owner-123",
                redemption_id=created.id,
            )
    finally:
        engine.dispose()


def test_uncancel_redemption() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        service.cancel_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
        )
        uncanceled = service.uncancel_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
        )
    finally:
        engine.dispose()

    assert uncanceled.status == "PENDING"
    assert uncanceled.canceled_at is None
    assert uncanceled.cancel_reason is None


def test_uncancel_pending_raises() -> None:
    """Cannot uncancel a redemption that is already PENDING."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        with pytest.raises(ValueError, match="Only canceled"):
            service.uncancel_redemption(
                supabase_user_id="owner-123",
                redemption_id=created.id,
            )
    finally:
        engine.dispose()


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_cancel_releases_fifo_basis() -> None:
    """Canceling a redemption should restore the purchased lot's remaining_amount."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)
    purchase_service = HostedWorkspacePurchaseService(session_factory)

    try:
        redemption = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
            more_remaining=True,  # partial — consumes exactly 100
        )
        # Before cancel: purchase remaining should be reduced
        page_before = purchase_service.list_purchases_page(
            supabase_user_id="owner-123", limit=100
        )
        remaining_before = Decimal(str(page_before["purchases"][0].remaining_amount))

        service.cancel_redemption(
            supabase_user_id="owner-123",
            redemption_id=redemption.id,
        )
        # After cancel: purchase remaining should be restored
        page_after = purchase_service.list_purchases_page(
            supabase_user_id="owner-123", limit=100
        )
        remaining_after = Decimal(str(page_after["purchases"][0].remaining_amount))
    finally:
        engine.dispose()

    assert remaining_after > remaining_before
    assert remaining_after == Decimal("500.00")


def test_update_canceled_raises() -> None:
    """Cannot update a canceled redemption."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        created = service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
        )
        service.cancel_redemption(
            supabase_user_id="owner-123",
            redemption_id=created.id,
        )
        with pytest.raises(ValueError, match="Cannot update a canceled"):
            service.update_redemption(
                supabase_user_id="owner-123",
                redemption_id=created.id,
                user_id=user.id,
                site_id=site.id,
                amount="200.00",
                redemption_date="2025-01-16",
            )
    finally:
        engine.dispose()


def test_delete_nonexistent_raises() -> None:
    engine, session_factory = _session_factory()
    _ = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        with pytest.raises(LookupError):
            service.delete_redemption(
                supabase_user_id="owner-123",
                redemption_id="nonexistent-id",
            )
    finally:
        engine.dispose()


def test_batch_delete_empty_raises() -> None:
    engine, session_factory = _session_factory()
    _ = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)

    try:
        with pytest.raises(ValueError, match="At least one"):
            service.delete_redemptions(
                supabase_user_id="owner-123",
                redemption_ids=[],
            )
    finally:
        engine.dispose()


# ── Invariants ───────────────────────────────────────────────────────────────


def test_redemption_does_not_affect_other_pairs() -> None:
    """A redemption for user+site A must not affect purchases of user+site B."""
    engine, session_factory = _session_factory()
    _, user, site, card, purchase = _bootstrap(session_factory)
    service = HostedWorkspaceRedemptionService(session_factory)
    purchase_service = HostedWorkspacePurchaseService(session_factory)
    site_service = HostedWorkspaceSiteService(session_factory)

    try:
        site_b = site_service.create_site(
            supabase_user_id="owner-123",
            name="Site B",
        )
        purchase_b = purchase_service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site_b.id,
            amount="300.00",
            purchase_date="2025-01-01",
            card_id=card.id,
            starting_sc_balance="0.00",
        )

        # Redeem from site A
        service.create_redemption(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            redemption_date="2025-01-15",
            more_remaining=True,
        )

        # Site B purchase should be unaffected
        page_b = purchase_service.list_purchases_page(
            supabase_user_id="owner-123", limit=100
        )
        site_b_purchases = [p for p in page_b["purchases"] if p.site_id == site_b.id]
    finally:
        engine.dispose()

    assert len(site_b_purchases) == 1
    assert Decimal(str(site_b_purchases[0].remaining_amount)) == Decimal("300.00")
