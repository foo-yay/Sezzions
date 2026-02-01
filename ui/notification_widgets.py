"""
Notification UI components - Bell, badge, and notification center dialog
"""
from PySide6.QtWidgets import (
    QPushButton, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QWidget, QFrame, QMessageBox, QComboBox, QDateTimeEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QDateTime, QRect, QPoint, QTimer
from PySide6.QtGui import QFont, QFontMetricsF
from datetime import datetime, timedelta


class NotificationBellWidget(QPushButton):
    """Notification bell button with badge overlay"""
    
    clicked_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__("🔔", parent)
        # Shared styling with the Settings gear button (see ui/themes.py).
        self.setObjectName("HeaderIconButton")
        self.setFixedSize(32, 32)
        self.setToolTip("Notifications")
        self._unread_count = 0
        font = QFont("Apple Color Emoji")
        font.setPixelSize(16)
        self.setFont(font)

        # Badge overlay (use a real label so text layout/centering is consistent).
        self._badge = QLabel(self)
        self._badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setVisible(False)
        self._badge.setStyleSheet(
            "QLabel {"
            "  background-color: rgb(220, 50, 50);"
            "  color: white;"
            "  border: 1px solid white;"
            "  border-radius: 7px;"
            "}"
        )
    
    def set_unread_count(self, count: int):
        """Update badge count"""
        self._unread_count = count
        if count > 0:
            self.setToolTip(f"{count} notification(s)")
        else:
            self.setToolTip("Notifications")

        if self._unread_count > 0:
            self._badge.setVisible(True)
            self._badge.setText(str(self._unread_count) if self._unread_count < 100 else "99+")
            self._update_badge_geometry()
        else:
            self._badge.setVisible(False)

        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._badge.isVisible():
            self._update_badge_geometry()

    def _update_badge_geometry(self):
        # Keep the badge compact and readable.
        badge_h = 14
        badge_margin = 2

        text = self._badge.text()

        badge_font = QFont()
        badge_font.setBold(True)
        badge_font.setPixelSize(9 if len(text) <= 2 else 8)
        self._badge.setFont(badge_font)

        metrics = QFontMetricsF(badge_font)
        text_w = metrics.horizontalAdvance(text)
        pad_x = 5.0
        badge_w = max(float(badge_h), float(text_w + pad_x * 2.0))

        # QLabel positioning uses ints; snapping helps keep things steady.
        badge_w_i = int(round(badge_w))
        self._badge.setFixedSize(badge_w_i, badge_h)

        radius = badge_h // 2
        self._badge.setStyleSheet(
            "QLabel {"
            "  background-color: rgb(220, 50, 50);"
            "  color: white;"
            "  border: 1px solid white;"
            f"  border-radius: {radius}px;"
            "}"
        )

        self._badge.move(self.width() - badge_w_i - badge_margin, badge_margin)


class NotificationItemWidget(QFrame):
    """Single notification item in the list"""
    
    action_clicked = Signal(object)  # notification
    dismissed = Signal(int)  # notification_id
    snoozed = Signal(int, datetime)  # notification_id, until
    deleted = Signal(int)  # notification_id
    marked_read = Signal(int)  # notification_id
    marked_unread = Signal(int)  # notification_id
    
    def __init__(self, notification, parent=None):
        super().__init__(parent)
        self.notification = notification
        self._is_expanded = not notification.is_snoozed  # Collapse snoozed by default
        self._init_ui()
    
    def _init_ui(self):
        # Use the app's global "section" styling
        self.setObjectName("SectionBackground")
        
        layout = QVBoxLayout(self)
        # Let the global SectionBackground style provide padding.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header: severity icon + title + timestamp + expand/collapse for snoozed
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Expand/collapse button for snoozed notifications
        if self.notification.is_snoozed:
            self.expand_btn = QPushButton("▶" if not self._is_expanded else "▼")
            self.expand_btn.setFixedSize(28, 28)
            self.expand_btn.setStyleSheet("border: none; font-size: 14px; font-weight: 600;")
            self.expand_btn.clicked.connect(self._toggle_expanded)
            header_layout.addWidget(self.expand_btn)
        
        # Severity indicator
        severity_icon = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌'
        }.get(self.notification.severity.value, 'ℹ️')
        
        severity_label = QLabel(severity_icon)
        severity_label.setFixedWidth(24)
        header_layout.addWidget(severity_label)
        
        # Title (with snooze indicator if snoozed)
        title_text = self.notification.title
        if self.notification.is_snoozed and self.notification.snoozed_until:
            until_str = self.notification.snoozed_until.strftime("%I:%M%p")
            title_text = f"💤 {title_text} (snoozed until {until_str})"
        
        title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setBold(not self.notification.is_read)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label, 1)
        
        # Timestamp
        if self.notification.created_at:
            time_str = self.notification.created_at.strftime("%m/%d %I:%M%p")
            time_label = QLabel(time_str)
            time_label.setObjectName("HelperText")
            header_layout.addWidget(time_label)
        
        layout.addLayout(header_layout)
        
        # Details container (collapsible for snoozed)
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(10)
        
        # Notification body in bordered section with different background
        # Notification body (no extra inner borders; keep padding modest)
        body_label = QLabel(self.notification.body)
        body_label.setWordWrap(True)
        details_layout.addWidget(body_label)
        
        # Actions row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        # Action button (if notification has an action)
        if self.notification.action_key:
            action_btn = QPushButton("📂 Open")
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

        # Mark as read/unread (moves between groups)
        if self.notification.is_read:
            unread_btn = QPushButton("↩︎ Mark Unread")
            unread_btn.clicked.connect(lambda: self.marked_unread.emit(self.notification.id))
            actions_layout.addWidget(unread_btn)
        else:
            read_btn = QPushButton("✓ Mark Read")
            read_btn.clicked.connect(lambda: self.marked_read.emit(self.notification.id))
            actions_layout.addWidget(read_btn)
        
        # Delete button (larger, more usable)
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(lambda: self.deleted.emit(self.notification.id))
        actions_layout.addWidget(delete_btn)
        
        actions_layout.addStretch()
        details_layout.addLayout(actions_layout)
        
        layout.addWidget(self.details_widget)
        
        # Show/hide details based on expanded state
        self.details_widget.setVisible(self._is_expanded)
    
    def _toggle_expanded(self):
        """Toggle expand/collapse for snoozed notifications"""
        self._is_expanded = not self._is_expanded
        self.details_widget.setVisible(self._is_expanded)
        if hasattr(self, 'expand_btn'):
            self.expand_btn.setText("▼" if self._is_expanded else "▶")
    
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
        self.setObjectName("NotificationsDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("Notifications")
        self.setMinimumSize(600, 500)
        self._init_ui()
        self.load_notifications()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header (no underline; uses global typography)
        header = QWidget()
        header.setObjectName("NotificationsHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 8)

        title = QLabel("🔔 Notifications")
        title.setObjectName("PageTitle")
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
        scroll.setObjectName("NotificationsScroll")
        scroll.setAttribute(Qt.WA_StyledBackground, True)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        if scroll.viewport() is not None:
            scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        
        self.notifications_container = QWidget()
        self.notifications_container.setObjectName("NotificationsContainer")
        self.notifications_container.setAttribute(Qt.WA_StyledBackground, True)
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        self.notifications_layout.setSpacing(10)
        self.notifications_layout.setContentsMargins(12, 12, 12, 12)

        self._groups = {}
        self._groups["unread"] = self._create_group("Unread", initially_expanded=True)
        self._groups["read"] = self._create_group("Read", initially_expanded=False)
        self._groups["snoozed"] = self._create_group("Snoozed", initially_expanded=False)

        self.notifications_layout.addWidget(self._groups["unread"]["root"])
        self.notifications_layout.addWidget(self._groups["read"]["root"])
        self.notifications_layout.addWidget(self._groups["snoozed"]["root"])
        self.notifications_layout.addStretch()
        
        scroll.setWidget(self.notifications_container)
        layout.addWidget(scroll)

    def _create_group(self, title: str, initially_expanded: bool):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        toggle_btn = QPushButton("▼" if initially_expanded else "▶")
        toggle_btn.setFixedSize(30, 30)
        toggle_btn.setStyleSheet("font-size: 16px; font-weight: 700; padding: 0;")
        header_layout.addWidget(toggle_btn)

        label = QLabel(title)
        label.setObjectName("SectionHeader")
        header_layout.addWidget(label)

        header_layout.addStretch(1)

        count_label = QLabel("")
        count_label.setObjectName("HelperText")
        header_layout.addWidget(count_label)

        content = QWidget()
        content.setVisible(initially_expanded)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        def _toggle():
            content.setVisible(not content.isVisible())
            toggle_btn.setText("▼" if content.isVisible() else "▶")

        toggle_btn.clicked.connect(_toggle)

        root_layout.addWidget(header)
        root_layout.addWidget(content)

        return {
            "root": root,
            "content": content,
            "content_layout": content_layout,
            "count_label": count_label,
        }

    def _refresh_bell_badge(self):
        main_window = self.parent()
        if main_window is not None and hasattr(main_window, "_refresh_notification_badge"):
            main_window._refresh_notification_badge()
    
    def load_notifications(self):
        """Load and display notifications, grouped by state."""

        def _clear_layout(vbox: QVBoxLayout):
            while vbox.count():
                item = vbox.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        for g in self._groups.values():
            _clear_layout(g["content_layout"])

        notifications = self.facade.notification_service.get_all(
            include_dismissed=False,
            include_deleted=False,
            include_snoozed=True,
        )

        unread = [n for n in notifications if (not n.is_snoozed and not n.is_read)]
        read = [n for n in notifications if (not n.is_snoozed and n.is_read)]
        snoozed = [n for n in notifications if n.is_snoozed]

        def _add_items(group_key: str, items):
            group = self._groups[group_key]
            group["count_label"].setText(f"{len(items)}")
            group["root"].setVisible(len(items) > 0 or group_key == "unread")
            if not items and group_key == "unread":
                empty_label = QLabel("No notifications")
                empty_label.setAlignment(Qt.AlignCenter)
                empty_label.setObjectName("HelperText")
                group["content_layout"].addWidget(empty_label)
                return
            for notif in items:
                item_widget = NotificationItemWidget(notif)
                item_widget.action_clicked.connect(self._handle_action)
                item_widget.dismissed.connect(self._dismiss_notification)
                item_widget.snoozed.connect(self._snooze_notification)
                item_widget.deleted.connect(self._delete_notification)
                item_widget.marked_unread.connect(self._mark_unread_notification)
                item_widget.marked_read.connect(self._mark_read_notification)
                group["content_layout"].addWidget(item_widget)

        _add_items("unread", unread)
        _add_items("read", read)
        _add_items("snoozed", snoozed)

        self._refresh_bell_badge()
    
    def _handle_action(self, notification):
        """Handle notification action"""
        if not notification.action_key:
            return
        
        # Mark as read
        self.facade.notification_service.mark_read(notification.id)
        
        # Close dialog
        self.accept()
        
        # Route action
        main_window = self.parent()
        if not hasattr(main_window, 'tab_bar'):
            return
        
        if notification.action_key == 'open_tools':
            # Tools lives under Setup → Tools
            setup_index = None
            for i in range(main_window.tab_bar.count()):
                if "Setup" in main_window.tab_bar.tabText(i):
                    setup_index = i
                    break
            if setup_index is not None:
                main_window.tab_bar.setCurrentIndex(setup_index)
                if hasattr(main_window, 'setup_tab') and hasattr(main_window.setup_tab, 'sub_tabs'):
                    sub_tabs = main_window.setup_tab.sub_tabs
                    for j in range(sub_tabs.count()):
                        if "Tools" in sub_tabs.tabText(j):
                            sub_tabs.setCurrentIndex(j)
                            break
        
        elif notification.action_key == 'view_redemptions':
            # Find redemptions tab
            for i in range(main_window.tab_bar.count()):
                if "Redemptions" in main_window.tab_bar.tabText(i):
                    main_window.tab_bar.setCurrentIndex(i)
                    
                    # Highlight the specific redemption if subject_id is a redemption_id
                    if notification.subject_id and hasattr(main_window, 'redemptions_tab'):
                        try:
                            redemption_id = int(notification.subject_id.replace('redemption_', ''))
                            # Give tab time to load, then select the row
                            QTimer.singleShot(150, lambda: self._select_redemption_row(main_window.redemptions_tab, redemption_id))
                        except (ValueError, AttributeError):
                            pass
                    break

    def _select_redemption_row(self, redemptions_tab, redemption_id: int, _retried_all_time: bool = False):
        """Select and highlight a specific redemption row.

        Redemptions are stored in Qt.UserRole of the Date/Time column item.
        """
        if not hasattr(redemptions_tab, 'table'):
            return

        table = redemptions_tab.table

        # Try to find the row by the stored ID.
        for row in range(table.rowCount()):
            id_item = table.item(row, 0)
            if id_item and id_item.data(Qt.UserRole) == redemption_id:
                table.setFocus()
                table.setCurrentCell(row, 0)
                table.selectRow(row)
                table.scrollToItem(id_item, QAbstractItemView.PositionAtCenter)
                return

        # If the row isn't visible (date filter/search/header filters), widen to All Time once.
        if not _retried_all_time:
            if hasattr(redemptions_tab, 'search_edit'):
                redemptions_tab.search_edit.setText("")
            if hasattr(redemptions_tab, 'date_filter') and hasattr(redemptions_tab.date_filter, 'set_all_time'):
                redemptions_tab.date_filter.set_all_time()
                QTimer.singleShot(
                    200,
                    lambda: self._select_redemption_row(redemptions_tab, redemption_id, _retried_all_time=True),
                )
    
    def _dismiss_notification(self, notification_id):
        """Dismiss a notification"""
        self.facade.notification_service.dismiss(notification_id)
        self.load_notifications()
        self._refresh_bell_badge()
    
    def _snooze_notification(self, notification_id, until):
        """Snooze a notification"""
        self.facade.notification_service.snooze(notification_id, until)
        self.load_notifications()
        self._refresh_bell_badge()
    
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
            self._refresh_bell_badge()

    def _mark_read_notification(self, notification_id: int):
        """Mark a notification as read (moves it into the Read group)."""
        self.facade.notification_service.mark_read(notification_id)
        self.load_notifications()
        self._refresh_bell_badge()

    def _mark_unread_notification(self, notification_id: int):
        """Mark a notification as unread (moves it back to the Unread group)."""
        self.facade.notification_service.mark_unread(notification_id)
        self.load_notifications()
        self._refresh_bell_badge()
    
    def _mark_all_read(self):
        """Mark all notifications as read"""
        count = self.facade.notification_service.mark_all_read()
        if count > 0:
            self.load_notifications()
        self._refresh_bell_badge()
