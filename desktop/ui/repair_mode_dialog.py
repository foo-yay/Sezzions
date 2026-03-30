"""
Repair Mode confirmation dialog (Issue #55)

Shows warnings and requires explicit acknowledgment before enabling Repair Mode.
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QCheckBox, QFrame)
from PySide6.QtCore import Qt


class RepairModeConfirmDialog(QDialog):
    """Dialog to confirm enabling Repair Mode with explicit warnings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enable Repair Mode? (Advanced)")
        self.setModal(True)
        self.setMinimumWidth(550)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Warning icon + title
        title_layout = QHBoxLayout()
        title_label = QLabel("⚠️ <b>Enable Repair Mode?</b>")
        title_label.setStyleSheet("font-size: 14px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Warning bullets
        warnings = QLabel(
            "• <b>Auto-rebuild/auto-cascade is DISABLED</b> (FIFO allocations, session P/L, event links).<br><br>"
            "• Reports and balances may look <b>wrong</b> until you explicitly rebuild.<br><br>"
            "• You are <b>responsible</b> for rebuilding affected pairs after edits.<br><br>"
            "• Use only if you understand the risks."
        )
        warnings.setWordWrap(True)
        warnings.setTextFormat(Qt.RichText)
        warnings.setStyleSheet("padding: 12px; background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 4px;")
        layout.addWidget(warnings)
        
        # Acknowledgment checkbox
        self.ack_checkbox = QCheckBox("I understand derived calculations will not update automatically.")
        self.ack_checkbox.setStyleSheet("font-weight: bold;")
        self.ack_checkbox.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self.ack_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.enable_button = QPushButton("Enable Repair Mode")
        self.enable_button.setEnabled(False)
        self.enable_button.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; font-weight: bold; padding: 8px 16px; }"
            "QPushButton:hover { background-color: #c82333; }"
            "QPushButton:disabled { background-color: #cccccc; color: #666666; }"
        )
        self.enable_button.clicked.connect(self.accept)
        button_layout.addWidget(self.enable_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("padding: 8px 16px;")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _on_checkbox_toggled(self, checked):
        """Enable/disable the Enable button based on checkbox state."""
        self.enable_button.setEnabled(checked)
