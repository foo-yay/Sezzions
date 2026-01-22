"""
Unit tests for RedemptionService
"""
import pytest
from decimal import Decimal
from datetime import date
from models.purchase import Purchase


def test_create_redemption_without_fifo(redemption_service, sample_user, sample_site):
    """Test creating redemption without FIFO allocation"""
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=False
    )
    
    assert redemption.id is not None
    assert redemption.amount == Decimal("100.00")
    assert redemption.cost_basis is None
    assert redemption.taxable_profit is None
    assert not redemption.has_fifo_allocation


def test_create_redemption_with_fifo(redemption_service, purchase_repo, sample_user, sample_site):
    """Test creating redemption with automatic FIFO allocation"""
    # Create purchase first
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Create redemption with FIFO
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("80.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    assert redemption.cost_basis == Decimal("80.00")
    assert redemption.taxable_profit == Decimal("0.00")
    assert redemption.has_fifo_allocation


def test_create_redemption_fifo_updates_purchases(
    redemption_service, purchase_repo, sample_user, sample_site
):
    """Test that FIFO allocation updates purchase remaining_amount"""
    # Create purchase
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Create redemption
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("60.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    # Verify purchase consumed
    updated_purchase = purchase_repo.get_by_id(purchase.id)
    assert updated_purchase.remaining_amount == Decimal("40.00")


def test_update_redemption_allowed_fields(redemption_service, sample_redemption):
    """Test updating allowed fields on redemption without FIFO"""
    updated = redemption_service.update_redemption(
        sample_redemption.id,
        notes="Updated notes",
        redemption_time="15:00:00"
    )
    
    assert updated.notes == "Updated notes"
    assert updated.redemption_time == "15:00:00"


def test_update_redemption_protected_when_fifo_allocated(
    redemption_service, purchase_repo, sample_user, sample_site
):
    """Test that critical fields protected when FIFO allocated"""
    # Create purchase and redemption with FIFO
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    # Try to change protected field
    with pytest.raises(ValueError, match="Cannot change amount on redemption with FIFO allocation"):
        redemption_service.update_redemption(
            redemption.id,
            amount=Decimal("75.00")
        )


def test_delete_redemption_without_fifo(redemption_service, sample_redemption):
    """Test deleting redemption without FIFO succeeds"""
    redemption_id = sample_redemption.id
    redemption_service.delete_redemption(redemption_id)
    
    # Verify deleted
    retrieved = redemption_service.get_redemption(redemption_id)
    assert retrieved is None


def test_delete_redemption_with_fifo_fails(
    redemption_service, purchase_repo, sample_user, sample_site
):
    """Test that redemption with FIFO cannot be deleted (needs allocation table)"""
    # Create purchase and redemption with FIFO
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    # Try to delete
    with pytest.raises(ValueError, match="Cannot delete redemption with FIFO allocation"):
        redemption_service.delete_redemption(redemption.id)


def test_list_user_redemptions(redemption_service, sample_user, sample_site):
    """Test listing redemptions by user"""
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        redemption_date=date.today(),
        apply_fifo=False
    )
    
    redemptions = redemption_service.list_user_redemptions(sample_user.id)
    assert len(redemptions) >= 1


def test_list_site_redemptions(redemption_service, sample_user, sample_site):
    """Test listing redemptions by site"""
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date.today(),
        apply_fifo=False
    )
    
    redemptions = redemption_service.list_site_redemptions(sample_site.id)
    assert len(redemptions) >= 1


def test_list_redemptions_filtered(redemption_service, sample_user, sample_site):
    """Test listing redemptions with filters"""
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date.today(),
        apply_fifo=False
    )
    
    redemptions = redemption_service.list_redemptions(user_id=sample_user.id, site_id=sample_site.id)
    assert len(redemptions) >= 1


def test_get_redemption(redemption_service, sample_redemption):
    """Test getting redemption by ID"""
    retrieved = redemption_service.get_redemption(sample_redemption.id)
    assert retrieved is not None
    assert retrieved.id == sample_redemption.id


def test_update_redemption_not_found(redemption_service):
    """Test updating non-existent redemption"""
    with pytest.raises(ValueError, match="Redemption .* not found"):
        redemption_service.update_redemption(99999, notes="Test")


def test_update_redemption_protected_user_id(redemption_service, purchase_repo, sample_user, sample_site):
    """Test that user_id is protected when FIFO allocated"""
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    with pytest.raises(ValueError, match="Cannot change user_id"):
        redemption_service.update_redemption(redemption.id, user_id=999)


def test_update_redemption_protected_site_id(redemption_service, purchase_repo, sample_user, sample_site):
    """Test that site_id is protected when FIFO allocated"""
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    with pytest.raises(ValueError, match="Cannot change site_id"):
        redemption_service.update_redemption(redemption.id, site_id=999)


def test_update_redemption_protected_date(redemption_service, purchase_repo, sample_user, sample_site):
    """Test that redemption_date is protected when FIFO allocated"""
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 15),
        apply_fifo=True
    )
    
    with pytest.raises(ValueError, match="Cannot change redemption_date"):
        redemption_service.update_redemption(redemption.id, redemption_date=date(2026, 2, 1))
