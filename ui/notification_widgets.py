"""
Notification UI components - Bell, badge, and notification center dialog
"""
from PySide6.QtWidgets import (
    QPushButton, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QWidget, QFrame, QMessageBox, QComboBox, QDateTimeEdit
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtGui import QFont
from datetime import datetime, timedelta


class NotificationBellWidget(QPushButton):
    """Notification bell button with badge count"""
    
    clicked_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__("🔔", parent)
        self.setFixedSize(44, 32)
        self.setToolTip("Notifications")
        self._unread_count = 0
        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
    
    def set_unread_count(self, count: int):
        """Update badge count"""
        self._unread_count = count
        if count > 0:
            self.setText(f"🔔 {count}")
            self.setToolTip(f"{count} unread notification(s)")
        else:
            self.setText("🔔")
            self.setToolTip("Notifications")


class NotificationItemWidget(QFrame):
    """Single notification item in the list"""
    
    action_clicked = Signal(object)  # notification
    dismissed = Signal(int)  # notification_id
    snoozed = Signal(int, datetime)  # notification_id, until
    deleted = Signal(int)  # notification_id
    marked_read = Signal(int)  # notification_id
    
    def __init__(self, notification, parent=None):
        super().__init__(parent)
        self.notification = notification
        self._init_ui()
    
    def _init_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(1)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        # Header: severity icon + title + timestamp
        header_layout = QHBoxLayout()
        
        # Severity indicator
        severity_icon = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌'
        }.get(self.notification.severity.value, 'ℹ️')
        
        severity_label = QLabel(severity_icon)
        severity_label.setFixedWidth(24)
        header_layout.addWidget(severity_label)
        
        # Title
        title_label = QLabel(self.notification.title)
        title_font = QFont()
        title_font.setBold(not self.notification.is_read)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label, 1)
        
        # Timestamp
        if self.notification.created_at:
            time_str = self.notification.created_at.strftime("%m/%d %I:%M%p")
            time_label = QLabel(time_str)
            time_label.setStyleSheet("color: #666; font-size: 11px;")
            header_layout.addWidget(time_label)
        
        layout.addLayout(header_layout)
        
        # Body
        body_label = QLabel(self.notification.body)
        body_label.setWordWrap(True)
        body_label.setStyleSheet("color: #333;")
        layout.addWidget(body_label)
        
        # Actions row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        
        # Action button (if notification has an action)
        if self.notification.action_key:
            action_btn = QPushButton("📋 Open")
            action_btn.clicked.connect(lambda: self.action_clicked.emit(self.notification))
            actions_layout.addWidget(action_btn)
        
        # Snooze button
        snooze_btn = QPushButton("⏰ Snooze")
        snooze_btn.clicked.connect(self._show_snooze_menu)
        actions_layout.addWidget(snooze_btn)
        
        # Dismiss button
        dismiss_btn = QPushButton("✓ Dismiss")
        dismiss_btn.clicked.connect(lambda: self.dismissed.emit(self.notification.id))
        actions_layout.addWidget(dismiss_btn)
        
        # Delete button
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedWidth(32)
        delete_btn.setToolTip("Delete notification")
        delete_btn.clicked.connect(lambda: self.deleted.emit(self.notification.id))
        actions_layout.addWidget(delete_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        # Style based on read status
        if not self.notification.is_read:
            self.setStyleSheet("background-color: #f5f5ff;")
    
    def _show_snooze_menu(self):
        """Show snooze options"""
        # Simple dialog with preset options
        dialog = QDialog(self)
        dialog.setWindowTitle("Snooze Notification")
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        combo = QComboBox()
        combo.addItem("1 hour", 1)
        combo.addItem("4 hours", 4)
        combo.addItem("24 hours", 24)
        combo.addItem("Until tomorrow 8am", -1)
        layout.addWidget(combo)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton("Snooze")
        cancel_btn = QPushButton("Cancel")
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() == QDialog.Accepted:
            hours = combo.currentData()
            if hours == -1:
                # Until tomorrow 8am
                tomorrow = datetime.now() + timedelta(days=1)
                until = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
            else:
                until = datetime.now() + timedelta(hours=hours)
            
            self.snoozed.emit(self.notification.id, until)


class NotificationCenterDialog(QDialog):
    """Notification center dialog showing all notifications"""
    
    def __init__(self, facade, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.setWindowTitle("Notifications")
        self.setMinimumSize(600, 500)
        self._init_ui()
        self.load_notifications()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header_layout = QHBoxLayout(header)
        
        title = QLabel("Notifications")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Mark all read button
        mark_all_btn = QPushButton("✓ Mark All Read")
        mark_all_btn.clicked.connect(self._mark_all_read)
        header_layout.addWidget(mark_all_btn)
        
        # Close button
        close_btn = QPushButton("✕ Close")
        close_btn.clicked.connect(self.accept)
        header_layout.addWidget(close_btn)
        
        layout.addWidget(header)
        
        # Scroll area for notifications
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        self.notifications_layout.setSpacing(8)
        self.notifications_layout.setContentsMargins(12, 12, 12, 12)
        self.notifications_layout.addStretch()
        
        scroll.setWidget(self.notifications_container)
        layout.addWidget(scroll)
    
    def load_notifications(self):
        """Load and display all active notifications"""
        # Clear existing
        while self.notifications_layout.count() > 1:
            item = self.notifications_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get active notifications
        notifications = self.facade.notification_service.get_active()
        
        if not notifications:
            empty_label = QLabel("No notifications")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999; padding: 40px; font-size: 14px;")
            self.notifications_layout.insertWidget(0, empty_label)
        else:
            for notif in notifications:
                item_widget = NotificationItemWidget(notif)
                item_widget.action_clicked.connect(self._handle_action)
                item_widget.dismissed.connect(self._dismiss_notification)
                item_widget.snoozed.connect(self._snooze_notification)
                item_widget.deleted.connect(self._delete_notification)
                self.notifications_layout.insertWidget(self.notifications_layout.count() - 1, item_widget)
    
    def _handle_action(self, notification):
        """Handle notification action"""
        if not notification.action_key:
            return
        
        # Mark as read
        self.facade.notification_service.mark_read(notification.id)
        
        # Route action
        if notification.action_key == 'open_tools':
            # Close dialog and open tools tab
            self.accept()
            if hasattr(self.parent(), 'tab_bar'):
                # Find tools tab index
                for i in range(self.parent().tab_bar.count()):
                    if "Tools" in self.parent().tab_bar.tabText(i):
                        self.parent().tab_bar.setCurrentIndex(i)
                        break
        elif notification.action_key == 'view_redemptions':
            # Open redemptions tab
            self.accept()
            if hasattr(self.parent(), 'tab_bar'):
                for i in range(self.parent().tab_bar.count()):
                    if "Redemptions" in self.parent().tab_bar.tabText(i):
                        self.parent().tab_bar.setCurrentIndex(i)
                        break
    
    def _dismiss_notification(self, notification_id):
        """Dismiss a notification"""
        self.facade.notification_service.dismiss(notification_id)
        self.load_notifications()
    
    def _snooze_notification(self, notification_id, until):
        """Snooze a notification"""
        self.facade.notification_service.snooze(notification_id, until)
        self.load_notifications()
    
    def _delete_notification(self, notification_id):
        """Delete a notification"""
        reply = QMessageBox.question(
            self,
            "Delete Notification",
            "Are you sure you want to delete this notification?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.facade.notification_service.delete(notification_id)
            self.load_notifications()
    
    def _mark_all_read(self):
        """Mark all notifications as read"""
        count = self.facade.notification_service.mark_all_read()
        if count > 0:
            self.load_notifications()
