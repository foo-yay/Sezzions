"""
Tests for automatic backup notification settings persistence (Issue #35).
"""
import json
import os
import tempfile
from desktop.ui.settings import Settings


def test_default_backup_notification_settings():
    """Test default backup notification settings are present"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        settings = Settings(settings_file)
        config = settings.get_automatic_backup_config()
        
        assert 'notify_on_failure' in config
        assert 'notify_when_overdue' in config
        assert 'overdue_threshold_days' in config
        
        # Check defaults
        assert config['notify_on_failure'] is True
        assert config['notify_when_overdue'] is True
        assert config['overdue_threshold_days'] == 1
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_notification_settings_persistence():
    """Test backup notification settings persist across settings instances"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        # First instance: set custom values
        settings1 = Settings(settings_file)
        config = settings1.get_automatic_backup_config()
        config['notify_on_failure'] = False
        config['notify_when_overdue'] = False
        config['overdue_threshold_days'] = 7
        settings1.set_automatic_backup_config(config)
        
        # Second instance: verify values persisted
        settings2 = Settings(settings_file)
        config2 = settings2.get_automatic_backup_config()
        
        assert config2['notify_on_failure'] is False
        assert config2['notify_when_overdue'] is False
        assert config2['overdue_threshold_days'] == 7
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_notification_settings_in_json():
    """Test backup notification settings are written to JSON file correctly"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
    
    try:
        settings = Settings(settings_file)
        config = settings.get_automatic_backup_config()
        config['notify_on_failure'] = True
        config['notify_when_overdue'] = False
        config['overdue_threshold_days'] = 3
        settings.set_automatic_backup_config(config)
        
        # Read raw JSON
        with open(settings_file, 'r') as f:
            data = json.load(f)
        
        assert 'automatic_backup' in data
        backup = data['automatic_backup']
        assert backup['notify_on_failure'] is True
        assert backup['notify_when_overdue'] is False
        assert backup['overdue_threshold_days'] == 3
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)


def test_backup_notification_settings_backwards_compat():
    """Test that old settings files without notification keys use defaults"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        settings_file = f.name
        # Write old-style settings (pre-Issue #35)
        old_settings = {
            'theme': 'Light',
            'automatic_backup': {
                'enabled': True,
                'directory': '/tmp/backups',
                'frequency_hours': 48,
                'last_backup_time': '2024-01-01T12:00:00'
            }
        }
        json.dump(old_settings, f)
    
    try:
        settings = Settings(settings_file)
        config = settings.get_automatic_backup_config()
        
        # Old keys should still be present
        assert config['enabled'] is True
        assert config['directory'] == '/tmp/backups'
        
        # New keys should have defaults
        assert config['notify_on_failure'] is True
        assert config['notify_when_overdue'] is True
        assert config['overdue_threshold_days'] == 1
    finally:
        if os.path.exists(settings_file):
            os.unlink(settings_file)
