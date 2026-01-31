"""
Test suite for NotificationService
"""
import pytest
from datetime import datetime, timedelta
from models.notification import Notification, NotificationSeverity
from services.notification_service import NotificationService
from repositories.notification_repository import NotificationRepository


@pytest.fixture
def temp_settings_file(tmp_path):
    """Temporary settings file for isolated testing"""
    return tmp_path / "test_settings.json"


@pytest.fixture
def notification_repo(temp_settings_file):
    """Notification repository with isolated settings"""
    repo = NotificationRepository(str(temp_settings_file))
    return repo


@pytest.fixture
def notification_service(notification_repo):
    """Notification service for testing"""
    return NotificationService(notification_repo)


class TestNotificationCRUD:
    """Test create, read, update, delete operations"""
    
    def test_create_notification(self, notification_service):
        """Test creating a notification"""
        notif = notification_service.create_or_update(
            type="test_notification",
            title="Test Notification",
            body="This is a test",
            severity=NotificationSeverity.INFO
        )
        
        assert notif is not None
        assert notif.type == "test_notification"
        assert notif.title == "Test Notification"
        assert notif.body == "This is a test"
        assert notif.severity == NotificationSeverity.INFO
        assert notif.created_at is not None
    
    def test_create_with_action(self, notification_service):
        """Test creating notification with action"""
        notif = notification_service.create_or_update(
            type="test_action",
            title="Action Required",
            body="Click to perform action",
            severity=NotificationSeverity.WARNING,
            action_key="open_tools",
            action_payload={"tab": "backup"}
        )
        
        assert notif.action_key == "open_tools"
        assert notif.action_payload == {"tab": "backup"}
    
    def test_get_all(self, notification_service):
        """Test retrieving all notifications"""
        notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.WARNING)
        
        all_notifs = notification_service.get_all()
        assert len(all_notifs) == 2
    
    def test_get_active_filters_deleted(self, notification_service):
        """Test that get_active excludes deleted notifications"""
        notif1 = notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notif2 = notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        
        # Delete one
        notification_service.delete(notif1.id)
        
        active = notification_service.get_active()
        assert len(active) == 1
        assert active[0].id == notif2.id
    
    def test_get_active_filters_dismissed(self, notification_service):
        """Test that get_active excludes dismissed notifications"""
        notif1 = notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notif2 = notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        
        # Dismiss one
        notification_service.dismiss(notif1.id)
        
        active = notification_service.get_active()
        assert len(active) == 1
        assert active[0].id == notif2.id


class TestDeduplication:
    """Test notification de-duplication by composite key"""
    
    def test_create_or_update_deduplicates(self, notification_service):
        """Test that creating with same type+subject_id updates existing"""
        notif1 = notification_service.create_or_update(
            type="backup_due",
            title="Backup Due",
            body="Last backup was 25 hours ago",
            severity=NotificationSeverity.WARNING,
            subject_id="backup_monitor"
        )
        
        notif2 = notification_service.create_or_update(
            type="backup_due",
            title="Backup Overdue",
            body="Last backup was 50 hours ago",
            severity=NotificationSeverity.ERROR,
            subject_id="backup_monitor"
        )
        
        # Should have updated, not created new
        assert notif1.id == notif2.id
        assert notif2.title == "Backup Overdue"
        assert notif2.severity == NotificationSeverity.ERROR
        
        # Only one notification exists
        all_notifs = notification_service.get_all()
        assert len(all_notifs) == 1
    
    def test_different_subject_id_creates_new(self, notification_service):
        """Test that different subject_id creates separate notification"""
        notif1 = notification_service.create_or_update(
            type="redemption_pending",
            title="Redemption Pending",
            body="Redemption 123 pending",
            severity=NotificationSeverity.INFO,
            subject_id="redemption_123"
        )
        
        notif2 = notification_service.create_or_update(
            type="redemption_pending",
            title="Redemption Pending",
            body="Redemption 456 pending",
            severity=NotificationSeverity.INFO,
            subject_id="redemption_456"
        )
        
        # Should be two separate notifications
        assert notif1.id != notif2.id
        all_notifs = notification_service.get_all()
        assert len(all_notifs) == 2


class TestStateManagement:
    """Test notification state transitions"""
    
    def test_mark_read(self, notification_service):
        """Test marking notification as read"""
        notif = notification_service.create_or_update("test", "Test", "Body", NotificationSeverity.INFO)
        assert not notif.is_read
        
        notification_service.mark_read(notif.id)
        updated = notification_service.get_by_id(notif.id)
        assert updated.is_read
        assert updated.read_at is not None
    
    def test_mark_unread(self, notification_service):
        """Test marking notification as unread"""
        notif = notification_service.create_or_update("test", "Test", "Body", NotificationSeverity.INFO)
        notification_service.mark_read(notif.id)
        
        notification_service.mark_unread(notif.id)
        updated = notification_service.get_by_id(notif.id)
        assert not updated.is_read
        assert updated.read_at is None
    
    def test_mark_all_read(self, notification_service):
        """Test marking all notifications as read"""
        notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        notification_service.create_or_update("test3", "Test 3", "Body 3", NotificationSeverity.INFO)
        
        count = notification_service.mark_all_read()
        assert count == 3
        
        for notif in notification_service.get_all():
            assert notif.is_read
    
    def test_dismiss(self, notification_service):
        """Test dismissing notification"""
        notif = notification_service.create_or_update("test", "Test", "Body", NotificationSeverity.INFO)
        
        notification_service.dismiss(notif.id)
        updated = notification_service.get_by_id(notif.id)
        assert updated.is_dismissed
        assert updated.dismissed_at is not None
        
        # Should not appear in active
        assert len(notification_service.get_active()) == 0
    
    def test_snooze(self, notification_service):
        """Test snoozing notification"""
        notif = notification_service.create_or_update("test", "Test", "Body", NotificationSeverity.INFO)
        
        until = datetime.now() + timedelta(hours=1)
        notification_service.snooze(notif.id, until)
        
        updated = notification_service.get_by_id(notif.id)
        assert updated.is_snoozed
        assert updated.snoozed_until is not None
        
        # Should not appear in active while snoozed
        assert len(notification_service.get_active()) == 0
    
    def test_snooze_expired_shows_in_active(self, notification_service):
        """Test that expired snooze shows in active again"""
        notif = notification_service.create_or_update("test", "Test", "Body", NotificationSeverity.INFO)
        
        # Snooze until past
        until = datetime.now() - timedelta(hours=1)
        notification_service.snooze(notif.id, until)
        
        # Should appear in active again
        assert len(notification_service.get_active()) == 1
    
    def test_delete(self, notification_service):
        """Test deleting notification"""
        notif = notification_service.create_or_update("test", "Test", "Body", NotificationSeverity.INFO)
        
        notification_service.delete(notif.id)
        updated = notification_service.get_by_id(notif.id)
        assert updated.is_deleted
        assert updated.deleted_at is not None
        
        # Should not appear in active
        assert len(notification_service.get_active()) == 0


class TestUnreadCount:
    """Test unread count calculation"""
    
    def test_get_unread_count(self, notification_service):
        """Test getting unread notification count"""
        notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        notification_service.create_or_update("test3", "Test 3", "Body 3", NotificationSeverity.INFO)
        
        assert notification_service.get_unread_count() == 3
    
    def test_unread_count_excludes_read(self, notification_service):
        """Test that unread count excludes read notifications"""
        notif1 = notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notif2 = notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        
        notification_service.mark_read(notif1.id)
        
        assert notification_service.get_unread_count() == 1
    
    def test_unread_count_excludes_deleted(self, notification_service):
        """Test that unread count excludes deleted notifications"""
        notif1 = notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notif2 = notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        
        notification_service.delete(notif1.id)
        
        assert notification_service.get_unread_count() == 1


class TestBulkOperations:
    """Test bulk operations"""
    
    def test_clear_dismissed(self, notification_service):
        """Test clearing all dismissed notifications"""
        notif1 = notification_service.create_or_update("test1", "Test 1", "Body 1", NotificationSeverity.INFO)
        notif2 = notification_service.create_or_update("test2", "Test 2", "Body 2", NotificationSeverity.INFO)
        notif3 = notification_service.create_or_update("test3", "Test 3", "Body 3", NotificationSeverity.INFO)
        
        notification_service.dismiss(notif1.id)
        notification_service.dismiss(notif2.id)
        
        count = notification_service.clear_dismissed()
        assert count == 2
        
        # Only one remains
        assert len(notification_service.get_all()) == 1
    
    def test_dismiss_by_type(self, notification_service):
        """Test dismissing notification by composite key"""
        notification_service.create_or_update("backup_due", "Backup 1", "Body 1", NotificationSeverity.INFO, subject_id="1")
        notification_service.create_or_update("backup_due", "Backup 2", "Body 2", NotificationSeverity.INFO, subject_id="2")
        notification_service.create_or_update("other_type", "Other", "Body 3", NotificationSeverity.INFO)
        
        # Dismiss one specific backup notification
        notif = notification_service.dismiss_by_type("backup_due", subject_id="1")
        assert notif is not None
        assert notif.is_dismissed
        
        active = notification_service.get_active()
        assert len(active) == 2
        
        # Check that subject_id="1" is dismissed
        for n in notification_service.get_all():
            if n.type == "backup_due" and n.subject_id == "1":
                assert n.is_dismissed
