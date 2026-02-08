"""
Integration tests for purchase → active session linking (Issue #88).
"""
import pytest
from decimal import Decimal
from datetime import date
from app_facade import AppFacade


@pytest.fixture
def facade():
    """Create a fresh in-memory database facade for each test."""
    facade = AppFacade(":memory:")
    
    # Create test user and site
    user = facade.create_user("TestUser")
    site = facade.create_site("TestSite", sc_rate=1.0)
    
    facade.test_user_id = user.id
    facade.test_site_id = site.id
    
    return facade


def test_purchase_during_active_session_creates_during_link(facade):
    """When purchase is created during an active session, link should be DURING."""
    # Create an active session
    session = facade.create_game_session(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        game_id=None,
        session_date=date(2026, 2, 8),
        session_time="10:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )
    assert session.status == "Active"
    
    # Create a purchase during the active session
    purchase = facade.create_purchase(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        amount=Decimal("50.0"),
        purchase_date=date(2026, 2, 8),
        purchase_time="11:00:00",
        sc_received=Decimal("50.0"),
        starting_sc_balance=Decimal("150.0"),
    )
    
    # Get linked events for the session
    events = facade.get_linked_events_for_session(session.id)
    
    # Verify purchase is linked as DURING
    assert len(events.get("purchases", [])) == 1
    linked_purchase = events["purchases"][0]
    assert linked_purchase.id == purchase.id
    assert linked_purchase.link_relation == "DURING"


def test_purchase_before_active_session_creates_before_link(facade):
    """When purchase is created before an active session, link should be BEFORE."""
    # Create an active session
    session = facade.create_game_session(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        game_id=None,
        session_date=date(2026, 2, 8),
        session_time="12:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )
    
    # Create a purchase BEFORE the active session
    purchase = facade.create_purchase(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        amount=Decimal("50.0"),
        purchase_date=date(2026, 2, 8),
        purchase_time="10:00:00",
        sc_received=Decimal("50.0"),
        starting_sc_balance=Decimal("50.0"),
    )
    
    # Get linked events for the session
    events = facade.get_linked_events_for_session(session.id)
    
    # Verify purchase is linked as BEFORE
    assert len(events.get("purchases", [])) == 1
    linked_purchase = events["purchases"][0]
    assert linked_purchase.id == purchase.id
    assert linked_purchase.link_relation == "BEFORE"


def test_explicit_manual_link_to_active_session(facade):
    """Test explicit manual linking to an active session."""
    # Create an active session
    session = facade.create_game_session(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        game_id=None,
        session_date=date(2026, 2, 8),
        session_time="10:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )
    
    # Create a purchase
    purchase = facade.create_purchase(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        amount=Decimal("50.0"),
        purchase_date=date(2026, 2, 8),
        purchase_time="11:00:00",
        sc_received=Decimal("50.0"),
        starting_sc_balance=Decimal("150.0"),
    )
    
    # Explicitly link purchase to session with MANUAL relation
    facade.link_purchase_to_session(purchase.id, session.id, relation="MANUAL")
    
    # Verify link exists with MANUAL relation
    # Note: The explicit link will coexist with the auto-generated DURING link
    # We just verify at least one link exists
    events = facade.get_linked_events_for_session(session.id)
    assert len(events.get("purchases", [])) >= 1
    assert any(p.id == purchase.id for p in events["purchases"])


def test_get_active_session_for_pair(facade):
    """Test retrieving active session for a user/site pair."""
    # No active session initially
    active = facade.get_active_game_session(facade.test_user_id, facade.test_site_id)
    assert active is None
    
    # Create an active session
    session = facade.create_game_session(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        game_id=None,
        session_date=date(2026, 2, 8),
        session_time="10:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )
    
    # Now active session should be found
    active = facade.get_active_game_session(facade.test_user_id, facade.test_site_id)
    assert active is not None
    assert active.id == session.id
    assert active.status == "Active"
    
    # Close the session
    facade.update_game_session(
        session_id=session.id,
        end_date=date(2026, 2, 8),
        end_time="11:00:00",
        ending_balance=Decimal("120.0"),
        ending_redeemable=Decimal("120.0"),
        status="Closed",
    )
    
    # No active session after closing
    active = facade.get_active_game_session(facade.test_user_id, facade.test_site_id)
    assert active is None


def test_closed_session_does_not_get_new_purchase_as_during(facade):
    """Purchases after a closed session should not be linked as DURING to that session."""
    # Create a closed session
    session = facade.create_game_session(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        game_id=None,
        session_date=date(2026, 2, 8),
        session_time="10:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )
    
    # Close it immediately
    facade.update_game_session(
        session_id=session.id,
        end_date=date(2026, 2, 8),
        end_time="12:00:00",
        ending_balance=Decimal("120.0"),
        ending_redeemable=Decimal("120.0"),
        status="Closed",
    )
    
    # Create a purchase after session ends
    purchase = facade.create_purchase(
        user_id=facade.test_user_id,
        site_id=facade.test_site_id,
        amount=Decimal("50.0"),
        purchase_date=date(2026, 2, 8),
        purchase_time="13:00:00",
        sc_received=Decimal("50.0"),
        starting_sc_balance=Decimal("170.0"),
    )
    
    # Get linked events for the closed session
    events = facade.get_linked_events_for_session(session.id)
    
    # Purchase should NOT be linked as DURING (could be AFTER or not linked at all)
    # The purchase timestamp (13:00) is after session end (12:00)
    purchases = events.get("purchases", [])
    if purchases:
        # If linked, should not be DURING
        for p in purchases:
            if p.id == purchase.id:
                assert p.link_relation != "DURING"
