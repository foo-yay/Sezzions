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
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left navigation list
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setMaximumWidth(180)
        self.nav_list.addItems(["Notifications", "Taxes"])
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_section_changed)
        
        # Right content area (stacked widget for sections)
        self.content_stack = QtWidgets.QStackedWidget()
        self.content_stack.addWidget(self._build_notifications_section())
        self.content_stack.addWidget(self._build_taxes_section())
        
        # Assemble
        main_layout.addWidget(self.nav_list)
        main_layout.addWidget(self.content_stack, 1)
        
        # Bottom button row
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        # Add button row to main layout (outside the H split)
        outer_layout = QtWidgets.QVBoxLayout()
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.addLayout(main_layout, 1)
        outer_layout.addLayout(button_layout)
        
        # Replace root layout
        root_widget = QtWidgets.QWidget()
        root_widget.setLayout(outer_layout)
        container_layout = QtWidgets.QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(root_widget)
    
    def _build_notifications_section(self):
        """Build Notifications settings section."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Title
        title = QtWidgets.QLabel("<b>Notification Settings</b>")
        title.setStyleSheet("font-size: 14pt;")
        layout.addRow(title)
        
        # Redemption pending-receipt threshold
        threshold_label = QtWidgets.QLabel("Pending receipt threshold (days):")
        threshold_label.setToolTip("Redemptions without a receipt date older than this will trigger a notification.")
        self.redemption_threshold_spin = QtWidgets.QSpinBox()
        self.redemption_threshold_spin.setMinimum(0)
        self.redemption_threshold_spin.setMaximum(365)
        self.redemption_threshold_spin.setSuffix(" days")
        layout.addRow(threshold_label, self.redemption_threshold_spin)
        
        # Spacer
        layout.addRow(QtWidgets.QLabel(""))
        
        # Future: enable/disable rules toggles can go here
        info_label = QtWidgets.QLabel(
            "<i>Additional notification preferences will be added here in future updates.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray;")
        layout.addRow(info_label)
        
        return widget
    
    def _build_taxes_section(self):
        """Build Taxes settings section (placeholder for Issue #29)."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title = QtWidgets.QLabel("<b>Tax Settings</b>")
        title.setStyleSheet("font-size: 14pt;")
        layout.addWidget(title)
        
        placeholder = QtWidgets.QLabel(
            "<i>Tax withholding estimate settings will appear here once Issue #29 is completed.</i>"
        )
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet("color: gray;")
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
    
    def _on_save(self):
        """Save settings and close dialog."""
        # Write notification settings
        self.settings.settings["redemption_pending_receipt_threshold_days"] = self.redemption_threshold_spin.value()
        
        # Persist to settings.json
        self.settings.save()
        
        # Accept dialog
        self.accept()
    
    def keyPressEvent(self, event):
        """Handle ESC to close."""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
