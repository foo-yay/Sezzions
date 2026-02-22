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
        
        # First, check if automatic backups are enabled
        # This is a gentle reminder for all users to enable data protection
        if not backup_config.get('enabled', False):
            # Auto-backup not enabled - show INFO notification
            self.notification_service.create_or_update(
                type='backup_not_enabled',
                title='Automatic Backups Not Enabled',
                body='Automatic backups are not enabled. Consider enabling automatic backups in Tools → Database to protect your data.',
                severity=NotificationSeverity.INFO,
                action_key='open_tools',
                action_payload={'tab': 'database_tools'}
            )
            # Dismiss automatic backup-specific notifications
            self.notification_service.dismiss_by_type('backup_directory_missing')
            self.notification_service.dismiss_by_type('backup_due')
            self.notification_service.dismiss_by_type('backup_failed')
            return
        else:
            # Auto-backup enabled, dismiss the reminder
            self.notification_service.dismiss_by_type('backup_not_enabled')
        
        # Now evaluate automatic backup-specific rules (directory, overdue, failed)
        backup_dir = backup_config.get('directory', '').strip()
        if False:
            # Backup disabled, no automatic backup notifications needed
            # Dismiss any existing automatic backup notifications
            self.notification_service.dismiss_by_type('backup_directory_missing')
            self.notification_service.dismiss_by_type('backup_due')
            self.notification_service.dismiss_by_type('backup_failed')
            return
        
        # Check if backup directory is configured (for automatic backups)
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
            
            # Check if overdue notifications are enabled
            notify_when_overdue = backup_config.get('notify_when_overdue', True)
            if not notify_when_overdue:
                # User has disabled overdue notifications
                self.notification_service.dismiss_by_type('backup_due')
                return
            
            # Check if backup is overdue
            last_backup_time_str = backup_config.get('last_backup_time')
            frequency_hours = backup_config.get('frequency_hours', 24)
            overdue_threshold_days = backup_config.get('overdue_threshold_days', 1)
            overdue_threshold_hours = overdue_threshold_days * 24
            
            if last_backup_time_str:
                try:
                    last_backup_time = datetime.fromisoformat(last_backup_time_str)
                    hours_since_backup = (datetime.now() - last_backup_time).total_seconds() / 3600
                    hours_overdue = hours_since_backup - frequency_hours
                    
                    # Only notify if overdue by threshold
                    if hours_overdue >= overdue_threshold_hours:
                        days_overdue = int(hours_overdue / 24)
                        overdue_msg = f" (overdue by {days_overdue} day{'s' if days_overdue != 1 else ''})"
                        
                        self.notification_service.create_or_update(
                            type='backup_due',
                            title='Database Backup Overdue',
                            body=f'A database backup is overdue{overdue_msg}. Last backup was {int(hours_since_backup / 24)} day(s) ago.',
                            severity=NotificationSeverity.WARNING,
                            action_key='open_tools',
                            action_payload={'tab': 'database_tools'}
                        )
                    else:
                        # Backup is not overdue by threshold yet
                        self.notification_service.dismiss_by_type('backup_due')
                except (ValueError, TypeError):
                    # Could not parse last backup time, consider backup due if overdue threshold is 0
                    if overdue_threshold_days == 0:
                        self.notification_service.create_or_update(
                            type='backup_due',
                            title='Database Backup Recommended',
                            body='A database backup is recommended. No recent backup timestamp found.',
                            severity=NotificationSeverity.WARNING,
                            action_key='open_tools',
                            action_payload={'tab': 'database_tools'}
                        )
                    else:
                        self.notification_service.dismiss_by_type('backup_due')
            else:
                # No last backup time recorded, only notify if overdue threshold allows
                if overdue_threshold_days == 0:
                    self.notification_service.create_or_update(
                        type='backup_due',
                        title='Database Backup Recommended',
                        body='A database backup is recommended. No previous backups recorded.',
                        severity=NotificationSeverity.WARNING,
                        action_key='open_tools',
                        action_payload={'tab': 'database_tools'}
                    )
                else:
                    # Don't nag user immediately - wait for threshold
                    self.notification_service.dismiss_by_type('backup_due')
    
    def evaluate_redemption_pending_rules(self):
        """Evaluate redemption pending-receipt notification rules"""
        # Get threshold from settings (default 7 days)
        if self.settings is None:
            threshold_days = 7
        else:
            settings_data = self.settings.settings
            threshold_days = settings_data.get('redemption_pending_receipt_threshold_days', 7)
        
        if threshold_days <= 0:
            # Feature disabled
            return
        
        # Query redemptions where receipt_date is NULL and redemption_date is > threshold days ago
        threshold_date = (datetime.now() - timedelta(days=threshold_days)).date()
        from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc, utc_date_time_to_local
        tz_name = get_configured_timezone_name()
        cutoff_date, cutoff_time = local_date_time_to_utc(threshold_date, "23:59:59", tz_name)
        
        query = """
            SELECT r.id, r.redemption_date, r.redemption_time, r.amount, r.receipt_date,
                   u.name as user_name, s.name as site_name
            FROM redemptions r
            JOIN users u ON r.user_id = u.id
            JOIN sites s ON r.site_id = s.id
            WHERE r.receipt_date IS NULL
                            AND r.deleted_at IS NULL
                            AND COALESCE(r.status, 'PENDING') = 'PENDING'
                            AND (
                                        r.redemption_date < ?
                                        OR (r.redemption_date = ? AND COALESCE(r.redemption_time, '00:00:00') <= ?)
                                    )
            ORDER BY r.redemption_date ASC
        """
        
        try:
            pending_redemptions = self.db.fetch_all(query, (cutoff_date, cutoff_date, cutoff_time))
            
            # Track which redemption notifications should exist
            active_redemption_ids = set()
            
            for row in pending_redemptions:
                redemption_id = row['id']
                redemption_date_str = row['redemption_date']
                redemption_time_str = row['redemption_time'] if 'redemption_time' in row.keys() else None
                amount = float(row['amount'])
                user_name = row['user_name']
                site_name = row['site_name']
                
                # Parse redemption date
                try:
                    if isinstance(redemption_date_str, str):
                        redemption_date = datetime.strptime(redemption_date_str, "%Y-%m-%d").date()
                    else:
                        redemption_date = redemption_date_str

                    redemption_date, _ = utc_date_time_to_local(
                        redemption_date,
                        redemption_time_str or "00:00:00",
                        tz_name,
                    )
                    
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
        """Called when a backup completes successfully. Dismisses backup due and failed notifications."""
        self.notification_service.dismiss_by_type('backup_due')
        self.notification_service.dismiss_by_type('backup_directory_missing')
        self.notification_service.dismiss_by_type('backup_failed')
    
    def on_backup_failed(self, error_msg: str):
        """Called when a backup fails. Creates failure notification if enabled."""
        backup_config = self.settings.get_automatic_backup_config()
        notify_on_failure = backup_config.get('notify_on_failure', True)
        
        if notify_on_failure:
            self.notification_service.create_or_update(
                type='backup_failed',
                title='Automatic Backup Failed',
                body=f'The automatic backup failed: {error_msg}',
                severity=NotificationSeverity.ERROR,
                action_key='open_tools',
                action_payload={'tab': 'database_tools'}
            )
    
    def on_redemption_received(self, redemption_id: int):
        """Called when a redemption is marked as received. Dismisses pending notification."""
        self.notification_service.dismiss_by_type('redemption_pending_receipt', subject_id=str(redemption_id))
