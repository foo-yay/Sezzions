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
            "for daily sessions using the current default rate from Settings."
        )
        warning_label.setWordWrap(True)
        warning_label.setObjectName("HelperText")
        layout.addWidget(warning_label)
        
        # Date range filter section
        filter_section = QtWidgets.QWidget()
        filter_section.setObjectName("SectionBackground")
        filter_layout = QtWidgets.QHBoxLayout(filter_section)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(12)
        
        # Start date
        from_label = QtWidgets.QLabel("From:")
        from_label.setObjectName("FieldLabel")
        filter_layout.addWidget(from_label)
        
        self.start_date_edit = QtWidgets.QLineEdit()
        self.start_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.start_date_edit.setFixedWidth(120)
        filter_layout.addWidget(self.start_date_edit)
        
        self.start_calendar_btn = QtWidgets.QPushButton("📅")
        self.start_calendar_btn.setFixedWidth(44)
        self.start_calendar_btn.clicked.connect(lambda: self._pick_date(self.start_date_edit))
        filter_layout.addWidget(self.start_calendar_btn)
        
        self.clear_start_btn = QtWidgets.QPushButton("Clear")
        self.clear_start_btn.clicked.connect(lambda: self.start_date_edit.clear())
        filter_layout.addWidget(self.clear_start_btn)
        
        filter_layout.addSpacing(30)
        
        # End date
        to_label = QtWidgets.QLabel("To:")
        to_label.setObjectName("FieldLabel")
        filter_layout.addWidget(to_label)
        
        self.end_date_edit = QtWidgets.QLineEdit()
        self.end_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.end_date_edit.setFixedWidth(120)
        filter_layout.addWidget(self.end_date_edit)
        
        self.end_calendar_btn = QtWidgets.QPushButton("📅")
        self.end_calendar_btn.setFixedWidth(44)
        self.end_calendar_btn.clicked.connect(lambda: self._pick_date(self.end_date_edit))
        filter_layout.addWidget(self.end_calendar_btn)
        
        self.clear_end_btn = QtWidgets.QPushButton("Clear")
        self.clear_end_btn.clicked.connect(lambda: self.end_date_edit.clear())
        filter_layout.addWidget(self.clear_end_btn)
        
        filter_layout.addStretch()
        
        layout.addWidget(filter_section)
        
        # Info message
        info_label = QtWidgets.QLabel(
            "<b>ℹ️ Scope:</b> Tax is computed on the net P/L of all users for each date. "
            "Leave date range empty to recalculate all dates."
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("HelperText")
        layout.addWidget(info_label)
        
        # Options
        options_group = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)
        options_layout.setSpacing(8)
        
        self.overwrite_custom_checkbox = QtWidgets.QCheckBox(
            "Overwrite custom daily withholding rates"
        )
        self.overwrite_custom_checkbox.setToolTip(
            "If checked, daily sessions with user-entered custom rates will also be recalculated. "
            "If unchecked, only daily sessions using the default rate will be updated."
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
        """No longer needed - filters removed."""
        pass
    
    def _pick_date(self, target_edit: QtWidgets.QLineEdit):
        """Show calendar picker for date selection."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        
        # Parse current date if any
        current_text = target_edit.text().strip()
        if current_text:
            try:
                from datetime import datetime
                parsed = datetime.strptime(current_text, "%Y-%m-%d")
                calendar.setSelectedDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
            except:
                calendar.setSelectedDate(QtCore.QDate.currentDate())
        else:
            calendar.setSelectedDate(QtCore.QDate.currentDate())
        
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            selected = calendar.selectedDate()
            target_edit.setText(selected.toString("yyyy-MM-dd"))
    
    def _on_recalculate(self):
        """Execute bulk recalculation."""
        if self.facade is None or not hasattr(self.facade, 'tax_withholding_service'):
            QtWidgets.QMessageBox.critical(
                self, "Error", "Tax withholding service not available."
            )
            return
        
        overwrite = self.overwrite_custom_checkbox.isChecked()
        
        # Get date range from text fields (empty string = None)
        start_date = self.start_date_edit.text().strip() or None
        end_date = self.end_date_edit.text().strip() or None
        
        # Validate date format if provided
        if start_date:
            try:
                from datetime import datetime
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid Date", "Start date must be in YYYY-MM-DD format."
                )
                return
        
        if end_date:
            try:
                from datetime import datetime
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid Date", "End date must be in YYYY-MM-DD format."
                )
                return
        
        # Build confirmation message
        date_range_display = "All dates"
        if start_date and end_date:
            date_range_display = f"{start_date} to {end_date}"
        elif start_date:
            date_range_display = f"From {start_date} onwards"
        elif end_date:
            date_range_display = f"Up to {end_date}"
        
        confirm_msg = (
            f"This will recalculate tax withholding:\n"
            f"  • Date range: {date_range_display}\n"
            f"  • Overwrite custom rates: {'Yes' if overwrite else 'No'}\n\n"
            f"Historical values will be overwritten. Continue?"
        )
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Recalculation", confirm_msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        try:
            self.updated_count = self.facade.tax_withholding_service.bulk_recalculate(
                start_date=start_date,
                end_date=end_date,
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
