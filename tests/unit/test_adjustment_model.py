"""
Tests for Adjustment model
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from models.adjustment import Adjustment, AdjustmentType


class TestAdjustmentModel:
    """Test Adjustment model validation and behavior"""
    
    def test_basis_adjustment_creation(self):
        """Test creating a basis adjustment"""
        adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 1),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("100.00"),
            reason="Correcting purchase amount"
        )
        
        assert adj.user_id == 1
        assert adj.site_id == 1
        assert adj.type == AdjustmentType.BASIS_USD_CORRECTION
        assert adj.delta_basis_usd == Decimal("100.00")
        assert adj.effective_time == "00:00:00"
        assert not adj.is_deleted()
    
    def test_checkpoint_adjustment_creation(self):
        """Test creating a balance checkpoint adjustment"""
        adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 1),
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            checkpoint_redeemable_sc=Decimal("900.00"),
            reason="Known balance from site screenshot"
        )
        
        assert adj.type == AdjustmentType.BALANCE_CHECKPOINT_CORRECTION
        assert adj.checkpoint_total_sc == Decimal("1000.00")
        assert adj.checkpoint_redeemable_sc == Decimal("900.00")
    
    def test_effective_time_normalization(self):
        """Test that missing effective_time is normalized to 00:00:00"""
        adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 1),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="Test",
            effective_time=None
        )
        
        assert adj.effective_time == "00:00:00"
    
    def test_type_string_conversion(self):
        """Test that type string is converted to enum"""
        adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 1),
            type="BASIS_USD_CORRECTION",
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        assert isinstance(adj.type, AdjustmentType)
        assert adj.type == AdjustmentType.BASIS_USD_CORRECTION
    
    def test_decimal_field_conversion(self):
        """Test that numeric fields are converted to Decimal"""
        adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 1),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=100.00,  # float input
            reason="Test"
        )
        
        assert isinstance(adj.delta_basis_usd, Decimal)
        assert adj.delta_basis_usd == Decimal("100.00")
    
    def test_invalid_user_id(self):
        """Test that invalid user_id raises ValueError"""
        with pytest.raises(ValueError, match="Valid user_id is required"):
            Adjustment(
                user_id=0,
                site_id=1,
                effective_date=date(2026, 1, 1),
                type=AdjustmentType.BASIS_USD_CORRECTION,
                delta_basis_usd=Decimal("50.00"),
                reason="Test"
            )
    
    def test_invalid_site_id(self):
        """Test that invalid site_id raises ValueError"""
        with pytest.raises(ValueError, match="Valid site_id is required"):
            Adjustment(
                user_id=1,
                site_id=-1,
                effective_date=date(2026, 1, 1),
                type=AdjustmentType.BASIS_USD_CORRECTION,
                delta_basis_usd=Decimal("50.00"),
                reason="Test"
            )
    
    def test_missing_reason(self):
        """Test that missing reason raises ValueError"""
        with pytest.raises(ValueError, match="Reason is required"):
            Adjustment(
                user_id=1,
                site_id=1,
                effective_date=date(2026, 1, 1),
                type=AdjustmentType.BASIS_USD_CORRECTION,
                delta_basis_usd=Decimal("50.00"),
                reason=""
            )
    
    def test_basis_adjustment_zero_delta(self):
        """Test that basis adjustment with zero delta raises ValueError"""
        with pytest.raises(ValueError, match="Basis adjustment delta cannot be zero"):
            Adjustment(
                user_id=1,
                site_id=1,
                effective_date=date(2026, 1, 1),
                type=AdjustmentType.BASIS_USD_CORRECTION,
                delta_basis_usd=Decimal("0.00"),
                reason="Test"
            )
    
    def test_checkpoint_adjustment_zero_balances(self):
        """Test that checkpoint adjustment with all zero balances raises ValueError"""
        with pytest.raises(ValueError, match="Balance checkpoint must specify at least one non-zero balance"):
            Adjustment(
                user_id=1,
                site_id=1,
                effective_date=date(2026, 1, 1),
                type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
                checkpoint_total_sc=Decimal("0.00"),
                checkpoint_redeemable_sc=Decimal("0.00"),
                reason="Test"
            )
    
    def test_soft_delete_status(self):
        """Test is_deleted() method"""
        adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 1),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        assert not adj.is_deleted()
        
        adj.deleted_at = datetime.now()
        assert adj.is_deleted()
    
    def test_string_representation(self):
        """Test __str__ method"""
        basis_adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("100.00"),
            reason="Test"
        )
        
        assert "Basis Adjustment" in str(basis_adj)
        assert "$100.00" in str(basis_adj)
        assert "2026-01-15" in str(basis_adj)
        
        checkpoint_adj = Adjustment(
            user_id=1,
            site_id=1,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            reason="Test"
        )
        
        assert "Balance Checkpoint" in str(checkpoint_adj)
        assert "2026-01-15" in str(checkpoint_adj)
