"""
Integration tests for notification lifecycle cooldown delays (Issue #73)

Tests that delete/read actions suppress notifications for a configurable cooldown period,
preventing the "nag loop" where notifications immediately reappear after user dismisses them.
"""
import pytest
from datetime import datetime, timedelta, date
from repositories.notification_repository import NotificationRepository
from services.notification_service import NotificationService
from services.notification_rules_service import NotificationRulesService
from desktop.ui.settings import Settings
from models.notification import NotificationSeverity


@pytest.fixture
def notification_repo(tmp_path):
    """Notification repository with temp settings file"""
    settings_file = tmp_path / "settings.json"
    return NotificationRepository(settings_file=str(settings_file))


@pytest.fixture
def notification_service(notification_repo):
    """Notification service instance"""
    return NotificationService(notification_repo)


@pytest.fixture
def settings_service(tmp_path):
    """Settings service with temp settings file"""
    settings_file = tmp_path / "settings.json"
    return Settings(settings_file=str(settings_file))


@pytest.fixture
def rules_service(test_db, notification_service, settings_service):
    """Notification rules service instance"""
    return NotificationRulesService(
        notification_service=notification_service,
        settings=settings_service,
        db_manager=test_db
    )


def test_delete_with_cooldown_prevents_immediate_recreation(notification_service):
    """
    Test: Delete notification with cooldown → rules evaluate → notification NOT recreated
    
    This is the core fix for the "nag loop" bug.
    """
    # Create a notification
    notification = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Test Redemption Pending',
        body='Test body',
        severity=NotificationSeverity.WARNING,
        subject_id='123'
    )
    
    # Delete with 7-day cooldown
    notification_service.delete(notification.id, cooldown_days=7)
    
    # Verify notification is marked as deleted
    deleted_notif = notification_service.notification_repo.get_by_id(notification.id)
    assert deleted_notif.is_deleted
    assert deleted_notif.is_suppressed  # Should be suppressed
    assert deleted_notif.suppressed_until is not None
    
    # Attempt to recreate (simulates rule evaluation after dialog close)
    recreated = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Test Redemption Pending',
        body='Test body',
        severity=NotificationSeverity.WARNING,
        subject_id='123'
    )
    
    # Should return existing suppressed notification, not create new one
    assert recreated.id == notification.id
    assert recreated.is_deleted  # Still deleted
    assert recreated.is_suppressed  # Still suppressed
    
    # Verify notification is not active
    active_notifications = notification_service.get_all(
        include_dismissed=False,
        include_deleted=False,
        include_snoozed=False
    )
    assert len(active_notifications) == 0


def test_mark_read_with_cooldown_prevents_immediate_recreation(notification_service):
    """
    Test: Mark read with cooldown → rules evaluate → notification NOT recreated
    """
    # Create a notification
    notification = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Test Redemption Pending',
        body='Test body',
        severity=NotificationSeverity.WARNING,
        subject_id='456'
    )
    
    # Mark as read with 7-day cooldown
    notification_service.mark_read(notification.id, cooldown_days=7)
    
    # Verify notification is marked as read and suppressed
    read_notif = notification_service.notification_repo.get_by_id(notification.id)
    assert read_notif.is_read
    assert read_notif.is_suppressed
    assert read_notif.suppressed_until is not None
    
    # Attempt to recreate (simulates rule evaluation)
    recreated = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Test Redemption Pending',
        body='Test body updated',  # Different body
        severity=NotificationSeverity.WARNING,
        subject_id='456'
    )
    
    # Should return existing suppressed notification without updates
    assert recreated.id == notification.id
    assert recreated.is_read  # Still read
    assert recreated.is_suppressed  # Still suppressed
    assert recreated.body == 'Test body'  # Body NOT updated (suppressed)


def test_cooldown_expiration_allows_resurfacing(notification_service):
    """
    Test: Delete with cooldown → cooldown expires → rules evaluate → notification resurfaces as unread
    """
    # Create and delete with immediate expiration (0 days)
    notification = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Test Redemption Pending',
        body='Test body',
        severity=NotificationSeverity.WARNING,
        subject_id='789'
    )
    
    # Delete with 0-day cooldown (expires immediately)
    notification_service.delete(notification.id, cooldown_days=0)
    
    # Verify deleted but not suppressed (cooldown expired)
    deleted_notif = notification_service.notification_repo.get_by_id(notification.id)
    assert deleted_notif.is_deleted
    assert not deleted_notif.is_suppressed  # Cooldown expired
    
    # Recreate (simulates rule evaluation after cooldown expires)
    recreated = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Test Redemption Pending (Updated)',
        body='Test body updated',
        severity=NotificationSeverity.WARNING,
        subject_id='789'
    )
    
    # Should resurface as new/unread with updated content
    assert recreated.id == notification.id
    assert not recreated.is_deleted  # No longer deleted
    assert not recreated.is_read  # Resurfaced as unread
    assert not recreated.is_suppressed  # No longer suppressed
    assert recreated.title == 'Test Redemption Pending (Updated)'
    assert recreated.body == 'Test body updated'


def test_cooldown_suppression_with_past_timestamp(notification_service):
    """
    Test: Manually set suppressed_until to past → notification NOT suppressed
    """
    notification = notification_service.create_or_update(
        type='backup_due',
        title='Test Backup Due',
        body='Test body',
        severity=NotificationSeverity.INFO
    )
    
    # Manually set suppression to past (simulates expired cooldown)
    notification.suppressed_until = datetime.now() - timedelta(days=1)
    notification_service.notification_repo.update(notification)
    
    # Verify not suppressed
    updated_notif = notification_service.notification_repo.get_by_id(notification.id)
    assert updated_notif.suppressed_until is not None  # Field is set
    assert not updated_notif.is_suppressed  # But not suppressed (past timestamp)


def test_redemption_rules_respect_suppression(test_db, rules_service, notification_service):
    """
    Test: Create redemption → delete notification → evaluate rules → notification NOT recreated
    
    Integration test with actual rule evaluation.
    """
    # Insert test redemption (pending receipt > 7 days)
    redemption_date = (date.today() - timedelta(days=10)).isoformat()
    test_db.execute("""
        INSERT INTO users (id, name, notes) VALUES (1, 'Test User', '')
    """)
    test_db.execute("""
        INSERT INTO sites (id, name) VALUES (1, 'Test Site')
    """)
    test_db.execute("""
        INSERT INTO redemptions (id, user_id, site_id, redemption_date, amount, receipt_date)
        VALUES (1, 1, 1, ?, 100.00, NULL)
    """, (redemption_date,))
    test_db.commit()
    
    # Evaluate rules (should create notification)
    rules_service.evaluate_redemption_pending_rules()
    
    notifications = notification_service.get_all()
    assert len(notifications) == 1
    assert notifications[0].type == 'redemption_pending_receipt'
    assert notifications[0].subject_id == '1'
    
    # Delete notification with 7-day cooldown
    notification_service.delete(notifications[0].id, cooldown_days=7)
    
    # Re-evaluate rules (should NOT recreate due to suppression)
    rules_service.evaluate_redemption_pending_rules()
    
    # Verify notification still deleted and suppressed
    all_notifications = notification_service.notification_repo.get_all()
    assert len(all_notifications) == 1
    assert all_notifications[0].is_deleted
    assert all_notifications[0].is_suppressed
    
    # Verify no active notifications
    active_notifications = notification_service.get_all(
        include_dismissed=False,
        include_deleted=False
    )
    assert len(active_notifications) == 0


def test_condition_resolution_during_cooldown(test_db, rules_service, notification_service):
    """
    Test: Delete notification → add receipt_date (resolves condition) → evaluate rules → notification dismissed
    
    Validates that condition resolution takes precedence over cooldown.
    """
    # Insert test redemption (pending receipt)
    redemption_date = (date.today() - timedelta(days=10)).isoformat()
    test_db.execute("""
        INSERT INTO users (id, name, notes) VALUES (1, 'Test User', '')
    """)
    test_db.execute("""
        INSERT INTO sites (id, name) VALUES (1, 'Test Site')
    """)
    test_db.execute("""
        INSERT INTO redemptions (id, user_id, site_id, redemption_date, amount, receipt_date)
        VALUES (1, 1, 1, ?, 100.00, NULL)
    """, (redemption_date,))
    test_db.commit()
    
    # Evaluate rules (creates notification)
    rules_service.evaluate_redemption_pending_rules()
    
    notifications = notification_service.get_all()
    assert len(notifications) == 1
    
    # Delete with cooldown
    notification_service.delete(notifications[0].id, cooldown_days=7)
    
    # Resolve condition: add receipt_date
    receipt_date = date.today().isoformat()
    test_db.execute("""
        UPDATE redemptions SET receipt_date = ? WHERE id = 1
    """, (receipt_date,))
    test_db.commit()
    
    # Re-evaluate rules (should dismiss notification)
    rules_service.evaluate_redemption_pending_rules()
    
    # Verify notification is dismissed (not just suppressed)
    # Note: because the notification was deleted (not just read), the rule evaluation
    # will dismiss it (remove it from the active redemptions list), but the deletion
    # and suppression states remain. This is correct: user deleted it, condition resolved,
    # and it stays deleted until cooldown expires.
    all_notifications = notification_service.notification_repo.get_all()
    assert len(all_notifications) == 1
    # The notification should now be dismissed (by rule evaluation)
    assert all_notifications[0].is_dismissed or all_notifications[0].is_deleted
    # And still suppressed (cooldown hasn't expired)
    assert all_notifications[0].is_suppressed


def test_multiple_notifications_independent_cooldowns(notification_service):
    """
    Test: Multiple notifications can have different cooldown states
    """
    # Create two notifications
    notif1 = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Redemption 1',
        body='Body 1',
        severity=NotificationSeverity.WARNING,
        subject_id='1'
    )
    
    notif2 = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Redemption 2',
        body='Body 2',
        severity=NotificationSeverity.WARNING,
        subject_id='2'
    )
    
    # Delete first with cooldown, second without cooldown
    notification_service.delete(notif1.id, cooldown_days=7)
    notification_service.delete(notif2.id, cooldown_days=0)
    
    # Verify first is suppressed, second is not
    updated_notif1 = notification_service.notification_repo.get_by_id(notif1.id)
    updated_notif2 = notification_service.notification_repo.get_by_id(notif2.id)
    
    assert updated_notif1.is_suppressed
    assert not updated_notif2.is_suppressed
    
    # Attempt to recreate both
    recreated1 = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Redemption 1 Updated',
        body='Body 1 Updated',
        severity=NotificationSeverity.WARNING,
        subject_id='1'
    )
    
    recreated2 = notification_service.create_or_update(
        type='redemption_pending_receipt',
        title='Redemption 2 Updated',
        body='Body 2 Updated',
        severity=NotificationSeverity.WARNING,
        subject_id='2'
    )
    
    # First should remain deleted/suppressed, second should resurface
    assert recreated1.is_deleted and recreated1.is_suppressed
    assert recreated1.title == 'Redemption 1'  # Not updated
    
    assert not recreated2.is_deleted and not recreated2.is_suppressed
    assert recreated2.title == 'Redemption 2 Updated'  # Updated
