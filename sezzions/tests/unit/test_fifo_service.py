"""
Unit tests for FIFOService - CRITICAL ACCOUNTING LOGIC
"""
import pytest
from decimal import Decimal
from datetime import date
from models.purchase import Purchase


def test_fifo_calculate_cost_basis_single_purchase(fifo_service, purchase_repo, sample_user, sample_site):
    """Test FIFO with single purchase covering full redemption"""
    # Create purchase
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Calculate FIFO for $50 redemption
    cost_basis, profit, allocations = fifo_service.calculate_cost_basis(
        sample_user.id,
        sample_site.id,
        Decimal("50.00")
    )
    
    assert cost_basis == Decimal("50.00")
    assert profit == Decimal("0.00")
    assert len(allocations) == 1
    assert allocations[0] == (purchase.id, Decimal("50.00"))


def test_fifo_calculate_cost_basis_multiple_purchases(fifo_service, purchase_repo, sample_user, sample_site):
    """Test FIFO across multiple purchases"""
    # Create purchases
    p1 = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        purchase_date=date(2026, 1, 1)
    ))
    p2 = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("75.00"),
        purchase_date=date(2026, 1, 2)
    ))
    
    # Redeem $100 (should use all of p1 + $50 from p2)
    cost_basis, profit, allocations = fifo_service.calculate_cost_basis(
        sample_user.id,
        sample_site.id,
        Decimal("100.00")
    )
    
    assert cost_basis == Decimal("100.00")
    assert profit == Decimal("0.00")
    assert len(allocations) == 2
    assert allocations[0] == (p1.id, Decimal("50.00"))
    assert allocations[1] == (p2.id, Decimal("50.00"))


def test_fifo_insufficient_purchases(fifo_service, purchase_repo, sample_user, sample_site):
    """Test FIFO fails when insufficient purchases"""
    # Create small purchase
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Try to redeem more than available
    with pytest.raises(ValueError, match="Insufficient purchases"):
        fifo_service.calculate_cost_basis(
            sample_user.id,
            sample_site.id,
            Decimal("100.00")
        )


def test_fifo_apply_allocation(fifo_service, purchase_repo, sample_user, sample_site):
    """Test applying FIFO allocation reduces purchase remaining_amount"""
    # Create purchase
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Apply allocation
    allocations = [(purchase.id, Decimal("60.00"))]
    fifo_service.apply_allocation(allocations)
    
    # Verify purchase updated
    updated_purchase = purchase_repo.get_by_id(purchase.id)
    assert updated_purchase.remaining_amount == Decimal("40.00")
    assert updated_purchase.consumed_amount == Decimal("60.00")


def test_fifo_reverse_allocation(fifo_service, purchase_repo, sample_user, sample_site):
    """Test reversing FIFO allocation restores purchase remaining_amount"""
    # Create purchase and consume part
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        remaining_amount=Decimal("40.00")
    ))
    
    # Reverse allocation
    allocations = [(purchase.id, Decimal("60.00"))]
    fifo_service.reverse_allocation(allocations)
    
    # Verify purchase restored
    updated_purchase = purchase_repo.get_by_id(purchase.id)
    assert updated_purchase.remaining_amount == Decimal("100.00")


def test_fifo_respects_chronological_order(fifo_service, purchase_repo, sample_user, sample_site):
    """Test FIFO uses oldest purchases first"""
    # Create purchases (out of order)
    p_middle = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 2)
    ))
    p_oldest = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    p_newest = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 3)
    ))
    
    # Redeem $150 (should use oldest first)
    cost_basis, profit, allocations = fifo_service.calculate_cost_basis(
        sample_user.id,
        sample_site.id,
        Decimal("150.00")
    )
    
    # Verify oldest purchase used first
    assert allocations[0][0] == p_oldest.id
    assert allocations[1][0] == p_middle.id


def test_fifo_skips_consumed_purchases(fifo_service, purchase_repo, sample_user, sample_site):
    """Test FIFO skips fully consumed purchases"""
    # Create purchases
    p1 = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        remaining_amount=Decimal("0.00")  # Fully consumed
    ))
    p2 = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 2)
    ))
    
    # Calculate FIFO
    cost_basis, profit, allocations = fifo_service.calculate_cost_basis(
        sample_user.id,
        sample_site.id,
        Decimal("50.00")
    )
    
    # Should only use p2
    assert len(allocations) == 1
    assert allocations[0][0] == p2.id


def test_fifo_apply_allocation_negative_remaining(fifo_service, purchase_repo, sample_user, sample_site):
    """Test that applying allocation with amount > remaining raises error"""
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        remaining_amount=Decimal("30.00")
    ))
    
    # Try to allocate more than remaining
    allocations = [(purchase.id, Decimal("50.00"))]
    
    with pytest.raises(ValueError, match="Cannot allocate"):
        fifo_service.apply_allocation(allocations)


def test_fifo_reverse_allocation_exceeds_original(fifo_service, purchase_repo, sample_user, sample_site):
    """Test that reversing allocation that exceeds original amount raises error"""
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        remaining_amount=Decimal("90.00")
    ))
    
    # Try to reverse more than was consumed (would exceed original amount)
    allocations = [(purchase.id, Decimal("20.00"))]
    
    with pytest.raises(ValueError, match="Would exceed original amount"):
        fifo_service.reverse_allocation(allocations)
