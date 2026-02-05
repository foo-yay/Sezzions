"""
Tests for Adjustment service
"""
import pytest
from decimal import Decimal
from datetime import date
from repositories.database import DatabaseManager
from repositories.adjustment_repository import AdjustmentRepository
from repositories.user_repository import UserRepository
from repositories.site_repository import SiteRepository
from services.adjustment_service import AdjustmentService
from models.adjustment import AdjustmentType
from models.user import User
from models.site import Site


@pytest.fixture
def db():
    """Create test database"""
    db = DatabaseManager(":memory:")
    yield db
    db.close()


@pytest.fixture
def adjustment_repo(db):
    """Create adjustment repository"""
    return AdjustmentRepository(db)


@pytest.fixture
def adjustment_service(adjustment_repo):
    """Create adjustment service"""
    return AdjustmentService(adjustment_repo)


@pytest.fixture
def user_repo(db):
    """Create user repository"""
    return UserRepository(db)


@pytest.fixture
def site_repo(db):
    """Create site repository"""
    return SiteRepository(db)


@pytest.fixture
def test_user(user_repo):
    """Create test user"""
    user = User(name="Test User")
    return user_repo.create(user)


@pytest.fixture
def test_site(site_repo):
    """Create test site"""
    site = Site(name="Test Site")
    return site_repo.create(site)


class TestAdjustmentService:
    """Test Adjustment service business logic"""
    
    def test_create_basis_adjustment(self, adjustment_service, test_user, test_site):
        """Test creating a basis adjustment through service"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("100.00"),
            reason="Correcting purchase amount",
            notes="Test notes"
        )
        
        assert adj.id is not None
        assert adj.type == AdjustmentType.BASIS_USD_CORRECTION
        assert adj.delta_basis_usd == Decimal("100.00")
        assert adj.reason == "Correcting purchase amount"
    
    def test_create_balance_checkpoint(self, adjustment_service, test_user, test_site):
        """Test creating a balance checkpoint through service"""
        adj = adjustment_service.create_balance_checkpoint(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            checkpoint_total_sc=Decimal("1000.00"),
            checkpoint_redeemable_sc=Decimal("900.00"),
            reason="Known balance from screenshot"
        )
        
        assert adj.id is not None
        assert adj.type == AdjustmentType.BALANCE_CHECKPOINT_CORRECTION
        assert adj.checkpoint_total_sc == Decimal("1000.00")
        assert adj.checkpoint_redeemable_sc == Decimal("900.00")
    
    def test_create_basis_adjustment_zero_delta_fails(self, adjustment_service, test_user, test_site):
        """Test that zero delta basis adjustment is rejected"""
        with pytest.raises(ValueError, match="Basis adjustment delta cannot be zero"):
            adjustment_service.create_basis_adjustment(
                user_id=test_user.id,
                site_id=test_site.id,
                effective_date=date(2026, 1, 15),
                delta_basis_usd=Decimal("0.00"),
                reason="Test"
            )
    
    def test_create_checkpoint_zero_balances_fails(self, adjustment_service, test_user, test_site):
        """Test that checkpoint with all zero balances is rejected"""
        with pytest.raises(ValueError, match="Balance checkpoint must specify at least one non-zero balance"):
            adjustment_service.create_balance_checkpoint(
                user_id=test_user.id,
                site_id=test_site.id,
                effective_date=date(2026, 1, 15),
                checkpoint_total_sc=Decimal("0.00"),
                checkpoint_redeemable_sc=Decimal("0.00"),
                reason="Test"
            )
    
    def test_get_by_id(self, adjustment_service, test_user, test_site):
        """Test retrieving adjustment by ID"""
        created = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        retrieved = adjustment_service.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_get_latest_checkpoint_before(self, adjustment_service, test_user, test_site):
        """Test getting the most recent checkpoint before a cutoff"""
        # Create multiple checkpoints
        adj1 = adjustment_service.create_balance_checkpoint(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            checkpoint_total_sc=Decimal("1000.00"),
            checkpoint_redeemable_sc=Decimal("900.00"),
            reason="Early"
        )
        adj2 = adjustment_service.create_balance_checkpoint(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            checkpoint_total_sc=Decimal("1500.00"),
            checkpoint_redeemable_sc=Decimal("1400.00"),
            reason="Later"
        )
        adj3 = adjustment_service.create_balance_checkpoint(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 20),
            checkpoint_total_sc=Decimal("2000.00"),
            checkpoint_redeemable_sc=Decimal("1900.00"),
            reason="Latest"
        )
        
        # Get latest before Jan 16
        latest = adjustment_service.get_latest_checkpoint_before(
            test_user.id,
            test_site.id,
            date(2026, 1, 16)
        )
        
        assert latest is not None
        assert latest.id == adj2.id
        assert latest.checkpoint_total_sc == Decimal("1500.00")
    
    def test_get_latest_checkpoint_none(self, adjustment_service, test_user, test_site):
        """Test that None is returned when no checkpoint exists before cutoff"""
        # Create checkpoint after cutoff
        adjustment_service.create_balance_checkpoint(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 20),
            checkpoint_total_sc=Decimal("1000.00"),
            checkpoint_redeemable_sc=Decimal("900.00"),
            reason="Test"
        )
        
        # Query before the checkpoint
        latest = adjustment_service.get_latest_checkpoint_before(
            test_user.id,
            test_site.id,
            date(2026, 1, 15)
        )
        
        assert latest is None
    
    def test_get_active_basis_adjustments(self, adjustment_service, test_user, test_site):
        """Test getting all active basis adjustments"""
        adj1 = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            delta_basis_usd=Decimal("50.00"),
            reason="First"
        )
        adj2 = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("-25.00"),
            reason="Second"
        )
        
        adjustments = adjustment_service.get_active_basis_adjustments(
            test_user.id,
            test_site.id
        )
        
        assert len(adjustments) == 2
        # Should be ordered ASC by date
        assert adjustments[0].id == adj1.id
        assert adjustments[1].id == adj2.id
    
    def test_update_notes(self, adjustment_service, test_user, test_site):
        """Test updating adjustment notes"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test",
            notes="Original notes"
        )
        
        success = adjustment_service.update_notes(adj.id, "Updated notes")
        assert success
        
        retrieved = adjustment_service.get_by_id(adj.id)
        assert retrieved.notes == "Updated notes"
    
    def test_update_notes_deleted_fails(self, adjustment_service, test_user, test_site):
        """Test that updating notes on deleted adjustment fails"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        adjustment_service.soft_delete(adj.id, "Testing")
        
        with pytest.raises(ValueError, match="Cannot update a deleted adjustment"):
            adjustment_service.update_notes(adj.id, "New notes")
    
    def test_soft_delete(self, adjustment_service, test_user, test_site):
        """Test soft deleting an adjustment"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        success = adjustment_service.soft_delete(adj.id, "Testing delete")
        assert success
        
        # Verify not in active list
        active = adjustment_service.get_by_user_and_site(
            test_user.id,
            test_site.id,
            include_deleted=False
        )
        assert len(active) == 0
        
        # Verify in deleted list
        all_including_deleted = adjustment_service.get_by_user_and_site(
            test_user.id,
            test_site.id,
            include_deleted=True
        )
        assert len(all_including_deleted) == 1
        assert all_including_deleted[0].is_deleted()
    
    def test_soft_delete_missing_reason_fails(self, adjustment_service, test_user, test_site):
        """Test that soft delete without reason fails"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        with pytest.raises(ValueError, match="Deletion reason is required"):
            adjustment_service.soft_delete(adj.id, "")
    
    def test_soft_delete_already_deleted_fails(self, adjustment_service, test_user, test_site):
        """Test that deleting already-deleted adjustment fails"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        adjustment_service.soft_delete(adj.id, "First delete")
        
        with pytest.raises(ValueError, match="Adjustment is already deleted"):
            adjustment_service.soft_delete(adj.id, "Second delete")
    
    def test_restore(self, adjustment_service, test_user, test_site):
        """Test restoring a soft-deleted adjustment"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        adjustment_service.soft_delete(adj.id, "Testing")
        success = adjustment_service.restore(adj.id)
        assert success
        
        # Verify back in active list
        active = adjustment_service.get_by_user_and_site(
            test_user.id,
            test_site.id,
            include_deleted=False
        )
        assert len(active) == 1
        assert not active[0].is_deleted()
    
    def test_restore_not_deleted_fails(self, adjustment_service, test_user, test_site):
        """Test that restoring non-deleted adjustment fails"""
        adj = adjustment_service.create_basis_adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        with pytest.raises(ValueError, match="Adjustment is not deleted"):
            adjustment_service.restore(adj.id)
