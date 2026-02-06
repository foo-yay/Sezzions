"""
Notification model - represents a system notification/alert
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class NotificationSeverity(Enum):
    """Notification severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Notification:
    """
    Represents a system notification with state management.
    
    Notifications are identified by (type, subject_id) for de-duplication.
    Examples:
    - type='backup_due', subject_id=None (global)
    - type='redemption_pending', subject_id=redemption_id
    """
    type: str  # notification type (e.g., 'backup_due', 'redemption_pending')
    title: str
    body: str
    severity: NotificationSeverity = NotificationSeverity.INFO
    subject_id: Optional[str] = None  # identifier for de-duplication
    action_key: Optional[str] = None  # action identifier (e.g., 'open_tools', 'view_redemption')
    action_payload: Optional[Dict[str, Any]] = None  # action parameters
    
    # State fields
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    suppressed_until: Optional[datetime] = None  # Cooldown period for delete/read actions
    
    # Metadata
    id: Optional[int] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate notification data"""
        if not self.type:
            raise ValueError("Notification type is required")
        if not self.title:
            raise ValueError("Notification title is required")
        if not self.body:
            raise ValueError("Notification body is required")
        
        # Convert severity string to enum if needed
        if isinstance(self.severity, str):
            self.severity = NotificationSeverity(self.severity.lower())
    
    @property
    def is_read(self) -> bool:
        """Check if notification has been read"""
        return self.read_at is not None
    
    @property
    def is_dismissed(self) -> bool:
        """Check if notification has been dismissed"""
        return self.dismissed_at is not None
    
    @property
    def is_snoozed(self) -> bool:
        """Check if notification is currently snoozed"""
        if self.snoozed_until is None:
            return False
        return datetime.now() < self.snoozed_until
    
    @property
    def is_deleted(self) -> bool:
        """Check if notification has been deleted"""
        return self.deleted_at is not None
    
    @property
    def is_suppressed(self) -> bool:
        """Check if notification is currently suppressed (cooldown period)"""
        if self.suppressed_until is None:
            return False
        return datetime.now() < self.suppressed_until
    
    @property
    def is_active(self) -> bool:
        """Check if notification is active (not dismissed, deleted, snoozed, or suppressed)"""
        return not (self.is_dismissed or self.is_deleted or self.is_snoozed or self.is_suppressed)
    
    @property
    def composite_key(self) -> tuple:
        """Get composite key for de-duplication"""
        return (self.type, self.subject_id)
    
    def mark_read(self):
        """Mark notification as read"""
        if self.read_at is None:
            self.read_at = datetime.now()
    
    def mark_unread(self):
        """Mark notification as unread"""
        self.read_at = None
    
    def dismiss(self):
        """Dismiss notification"""
        self.dismissed_at = datetime.now()
    
    def snooze(self, until: datetime):
        """Snooze notification until specified time"""
        self.snoozed_until = until
    
    def delete(self):
        """Mark notification as deleted"""
        self.deleted_at = datetime.now()
    
    def suppress(self, until: datetime):
        """Suppress notification until specified time (cooldown period)"""
        self.suppressed_until = until
