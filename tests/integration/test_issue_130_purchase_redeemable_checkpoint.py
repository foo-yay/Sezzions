"""
Integration tests for Issue #130: Purchase checkpoints should store redeemable balance.

Tests verify that making a purchase after a session preserves the redeemable balance
instead of resetting it to 0.
"""

from decimal import Decimal
from datetime import date

from app_facade import AppFacade


def test_purchase_after_session_preserves_redeemable():
    """
    Core bug fix test: Purchase after session should preserve redeemable balance, not reset to 0.
    """
    facade = AppFacade(":memory:")

    # Setup
    site = facade.create_site(name="Test Site")
    user = facade.create_user(name="Test User")
    game_type = facade.create_game_type(name="Slots")
    game = facade.create_game(name="Test Slots", game_type_id=game_type.id)

    # Step 1: Make initial purchase
    purchase1 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 1),
        purchase_time="09:00:00",
        amount=Decimal("100.00"),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("0.00"),
    )

    # Step 2: Play session that generates redeemable balance
    session = facade.create_game_session(
        site_id=site.id,
        user_id=user.id,
        game_id=game.id,
        session_date=date(2025, 1, 1),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("100.00"),  # User won 50 total, 100 redeemable
        calculate_pl=False,
    )

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date(2025, 1, 1),
        end_time="11:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    # Step 3: Make another purchase (the critical test)
    purchase2 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 2),
        purchase_time="14:00:00",
        amount=Decimal("50.00"),
        sc_received=Decimal("50.00"),
        starting_sc_balance=Decimal("200.00"),  # POST-purchase: 150 (from session) + 50 (this purchase)
    )

    # Verify: Purchase should have stored the redeemable balance
    assert purchase2.starting_redeemable_balance == Decimal("100.00"), \
        f"Purchase should store redeemable=100 from session, got {purchase2.starting_redeemable_balance}"

    # Step 4: Verify Unrealized position shows correct redeemable
    positions = facade.get_unrealized_positions()
    assert len(positions) == 1

    position = positions[0]
    assert position.total_sc == Decimal("200.00"), \
        f"Total should be 200 (POST-purchase snapshot), got {position.total_sc}"
    assert position.redeemable_sc == Decimal("100.00"), \
        f"Redeemable should stay 100 (from session), got {position.redeemable_sc}"


def test_redemption_between_purchases_reduces_redeemable():
    """
    Verify redemptions between purchases correctly reduce redeemable balance in next purchase checkpoint.
    """
    facade = AppFacade(":memory:")

    site = facade.create_site(name="Test Site")
    user = facade.create_user(name="Test User")
    game_type = facade.create_game_type(name="Slots")
    game = facade.create_game(name="Test Slots", game_type_id=game_type.id)

    # Initial purchase + session
    facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 1),
        purchase_time="09:00:00",
        amount=Decimal("100.00"),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("0.00"),
    )

    session = facade.create_game_session(
        site_id=site.id,
        user_id=user.id,
        game_id=game.id,
        session_date=date(2025, 1, 1),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("200.00"),
        ending_redeemable=Decimal("150.00"),
        calculate_pl=False,
    )

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("200.00"),
        ending_redeemable=Decimal("150.00"),
        end_date=date(2025, 1, 1),
        end_time="11:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    # Redemption reduces redeemable (is_free_sc defaults to False)
    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2025, 1, 1),
        redemption_time="12:00:00",
    )

    # Purchase after redemption should reflect reduced redeemable
    purchase2 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 2),
        purchase_time="09:00:00",
        amount=Decimal("50.00"),
        sc_received=Decimal("50.00"),
        starting_sc_balance=Decimal("200.00"),  # POST-purchase: 150 (after redemption) + 50 (this purchase)
    )

    # Redeemable should be 100 (150 from session - 50 redemption)
    assert purchase2.starting_redeemable_balance == Decimal("100.00"), \
        f"Redeemable should be 100 (150 - 50 redemption), got {purchase2.starting_redeemable_balance}"


def test_first_purchase_has_zero_redeemable():
    """
    Verify that first purchase (no prior sessions) correctly has redeemable=0.
    """
    facade = AppFacade(":memory:")

    site = facade.create_site(name="Test Site")
    user = facade.create_user(name="Test User")

    purchase = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 1),
        purchase_time="10:00:00",
        amount=Decimal("100.00"),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("0.00"),
    )

    assert purchase.starting_redeemable_balance == Decimal("0.00"), \
        "First purchase should have redeemable=0 (no prior sessions)"


def test_multiple_purchases_back_to_back():
    """
    Verify that multiple purchases in sequence properly reference each other's checkpoints.
    """
    facade = AppFacade(":memory:")

    site = facade.create_site(name="Test Site")
    user = facade.create_user(name="Test User")
    game_type = facade.create_game_type(name="Slots")
    game = facade.create_game(name="Test Slots", game_type_id=game_type.id)

    # Purchase 1
    purchase1 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 1),
        purchase_time="09:00:00",
        amount=Decimal("100.00"),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("0.00"),
    )

    # Session establishes redeemable
    session = facade.create_game_session(
        site_id=site.id,
        user_id=user.id,
        game_id=game.id,
        session_date=date(2025, 1, 1),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date(2025, 1, 1),
        end_time="11:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    # Purchase 2 (should reference session)
    purchase2 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 2),
        purchase_time="09:00:00",
        amount=Decimal("50.00"),
        sc_received=Decimal("50.00"),
        starting_sc_balance=Decimal("200.00"),  # POST-purchase: 150 + 50
    )

    assert purchase2.starting_redeemable_balance == Decimal("100.00")

    # Purchase 3 immediately after Purchase 2 (should reference Purchase 2)
    purchase3 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 2),
        purchase_time="09:01:00",
        amount=Decimal("25.00"),
        sc_received=Decimal("25.00"),
        starting_sc_balance=Decimal("225.00"),  # POST-purchase: 200 + 25
    )

    # Purchase 3 should still have redeemable=100 (from Purchase 2's snapshot)
    assert purchase3.starting_redeemable_balance == Decimal("100.00"), \
        f"Purchase 3 should reference Purchase 2's redeemable, got {purchase3.starting_redeemable_balance}"


def test_balance_checkpoint_takes_priority():
    """
    Verify that explicit balance checkpoint takes priority over session for redeemable.
    """
    facade = AppFacade(":memory:")

    site = facade.create_site(name="Test Site")
    user = facade.create_user(name="Test User")
    game_type = facade.create_game_type(name="Slots")
    game = facade.create_game(name="Test Slots", game_type_id=game_type.id)

    # Purchase + Session
    facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 1),
        purchase_time="09:00:00",
        amount=Decimal("100.00"),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("0.00"),
    )

    session = facade.create_game_session(
        site_id=site.id,
        user_id=user.id,
        game_id=game.id,
        session_date=date(2025, 1, 1),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date(2025, 1, 1),
        end_time="11:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    # Manual balance correction (takes priority)
    facade.db.execute("""
        INSERT INTO account_adjustments 
        (site_id, user_id, type, effective_date, effective_time, 
         checkpoint_total_sc, checkpoint_redeemable_sc, reason)
        VALUES (?, ?, 'BALANCE_CHECKPOINT_CORRECTION', ?, ?, ?, ?, ?)
    """, (
        site.id, user.id,
        date(2025, 1, 2), '09:00:00',
        str(Decimal("150.00")), str(Decimal("75.00")),  # Correction: redeemable is actually 75, not 100
        "Manual redeemable balance correction"
    ))

    # Purchase after balance correction should use corrected redeemable
    purchase2 = facade.create_purchase(
        site_id=site.id,
        user_id=user.id,
        purchase_date=date(2025, 1, 3),
        purchase_time="10:00:00",
        amount=Decimal("50.00"),
        sc_received=Decimal("50.00"),
        starting_sc_balance=Decimal("200.00"),  # POST-purchase: 150 + 50
    )

    assert purchase2.starting_redeemable_balance == Decimal("75.00"), \
        f"Purchase should use balance checkpoint (75), not session (100), got {purchase2.starting_redeemable_balance}"
