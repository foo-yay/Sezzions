"""
Tax withholding bulk recalculation dialog (Issue #29).

Provides a UI for triggering TaxWithholdingService.bulk_recalculate().
"""
from PySide6 import QtWidgets, QtCore


class TaxRecalcDialog(QtWidgets.QDialog):
    """
    Dialog for bulk-recalculating tax withholding estimates.
    """
    
    def __init__(self, facade, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.updated_count = 0
        self.setObjectName("TaxRecalcDialog")
        self.setWindowTitle("Recalculate Tax Withholding")
        self.setMinimumWidth(500)
        self.setModal(True)
        
        self._setup_ui()
        self._load_filter_options()
    
    def _setup_ui(self):
        """Build dialog layout."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        title = QtWidgets.QLabel("⚙️ Bulk Recalculate Tax Withholding")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        
        # Warning
        warning_label = QtWidgets.QLabel(
            "<b>⚠️ Warning:</b> This will <u>overwrite</u> historical withholding values "
            "for closed sessions using the current default rate from Settings."
        )
        warning_label.setWordWrap(True)
        warning_label.setObjectName("HelperText")
        layout.addWidget(warning_label)
        
        # Filters group
        filter_group = QtWidgets.QGroupBox("Scope")
        filter_layout = QtWidgets.QFormLayout(filter_group)
        filter_layout.setSpacing(10)
        filter_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Site filter
        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.site_combo.lineEdit().setPlaceholderText("All Sites")
        filter_layout.addRow("Site:", self.site_combo)
        
        # User filter
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.user_combo.lineEdit().setPlaceholderText("All Users")
        filter_layout.addRow("User:", self.user_combo)
        
        layout.addWidget(filter_group)
        
        # Options
        options_group = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)
        options_layout.setSpacing(8)
        
        self.overwrite_custom_checkbox = QtWidgets.QCheckBox(
            "Overwrite custom session withholding rates"
        )
        self.overwrite_custom_checkbox.setToolTip(
            "If checked, sessions with user-entered custom rates will also be recalculated. "
            "If unchecked, only sessions using the default rate will be updated."
        )
        options_layout.addWidget(self.overwrite_custom_checkbox)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QtWidgets.QPushButton("✖️ Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.recalc_button = QtWidgets.QPushButton("⚙️ Recalculate")
        self.recalc_button.clicked.connect(self._on_recalculate)
        self.recalc_button.setDefault(True)
        button_layout.addWidget(self.recalc_button)
        
        layout.addLayout(button_layout)
    
    def _load_filter_options(self):
        """Populate site and user dropdowns."""
        if self.facade is None:
            return
        
        # Load sites
        try:
            sites = self.facade.get_all_sites()
            for site in sites:
                self.site_combo.addItem(site.name, site.id)
        except Exception:
            pass
        
        # Load users
        try:
            users = self.facade.get_all_users()
            for user in users:
                self.user_combo.addItem(user.name, user.id)
        except Exception:
            pass
    
    def _on_recalculate(self):
        """Execute bulk recalculation."""
        if self.facade is None or not hasattr(self.facade, 'tax_withholding_service'):
            QtWidgets.QMessageBox.critical(
                self, "Error", "Tax withholding service not available."
            )
            return
        
        # Confirm
        site_text = self.site_combo.currentText().strip()
        user_text = self.user_combo.currentText().strip()
        overwrite = self.overwrite_custom_checkbox.isChecked()
        
        # If text is empty or doesn't match any item, treat as "All"
        site_display = site_text if site_text else "All Sites"
        user_display = user_text if user_text else "All Users"
        
        confirm_msg = (
            f"This will recalculate tax withholding for closed sessions:\n"
            f"  • Site: {site_display}\n"
            f"  • User: {user_display}\n"
            f"  • Overwrite custom rates: {'Yes' if overwrite else 'No'}\n\n"
            f"Historical values will be overwritten. Continue?"
        )
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Recalculation", confirm_msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        # Execute - get ID from currentData() or find by text, None = all
        site_id = self.site_combo.currentData()
        user_id = self.user_combo.currentData()
        
        # If currentData is None but we have text, find the ID
        if site_id is None and site_text:
            for i in range(self.site_combo.count()):
                if self.site_combo.itemText(i).lower() == site_text.lower():
                    site_id = self.site_combo.itemData(i)
                    break
        
        if user_id is None and user_text:
            for i in range(self.user_combo.count()):
                if self.user_combo.itemText(i).lower() == user_text.lower():
                    user_id = self.user_combo.itemData(i)
                    break
        
        try:
            self.updated_count = self.facade.tax_withholding_service.bulk_recalculate(
                site_id=site_id,
                user_id=user_id,
                overwrite_custom=overwrite
            )
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Recalculation Error", f"Failed to recalculate:\n{e}"
            )
    
    def keyPressEvent(self, event):
        """Handle ESC to close."""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
