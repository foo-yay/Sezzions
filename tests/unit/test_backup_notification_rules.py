"""
Tests for automatic backup notification rules (Issue #35).
"""
import tempfile
import os
from datetime import datetime, timedelta
from services.notification_rules_service import NotificationRulesService
from services.notification_service import NotificationService
from models.notification import NotificationSeverity
from repositories.notification_repository import NotificationRepository


class MockDatabase:
    """Mock database for testing (notification rules don't actually query DB for backup notifications)"""
    pass


class MockSettings:
    """Mock Settings class for testing"""
    def __init__(self, backup_config=None):
        self.backup_config = backup_config or {
            'enabled': True,
            'directory': '/tmp/backups',
            'frequency_hours': 24,
            'last_backup_time': None,
            'notify_on_failure': True,
            'notify_when_overdue': True,
            'overdue_threshold_days': 1
        }
    
    def get_automatic_backup_config(self):
        return self.backup_config.copy()


def test_backup_failure_notification_when_enabled():
    """Test that backup failure notifications are created when enabled"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        notification_repo = NotificationRepository(settings_file)
        notification_service = NotificationService(notification_repo)
        settings = MockSettings()
        db = MockDatabase()
        
        rules_service = NotificationRulesService(notification_service, settings, db)
        
        # Trigger backup failure
        rules_service.on_backup_failed("Disk full")
        
        # Verify notification was created
        notifications = notification_service.notification_repo.get_all()
        failures = [n for n in notifications if n.type == 'backup_failed' and n.is_active]
        
        assert len(failures) == 1
        assert failures[0].title == 'Automatic Backup Failed'
        assert 'Disk full' in failures[0].body
        assert failures[0].severity == NotificationSeverity.ERROR
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_failure_notification_when_disabled():
    """Test that backup failure notifications are NOT created when disabled"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        notification_repo = NotificationRepository(settings_file)
        notification_service = NotificationService(notification_repo)
        
        # Disable failure notifications
        backup_config = {
            'enabled': True,
            'directory': '/tmp/backups',
            'notify_on_failure': False,
            'notify_when_overdue': True,
            'overdue_threshold_days': 1
        }
        settings = MockSettings(backup_config)
        db = MockDatabase()
        
        rules_service = NotificationRulesService(notification_service, settings, db)
        
        # Trigger backup failure
        rules_service.on_backup_failed("Disk full")
        
        # Verify NO notification was created
        notifications = notification_service.notification_repo.get_all()
        failures = [n for n in notifications if n.type == 'backup_failed' and n.is_active]
        
        assert len(failures) == 0
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_overdue_notification_respects_threshold():
    """Test that overdue notifications only appear after threshold is exceeded"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        notification_repo = NotificationRepository(settings_file)
        notification_service = NotificationService(notification_repo)
        
        # Set threshold to 1 day, make backup overdue by 2 days (total 3 days since last backup)
        backup_config = {
            'enabled': True,
            'directory': '/tmp/backups',
            'frequency_hours': 24,
            'last_backup_time': (datetime.now() - timedelta(days=3)).isoformat(),  # 3 days ago
            'notify_on_failure': True,
            'notify_when_overdue': True,
            'overdue_threshold_days': 1  # Notify if overdue by 1+ days
        }
        settings = MockSettings(backup_config)
        db = MockDatabase()
        
        rules_service = NotificationRulesService(notification_service, settings, db)
        
        # Evaluate rules - should create notification
        # (72 hours since backup, 24 hour frequency → 48 hours overdue, threshold is 24 hours)
        rules_service.evaluate_backup_rules()
        
        notifications = notification_service.notification_repo.get_all()
        overdue = [n for n in notifications if n.type == 'backup_due' and n.is_active]
        
        # Should have notification because we're overdue by more than threshold
        assert len(overdue) == 1
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_overdue_notification_not_shown_before_threshold():
    """Test that overdue notifications don't appear before threshold"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        notification_repo = NotificationRepository(settings_file)
        notification_service = NotificationService(notification_repo)
        
        # Set threshold to 2 days, but only 1 day overdue
        backup_config = {
            'enabled': True,
            'directory': '/tmp/backups',
            'frequency_hours': 24,
            'last_backup_time': (datetime.now() - timedelta(hours=36)).isoformat(),  # 12 hours overdue (36 - 24)
            'notify_on_failure': True,
            'notify_when_overdue': True,
            'overdue_threshold_days': 2  # Threshold is 48 hours
        }
        settings = MockSettings(backup_config)
        db = MockDatabase()
        
        rules_service = NotificationRulesService(notification_service, settings, db)
        
        # Evaluate rules - should NOT create notification (only 12 hours overdue, threshold is 48)
        rules_service.evaluate_backup_rules()
        
        notifications = notification_service.notification_repo.get_all()
        overdue = [n for n in notifications if n.type == 'backup_due' and n.is_active]
        
        assert len(overdue) == 0
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_overdue_notification_when_disabled():
    """Test that overdue notifications are NOT created when disabled"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        notification_repo = NotificationRepository(settings_file)
        notification_service = NotificationService(notification_repo)
        
        # Disable overdue notifications
        backup_config = {
            'enabled': True,
            'directory': '/tmp/backups',
            'frequency_hours': 24,
            'last_backup_time': (datetime.now() - timedelta(days=5)).isoformat(),  # Very overdue
            'notify_on_failure': True,
            'notify_when_overdue': False,  # Disabled
            'overdue_threshold_days': 1
        }
        settings = MockSettings(backup_config)
        db = MockDatabase()
        
        rules_service = NotificationRulesService(notification_service, settings, db)
        
        # Evaluate rules
        rules_service.evaluate_backup_rules()
        
        # Verify NO notification was created
        notifications = notification_service.notification_repo.get_all()
        overdue = [n for n in notifications if n.type == 'backup_due' and n.is_active]
        
        assert len(overdue) == 0
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_completed_dismisses_notifications():
    """Test that successful backup dismisses all backup-related notifications"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        notification_repo = NotificationRepository(settings_file)
        notification_service = NotificationService(notification_repo)
        settings = MockSettings()
        db = MockDatabase()
        
        rules_service = NotificationRulesService(notification_service, settings, db)
        
        # Create some backup notifications
        notification_service.create_or_update(
            type='backup_due',
            title='Backup Overdue',
            body='Test',
            severity=NotificationSeverity.WARNING
        )
        notification_service.create_or_update(
            type='backup_failed',
            title='Backup Failed',
            body='Test',
            severity=NotificationSeverity.ERROR
        )
        notification_service.create_or_update(
            type='backup_directory_missing',
            title='Missing Dir',
            body='Test',
            severity=NotificationSeverity.WARNING
        )
        
        # Verify notifications exist and are active
        all_notifs = notification_service.notification_repo.get_all()
        backup_notifs = [n for n in all_notifs if n.type in ['backup_due', 'backup_failed', 'backup_directory_missing'] and n.is_active]
        assert len(backup_notifs) == 3
        
        # Complete backup
        rules_service.on_backup_completed()
        
        # Verify all backup notifications are dismissed (not active)
        all_notifs = notification_service.notification_repo.get_all()
        backup_notifs = [n for n in all_notifs if n.type in ['backup_due', 'backup_failed', 'backup_directory_missing'] and n.is_active]
        assert len(backup_notifs) == 0
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)
