"""
Tests for RepairModeService (Issue #55)
"""
import pytest
from datetime import datetime, timedelta
from services.repair_mode_service import RepairModeService, StalePair


class MockSettings:
    """Mock settings for testing"""
    def __init__(self):
        self.data = {
            'repair_mode_enabled': False,
            'repair_mode_stale_pairs': {}
        }
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value


@pytest.fixture
def settings():
    """Create mock settings"""
    return MockSettings()


@pytest.fixture
def service(settings):
    """Create RepairModeService with mock settings"""
    return RepairModeService(settings)


class TestRepairModeToggle:
    """Test enable/disable functionality"""
    
    def test_initial_state_disabled(self, service):
        """Repair mode should be disabled by default"""
        assert service.is_enabled() is False
    
    def test_enable_repair_mode(self, service):
        """Should enable repair mode"""
        service.set_enabled(True)
        assert service.is_enabled() is True
    
    def test_disable_repair_mode(self, service):
        """Should disable repair mode"""
        service.set_enabled(True)
        assert service.is_enabled() is True
        
        service.set_enabled(False)
        assert service.is_enabled() is False
    
    def test_enable_persists_to_settings(self, service, settings):
        """Enabled state should persist to settings"""
        service.set_enabled(True)
        assert settings.get('repair_mode_enabled') is True
    
    def test_disable_persists_to_settings(self, service, settings):
        """Disabled state should persist to settings"""
        service.set_enabled(True)
        service.set_enabled(False)
        assert settings.get('repair_mode_enabled') is False


class TestStalePairTracking:
    """Test stale pair marking and clearing"""
    
    def test_mark_pair_stale(self, service):
        """Should mark a pair as stale"""
        service.mark_pair_stale(
            user_id=1,
            site_id=2,
            from_date="2026-01-01",
            from_time="10:00",
            reason="purchase created"
        )
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].user_id == 1
        assert stale_pairs[0].site_id == 2
        assert stale_pairs[0].from_date == "2026-01-01"
        assert stale_pairs[0].from_time == "10:00"
        assert "purchase created" in stale_pairs[0].reasons
    
    def test_mark_same_pair_twice_accumulates_reasons(self, service):
        """Marking same pair twice should accumulate reasons"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "purchase created")
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "redemption created")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert len(stale_pairs[0].reasons) == 2
        assert "purchase created" in stale_pairs[0].reasons
        assert "redemption created" in stale_pairs[0].reasons
    
    def test_mark_same_pair_updates_boundary(self, service):
        """Marking same pair with earlier boundary should update boundary"""
        service.mark_pair_stale(1, 2, "2026-01-15", "10:00", "first edit")
        service.mark_pair_stale(1, 2, "2026-01-10", "08:00", "second edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].from_date == "2026-01-10"
        assert stale_pairs[0].from_time == "08:00"
    
    def test_mark_same_pair_keeps_earlier_boundary(self, service):
        """Marking same pair with later boundary should keep earlier boundary"""
        service.mark_pair_stale(1, 2, "2026-01-10", "08:00", "first edit")
        service.mark_pair_stale(1, 2, "2026-01-15", "10:00", "second edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].from_date == "2026-01-10"
        assert stale_pairs[0].from_time == "08:00"
    
    def test_mark_multiple_pairs(self, service):
        """Should track multiple stale pairs independently"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "user1 site2 edit")
        service.mark_pair_stale(1, 3, "2026-01-02", "11:00", "user1 site3 edit")
        service.mark_pair_stale(2, 2, "2026-01-03", "12:00", "user2 site2 edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 3
        
        # Verify each pair is tracked separately
        pair_keys = {(p.user_id, p.site_id) for p in stale_pairs}
        assert (1, 2) in pair_keys
        assert (1, 3) in pair_keys
        assert (2, 2) in pair_keys
    
    def test_clear_pair(self, service):
        """Should clear a specific stale pair"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit")
        service.mark_pair_stale(1, 3, "2026-01-02", "11:00", "edit")
        
        service.clear_pair(1, 2)
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].user_id == 1
        assert stale_pairs[0].site_id == 3
    
    def test_clear_nonexistent_pair_no_error(self, service):
        """Clearing non-existent pair should not raise error"""
        service.clear_pair(999, 999)  # Should not raise
        assert len(service.get_stale_pairs()) == 0
    
    def test_clear_all(self, service):
        """Should clear all stale pairs"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit1")
        service.mark_pair_stale(1, 3, "2026-01-02", "11:00", "edit2")
        service.mark_pair_stale(2, 2, "2026-01-03", "12:00", "edit3")
        
        service.clear_all()
        
        assert len(service.get_stale_pairs()) == 0
    
    def test_stale_pairs_persist_to_settings(self, service, settings):
        """Stale pairs should persist to settings"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit")
        
        stale_data = settings.get('repair_mode_stale_pairs')
        assert '1:2' in stale_data
        assert stale_data['1:2']['from_date'] == "2026-01-01"
        assert stale_data['1:2']['from_time'] == "10:00"


class TestStalePairRetrieval:
    """Test stale pair retrieval with user/site names"""
    
    def test_get_stale_pairs_empty(self, service):
        """Should return empty list when no stale pairs"""
        assert service.get_stale_pairs() == []
    
    def test_stale_pair_includes_names(self, service):
        """Should include user and site names in stale pairs"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].user_name is not None
        assert stale_pairs[0].site_name is not None
    
    def test_stale_pair_with_deleted_user_shows_unknown(self, service):
        """Should show 'Unknown User' for deleted users"""
        # Mark a pair with a user that doesn't exist
        service.mark_pair_stale(9999, 2, "2026-01-01", "10:00", "edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].user_name == "Unknown User (ID: 9999)"
    
    def test_stale_pair_with_deleted_site_shows_unknown(self, service):
        """Should show 'Unknown Site' for deleted sites"""
        # Mark a pair with a site that doesn't exist
        service.mark_pair_stale(1, 9999, "2026-01-01", "10:00", "edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].site_name == "Unknown Site (ID: 9999)"


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_mark_stale_with_none_boundary(self, service):
        """Should handle None boundary gracefully"""
        service.mark_pair_stale(1, 2, None, None, "edit")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert stale_pairs[0].from_date is None
        assert stale_pairs[0].from_time is None
    
    def test_mark_stale_with_empty_reason(self, service):
        """Should handle empty reason"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        assert "" in stale_pairs[0].reasons
    
    def test_stale_pairs_survive_service_recreation(self, service, settings):
        """Stale pairs should survive service recreation (settings persistence)"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit")
        
        # Create new service with same settings
        new_service = RepairModeService(settings)
        stale_pairs = new_service.get_stale_pairs()
        
        assert len(stale_pairs) == 1
        assert stale_pairs[0].user_id == 1
        assert stale_pairs[0].site_id == 2


class TestCrossPairScenarios:
    """Test scenarios involving multiple pairs (e.g., cross-pair moves)"""
    
    def test_cross_pair_move_marks_both_pairs(self, service):
        """Cross-pair move should mark both old and new pairs as stale"""
        # Simulate moving a purchase from user1@site2 to user1@site3
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "purchase moved away")
        service.mark_pair_stale(1, 3, "2026-01-01", "10:00", "purchase moved here")
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 2
        
        pair_keys = {(p.user_id, p.site_id) for p in stale_pairs}
        assert (1, 2) in pair_keys
        assert (1, 3) in pair_keys
    
    def test_rebuild_can_clear_subset_of_pairs(self, service):
        """Should be able to rebuild and clear subset of stale pairs"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit1")
        service.mark_pair_stale(1, 3, "2026-01-02", "11:00", "edit2")
        service.mark_pair_stale(2, 2, "2026-01-03", "12:00", "edit3")
        
        # Simulate rebuilding only pair (1, 2)
        service.clear_pair(1, 2)
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 2
        pair_keys = {(p.user_id, p.site_id) for p in stale_pairs}
        assert (1, 2) not in pair_keys
        assert (1, 3) in pair_keys
        assert (2, 2) in pair_keys


class TestTimestampTracking:
    """Test updated_at timestamp behavior"""
    
    def test_updated_at_set_on_mark(self, service):
        """Should set updated_at when marking pair stale"""
        before = datetime.now()
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "edit")
        after = datetime.now()
        
        stale_pairs = service.get_stale_pairs()
        assert len(stale_pairs) == 1
        
        updated_at_str = stale_pairs[0].updated_at
        updated_at = datetime.fromisoformat(updated_at_str)
        
        assert before <= updated_at <= after
    
    def test_updated_at_updates_on_remark(self, service):
        """Should update updated_at when remarking same pair"""
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "first edit")
        
        first_updated = service.get_stale_pairs()[0].updated_at
        
        # Wait a bit (in real scenario there would be time between edits)
        import time
        time.sleep(0.01)
        
        service.mark_pair_stale(1, 2, "2026-01-01", "10:00", "second edit")
        
        second_updated = service.get_stale_pairs()[0].updated_at
        
        assert second_updated > first_updated
