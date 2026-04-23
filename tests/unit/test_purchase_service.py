"""
Unit tests for PurchaseService
"""
import pytest
from decimal import Decimal
from datetime import date
from models.purchase import Purchase


def test_create_purchase_service(purchase_service, sample_user, sample_site):
    """Test creating purchase through service"""
    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15),
        notes="Test purchase"
    )
    
    assert purchase.id is not None
    assert purchase.amount == Decimal("100.00")
    assert purchase.remaining_amount == Decimal("100.00")


def test_create_purchase_validation(purchase_service, sample_user, sample_site):
    """Test service validates purchase data"""
    with pytest.raises(ValueError, match="Purchase amount cannot be negative"):
        purchase_service.create_purchase(
            user_id=sample_user.id,
            site_id=sample_site.id,
            amount=Decimal("-100.00"),
            purchase_date=date.today()
        )


def test_update_purchase_allowed_fields(purchase_service, sample_purchase):
    """Test updating allowed fields on unconsumed purchase"""
    updated = purchase_service.update_purchase(
        sample_purchase.id,
        notes="Updated notes",
        purchase_time="15:00:00"
    )
    
    assert updated.notes == "Updated notes"
    assert updated.purchase_time == "15:00:00"


def test_update_purchase_protected_when_consumed(purchase_service, purchase_repo, sample_user, sample_site):
    """Test that critical fields are protected when purchase is consumed"""
    # Create purchase and consume part of it
    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15)
    )
    
    # Manually consume part (simulating FIFO allocation)
    purchase.remaining_amount = Decimal("60.00")
    purchase_repo.update(purchase)
    
    # Try to change protected field
    with pytest.raises(ValueError, match="Cannot change amount on a purchase that has been consumed"):
        purchase_service.update_purchase(
            purchase.id,
            amount=Decimal("200.00")
        )


def test_update_purchase_protect_user_id_when_consumed(purchase_service, purchase_repo, sample_user, sample_site, user_service):
    """Test that user_id is protected when consumed"""
    user2 = user_service.create_user(name="User 2")
    
    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today()
    )
    
    # Consume part
    purchase.remaining_amount = Decimal("50.00")
    purchase_repo.update(purchase)
    
    # Try to change user_id
    with pytest.raises(ValueError, match="Cannot change user_id on a consumed purchase unless forced"):
        purchase_service.update_purchase(purchase.id, user_id=user2.id)


def test_update_purchase_protect_site_id_when_consumed(purchase_service, purchase_repo, sample_user, sample_site, site_service):
    """Test that site_id is protected when consumed"""
    site2 = site_service.create_site(name="Site 2")
    
    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today()
    )
    
    # Consume part
    purchase.remaining_amount = Decimal("50.00")
    purchase_repo.update(purchase)
    
    # Try to change site_id
    with pytest.raises(ValueError, match="Cannot change site_id on a consumed purchase unless forced"):
        purchase_service.update_purchase(purchase.id, site_id=site2.id)


def test_update_purchase_force_user_site_change_when_consumed(
    purchase_service, purchase_repo, sample_user, sample_site, user_service, site_service
):
    """Test that user/site change is allowed when explicitly forced on consumed purchase"""
    user2 = user_service.create_user(name="User Force")
    site2 = site_service.create_site(name="Site Force")

    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today(),
    )

    # Consume part
    purchase.remaining_amount = Decimal("50.00")
    purchase_repo.update(purchase)

    updated = purchase_service.update_purchase(
        purchase.id,
        force_site_user_change=True,
        user_id=user2.id,
        site_id=site2.id,
        notes="moved",
    )

    assert updated.user_id == user2.id
    assert updated.site_id == site2.id


def test_delete_purchase_unconsumed(purchase_service, sample_purchase):
    """Test deleting unconsumed purchase succeeds"""
    purchase_id = sample_purchase.id
    purchase_service.delete_purchase(purchase_id)
    
    # Verify deleted
    retrieved = purchase_service.get_purchase(purchase_id)
    assert retrieved is None


def test_delete_purchase_consumed_fails(purchase_service, purchase_repo, sample_user, sample_site):
    """Test that consumed purchase cannot be deleted"""
    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today()
    )
    
    # Consume part
    purchase.remaining_amount = Decimal("60.00")
    purchase_repo.update(purchase)
    
    # Try to delete
    with pytest.raises(ValueError, match="Cannot delete purchase that has been consumed"):
        purchase_service.delete_purchase(purchase.id)


def test_list_user_purchases(purchase_service, sample_user, sample_site):
    """Test listing purchases by user"""
    purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today()
    )
    purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("200.00"),
        purchase_date=date.today()
    )
    
    purchases = purchase_service.list_user_purchases(sample_user.id)
    assert len(purchases) == 2


def test_list_site_purchases(purchase_service, sample_user, sample_site):
    """Test listing purchases by site"""
    purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today()
    )
    
    purchases = purchase_service.list_site_purchases(sample_site.id)
    assert len(purchases) >= 1


def test_list_purchases_filtered(purchase_service, sample_user, sample_site):
    """Test listing purchases with filters"""
    purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today()
    )
    
    purchases = purchase_service.list_purchases(
        user_id=sample_user.id,
        site_id=sample_site.id
    )
    assert len(purchases) >= 1


def test_get_available_for_allocation(purchase_service, sample_user, sample_site, purchase_repo):
    """Test getting purchases available for FIFO allocation"""
    # Create mix of consumed and available purchases
    p1 = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    )
    p2 = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("200.00"),
        purchase_date=date(2026, 1, 2)
    )
    
    # Fully consume p1
    p1.remaining_amount = Decimal("0.00")
    purchase_repo.update(p1)
    
    available = purchase_service.get_available_for_allocation(
        sample_user.id,
        sample_site.id
    )
    
    # Should only return p2
    assert len(available) == 1
    assert available[0].id == p2.id


def test_get_purchase(purchase_service, sample_purchase):
    """Test getting purchase by ID"""
    retrieved = purchase_service.get_purchase(sample_purchase.id)
    assert retrieved is not None
    assert retrieved.id == sample_purchase.id


def test_update_purchase_not_found(purchase_service):
    """Test updating non-existent purchase"""
    with pytest.raises(ValueError, match="Purchase .* not found"):
        purchase_service.update_purchase(99999, notes="Test")


def test_update_purchase_protected_purchase_date_when_consumed(purchase_service, purchase_repo, sample_user, sample_site):
    """Test that purchase_date is protected when purchase is consumed"""
    purchase = purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15)
    )
    
    # Consume part
    purchase.remaining_amount = Decimal("50.00")
    purchase_repo.update(purchase)
    
    with pytest.raises(ValueError, match="Cannot change purchase_date on a purchase that has been consumed"):
        purchase_service.update_purchase(purchase.id, purchase_date=date(2026, 2, 1))
