from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.account_bootstrap_service import HostedAccountBootstrapService
from services.hosted.models import HostedPurchase
from services.hosted.persistence import HostedBase
from services.hosted.workspace_card_service import HostedWorkspaceCardService
from services.hosted.workspace_purchase_service import HostedWorkspacePurchaseService
from services.hosted.workspace_site_service import HostedWorkspaceSiteService
from services.hosted.workspace_user_service import HostedWorkspaceUserService


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _bootstrap(session_factory):
    """Bootstrap account + workspace + create a user, site, and card for FK references."""
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

    return result, user, site, card


# ── Happy path ───────────────────────────────────────────────────────────────


def test_create_purchase_basic() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="100.00",
            purchase_time="10:30:00",
            notes="Test purchase",
        )
    finally:
        engine.dispose()

    assert purchase.user_id == user.id
    assert purchase.site_id == site.id
    assert purchase.amount == "50.00"
    assert purchase.sc_received == "50.00"  # defaults to amount
    assert purchase.remaining_amount == "50.00"  # defaults to amount
    assert purchase.purchase_date == "2025-01-15"
    assert purchase.purchase_time == "10:30:00"
    assert purchase.notes == "Test purchase"
    assert purchase.status == "active"
    assert purchase.user_name == "Test User"
    assert purchase.site_name == "Test Site"
    assert purchase.card_name == "Default Card"
    assert purchase.starting_sc_balance == "100.00"


def test_create_purchase_with_card() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    card_service = HostedWorkspaceCardService(session_factory)
    visa = card_service.create_card(
        supabase_user_id="owner-123",
        name="Visa",
        user_id=user.id,
        last_four="1234",
        cashback_rate=2.0,
    )
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=visa.id,
            starting_sc_balance="200.00",
        )
    finally:
        engine.dispose()

    assert purchase.card_id == visa.id
    assert purchase.card_name == "Visa"


def test_create_purchase_explicit_sc_received() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="100.00",
            sc_received="75.00",
        )
    finally:
        engine.dispose()

    assert purchase.sc_received == "75.00"
    assert purchase.amount == "50.00"


def test_list_purchases_returns_workspace_scoped() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="25.00",
            purchase_date="2025-01-10",
            card_id=card.id,
            starting_sc_balance="50.00",
        )
        service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="75.00",
            purchase_date="2025-01-11",
            card_id=card.id,
            starting_sc_balance="150.00",
        )
        page = service.list_purchases_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 2
    assert len(page["purchases"]) == 2
    assert page["has_more"] is False
    # Most recent first (desc order)
    assert page["purchases"][0].purchase_date == "2025-01-11"
    assert page["purchases"][1].purchase_date == "2025-01-10"


def test_update_purchase() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="100.00",
        )
        updated = service.update_purchase(
            supabase_user_id="owner-123",
            purchase_id=created.id,
            user_id=user.id,
            site_id=site.id,
            amount="75.00",
            purchase_date="2025-01-16",
            card_id=card.id,
            starting_sc_balance="150.00",
            notes="Updated",
        )
    finally:
        engine.dispose()

    assert updated.id == created.id
    assert updated.amount == "75.00"
    assert updated.remaining_amount == "75.00"
    assert updated.purchase_date == "2025-01-16"
    assert updated.notes == "Updated"


def test_delete_purchase() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="100.00",
        )
        service.delete_purchase(
            supabase_user_id="owner-123",
            purchase_id=created.id,
        )
        page = service.list_purchases_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 0


def test_batch_delete_purchases() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        p1 = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="10.00",
            purchase_date="2025-01-01",
            card_id=card.id,
            starting_sc_balance="10.00",
        )
        p2 = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="20.00",
            purchase_date="2025-01-02",
            card_id=card.id,
            starting_sc_balance="30.00",
        )
        service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="30.00",
            purchase_date="2025-01-03",
            card_id=card.id,
            starting_sc_balance="60.00",
        )
        deleted_count = service.delete_purchases(
            supabase_user_id="owner-123",
            purchase_ids=[p1.id, p2.id],
        )
        page = service.list_purchases_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert deleted_count == 2
    assert page["total_count"] == 1


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_create_purchase_no_time() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="50.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="100.00",
        )
    finally:
        engine.dispose()

    assert purchase.purchase_time is None


def test_create_purchase_cashback_manual() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
            cashback_earned="3.50",
            cashback_is_manual=True,
        )
    finally:
        engine.dispose()

    assert purchase.cashback_earned == "3.50"
    assert purchase.cashback_is_manual is True


def test_list_purchases_empty_workspace() -> None:
    engine, session_factory = _session_factory()
    _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        page = service.list_purchases_page(
            supabase_user_id="owner-123",
            limit=100,
        )
    finally:
        engine.dispose()

    assert page["total_count"] == 0
    assert page["purchases"] == []
    assert page["has_more"] is False


def test_list_purchases_pagination() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        for i in range(5):
            service.create_purchase(
                supabase_user_id="owner-123",
                user_id=user.id,
                site_id=site.id,
                amount="10.00",
                purchase_date=f"2025-01-{10 + i:02d}",
                card_id=card.id,
                starting_sc_balance="100.00",
            )
        page1 = service.list_purchases_page(
            supabase_user_id="owner-123",
            limit=2,
            offset=0,
        )
        page2 = service.list_purchases_page(
            supabase_user_id="owner-123",
            limit=2,
            offset=2,
        )
    finally:
        engine.dispose()

    assert len(page1["purchases"]) == 2
    assert page1["has_more"] is True
    assert page1["total_count"] == 5
    assert len(page2["purchases"]) == 2
    assert page2["has_more"] is True


# ── Failure injection ────────────────────────────────────────────────────────


def test_delete_nonexistent_purchase_raises() -> None:
    engine, session_factory = _session_factory()
    _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        with pytest.raises(LookupError, match="not found"):
            service.delete_purchase(
                supabase_user_id="owner-123",
                purchase_id="nonexistent-id",
            )
    finally:
        engine.dispose()


def test_update_nonexistent_purchase_raises() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        with pytest.raises(LookupError, match="not found"):
            service.update_purchase(
                supabase_user_id="owner-123",
                purchase_id="nonexistent-id",
                user_id=user.id,
                site_id=site.id,
                amount="50.00",
                purchase_date="2025-01-15",
                card_id=card.id,
                starting_sc_balance="100.00",
            )
    finally:
        engine.dispose()


def test_batch_delete_partial_raises() -> None:
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        p1 = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="10.00",
            purchase_date="2025-01-01",
            card_id=card.id,
            starting_sc_balance="10.00",
        )
        with pytest.raises(LookupError, match="not found"):
            service.delete_purchases(
                supabase_user_id="owner-123",
                purchase_ids=[p1.id, "nonexistent-id"],
            )
    finally:
        engine.dispose()


def test_batch_delete_empty_raises() -> None:
    engine, session_factory = _session_factory()
    _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        with pytest.raises(ValueError, match="At least one"):
            service.delete_purchases(
                supabase_user_id="owner-123",
                purchase_ids=[],
            )
    finally:
        engine.dispose()


# ── Model validation ─────────────────────────────────────────────────────────


def test_model_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        HostedPurchase(
            user_id="u1",
            site_id="s1",
            amount="0",
            purchase_date="2025-01-01",
        )


def test_model_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        HostedPurchase(
            user_id="u1",
            site_id="s1",
            amount="-10",
            purchase_date="2025-01-01",
        )


def test_model_rejects_missing_user() -> None:
    with pytest.raises(ValueError, match="User is required"):
        HostedPurchase(
            user_id="",
            site_id="s1",
            amount="50",
            purchase_date="2025-01-01",
        )


def test_model_rejects_missing_site() -> None:
    with pytest.raises(ValueError, match="Site is required"):
        HostedPurchase(
            user_id="u1",
            site_id="",
            amount="50",
            purchase_date="2025-01-01",
        )


def test_model_rejects_missing_date() -> None:
    with pytest.raises(ValueError, match="Purchase date is required"):
        HostedPurchase(
            user_id="u1",
            site_id="s1",
            amount="50",
            purchase_date="",
        )


def test_model_defaults_sc_received_to_amount() -> None:
    p = HostedPurchase(
        user_id="u1",
        site_id="s1",
        amount="50.00",
        purchase_date="2025-01-01",
    )
    assert p.sc_received == "50.00"
    assert p.remaining_amount == "50.00"


def test_model_as_dict() -> None:
    p = HostedPurchase(
        user_id="u1",
        site_id="s1",
        amount="50.00",
        purchase_date="2025-01-01",
        id="test-id",
    )
    d = p.as_dict()
    assert d["id"] == "test-id"
    assert d["user_id"] == "u1"
    assert d["site_id"] == "s1"
    assert d["amount"] == "50.00"
    assert d["purchase_date"] == "2025-01-01"
    assert d["sc_received"] == "50.00"
    assert d["remaining_amount"] == "50.00"


# ── Auto-cashback calculation ────────────────────────────────────────────────


def test_auto_cashback_from_card_rate() -> None:
    """When cashback_is_manual=False, cashback should be auto-calculated from card rate."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    # card has cashback_rate=2.0
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
        )
    finally:
        engine.dispose()

    # 100.00 * 2.0 / 100 = 2.00
    assert purchase.cashback_earned == "2.00"
    assert purchase.cashback_is_manual is False


def test_auto_cashback_not_overridden_when_manual() -> None:
    """When cashback_is_manual=True, auto-calc should not override the explicit value."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        purchase = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
            cashback_earned="5.00",
            cashback_is_manual=True,
        )
    finally:
        engine.dispose()

    assert purchase.cashback_earned == "5.00"
    assert purchase.cashback_is_manual is True


def test_auto_cashback_recalculated_on_update() -> None:
    """When amount changes and cashback is auto, cashback should be recalculated."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
        )
        assert created.cashback_earned == "2.00"

        updated = service.update_purchase(
            supabase_user_id="owner-123",
            purchase_id=created.id,
            user_id=user.id,
            site_id=site.id,
            amount="200.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="400.00",
        )
    finally:
        engine.dispose()

    # 200.00 * 2.0 / 100 = 4.00
    assert updated.cashback_earned == "4.00"


# ── Consumed protection ─────────────────────────────────────────────────────


def test_consumed_purchase_blocks_amount_change() -> None:
    """If purchase has been consumed (remaining < amount), cannot change amount."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
        )
        # Simulate consumption by directly updating remaining_amount via repository
        with session_factory() as session:
            from repositories.hosted_workspace_repository import HostedWorkspaceRepository
            ws = HostedWorkspaceRepository().get_by_account_id(
                session,
                service.account_repository.get_by_supabase_user_id(session, "owner-123").id,
            )
            service.purchase_repository.update(
                session,
                purchase_id=created.id,
                workspace_id=ws.id,
                user_id=user.id,
                site_id=site.id,
                amount="100.00",
                purchase_date="2025-01-15",
                card_id=card.id,
                starting_sc_balance="200.00",
                remaining_amount="50.00",  # Half consumed
            )
            session.commit()

        with pytest.raises(ValueError, match="consumed"):
            service.update_purchase(
                supabase_user_id="owner-123",
                purchase_id=created.id,
                user_id=user.id,
                site_id=site.id,
                amount="150.00",  # Trying to change amount
                purchase_date="2025-01-15",
                card_id=card.id,
                starting_sc_balance="200.00",
            )
    finally:
        engine.dispose()


def test_consumed_purchase_blocks_date_change() -> None:
    """If purchase has been consumed, cannot change date."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
        )
        # Simulate consumption
        with session_factory() as session:
            from repositories.hosted_workspace_repository import HostedWorkspaceRepository
            ws = HostedWorkspaceRepository().get_by_account_id(
                session,
                service.account_repository.get_by_supabase_user_id(session, "owner-123").id,
            )
            service.purchase_repository.update(
                session,
                purchase_id=created.id,
                workspace_id=ws.id,
                user_id=user.id,
                site_id=site.id,
                amount="100.00",
                purchase_date="2025-01-15",
                card_id=card.id,
                starting_sc_balance="200.00",
                remaining_amount="50.00",
            )
            session.commit()

        with pytest.raises(ValueError, match="consumed"):
            service.update_purchase(
                supabase_user_id="owner-123",
                purchase_id=created.id,
                user_id=user.id,
                site_id=site.id,
                amount="100.00",
                purchase_date="2025-02-01",  # Trying to change date
                card_id=card.id,
                starting_sc_balance="200.00",
            )
    finally:
        engine.dispose()


def test_consumed_purchase_blocks_delete() -> None:
    """Cannot delete a purchase that has been consumed."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
        )
        # Simulate consumption
        with session_factory() as session:
            from repositories.hosted_workspace_repository import HostedWorkspaceRepository
            ws = HostedWorkspaceRepository().get_by_account_id(
                session,
                service.account_repository.get_by_supabase_user_id(session, "owner-123").id,
            )
            service.purchase_repository.update(
                session,
                purchase_id=created.id,
                workspace_id=ws.id,
                user_id=user.id,
                site_id=site.id,
                amount="100.00",
                purchase_date="2025-01-15",
                card_id=card.id,
                starting_sc_balance="200.00",
                remaining_amount="50.00",
            )
            session.commit()

        with pytest.raises(ValueError, match="consumed"):
            service.delete_purchase(
                supabase_user_id="owner-123",
                purchase_id=created.id,
            )
    finally:
        engine.dispose()


def test_proportional_remaining_on_amount_change() -> None:
    """When amount changes on unconsumed purchase, remaining_amount adjusts proportionally."""
    engine, session_factory = _session_factory()
    _, user, site, card = _bootstrap(session_factory)
    service = HostedWorkspacePurchaseService(session_factory)

    try:
        created = service.create_purchase(
            supabase_user_id="owner-123",
            user_id=user.id,
            site_id=site.id,
            amount="100.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="200.00",
        )
        assert created.remaining_amount == "100.00"

        # Change amount from 100 to 200 — remaining should go from 100 → 200 (ratio 1.0)
        updated = service.update_purchase(
            supabase_user_id="owner-123",
            purchase_id=created.id,
            user_id=user.id,
            site_id=site.id,
            amount="200.00",
            purchase_date="2025-01-15",
            card_id=card.id,
            starting_sc_balance="400.00",
        )
    finally:
        engine.dispose()

    assert updated.amount == "200.00"
    assert updated.remaining_amount == "200.00"
