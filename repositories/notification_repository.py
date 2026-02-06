"""
Notification repository - Data access for notifications
Stores notifications in settings.json for v1 (machine/ops notifications)
"""
import json
import os
from typing import List, Optional
from datetime import datetime
from models.notification import Notification, NotificationSeverity


class NotificationRepository:
    """
    Repository for notification persistence using settings.json.
    
    For v1, all notifications are stored in settings.json.
    Future: split DB-backed (redemption reminders) vs settings-backed (backup alerts).
    """
    
    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = settings_file
        self._next_id = 1
    
    def _load_settings(self) -> dict:
        """Load settings from file"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_settings(self, settings: dict):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"Warning: Could not save notification settings: {e}")
    
    def _get_notifications_data(self) -> List[dict]:
        """Get notifications array from settings"""
        settings = self._load_settings()
        return settings.get('notifications', [])
    
    def _save_notifications_data(self, notifications_data: List[dict]):
        """Save notifications array to settings"""
        settings = self._load_settings()
        settings['notifications'] = notifications_data
        self._save_settings(settings)
    
    def _dict_to_notification(self, data: dict) -> Notification:
        """Convert dict to Notification model"""
        # Parse datetime fields
        for field in ['created_at', 'read_at', 'dismissed_at', 'snoozed_until', 'deleted_at', 'suppressed_until', 'updated_at']:
            if field in data and data[field]:
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except (ValueError, TypeError):
                    data[field] = None
        
        # Parse severity
        if 'severity' in data and isinstance(data['severity'], str):
            data['severity'] = NotificationSeverity(data['severity'])
        
        return Notification(**data)
    
    def _notification_to_dict(self, notification: Notification) -> dict:
        """Convert Notification model to dict"""
        data = {
            'id': notification.id,
            'type': notification.type,
            'title': notification.title,
            'body': notification.body,
            'severity': notification.severity.value if isinstance(notification.severity, NotificationSeverity) else notification.severity,
            'subject_id': notification.subject_id,
            'action_key': notification.action_key,
            'action_payload': notification.action_payload,
            'created_at': notification.created_at.isoformat() if notification.created_at else None,
            'read_at': notification.read_at.isoformat() if notification.read_at else None,
            'dismissed_at': notification.dismissed_at.isoformat() if notification.dismissed_at else None,
            'snoozed_until': notification.snoozed_until.isoformat() if notification.snoozed_until else None,
            'deleted_at': notification.deleted_at.isoformat() if notification.deleted_at else None,
            'suppressed_until': notification.suppressed_until.isoformat() if notification.suppressed_until else None,
            'updated_at': notification.updated_at.isoformat() if notification.updated_at else None,
        }
        return data
    
    def get_all(self) -> List[Notification]:
        """Get all notifications"""
        notifications_data = self._get_notifications_data()
        return [self._dict_to_notification(data) for data in notifications_data]
    
    def get_by_id(self, notification_id: int) -> Optional[Notification]:
        """Get notification by ID"""
        notifications_data = self._get_notifications_data()
        for data in notifications_data:
            if data.get('id') == notification_id:
                return self._dict_to_notification(data)
        return None
    
    def get_by_composite_key(self, type: str, subject_id: Optional[str]) -> Optional[Notification]:
        """Get notification by type and subject_id"""
        notifications_data = self._get_notifications_data()
        for data in notifications_data:
            if data.get('type') == type and data.get('subject_id') == subject_id:
                return self._dict_to_notification(data)
        return None
    
    def create(self, notification: Notification) -> Notification:
        """Create new notification"""
        notifications_data = self._get_notifications_data()
        
        # Assign ID
        if notifications_data:
            max_id = max(n.get('id', 0) for n in notifications_data)
            notification.id = max_id + 1
        else:
            notification.id = 1
        
        # Add to list
        notifications_data.append(self._notification_to_dict(notification))
        self._save_notifications_data(notifications_data)
        
        return notification
    
    def update(self, notification: Notification) -> Notification:
        """Update existing notification"""
        if not notification.id:
            raise ValueError("Cannot update notification without ID")
        
        notifications_data = self._get_notifications_data()
        updated = False
        
        for i, data in enumerate(notifications_data):
            if data.get('id') == notification.id:
                notifications_data[i] = self._notification_to_dict(notification)
                updated = True
                break
        
        if not updated:
            raise ValueError(f"Notification {notification.id} not found")
        
        self._save_notifications_data(notifications_data)
        return notification
    
    def hard_delete(self, notification_id: int) -> None:
        """Permanently delete notification"""
        notifications_data = self._get_notifications_data()
        notifications_data = [n for n in notifications_data if n.get('id') != notification_id]
        self._save_notifications_data(notifications_data)
