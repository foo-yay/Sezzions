"""
Unit tests for PurchaseRepository
"""
import pytest
from decimal import Decimal
from datetime import date
from models.purchase import Purchase


def test_create_purchase(purchase_repo, sample_user, sample_site):
    """Test creating a purchase in database"""
    purchase = Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15)
    )
    created_purchase = purchase_repo.create(purchase)
    
    assert created_purchase.id is not None
    assert created_purchase.amount == Decimal("100.00")
    assert created_purchase.remaining_amount == Decimal("100.00")


def test_get_purchase_by_id(purchase_repo, sample_user, sample_site):
    """Test getting purchase by ID"""
    purchase = Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        purchase_date=date.today()
    )
    created_purchase = purchase_repo.create(purchase)
    
    retrieved_purchase = purchase_repo.get_by_id(created_purchase.id)
    assert retrieved_purchase is not None
    assert retrieved_purchase.amount == Decimal("50.00")


def test_get_purchase_by_id_not_found(purchase_repo):
    """Test getting non-existent purchase returns None"""
    purchase = purchase_repo.get_by_id(9999)
    assert purchase is None


def test_get_purchases_by_user(purchase_repo, user_service, sample_site):
    """Test getting purchases by user"""
    user1 = user_service.create_user(name="User 1")
    user2 = user_service.create_user(name="User 2")
    
    purchase_repo.create(Purchase(
        user_id=user1.id, site_id=sample_site.id,
        amount=100, purchase_date=date.today()
    ))
    purchase_repo.create(Purchase(
        user_id=user1.id, site_id=sample_site.id,
        amount=200, purchase_date=date.today()
    ))
    purchase_repo.create(Purchase(
        user_id=user2.id, site_id=sample_site.id,
        amount=300, purchase_date=date.today()
    ))
    
    user1_purchases = purchase_repo.get_by_user(user1.id)
    assert len(user1_purchases) == 2


def test_get_purchases_by_site(purchase_repo, sample_user, site_service):
    """Test getting purchases by site"""
    site1 = site_service.create_site(name="Site 1")
    site2 = site_service.create_site(name="Site 2")
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=site1.id,
        amount=100, purchase_date=date.today()
    ))
    purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=site2.id,
        amount=200, purchase_date=date.today()
    ))
    
    site1_purchases = purchase_repo.get_by_site(site1.id)
    assert len(site1_purchases) == 1


def test_get_purchases_by_user_and_site(purchase_repo, user_service, site_service):
    """Test getting purchases by user and site"""
    user1 = user_service.create_user(name="User 1")
    site1 = site_service.create_site(name="Site 1")
    site2 = site_service.create_site(name="Site 2")
    
    purchase_repo.create(Purchase(
        user_id=user1.id, site_id=site1.id,
        amount=100, purchase_date=date.today()
    ))
    purchase_repo.create(Purchase(
        user_id=user1.id, site_id=site2.id,
        amount=200, purchase_date=date.today()
    ))
    
    user1_site1 = purchase_repo.get_by_user_and_site(user1.id, site1.id)
    assert len(user1_site1) == 1
    assert user1_site1[0].amount == Decimal("100.00")


def test_get_available_for_fifo(purchase_repo, sample_user, sample_site):
    """Test getting purchases available for FIFO allocation"""
    # Create purchases with different remaining amounts
    p1 = purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=sample_site.id,
        amount=Decimal("100.00"), purchase_date=date(2026, 1, 1),
        purchase_time="10:00:00", remaining_amount=Decimal("50.00")
    ))
    p2 = purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=sample_site.id,
        amount=Decimal("200.00"), purchase_date=date(2026, 1, 2),
        purchase_time="11:00:00", remaining_amount=Decimal("0.00")
    ))
    p3 = purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=sample_site.id,
        amount=Decimal("150.00"), purchase_date=date(2026, 1, 3),
        purchase_time="12:00:00", remaining_amount=Decimal("150.00")
    ))
    
    available = purchase_repo.get_available_for_fifo(sample_user.id, sample_site.id)
    
    # Should return only purchases with remaining_amount > 0, ordered by date/time
    assert len(available) == 2
    assert available[0].id == p1.id  # Oldest first
    assert available[1].id == p3.id


def test_update_purchase(purchase_repo, sample_user, sample_site):
    """Test updating purchase"""
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=sample_site.id,
        amount=Decimal("100.00"), purchase_date=date.today()
    ))
    
    # Consume part of purchase
    purchase.remaining_amount = Decimal("60.00")
    purchase.notes = "Partially consumed"
    
    updated_purchase = purchase_repo.update(purchase)
    assert updated_purchase.remaining_amount == Decimal("60.00")
    assert updated_purchase.notes == "Partially consumed"
    
    # Verify in database
    retrieved = purchase_repo.get_by_id(purchase.id)
    assert retrieved.remaining_amount == Decimal("60.00")


def test_delete_purchase(purchase_repo, sample_user, sample_site):
    """Test deleting purchase"""
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id, site_id=sample_site.id,
        amount=Decimal("100.00"), purchase_date=date.today()
    ))
    purchase_id = purchase.id
    
    purchase_repo.delete(purchase_id)
    
    # Verify deleted
    retrieved = purchase_repo.get_by_id(purchase_id)
    assert retrieved is None
