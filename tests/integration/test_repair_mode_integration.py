"""
Integration tests for Repair Mode in AppFacade (Issue #55)

These tests verify that CRUD operations conditionally rebuild or mark pairs stale
based on repair mode state.
"""
import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch
from app_facade import AppFacade
from services.repair_mode_service import RepairModeService


@pytest.fixture
def facade_with_repair_mode(test_db):
    """Setup AppFacade with repair mode service initialized"""
    facade = AppFacade(db_path=':memory:')
    
    # Wire repair mode service with mock settings
    mock_settings = Mock()
    mock_settings.data = {
        'repair_mode_enabled': False,
        'repair_mode_stale_pairs': {}
    }
    mock_settings.get = Mock(side_effect=lambda key, default=None: mock_settings.data.get(key, default))
    
    def mock_set(key, value):
        mock_settings.data[key] = value
    
    mock_settings.set = Mock(side_effect=mock_set)
    
    facade.repair_mode_service = RepairModeService(mock_settings)
    
    return facade, mock_settings


class TestRepairModeNormalMode:
    """Test that normal mode rebuilds immediately"""
    
    def test_create_purchase_rebuilds_in_normal_mode(self, facade_with_repair_mode):
        """Creating purchase should rebuild derived data in normal mode"""
        facade, _ = facade_with_repair_mode
        
        # Normal mode (repair mode disabled)
        assert facade.repair_mode_service.is_enabled() is False
        
        # Create purchase
        purchase = facade.create_purchase(
            user_id=1,
            site_id=1,
            purchase_date=date(2026, 1, 1),
            purchase_time="10:00",
            cards=50,
            amount=50.00
        )
        
        assert purchase.id is not None
        
        # Should have immediately rebuilt derived data
        # Verify unrealized positions exist
        positions = facade.unrealized_service.get_unrealized_for_user_site(1, 1)
        assert len(positions) > 0


class TestRepairModeEnabled:
    """Test that repair mode marks pairs stale instead of rebuilding"""
    
    def test_create_purchase_marks_stale_in_repair_mode(self, facade_with_repair_mode):
        """Creating purchase should mark pair stale in repair mode"""
        facade, mock_settings = facade_with_repair_mode
        
        # Enable repair mode
        facade.repair_mode_service.set_enabled(True)
        
        assert facade.repair_mode_service.is_enabled() is True
        
        # Create purchase
        facade.create_purchase(
            user_id=1,
            site_id=1,
            purchase_date=date(2026, 1, 1),
            purchase_time="10:00",
            cards=50,
            amount=50.00
        )
        
        # Should have marked pair stale
        stale_pairs = facade.repair_mode_service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].user_id == 1
        assert stale_pairs[0].site_id == 1
    
    def test_cross_pair_move_marks_both_pairs_stale(self, facade_with_repair_mode):
        """Moving purchase to different site should mark both pairs stale"""
        facade, mock_settings = facade_with_repair_mode
        
        # Create purchase in normal mode first
        purchase = facade.create_purchase(
            user_id=1,
            site_id=1,
            purchase_date=date(2026, 1, 1),
            purchase_time="10:00",
            cards=50,
            amount=50.00
        )
        
        # Enable repair mode
        facade.repair_mode_service.set_enabled(True)
        
        # Move purchase to different site
        facade.update_purchase(
            purchase_id=purchase.id,
            user_id=1,
            site_id=2,  # Changed site
            purchase_date=date(2026, 1, 1),
            purchase_time="10:00",
            cards=50,
            amount=50.00
        )
        
        # Should have marked both old and new pairs stale
        stale_pairs = facade.repair_mode_service.get_stale_pairs()
        assert len(stale_pairs) == 2
        pair_keys = {(p.user_id, p.site_id) for p in stale_pairs}
        assert (1, 1) in pair_keys  # Old pair
        assert (1, 2) in pair_keys  # New pair
