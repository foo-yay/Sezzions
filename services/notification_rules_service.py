"""
Notification rules evaluator - Business logic for generating notifications
"""
from datetime import datetime, timedelta, date
from typing import Optional
from models.notification import NotificationSeverity
from services.notification_service import NotificationService


class NotificationRulesService:
    """
    Service for evaluating notification rules and creating/dismissing notifications.
    
    This service checks app state (settings + DB) and creates notifications when
    conditions are met. UI calls this periodically (startup + hourly).
    """
    
    def __init__(self, notification_service: NotificationService, settings, db_manager):
        self.notification_service = notification_service
        self.settings = settings
        self.db = db_manager
    
    def evaluate_all_rules(self):
        """Evaluate all notification rules"""
        self.evaluate_backup_rules()
        self.evaluate_redemption_pending_rules()
    
    def evaluate_backup_rules(self):
        """Evaluate backup-related notification rules"""
        backup_config = self.settings.get_automatic_backup_config()
        
        if not backup_config.get('enabled', False):
            # Backup disabled, no notifications needed
            # Dismiss any existing backup notifications
            self.notification_service.dismiss_by_type('backup_directory_missing')
            self.notification_service.dismiss_by_type('backup_due')
            return
        
        # Check if backup directory is configured
        backup_dir = backup_config.get('directory', '').strip()
        if not backup_dir:
            # Directory not configured
            self.notification_service.create_or_update(
                type='backup_directory_missing',
                title='Backup Directory Not Configured',
                body='Automatic backups are enabled but no backup directory has been set. Please configure the backup directory in Tools.',
                severity=NotificationSeverity.WARNING,
                action_key='open_tools',
                action_payload={'tab': 'database_tools'}
            )
        else:
            # Directory configured, dismiss any "missing directory" notification
            self.notification_service.dismiss_by_type('backup_directory_missing')
            
            # Check if backup is due
            last_backup_time_str = backup_config.get('last_backup_time')
            frequency_hours = backup_config.get('frequency_hours', 24)
            
            if last_backup_time_str:
                try:
                    last_backup_time = datetime.fromisoformat(last_backup_time_str)
                    hours_since_backup = (datetime.now() - last_backup_time).total_seconds() / 3600
                    
                    if hours_since_backup >= frequency_hours:
                        # Backup is due
                        hours_overdue = int(hours_since_backup - frequency_hours)
                        overdue_msg = f" (overdue by {hours_overdue} hours)" if hours_overdue > 0 else ""
                        
                        self.notification_service.create_or_update(
                            type='backup_due',
                            title='Database Backup Due',
                            body=f'A database backup is due{overdue_msg}. Last backup was {int(hours_since_backup)} hours ago.',
                            severity=NotificationSeverity.WARNING,
                            action_key='open_tools',
                            action_payload={'tab': 'database_tools'}
                        )
                    else:
                        # Backup is not due yet
                        self.notification_service.dismiss_by_type('backup_due')
                except (ValueError, TypeError):
                    # Could not parse last backup time, consider backup due
                    self.notification_service.create_or_update(
                        type='backup_due',
                        title='Database Backup Recommended',
                        body='A database backup is recommended. No recent backup timestamp found.',
                        severity=NotificationSeverity.WARNING,
                        action_key='open_tools',
                        action_payload={'tab': 'database_tools'}
                    )
            else:
                # No last backup time recorded, consider backup due
                self.notification_service.create_or_update(
                    type='backup_due',
                    title='Database Backup Recommended',
                    body='A database backup is recommended. No previous backups recorded.',
                    severity=NotificationSeverity.WARNING,
                    action_key='open_tools',
                    action_payload={'tab': 'database_tools'}
                )
    
    def evaluate_redemption_pending_rules(self):
        """Evaluate redemption pending-receipt notification rules"""
        # Get threshold from settings (default 7 days)
        settings_data = self.settings.settings
        threshold_days = settings_data.get('redemption_pending_receipt_threshold_days', 7)
        
        if threshold_days <= 0:
            # Feature disabled
            return
        
        # Query redemptions where receipt_date is NULL and redemption_date is > threshold days ago
        threshold_date = (datetime.now() - timedelta(days=threshold_days)).date()
        
        query = """
            SELECT r.id, r.redemption_date, r.amount, r.receipt_date,
                   u.name as user_name, s.name as site_name
            FROM redemptions r
            JOIN users u ON r.user_id = u.id
            JOIN sites s ON r.site_id = s.id
            WHERE r.receipt_date IS NULL
              AND r.redemption_date <= ?
            ORDER BY r.redemption_date ASC
        """
        
        try:
            pending_redemptions = self.db.fetch_all(query, (threshold_date.isoformat(),))
            
            # Track which redemption notifications should exist
            active_redemption_ids = set()
            
            for row in pending_redemptions:
                redemption_id = row['id']
                redemption_date_str = row['redemption_date']
                amount = float(row['amount'])
                user_name = row['user_name']
                site_name = row['site_name']
                
                # Parse redemption date
                try:
                    if isinstance(redemption_date_str, str):
                        redemption_date = datetime.strptime(redemption_date_str, "%Y-%m-%d").date()
                    else:
                        redemption_date = redemption_date_str
                    
                    days_pending = (date.today() - redemption_date).days
                    
                    # Create/update notification for this redemption
                    self.notification_service.create_or_update(
                        type='redemption_pending_receipt',
                        title=f'Redemption Pending Receipt ({days_pending} days)',
                        body=f'${amount:.2f} redemption at {site_name} for {user_name} submitted on {redemption_date} has not been received.',
                        severity=NotificationSeverity.WARNING,
                        subject_id=str(redemption_id),
                        action_key='view_redemptions',
                        action_payload={'redemption_id': redemption_id}
                    )
                    
                    active_redemption_ids.add(str(redemption_id))
                except (ValueError, TypeError):
                    continue
            
            # Dismiss notifications for redemptions that are no longer pending
            # (either received or within threshold)
            all_notifications = self.notification_service.notification_repo.get_all()
            for notif in all_notifications:
                if notif.type == 'redemption_pending_receipt' and not notif.is_deleted:
                    if notif.subject_id not in active_redemption_ids:
                        self.notification_service.dismiss(notif.id)
        
        except Exception as e:
            print(f"Warning: Could not evaluate redemption pending rules: {e}")
    
    def on_backup_completed(self):
        """Called when a backup completes successfully. Dismisses backup due notifications."""
        self.notification_service.dismiss_by_type('backup_due')
        self.notification_service.dismiss_by_type('backup_directory_missing')
    
    def on_redemption_received(self, redemption_id: int):
        """Called when a redemption is marked as received. Dismisses pending notification."""
        self.notification_service.dismiss_by_type('redemption_pending_receipt', subject_id=str(redemption_id))
