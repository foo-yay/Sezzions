"""
Notification service - Business logic for notifications
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from models.notification import Notification, NotificationSeverity


class NotificationService:
    """
    Service for managing system notifications.
    
    Handles CRUD operations, de-duplication, and state management.
    """
    
    def __init__(self, notification_repo):
        self.notification_repo = notification_repo
    
    def create_or_update(
        self,
        type: str,
        title: str,
        body: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        subject_id: Optional[str] = None,
        action_key: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """
        Create or update a notification. De-duplicates by (type, subject_id).
        
        If a notification with the same (type, subject_id) exists:
        - If suppressed (cooldown), do nothing and return existing
        - Otherwise update its title/body/severity/action
        - Reset dismissed/deleted/snoozed state
        - Preserve read state
        """
        # Check if notification already exists
        existing = self.notification_repo.get_by_composite_key(type, subject_id)
        
        if existing:
            # If notification is suppressed (cooldown period), don't recreate or update
            if existing.is_suppressed:
                return existing
            
            # If deleted but cooldown expired, resurface as new/unread
            if existing.is_deleted and not existing.is_suppressed:
                # Reset to active state
                existing.deleted_at = None
                existing.read_at = None  # Resurface as unread
                existing.dismissed_at = None
                existing.snoozed_until = None
                existing.suppressed_until = None
            
            # Update notification content
            existing.title = title
            existing.body = body
            existing.severity = severity
            existing.action_key = action_key
            existing.action_payload = action_payload
            
            # Reset dismissed/snoozed state (notification is relevant again)
            existing.dismissed_at = None
            existing.snoozed_until = None
            existing.updated_at = datetime.now()
            
            return self.notification_repo.update(existing)
        else:
            # Create new notification
            notification = Notification(
                type=type,
                title=title,
                body=body,
                severity=severity,
                subject_id=subject_id,
                action_key=action_key,
                action_payload=action_payload,
                created_at=datetime.now()
            )
            return self.notification_repo.create(notification)
    
    def get_all(
        self,
        include_dismissed: bool = False,
        include_deleted: bool = False,
        include_snoozed: bool = False,
    ) -> List[Notification]:
        """Get all notifications, optionally including dismissed/deleted/snoozed."""
        notifications = self.notification_repo.get_all()
        
        filtered = []
        for notif in notifications:
            # Skip deleted unless requested
            if notif.is_deleted and not include_deleted:
                continue
            
            # Skip dismissed unless requested
            if notif.is_dismissed and not include_dismissed:
                continue
            
            # Skip snoozed notifications unless requested
            if notif.is_snoozed and not include_snoozed:
                continue
            
            filtered.append(notif)
        
        # Sort newest first
        filtered.sort(key=lambda n: n.created_at or datetime.min, reverse=True)
        return filtered
    
    def get_active(self, include_snoozed: bool = False) -> List[Notification]:
        """Get all active (not dismissed, deleted, or snoozed) notifications."""
        return self.get_all(include_dismissed=False, include_deleted=False, include_snoozed=include_snoozed)

    def get_active_count(self) -> int:
        """Get count of active (not dismissed, deleted, or snoozed) notifications"""
        return len(self.get_active())
    
    def get_unread_count(self) -> int:
        """Get count of unread active notifications"""
        active = self.get_active()
        return sum(1 for n in active if not n.is_read)
    
    def get_by_id(self, notification_id: int) -> Optional[Notification]:
        """Get notification by ID"""
        return self.notification_repo.get_by_id(notification_id)
    
    def mark_read(self, notification_id: int, cooldown_days: int = 0) -> Optional[Notification]:
        """
        Mark notification as read.
        
        Args:
            notification_id: ID of notification to mark read
            cooldown_days: Number of days to suppress resurfacing (default 0 = no cooldown)
        """
        notification = self.notification_repo.get_by_id(notification_id)
        if notification:
            notification.mark_read()
            notification.updated_at = datetime.now()
            
            # Set suppression cooldown if specified
            if cooldown_days > 0:
                notification.suppress(datetime.now() + timedelta(days=cooldown_days))
            
            return self.notification_repo.update(notification)
        return None
    
    def mark_unread(self, notification_id: int) -> Optional[Notification]:
        """Mark notification as unread"""
        notification = self.notification_repo.get_by_id(notification_id)
        if notification:
            notification.mark_unread()
            notification.updated_at = datetime.now()
            return self.notification_repo.update(notification)
        return None
    
    def mark_all_read(self) -> int:
        """Mark all non-dismissed, non-deleted notifications as read. Returns count updated."""
        # Include snoozed items so the Notification Center can truly clear the badge.
        active = self.get_all(include_dismissed=False, include_deleted=False, include_snoozed=True)
        count = 0
        for notif in active:
            if not notif.is_read:
                self.mark_read(notif.id)
                count += 1
        return count
    
    def dismiss(self, notification_id: int) -> Optional[Notification]:
        """Dismiss notification"""
        notification = self.notification_repo.get_by_id(notification_id)
        if notification:
            notification.dismiss()
            notification.updated_at = datetime.now()
            return self.notification_repo.update(notification)
        return None
    
    def snooze(self, notification_id: int, until: datetime) -> Optional[Notification]:
        """Snooze notification until specified time"""
        notification = self.notification_repo.get_by_id(notification_id)
        if notification:
            notification.snooze(until)
            notification.updated_at = datetime.now()
            return self.notification_repo.update(notification)
        return None
    
    def snooze_for_hours(self, notification_id: int, hours: int) -> Optional[Notification]:
        """Snooze notification for specified hours"""
        until = datetime.now() + timedelta(hours=hours)
        return self.snooze(notification_id, until)
    
    def snooze_until_tomorrow(self, notification_id: int, hour: int = 8) -> Optional[Notification]:
        """Snooze notification until tomorrow at specified hour"""
        tomorrow = datetime.now() + timedelta(days=1)
        until = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
        return self.snooze(notification_id, until)
    
    def delete(self, notification_id: int, cooldown_days: int = 0) -> Optional[Notification]:
        """
        Mark notification as deleted.
        
        Args:
            notification_id: ID of notification to delete
            cooldown_days: Number of days to suppress resurfacing (default 0 = no cooldown)
        """
        notification = self.notification_repo.get_by_id(notification_id)
        if notification:
            notification.delete()
            notification.updated_at = datetime.now()
            
            # Set suppression cooldown if specified
            if cooldown_days > 0:
                notification.suppress(datetime.now() + timedelta(days=cooldown_days))
            
            return self.notification_repo.update(notification)
        return None
    
    def clear_dismissed(self) -> int:
        """Permanently delete all dismissed notifications. Returns count deleted."""
        notifications = self.notification_repo.get_all()
        count = 0
        for notif in notifications:
            if notif.is_dismissed and not notif.is_deleted:
                self.notification_repo.hard_delete(notif.id)
                count += 1
        return count
    
    def dismiss_by_type(self, type: str, subject_id: Optional[str] = None) -> Optional[Notification]:
        """Dismiss notification by type and subject_id (useful for rules clearing notifications)"""
        notification = self.notification_repo.get_by_composite_key(type, subject_id)
        if notification and not notification.is_deleted:
            return self.dismiss(notification.id)
        return None
