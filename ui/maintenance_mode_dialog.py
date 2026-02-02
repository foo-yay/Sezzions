"""Maintenance mode dialog for data integrity issues."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from services.data_integrity_service import IntegrityCheckResult


class MaintenanceModeDialog(QDialog):
    """Dialog shown when data integrity issues are detected at startup."""
    
    def __init__(self, check_result: IntegrityCheckResult, parent=None):
        super().__init__(parent)
        self.check_result = check_result
        self.setWindowTitle("Data Integrity Issues Detected")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create dialog UI."""
        layout = QVBoxLayout(self)
        
        # Warning icon and title
        title_layout = QHBoxLayout()
        warning_label = QLabel("⚠️")
        warning_font = QFont()
        warning_font.setPointSize(32)
        warning_label.setFont(warning_font)
        title_layout.addWidget(warning_label)
        
        title_text = QLabel("<b>Maintenance Mode Activated</b>")
        title_font = QFont()
        title_font.setPointSize(16)
        title_text.setFont(title_font)
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Summary
        summary_text = self.check_result.summary()
        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
        
        # Details box
        details_group = QGroupBox("Issue Details")
        details_layout = QVBoxLayout()
        
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setMaximumHeight(200)
        
        # Format violations for display
        details_content = []
        for violation in self.check_result.violations[:50]:  # Limit to first 50
            details_content.append(f"• {violation}")
        
        if len(self.check_result.violations) > 50:
            details_content.append(f"\n... and {len(self.check_result.violations) - 50} more issues")
        
        details_text.setPlainText("\n".join(details_content))
        details_layout.addWidget(details_text)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Instructions
        instructions = QLabel(
            "<b>What you can do:</b><br>"
            "• <b>Continue in Maintenance Mode</b>: Only database tools and CSV import/export will be available<br>"
            "• <b>Complete CSV imports</b> if you're in the middle of importing data, then <b>Recalculate Everything</b><br>"
            "• <b>Restore from a backup</b> if you have a recent clean backup<br>"
            "• <b>Reset database</b> and re-import all data"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        layout.addStretch()
        
        # Buttons
        button_box = QDialogButtonBox()
        continue_button = QPushButton("Continue in Maintenance Mode")
        continue_button.clicked.connect(self.accept)
        continue_button.setDefault(True)
        
        exit_button = QPushButton("Exit Application")
        exit_button.clicked.connect(self.reject)
        
        button_box.addButton(continue_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(exit_button, QDialogButtonBox.ButtonRole.RejectRole)
        
        layout.addWidget(button_box)
