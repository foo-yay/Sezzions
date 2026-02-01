"""
Settings dialog (Issue #31).

Provides a centralized Settings UI with sections:
- Notifications (manage notification rules/thresholds)
- Taxes (placeholder for Issue #29 tax withholding)
"""
from PySide6 import QtWidgets, QtCore, QtGui


class SettingsDialog(QtWidgets.QDialog):
    """
    Centralized Settings dialog with left navigation and section content.
    """
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Build the dialog layout: left nav + content area."""
        # Left navigation list
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setMaximumWidth(180)
        self.nav_list.addItems(["Notifications", "Display", "Taxes"])
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_section_changed)
        
        # Right content area (stacked widget for sections)
        self.content_stack = QtWidgets.QStackedWidget()
        self.content_stack.addWidget(self._build_notifications_section())
        self.content_stack.addWidget(self._build_display_section())
        self.content_stack.addWidget(self._build_taxes_section())
        
        # Horizontal split: nav + content
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.nav_list)
        content_layout.addWidget(self.content_stack, 1)
        
        # Bottom button row
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        
        self.cancel_button = QtWidgets.QPushButton("✖️ Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QtWidgets.QPushButton("💾 Save")
        self.save_button.clicked.connect(self._on_save)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        # Main layout: content + buttons
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.addLayout(content_layout, 1)
        main_layout.addLayout(button_layout)
    
    def _build_notifications_section(self):
        """Build Notifications settings section."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Title
        title = QtWidgets.QLabel("🔔 Notification Settings")
        title.setObjectName("PageTitle")
        layout.addRow(title)
        
        # Redemption pending-receipt threshold
        threshold_label = QtWidgets.QLabel("Pending receipt threshold:")
        threshold_label.setToolTip("Redemptions without a receipt date older than this will trigger a notification.")
        threshold_label.setObjectName("FieldLabel")
        threshold_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.redemption_threshold_spin = QtWidgets.QSpinBox()
        self.redemption_threshold_spin.setMinimum(0)
        self.redemption_threshold_spin.setMaximum(365)
        self.redemption_threshold_spin.setSuffix(" days")
        threshold_label.setMinimumHeight(self.redemption_threshold_spin.sizeHint().height())
        layout.addRow(threshold_label, self.redemption_threshold_spin)
        layout.setAlignment(threshold_label, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.setAlignment(self.redemption_threshold_spin, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Spacer
        layout.addRow(QtWidgets.QLabel(""))
        
        # Future: enable/disable rules toggles can go here
        info_label = QtWidgets.QLabel(
            "<i>Additional notification preferences will be added here in future updates.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("HelperText")
        layout.addRow(info_label)
        
        return widget
    
    def _build_display_section(self):
        """Build Display settings section (theme selection)."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Title
        title = QtWidgets.QLabel("🎨 Display Settings")
        title.setObjectName("PageTitle")
        layout.addRow(title)
        
        # Theme selector
        theme_label = QtWidgets.QLabel("Color Theme:")
        theme_label.setToolTip("Select the application color theme")
        theme_label.setObjectName("FieldLabel")
        theme_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "Blue"])
        theme_label.setMinimumHeight(self.theme_combo.sizeHint().height())
        layout.addRow(theme_label, self.theme_combo)
        layout.setAlignment(theme_label, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.setAlignment(self.theme_combo, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Info label
        info_label = QtWidgets.QLabel(
            "<i>Theme changes take effect immediately after saving.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("HelperText")
        layout.addRow(info_label)
        
        return widget
    
    def _build_taxes_section(self):
        """Build Taxes settings section (placeholder for Issue #29)."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title = QtWidgets.QLabel("💰 Tax Settings")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        
        placeholder = QtWidgets.QLabel(
            "<i>Tax withholding estimate settings will appear here once Issue #29 is completed.</i>"
        )
        placeholder.setWordWrap(True)
        placeholder.setObjectName("HelperText")
        layout.addWidget(placeholder)
        
        layout.addStretch()
        return widget
    
    def _on_section_changed(self, index):
        """Switch displayed section when nav list selection changes."""
        self.content_stack.setCurrentIndex(index)
    
    def _load_settings(self):
        """Load current settings values into UI controls."""
        # Redemption pending-receipt threshold
        threshold_days = self.settings.settings.get("redemption_pending_receipt_threshold_days", 14)
        self.redemption_threshold_spin.setValue(threshold_days)
        
        # Theme selection
        current_theme = self.settings.settings.get("theme", "Light")
        theme_index = self.theme_combo.findText(current_theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
    
    def _on_save(self):
        """Save settings and close dialog."""
        # Write notification settings
        self.settings.settings["redemption_pending_receipt_threshold_days"] = self.redemption_threshold_spin.value()
        
        # Write display settings
        selected_theme = self.theme_combo.currentText()
        self.settings.settings["theme"] = selected_theme
        
        # Persist to settings.json
        self.settings.save()
        
        # Apply theme immediately (notify parent window)
        if self.parent() and hasattr(self.parent(), 'apply_theme'):
            self.parent().apply_theme(selected_theme)
        
        # Accept dialog
        self.accept()
    
    def keyPressEvent(self, event):
        """Handle ESC to close."""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
