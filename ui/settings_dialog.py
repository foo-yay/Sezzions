"""
Settings dialog (Issue #31).

Provides a centralized Settings UI with sections:
- Notifications (manage notification rules/thresholds)
- Taxes (placeholder for Issue #29 tax withholding)
"""
from PySide6 import QtWidgets, QtCore, QtGui


class AccountingTimeZoneChangeDialog(QtWidgets.QDialog):
    """Dialog to confirm Accounting TZ changes with effective date/time."""

    def __init__(self, current_tz: str, timezones: list[str], selected_tz: str | None = None, parent=None, open_tools_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Change Accounting Time Zone")
        self.setModal(True)
        self.setMinimumSize(520, 320)
        self._open_tools_callback = open_tools_callback

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("🕒 Change Accounting Time Zone")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        info = QtWidgets.QLabel(
            "Accounting time zone changes can rebucket daily totals from the effective date forward.\n"
            "A backup is strongly recommended before applying this change."
        )
        info.setWordWrap(True)
        info.setObjectName("HelperText")
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.tz_combo = QtWidgets.QComboBox()
        self.tz_combo.setEditable(True)
        self.tz_combo.addItems(timezones)
        if selected_tz:
            idx = self.tz_combo.findText(selected_tz)
            if idx >= 0:
                self.tz_combo.setCurrentIndex(idx)
            else:
                self.tz_combo.setCurrentText(selected_tz)
        else:
            idx = self.tz_combo.findText(current_tz)
            if idx >= 0:
                self.tz_combo.setCurrentIndex(idx)
        form.addRow("New Accounting TZ:", self.tz_combo)

        self.effective_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.effective_date.setCalendarPopup(True)
        self.effective_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Effective date:", self.effective_date)

        self.effective_time = QtWidgets.QLineEdit(QtCore.QTime.currentTime().toString("HH:mm:ss"))
        self.effective_time.setPlaceholderText("HH:MM or HH:MM:SS")
        form.addRow("Effective time:", self.effective_time)

        layout.addLayout(form)

        backup_row = QtWidgets.QHBoxLayout()
        backup_label = QtWidgets.QLabel("Backup recommended before rebucketing.")
        backup_label.setObjectName("HelperText")
        backup_row.addWidget(backup_label)
        backup_row.addStretch()
        backup_btn = QtWidgets.QPushButton("Open Tools")
        backup_btn.clicked.connect(self._open_tools)
        backup_row.addWidget(backup_btn)
        layout.addLayout(backup_row)

        self.confirm_checkbox = QtWidgets.QCheckBox("I understand daily totals may change for affected dates")
        self.confirm_checkbox.toggled.connect(self._on_confirm_changed)
        layout.addWidget(self.confirm_checkbox)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        self._ok_button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._on_accept)
        layout.addWidget(buttons)

    def _on_confirm_changed(self, checked: bool):
        self._ok_button.setEnabled(bool(checked))

    def _open_tools(self):
        if self._open_tools_callback:
            self._open_tools_callback()

    def _on_accept(self):
        if not self.confirm_checkbox.isChecked():
            return
        self.accept()

    def values(self) -> tuple[str, str, str]:
        tz_name = self.tz_combo.currentText().strip()
        effective_date = self.effective_date.date().toString("yyyy-MM-dd")
        effective_time = self.effective_time.text().strip() or "00:00:00"
        return tz_name, effective_date, effective_time


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
        self._initial_max_undo = None  # Track initial value for warning (Issue #95)
        self._pending_accounting_tz_change = None
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Build the dialog layout: left nav + content area."""
        # Left navigation list
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setMaximumWidth(180)
        self.nav_list.addItems(["Notifications", "Display", "Time Zones", "Taxes", "Data"])
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_section_changed)
        
        # Right content area (stacked widget for sections)
        self.content_stack = QtWidgets.QStackedWidget()
        self.content_stack.addWidget(self._build_notifications_section())
        self.content_stack.addWidget(self._build_display_section())
        self.content_stack.addWidget(self._build_time_zones_section())
        self.content_stack.addWidget(self._build_taxes_section())
        self.content_stack.addWidget(self._build_data_section())
        
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
        
        # --- Redemption Notifications ---
        redemption_section_label = QtWidgets.QLabel("<b>Redemption Notifications</b>")
        redemption_section_label.setObjectName("SectionLabel")
        layout.addRow(redemption_section_label)
        
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
        
        # --- Backup Notifications ---
        backup_section_label = QtWidgets.QLabel("<b>Backup Notifications</b>")
        backup_section_label.setObjectName("SectionLabel")
        layout.addRow(backup_section_label)
        
        # Notify on backup failure
        failure_label = QtWidgets.QLabel("Notify on backup failure:")
        failure_label.setToolTip("Show notification when automatic backup fails.")
        failure_label.setObjectName("FieldLabel")
        failure_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.backup_notify_failure_checkbox = QtWidgets.QCheckBox()
        layout.addRow(failure_label, self.backup_notify_failure_checkbox)
        
        # Notify when backup overdue
        overdue_label = QtWidgets.QLabel("Notify when backup overdue:")
        overdue_label.setToolTip("Show notification when automatic backup is overdue.")
        overdue_label.setObjectName("FieldLabel")
        overdue_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.backup_notify_overdue_checkbox = QtWidgets.QCheckBox()
        self.backup_notify_overdue_checkbox.toggled.connect(self._on_backup_overdue_toggle)
        layout.addRow(overdue_label, self.backup_notify_overdue_checkbox)
        
        # Overdue threshold
        overdue_threshold_label = QtWidgets.QLabel("Overdue threshold:")
        overdue_threshold_label.setToolTip("Days past scheduled backup time before showing overdue notification.")
        overdue_threshold_label.setObjectName("FieldLabel")
        overdue_threshold_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.backup_overdue_threshold_spin = QtWidgets.QSpinBox()
        self.backup_overdue_threshold_spin.setMinimum(1)
        self.backup_overdue_threshold_spin.setMaximum(30)
        self.backup_overdue_threshold_spin.setSuffix(" day(s)")
        layout.addRow(overdue_threshold_label, self.backup_overdue_threshold_spin)
        layout.setAlignment(overdue_threshold_label, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.setAlignment(self.backup_overdue_threshold_spin, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
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
    
    def _on_backup_overdue_toggle(self, checked):
        """Enable/disable overdue threshold spinbox based on checkbox state."""
        self.backup_overdue_threshold_spin.setEnabled(checked)
    
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

    def _build_time_zones_section(self):
        """Build Time Zones settings section."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        title = QtWidgets.QLabel("🕒 Time Zones")
        title.setObjectName("PageTitle")
        layout.addRow(title)

        from tools.timezone_utils import list_timezones
        tz_list = list_timezones()

        accounting_label = QtWidgets.QLabel("Accounting Time Zone:")
        accounting_label.setToolTip("Controls daily bucketing and reports")
        accounting_label.setObjectName("FieldLabel")
        accounting_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.accounting_tz_combo = QtWidgets.QComboBox()
        self.accounting_tz_combo.setEditable(True)
        self.accounting_tz_combo.addItems(tz_list)
        accounting_label.setMinimumHeight(self.accounting_tz_combo.sizeHint().height())
        layout.addRow(accounting_label, self.accounting_tz_combo)
        layout.setAlignment(accounting_label, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.setAlignment(self.accounting_tz_combo, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.change_accounting_tz_button = QtWidgets.QPushButton("Change Accounting TZ...")
        self.change_accounting_tz_button.setToolTip("Set effective date/time and rebucket daily totals")
        self.change_accounting_tz_button.clicked.connect(self._on_accounting_tz_change_clicked)
        layout.addRow("", self.change_accounting_tz_button)

        self.travel_mode_checkbox = QtWidgets.QCheckBox("Enable Travel Mode (Entry Time Zone)")
        self.travel_mode_checkbox.setToolTip("Use a separate time zone when entering new data")
        self.travel_mode_checkbox.toggled.connect(self._on_travel_mode_toggle)
        layout.addRow("", self.travel_mode_checkbox)

        current_label = QtWidgets.QLabel("Current Entry Time Zone:")
        current_label.setToolTip("Used for new entries when Travel Mode is enabled")
        current_label.setObjectName("FieldLabel")
        current_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.current_tz_combo = QtWidgets.QComboBox()
        self.current_tz_combo.setEditable(True)
        self.current_tz_combo.addItems(tz_list)
        current_label.setMinimumHeight(self.current_tz_combo.sizeHint().height())
        layout.addRow(current_label, self.current_tz_combo)
        layout.setAlignment(current_label, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.setAlignment(self.current_tz_combo, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        info_label = QtWidgets.QLabel(
            "<i>Accounting time zone controls reporting dates. Entry time zone controls how new timestamps are interpreted.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("HelperText")
        layout.addRow(info_label)

        return widget
    
    def _build_taxes_section(self):
        """Build Taxes settings section (Issue #29 tax withholding estimates)."""
        widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(widget)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Title
        title = QtWidgets.QLabel("💰 Tax Settings")
        title.setObjectName("PageTitle")
        form_layout.addRow(title)
        
        # Enable withholding estimates toggle
        enable_label = QtWidgets.QLabel("Enable tax withholding estimates:")
        enable_label.setToolTip("When enabled, computes estimated tax set-aside per closed session.")
        enable_label.setObjectName("FieldLabel")
        enable_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.tax_withholding_enabled_checkbox = QtWidgets.QCheckBox()
        self.tax_withholding_enabled_checkbox.toggled.connect(self._on_withholding_enabled_changed)
        form_layout.addRow(enable_label, self.tax_withholding_enabled_checkbox)
        
        # Default withholding rate %
        rate_label = QtWidgets.QLabel("Default withholding rate (%):")
        rate_label.setToolTip("Default tax withholding % applied to new closed sessions (0-100).")
        rate_label.setObjectName("FieldLabel")
        rate_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.tax_withholding_rate_spin = QtWidgets.QDoubleSpinBox()
        self.tax_withholding_rate_spin.setMinimum(0.0)
        self.tax_withholding_rate_spin.setMaximum(100.0)
        self.tax_withholding_rate_spin.setDecimals(1)
        self.tax_withholding_rate_spin.setSingleStep(0.5)
        self.tax_withholding_rate_spin.setSuffix(" %")
        form_layout.addRow(rate_label, self.tax_withholding_rate_spin)
        
        # Spacer
        form_layout.addRow(QtWidgets.QLabel(""))
        
        # Bulk recalculation button
        recalc_button = QtWidgets.QPushButton("⚙️ Recalculate Withholding...")
        recalc_button.setToolTip("Bulk-recalculate tax withholding for closed sessions.")
        recalc_button.clicked.connect(self._show_recalc_dialog)
        form_layout.addRow("", recalc_button)
        
        # Info label
        info_label = QtWidgets.QLabel(
            "<i>These are estimates only (not legal/tax advice). Consult a tax professional.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("HelperText")
        form_layout.addRow(info_label)
        
        # Store refs for enabling/disabling controls
        self._tax_rate_label = rate_label
        self._tax_recalc_button = recalc_button
        
        return widget
    
    def _build_data_section(self):
        """Build Data settings section (Issue #95 & #97 - undo/redo + audit retention)."""
        widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(widget)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # Title
        title = QtWidgets.QLabel("💾 Data Settings")
        title.setObjectName("PageTitle")
        form_layout.addRow(title)
        
        # Undo/Redo retention section
        section_label = QtWidgets.QLabel("<b>Undo/Redo History</b>")
        form_layout.addRow(section_label)
        
        # Max undo operations
        max_undo_label = QtWidgets.QLabel("Maximum undo operations:")
        max_undo_label.setToolTip(
            "Maximum number of operations that can be undone (0 = disabled).\n"
            "Older operations remain in audit log for compliance, but lose undo capability.\n"
            "Lowering this value will permanently prune undo history."
        )
        max_undo_label.setObjectName("FieldLabel")
        max_undo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.max_undo_spin = QtWidgets.QSpinBox()
        self.max_undo_spin.setMinimum(0)
        self.max_undo_spin.setMaximum(5000)
        self.max_undo_spin.setSingleStep(10)
        self.max_undo_spin.setSpecialValueText("Disabled")
        form_layout.addRow(max_undo_label, self.max_undo_spin)
        
        # Helper text
        helper_text = QtWidgets.QLabel(
            "<i>Limiting undo history helps control database size. Audit trail is always preserved.</i>"
        )
        helper_text.setWordWrap(True)
        helper_text.setObjectName("HelperText")
        form_layout.addRow(helper_text)
        
        # Spacer
        form_layout.addRow(QtWidgets.QLabel(""))
        
        # Audit Log retention section (Issue #97)
        audit_section_label = QtWidgets.QLabel("<b>Audit Log Retention</b>")
        form_layout.addRow(audit_section_label)
        
        # Max audit log rows
        max_audit_label = QtWidgets.QLabel("Maximum audit log rows:")
        max_audit_label.setToolTip(
            "Maximum number of audit log entries to retain (0 = unlimited).\n"
            "Oldest entries are deleted when the limit is exceeded.\n"
            "Compact summaries are preserved for long-term compliance."
        )
        max_audit_label.setObjectName("FieldLabel")
        max_audit_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.max_audit_spin = QtWidgets.QSpinBox()
        self.max_audit_spin.setMinimum(0)
        self.max_audit_spin.setMaximum(100000)
        self.max_audit_spin.setSingleStep(1000)
        self.max_audit_spin.setSpecialValueText("Unlimited")
        form_layout.addRow(max_audit_label, self.max_audit_spin)
        
        # Audit helper text
        audit_helper_text = QtWidgets.QLabel(
            "<i>Audit retention controls long-term compliance storage. Default: 10,000 rows.</i>"
        )
        audit_helper_text.setWordWrap(True)
        audit_helper_text.setObjectName("HelperText")
        form_layout.addRow(audit_helper_text)
        
        return widget
    
    def _on_withholding_enabled_changed(self, checked):
        """Enable/disable withholding rate and recalc when toggle changes."""
        self.tax_withholding_rate_spin.setEnabled(checked)
        self._tax_recalc_button.setEnabled(checked)
    
    def _show_recalc_dialog(self):
        """Show bulk recalculation dialog."""
        from ui.tax_recalc_dialog import TaxRecalcDialog
        dialog = TaxRecalcDialog(self.parent().facade if hasattr(self.parent(), 'facade') else None, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtWidgets.QMessageBox.information(
                self, "Recalculation Complete",
                f"Successfully recalculated {dialog.updated_count} session(s)."
            )
    
    def _on_section_changed(self, index):
        """Switch displayed section when nav list selection changes."""
        self.content_stack.setCurrentIndex(index)

    def _on_travel_mode_toggle(self, checked: bool):
        self.current_tz_combo.setEnabled(bool(checked))

    def _open_tools_tab(self):
        parent = self.parent()
        if parent and hasattr(parent, "switch_to_tab"):
            parent.switch_to_tab("Tools")

    def _on_accounting_tz_change_clicked(self):
        current_tz = self.accounting_tz_combo.currentText().strip()
        dialog = AccountingTimeZoneChangeDialog(
            current_tz=current_tz,
            timezones=[self.accounting_tz_combo.itemText(i) for i in range(self.accounting_tz_combo.count())],
            selected_tz=current_tz,
            parent=self,
            open_tools_callback=self._open_tools_tab,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_tz, effective_date, effective_time = dialog.values()
            if new_tz:
                self.accounting_tz_combo.setCurrentText(new_tz)
            self._pending_accounting_tz_change = {
                "time_zone": new_tz,
                "effective_date": effective_date,
                "effective_time": effective_time,
            }
    
    def _load_settings(self):
        """Load current settings values into UI controls."""
        # Redemption pending-receipt threshold
        threshold_days = self.settings.settings.get("redemption_pending_receipt_threshold_days", 14)
        self.redemption_threshold_spin.setValue(threshold_days)
        
        # Backup notification settings
        backup_config = self.settings.get_automatic_backup_config()
        notify_failure = backup_config.get('notify_on_failure', True)
        notify_overdue = backup_config.get('notify_when_overdue', True)
        overdue_threshold = backup_config.get('overdue_threshold_days', 1)
        
        self.backup_notify_failure_checkbox.setChecked(notify_failure)
        self.backup_notify_overdue_checkbox.setChecked(notify_overdue)
        self.backup_overdue_threshold_spin.setValue(overdue_threshold)
        self.backup_overdue_threshold_spin.setEnabled(notify_overdue)
        
        # Theme selection
        current_theme = self.settings.settings.get("theme", "Light")
        theme_index = self.theme_combo.findText(current_theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)

        # Time zone selection
        accounting_tz = self.settings.settings.get("accounting_time_zone") or self.settings.settings.get("time_zone")
        if accounting_tz:
            tz_index = self.accounting_tz_combo.findText(accounting_tz)
            if tz_index >= 0:
                self.accounting_tz_combo.setCurrentIndex(tz_index)
            else:
                self.accounting_tz_combo.setCurrentText(accounting_tz)

        travel_mode_enabled = self.settings.settings.get("travel_mode_enabled", False)
        self.travel_mode_checkbox.setChecked(travel_mode_enabled)

        current_tz = self.settings.settings.get("current_time_zone") or accounting_tz
        if current_tz:
            tz_index = self.current_tz_combo.findText(current_tz)
            if tz_index >= 0:
                self.current_tz_combo.setCurrentIndex(tz_index)
            else:
                self.current_tz_combo.setCurrentText(current_tz)
        self.current_tz_combo.setEnabled(travel_mode_enabled)
        
        # Tax withholding settings
        tax_enabled = self.settings.settings.get("tax_withholding_enabled", False)
        self.tax_withholding_enabled_checkbox.setChecked(tax_enabled)
        tax_rate = self.settings.settings.get("tax_withholding_default_rate_pct", 20.0)
        self.tax_withholding_rate_spin.setValue(float(tax_rate))
        # Trigger enable/disable state
        self._on_withholding_enabled_changed(tax_enabled)
        
        # Undo/redo retention settings (Issue #95)
        if self.parent() and hasattr(self.parent(), 'facade'):
            facade = self.parent().facade
            if hasattr(facade, 'undo_redo_service'):
                max_undo = facade.undo_redo_service.get_max_undo_operations()
                self.max_undo_spin.setValue(max_undo)
                self._initial_max_undo = max_undo
            else:
                self.max_undo_spin.setValue(100)
                self._initial_max_undo = 100
            
            # Audit retention settings (Issue #97)
            if hasattr(facade, 'audit_service'):
                max_audit = facade.audit_service.get_max_audit_log_rows()
                self.max_audit_spin.setValue(max_audit)
            else:
                self.max_audit_spin.setValue(10000)
        else:
            self.max_undo_spin.setValue(100)
            self._initial_max_undo = 100
            self.max_audit_spin.setValue(10000)
    
    def _on_save(self):
        """Save settings and close dialog."""
        # Write notification settings
        self.settings.settings["redemption_pending_receipt_threshold_days"] = self.redemption_threshold_spin.value()
        
        # Write backup notification settings
        backup_config = self.settings.get_automatic_backup_config()
        backup_config['notify_on_failure'] = self.backup_notify_failure_checkbox.isChecked()
        backup_config['notify_when_overdue'] = self.backup_notify_overdue_checkbox.isChecked()
        backup_config['overdue_threshold_days'] = self.backup_overdue_threshold_spin.value()
        self.settings.set_automatic_backup_config(backup_config)
        
        # Write display settings
        selected_theme = self.theme_combo.currentText()
        self.settings.settings["theme"] = selected_theme

        # Write time zone settings
        previous_tz = self.settings.settings.get("accounting_time_zone") or self.settings.settings.get("time_zone")
        selected_accounting_tz = self.accounting_tz_combo.currentText().strip()
        if not selected_accounting_tz:
            selected_accounting_tz = previous_tz

        effective_change = None
        if selected_accounting_tz and selected_accounting_tz != previous_tz:
            if self._pending_accounting_tz_change and self._pending_accounting_tz_change.get("time_zone") == selected_accounting_tz:
                effective_change = self._pending_accounting_tz_change
            else:
                dialog = AccountingTimeZoneChangeDialog(
                    current_tz=previous_tz or selected_accounting_tz,
                    timezones=[self.accounting_tz_combo.itemText(i) for i in range(self.accounting_tz_combo.count())],
                    selected_tz=selected_accounting_tz,
                    parent=self,
                    open_tools_callback=self._open_tools_tab,
                )
                if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                    return
                new_tz, effective_date, effective_time = dialog.values()
                if not new_tz:
                    return
                selected_accounting_tz = new_tz
                self.accounting_tz_combo.setCurrentText(new_tz)
                effective_change = {
                    "time_zone": new_tz,
                    "effective_date": effective_date,
                    "effective_time": effective_time,
                }

        self.settings.settings["accounting_time_zone"] = selected_accounting_tz
        self.settings.settings["time_zone"] = selected_accounting_tz

        travel_mode_enabled = self.travel_mode_checkbox.isChecked()
        self.settings.settings["travel_mode_enabled"] = travel_mode_enabled
        selected_current_tz = self.current_tz_combo.currentText().strip() if travel_mode_enabled else selected_accounting_tz
        self.settings.settings["current_time_zone"] = selected_current_tz or selected_accounting_tz
        
        # Apply accounting TZ history change (if any)
        if effective_change and self.parent() and hasattr(self.parent(), "facade"):
            facade = self.parent().facade
            if hasattr(facade, "db"):
                from services.accounting_time_zone_service import AccountingTimeZoneService
                tz_service = AccountingTimeZoneService(facade.db, self.settings)
                effective_utc_ts = tz_service.add_history_entry(
                    effective_change["time_zone"],
                    effective_change["effective_date"],
                    effective_change["effective_time"],
                    reason="Settings change",
                )
                tz_service.recompute_from_utc(effective_utc_ts)
                try:
                    facade.db.log_audit(
                        "ACCOUNTING_TZ_CHANGE",
                        "accounting_time_zone_history",
                        f"{previous_tz} -> {effective_change['time_zone']} effective {effective_change['effective_date']} {effective_change['effective_time']}",
                    )
                except Exception:
                    pass

        # Write tax withholding settings
        self.settings.settings["tax_withholding_enabled"] = self.tax_withholding_enabled_checkbox.isChecked()
        self.settings.settings["tax_withholding_default_rate_pct"] = self.tax_withholding_rate_spin.value()
        
        # Handle undo/redo retention (Issue #95)
        new_max_undo = self.max_undo_spin.value()
        if self._initial_max_undo is not None and new_max_undo < self._initial_max_undo:
            # Warn user about permanent pruning
            current_stack_size = 0
            if self.parent() and hasattr(self.parent(), 'facade'):
                facade = self.parent().facade
                if hasattr(facade, 'undo_redo_service'):
                    current_stack_size = len(facade.undo_redo_service._undo_stack)
            
            operations_to_lose = max(0, current_stack_size - new_max_undo)
            
            msg = f"Lowering the limit to {new_max_undo} will permanently remove undo capability for "
            if operations_to_lose > 0:
                msg += f"{operations_to_lose} operation(s).\n\n"
            else:
                msg += "older operations (none currently affected).\n\n"
            msg += "Audit history will be preserved, but you won't be able to undo those operations.\n\n"
            msg += "This action cannot be undone. Continue?"
            
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Undo Limit Reduction",
                msg,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return  # Cancel save
        
        # Apply max undo operations setting
        if self.parent() and hasattr(self.parent(), 'facade'):
            facade = self.parent().facade
            if hasattr(facade, 'undo_redo_service'):
                try:
                    facade.undo_redo_service.set_max_undo_operations(new_max_undo)
                    # Update main window undo/redo states after pruning
                    if hasattr(self.parent(), '_update_undo_redo_states'):
                        self.parent()._update_undo_redo_states()
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Error Setting Undo Limit",
                        f"Failed to apply undo limit:\n\n{str(e)}"
                    )
                    return
            
            # Apply audit retention setting (Issue #97)
            if hasattr(facade, 'audit_service'):
                try:
                    new_max_audit = self.max_audit_spin.value()
                    facade.audit_service.set_max_audit_log_rows(new_max_audit)
                    # Optionally prune immediately
                    pruned = facade.audit_service.prune_audit_log()
                    if pruned > 0:
                        print(f"Pruned {pruned} old audit log entries")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Error Setting Audit Retention",
                        f"Failed to apply audit retention limit:\n\n{str(e)}"
                    )
                    return
        
        # Persist to settings.json
        self.settings.save()
        
        # Apply theme immediately (notify parent window)
        if self.parent() and hasattr(self.parent(), 'apply_theme'):
            self.parent().apply_theme(selected_theme)

        # Refresh data if time zone changed
        if previous_tz != selected_accounting_tz:
            if self.parent() and hasattr(self.parent(), 'refresh_all_tabs'):
                self.parent().refresh_all_tabs()
        
        # Accept dialog
        self.accept()
    
    def keyPressEvent(self, event):
        """Handle ESC to close."""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
