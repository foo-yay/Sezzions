"""
Tests for Adjustment repository
"""
import pytest
from decimal import Decimal
from datetime import date
from repositories.database import DatabaseManager
from repositories.adjustment_repository import AdjustmentRepository
from repositories.user_repository import UserRepository
from repositories.site_repository import SiteRepository
from models.adjustment import Adjustment, AdjustmentType
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


class TestAdjustmentRepository:
    """Test Adjustment repository operations"""
    
    def test_create_basis_adjustment(self, adjustment_repo, test_user, test_site):
        """Test creating a basis adjustment"""
        adj = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            effective_time="10:30:00",
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("100.00"),
            reason="Test basis correction",
            notes="Test notes"
        )
        
        created = adjustment_repo.create(adj)
        
        assert created.id is not None
        assert created.user_id == test_user.id
        assert created.site_id == test_site.id
        assert created.delta_basis_usd == Decimal("100.00")
    
    def test_create_checkpoint_adjustment(self, adjustment_repo, test_user, test_site):
        """Test creating a checkpoint adjustment"""
        adj = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            checkpoint_redeemable_sc=Decimal("900.00"),
            reason="Known balance"
        )
        
        created = adjustment_repo.create(adj)
        
        assert created.id is not None
        assert created.checkpoint_total_sc == Decimal("1000.00")
        assert created.checkpoint_redeemable_sc == Decimal("900.00")
    
    def test_get_by_id(self, adjustment_repo, test_user, test_site):
        """Test retrieving adjustment by ID"""
        adj = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        created = adjustment_repo.create(adj)
        retrieved = adjustment_repo.get_by_id(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.delta_basis_usd == Decimal("50.00")
    
    def test_get_all_filters(self, adjustment_repo, test_user, test_site):
        """Test get_all with various filters"""
        # Create multiple adjustments
        adj1 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="First"
        )
        adj2 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 20),
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            reason="Second"
        )
        
        adjustment_repo.create(adj1)
        adjustment_repo.create(adj2)
        
        # Filter by type
        basis_only = adjustment_repo.get_all(adjustment_type=AdjustmentType.BASIS_USD_CORRECTION)
        assert len(basis_only) == 1
        assert basis_only[0].type == AdjustmentType.BASIS_USD_CORRECTION
        
        # Filter by date range
        date_filtered = adjustment_repo.get_all(
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 25)
        )
        assert len(date_filtered) == 1
        assert date_filtered[0].effective_date == date(2026, 1, 20)
    
    def test_get_by_user_and_site(self, adjustment_repo, user_repo, site_repo, test_user, test_site):
        """Test get_by_user_and_site"""
        # Create another user/site
        other_user = user_repo.create(User(name="Other User"))
        other_site = site_repo.create(Site(name="Other Site"))
        
        # Create adjustments
        adj1 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="User1/Site1"
        )
        adj2 = Adjustment(
            user_id=other_user.id,
            site_id=other_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("100.00"),
            reason="User2/Site2"
        )
        
        adjustment_repo.create(adj1)
        adjustment_repo.create(adj2)
        
        results = adjustment_repo.get_by_user_and_site(test_user.id, test_site.id)
        
        assert len(results) == 1
        assert results[0].user_id == test_user.id
        assert results[0].site_id == test_site.id

    def test_get_active_checkpoints_after(self, adjustment_repo, test_user, test_site):
        """Test get_active_checkpoints_after returns strictly after cutoff and ASC order."""
        adj1 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            effective_time="10:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            reason="Early",
        )
        adj2 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            effective_time="15:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1500.00"),
            reason="Later",
        )
        adjustment_repo.create(adj1)
        adjustment_repo.create(adj2)

        results = adjustment_repo.get_active_checkpoints_after(
            test_user.id,
            test_site.id,
            date(2026, 1, 10),
            "10:00:00",
        )

        assert len(results) == 1
        assert results[0].checkpoint_total_sc == Decimal("1500.00")

    def test_get_active_adjustments_in_window_inclusive(self, adjustment_repo, test_user, test_site):
        """Test inclusive window bounds include both start and end checkpoints."""
        cp_start = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 1),
            effective_time="00:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            reason="Start",
        )
        basis = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            effective_time="12:00:00",
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("25.00"),
            reason="Mid",
        )
        cp_end = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 2, 1),
            effective_time="00:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("2000.00"),
            reason="End",
        )
        adjustment_repo.create(cp_start)
        adjustment_repo.create(basis)
        adjustment_repo.create(cp_end)

        results = adjustment_repo.get_active_adjustments_in_window(
            user_id=test_user.id,
            site_id=test_site.id,
            start_date=date(2026, 1, 1),
            start_time="00:00:00",
            end_date=date(2026, 2, 1),
            end_time="00:00:00",
        )

        assert len(results) == 3
        assert results[0].type == AdjustmentType.BALANCE_CHECKPOINT_CORRECTION
        assert results[-1].type == AdjustmentType.BALANCE_CHECKPOINT_CORRECTION
    
    def test_get_active_checkpoints_before(self, adjustment_repo, test_user, test_site):
        """Test get_active_checkpoints_before"""
        # Create checkpoints at different times
        adj1 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            effective_time="10:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            reason="Early"
        )
        adj2 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            effective_time="15:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1500.00"),
            reason="Later"
        )
        adj3 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 20),
            effective_time="10:00:00",
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("2000.00"),
            reason="Latest"
        )
        
        adjustment_repo.create(adj1)
        adjustment_repo.create(adj2)
        adjustment_repo.create(adj3)
        
        # Get checkpoints before Jan 16
        results = adjustment_repo.get_active_checkpoints_before(
            test_user.id,
            test_site.id,
            date(2026, 1, 16),
            "00:00:00"
        )
        
        assert len(results) == 2
        # Should be ordered DESC by date/time
        assert results[0].checkpoint_total_sc == Decimal("1500.00")
        assert results[1].checkpoint_total_sc == Decimal("1000.00")
    
    def test_get_active_basis_adjustments(self, adjustment_repo, test_user, test_site):
        """Test get_active_basis_adjustments"""
        # Create basis adjustments
        adj1 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 10),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="First"
        )
        adj2 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("-25.00"),
            reason="Second"
        )
        # Also create a checkpoint (should not be included)
        adj3 = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 12),
            type=AdjustmentType.BALANCE_CHECKPOINT_CORRECTION,
            checkpoint_total_sc=Decimal("1000.00"),
            reason="Checkpoint"
        )
        
        adjustment_repo.create(adj1)
        adjustment_repo.create(adj2)
        adjustment_repo.create(adj3)
        
        results = adjustment_repo.get_active_basis_adjustments(test_user.id, test_site.id)
        
        assert len(results) == 2
        assert all(r.type == AdjustmentType.BASIS_USD_CORRECTION for r in results)
        # Should be ordered ASC by date/time
        assert results[0].delta_basis_usd == Decimal("50.00")
        assert results[1].delta_basis_usd == Decimal("-25.00")
    
    def test_soft_delete(self, adjustment_repo, test_user, test_site):
        """Test soft delete"""
        adj = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        created = adjustment_repo.create(adj)
        
        # Soft delete
        success = adjustment_repo.soft_delete(created.id, "Testing delete")
        assert success
        
        # Verify not in normal queries
        all_active = adjustment_repo.get_all()
        assert len(all_active) == 0
        
        # Verify in queries with include_deleted
        all_including_deleted = adjustment_repo.get_all(include_deleted=True)
        assert len(all_including_deleted) == 1
        assert all_including_deleted[0].deleted_at is not None
        assert all_including_deleted[0].deleted_reason == "Testing delete"
    
    def test_restore(self, adjustment_repo, test_user, test_site):
        """Test restoring a soft-deleted adjustment"""
        adj = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="Test"
        )
        
        created = adjustment_repo.create(adj)
        adjustment_repo.soft_delete(created.id, "Testing")
        
        # Restore
        success = adjustment_repo.restore(created.id)
        assert success
        
        # Verify back in normal queries
        all_active = adjustment_repo.get_all()
        assert len(all_active) == 1
        assert all_active[0].deleted_at is None
    
    def test_update_notes(self, adjustment_repo, test_user, test_site):
        """Test updating adjustment notes"""
        adj = Adjustment(
            user_id=test_user.id,
            site_id=test_site.id,
            effective_date=date(2026, 1, 15),
            type=AdjustmentType.BASIS_USD_CORRECTION,
            delta_basis_usd=Decimal("50.00"),
            reason="Test",
            notes="Original notes"
        )
        
        created = adjustment_repo.create(adj)
        created.notes = "Updated notes"
        
        success = adjustment_repo.update(created)
        assert success
        
        retrieved = adjustment_repo.get_by_id(created.id)
        assert retrieved.notes == "Updated notes"
