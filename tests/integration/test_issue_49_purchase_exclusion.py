"""Regression test for Issue #49: Exclude edited purchase from balance checks.

Tests that when editing a purchase, its expected pre-purchase balance correctly
excludes the purchase being edited, even when multiple purchases share the same timestamp.
"""
import pytest
from datetime import date
from decimal import Decimal

from app_facade import AppFacade


@pytest.fixture
def facade():
    """Create test facade with in-memory database."""
    facade = AppFacade(":memory:")
    yield facade
    facade.db.close()


@pytest.fixture
def test_user_site(facade):
    """Create test user and site."""
    user = facade.user_service.create_user(name="TestUser")
    site = facade.site_service.create_site(name="TestSite", url="http://test.com")
    return user.id, site.id


class TestPurchaseBalanceCheckExclusion:
    """Test that purchase balance checks exclude the edited purchase."""
    
    def test_two_purchases_same_timestamp_edit_first(self, facade, test_user_site):
        """When two purchases share the same timestamp, editing one excludes only that purchase.
        
        The key behavior: at a given timestamp, all purchases at that timestamp are included
        EXCEPT the one being edited. This ensures stable, deterministic balance checks even
        when multiple purchases share the same timestamp.
        """
        user_id, site_id = test_user_site
        
        # Create two purchases at the exact same timestamp
        purchase1 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="10:30:00",
            amount=Decimal("100.00"),
            sc_received=Decimal("100.00"),
            starting_sc_balance=Decimal("100.00")
        )
        
        purchase2 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="10:30:00",  # Same timestamp
            amount=Decimal("50.00"),
            sc_received=Decimal("50.00"),
            starting_sc_balance=Decimal("150.00")
        )
        
        # When editing purchase1, expected balance is the balance *before* purchase1.
        # For same-timestamp purchases, we only include purchases with smaller IDs.
        # Since purchase1 is the earliest at that timestamp, expected is 0.
        expected_total, expected_redeemable = facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=date(2024, 1, 15),
            session_time="10:30:00",
            exclude_purchase_id=purchase1.id
        )
        
        assert expected_total == Decimal("0.00")
        
        # When editing purchase2, expected balance should include purchase1 but not purchase2
        expected_total, expected_redeemable = facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=date(2024, 1, 15),
            session_time="10:30:00",
            exclude_purchase_id=purchase2.id
        )
        
        # Should be 100 (purchase1 post-purchase balance)
        assert expected_total == Decimal("100.00")
    
    def test_two_purchases_same_timestamp_edit_second(self, facade, test_user_site):
        """Editing the second purchase at same timestamp should show correct expected balance."""
        user_id, site_id = test_user_site
        
        # Create two purchases at the exact same timestamp
        purchase1 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="10:30:00",
            amount=Decimal("75.00"),
            sc_received=Decimal("75.00"),
            starting_sc_balance=Decimal("75.00")
        )
        
        purchase2 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="10:30:00",  # Same timestamp
            amount=Decimal("25.00"),
            sc_received=Decimal("25.00"),
            starting_sc_balance=Decimal("100.00")
        )
        
        # When editing purchase2, should see purchase1's contribution
        expected_total, expected_redeemable = facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=date(2024, 1, 15),
            session_time="10:30:00",
            exclude_purchase_id=purchase2.id
        )
        
        assert expected_total == Decimal("75.00")  # Only purchase1
    
    def test_edit_purchase_does_not_affect_other_purchases(self, facade, test_user_site):
        """Editing a purchase should not affect balance checks for other purchases."""
        user_id, site_id = test_user_site
        
        # Create three purchases at different times
        purchase1 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="10:00:00",
            amount=Decimal("100.00"),
            sc_received=Decimal("100.00"),
            starting_sc_balance=Decimal("100.00")
        )
        
        purchase2 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="11:00:00",
            amount=Decimal("50.00"),
            sc_received=Decimal("50.00"),
            starting_sc_balance=Decimal("150.00")
        )
        
        purchase3 = facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="12:00:00",
            amount=Decimal("25.00"),
            sc_received=Decimal("25.00"),
            starting_sc_balance=Decimal("175.00")
        )
        
        # Editing purchase2 should show purchase1 but not purchase2
        expected_total, _ = facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=date(2024, 1, 15),
            session_time="11:00:00",
            exclude_purchase_id=purchase2.id
        )
        assert expected_total == Decimal("100.00")
        
        # Editing purchase3 should show purchase1 and purchase2
        expected_total, _ = facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=date(2024, 1, 15),
            session_time="12:00:00",
            exclude_purchase_id=purchase3.id
        )
        assert expected_total == Decimal("150.00")
    
    def test_exclude_purchase_none_includes_all_purchases(self, facade, test_user_site):
        """When exclude_purchase_id is None, all purchases should be included (existing behavior)."""
        user_id, site_id = test_user_site
        
        # Create two purchases
        facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="10:00:00",
            amount=Decimal("100.00"),
            sc_received=Decimal("100.00"),
            starting_sc_balance=Decimal("100.00")
        )
        
        facade.create_purchase(
            user_id=user_id,
            site_id=site_id,
            purchase_date=date(2024, 1, 15),
            purchase_time="11:00:00",
            amount=Decimal("50.00"),
            sc_received=Decimal("50.00"),
            starting_sc_balance=Decimal("150.00")
        )
        
        # Compute expected balance with no exclusion at 11:00:00.
        # Semantics: expected balance is strictly before the cutoff event.
        expected_total, _ = facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=date(2024, 1, 15),
            session_time="11:00:00",
            exclude_purchase_id=None
        )
        
        # Only the 10:00 purchase is before 11:00.
        assert expected_total == Decimal("100.00")
