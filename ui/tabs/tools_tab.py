"""
Tools Tab - Recalculation, CSV Import/Export, Database Tools, Audit
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFileDialog,
    QComboBox, QCompleter, QListView, QDialog, QLineEdit,
    QCheckBox, QSpinBox, QSizePolicy, QToolButton, QFrame
)
from PySide6.QtCore import QThreadPool, Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFontMetrics
from typing import Optional
import os
from datetime import datetime
import zipfile
import tempfile

from ui.tools_workers import RecalculationWorker
from ui.tools_dialogs import (
    ProgressDialog,
    RecalculationProgressDialog,
    RecalculationResultDialog,
    PostImportPromptDialog
)
from ui.csv_dialogs import (
    ImportPreviewDialog,
    ImportResultDialog,
    ExportOptionsDialog
)
from services.tools.dtos import ImportResult
from ui.repair_mode_dialog import RepairModeConfirmDialog


class ToolsTab(QWidget):
    """Tools tab for recalculation, imports, exports, and database operations"""
    
    # Signal emitted after database-modifying operations (backup/restore/reset)
    data_changed = Signal()
    
    def __init__(self, app_facade, parent=None, settings=None):
        super().__init__(parent)
        self.facade = app_facade
        self.settings = settings  # Store settings for persistence
        self.backup_dir = ''  # Initialize backup directory attribute
        self.thread_pool = QThreadPool.globalInstance()
        self._active_progress_dialog = None  # Store active progress dialog to prevent GC
        self._active_tools_worker = None  # Strong ref to active QRunnable to prevent GC
        self._background_tools_workers = []  # Strong refs for non-UI (auto) background workers
        self._setup_ui()
    
    def _get_settings_dict(self):
        """Get settings dictionary for passing to worker threads.
        
        Walks up widget hierarchy to find MainWindow and extract settings.
        Returns empty dict if MainWindow not found (graceful degradation).
        """
        widget = self
        while widget:
            if hasattr(widget, 'settings') and hasattr(widget.settings, 'settings'):
                return dict(widget.settings.settings)
            widget = widget.parentWidget()
        return {}
    
    def _get_settings_object(self):
        """Get settings object for reading/writing settings.
        
        Uses stored settings if available, otherwise walks up widget hierarchy.
        Returns None if not found.
        """
        # Use stored settings if available
        if self.settings and hasattr(self.settings, 'get'):
            return self.settings
        
        # Fall back to parent walk
        widget = self
        while widget:
            if hasattr(widget, 'settings') and hasattr(widget.settings, 'get'):
                return widget.settings
            widget = widget.parentWidget()
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "backup_dir_input") and hasattr(self, "backup_dir"):
            # Re-elide on resize so the display remains compact.
            self._set_backup_location_display(self.backup_dir)
        
    def _setup_ui(self):
        """Setup the UI components"""
        self.setObjectName("ToolsTabBackground")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header (match other Setup sub-tabs)
        header_layout = QHBoxLayout()
        title = QLabel("Tools")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # These Setup sub-tabs (Users/Sites/Cards/etc.) include a search box + buttons on the right.
        # Tools doesn't need search, but we still match the header row height/vertical alignment.
        dummy_search = QLineEdit()
        dummy_search.setFixedWidth(0)
        dummy_search.setMaximumWidth(0)
        header_layout.addWidget(dummy_search)

        dummy_clear = QPushButton("Clear")
        dummy_clear.setFixedWidth(0)
        dummy_clear.setMaximumWidth(0)
        header_layout.addWidget(dummy_clear)

        dummy_clear_filters = QPushButton("Clear All Filters")
        dummy_clear_filters.setFixedWidth(0)
        dummy_clear_filters.setMaximumWidth(0)
        header_layout.addWidget(dummy_clear_filters)

        layout.addLayout(header_layout)
        
        # Repair Mode Section
        repair_group = self._create_repair_mode_group()
        repair_collapsible = self._create_collapsible_section("🔧 Repair Mode", repair_group, section_id="repair_mode", expanded=False)
        layout.addWidget(repair_collapsible)
        
        # Recalculation Section
        recalc_group = self._create_recalculation_group()
        recalc_collapsible = self._create_collapsible_section("🔄 Recalculation Tools", recalc_group, section_id="recalculation", expanded=False)
        layout.addWidget(recalc_collapsible)
        
        # CSV Import/Export Section
        csv_group = self._create_csv_group()
        csv_collapsible = self._create_collapsible_section("📄 CSV Import / Export", csv_group, section_id="csv_tools", expanded=False)
        layout.addWidget(csv_collapsible)
        
        # Adjustments & Corrections Section
        adjustments_group = self._create_adjustments_group()
        adjustments_collapsible = self._create_collapsible_section("⚖️ Adjustments & Corrections", adjustments_group, section_id="adjustments", expanded=False)
        layout.addWidget(adjustments_collapsible)
        
        # Database Tools Section
        db_group = self._create_database_group()
        db_collapsible = self._create_collapsible_section("🔧 Database Tools", db_group, section_id="database_tools", expanded=False)
        layout.addWidget(db_collapsible)
        
        # Audit Log Section (Issue #92)
        audit_group = self._create_audit_log_group()
        audit_collapsible = self._create_collapsible_section("📋 Audit Log", audit_group, section_id="audit_log", expanded=False)
        layout.addWidget(audit_collapsible)
        
        layout.addStretch()
    
    def _create_collapsible_section(self, title: str, content_widget: QWidget, section_id: str = None, expanded: bool = False) -> QWidget:
        """Create a collapsible section with a title and content.
        
        Args:
            title: Section title text
            content_widget: Widget to show/hide
            section_id: Unique identifier for persisting expand/collapse state
            expanded: Default expanded state (overridden by saved state if section_id provided)
        """
        # Restore saved state if section_id provided
        if section_id:
            settings = self._get_settings_object()
            if settings:
                section_state_key = f'tools_section_{section_id}_expanded'
                expanded = settings.get(section_state_key, expanded)
        
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        container.setObjectName("CollapsibleSection")
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header button
        header_btn = QToolButton()
        header_btn.setText(title)
        header_btn.setCheckable(True)
        header_btn.setChecked(expanded)
        header_btn.setObjectName("CollapsibleHeader")
        header_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        header_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        
        layout.addWidget(header_btn)
        
        # Content container
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(8, 4, 8, 8)
        content_layout.addWidget(content_widget)
        
        content_container.setVisible(expanded)
        layout.addWidget(content_container)
        
        # Toggle function
        def toggle():
            is_expanded = header_btn.isChecked()
            header_btn.setArrowType(Qt.DownArrow if is_expanded else Qt.RightArrow)
            content_container.setVisible(is_expanded)
            
            # Save state if section_id provided
            if section_id:
                settings = self._get_settings_object()
                if settings:
                    section_state_key = f'tools_section_{section_id}_expanded'
                    settings.set(section_state_key, is_expanded)
        
        header_btn.toggled.connect(toggle)
        
        return container
    
    def _create_repair_mode_group(self) -> QWidget:
        """Create the repair mode section"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Description
        desc_label = QLabel(
            "Repair Mode disables automatic derived data rebuilds after edits. "
            "Use when troubleshooting data corruption or performing large bulk operations. "
            "Stale pairs must be rebuilt manually."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)

        layout.addSpacing(6)

        # Status row
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)
        
        status_label = QLabel("Status:")
        status_label.setObjectName("FieldLabel")
        status_layout.addWidget(status_label)
        
        # Status indicator
        self.repair_mode_indicator = QLabel()
        self._update_repair_mode_indicator()
        status_layout.addWidget(self.repair_mode_indicator)
        
        status_layout.addStretch()
        
        # Toggle button
        self.repair_mode_toggle_btn = QPushButton()
        self.repair_mode_toggle_btn.clicked.connect(self._on_repair_mode_toggle)
        self._update_repair_mode_button()
        status_layout.addWidget(self.repair_mode_toggle_btn)
        
        layout.addLayout(status_layout)
        
        # Stale pairs info row
        stale_layout = QHBoxLayout()
        stale_layout.setSpacing(8)
        
        stale_label = QLabel("Stale Pairs:")
        stale_label.setObjectName("FieldLabel")
        stale_layout.addWidget(stale_label)
        
        self.stale_pairs_count_label = QLabel()
        self._update_stale_pairs_count()
        stale_layout.addWidget(self.stale_pairs_count_label)
        
        stale_layout.addStretch()
        
        # Rebuild stale button
        self.rebuild_stale_btn = QPushButton("🔄 Rebuild Stale Pairs")
        self.rebuild_stale_btn.clicked.connect(self._on_rebuild_stale_pairs)
        stale_layout.addWidget(self.rebuild_stale_btn)
        
        # Clear stale button
        self.clear_stale_btn = QPushButton("🧹 Clear Stale List")
        self.clear_stale_btn.clicked.connect(self._on_clear_stale_pairs)
        stale_layout.addWidget(self.clear_stale_btn)
        
        # Initially hide buttons if not in repair mode (will be shown/hidden in _refresh_repair_mode_ui)
        if not (self.facade.repair_mode_service and self.facade.repair_mode_service.is_enabled()):
            self.rebuild_stale_btn.hide()
            self.clear_stale_btn.hide()
        
        layout.addLayout(stale_layout)
        
        container_layout.addWidget(section)
        return container
    
    def _create_recalculation_group(self) -> QWidget:
        """Create the recalculation section"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Description
        desc_label = QLabel(
            "Recalculate derived accounting data (FIFO allocations, cost basis, P/L). "
            "This should be run after importing data or correcting errors."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)

        layout.addSpacing(6)

        # Row 1: scoped recalculation
        scoped_layout = QHBoxLayout()
        scoped_layout.setSpacing(8)
        scoped_label = QLabel("Recalculate for:")
        scoped_label.setObjectName("FieldLabel")
        scoped_layout.addWidget(scoped_label)
        
        # User selector with autocomplete
        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setMinimumWidth(200)
        self.user_combo.lineEdit().setPlaceholderText("All Users")
        self._load_users()
        scoped_layout.addWidget(self.user_combo)
        
        # Site selector with autocomplete
        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.setMinimumWidth(200)
        self.site_combo.lineEdit().setPlaceholderText("All Sites")
        self._load_sites()
        scoped_layout.addWidget(self.site_combo)
        
        # Scoped recalculate button
        recalc_scoped_btn = QPushButton("🎯 Recalculate Pair")
        recalc_scoped_btn.clicked.connect(self._on_recalculate_scoped)
        scoped_layout.addWidget(recalc_scoped_btn)
        
        scoped_layout.addStretch()
        layout.addLayout(scoped_layout)
        
        layout.addSpacing(6)

        # Row 2: full recalculation (size-to-content)
        primary_row = QHBoxLayout()
        primary_row.setSpacing(8)
        recalc_all_btn = QPushButton("🔄 Recalculate Everything")
        recalc_all_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        recalc_all_btn.clicked.connect(self._on_recalculate_all)
        primary_row.addWidget(recalc_all_btn)
        primary_row.addStretch(1)
        layout.addLayout(primary_row)
        
        # Statistics display
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("HelperText")
        layout.addWidget(self.stats_label)
        self._update_stats()
        
        container_layout.addWidget(section)
        return container
        
    def _create_csv_group(self) -> QWidget:
        """Create the CSV import/export section."""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        desc_label = QLabel(
            "Import and export data as CSV files. "
            "Import validates data and shows preview before committing."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)

        layout.addSpacing(6)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        import_btn = QPushButton("📥 Import CSV")
        import_btn.clicked.connect(self._on_import_csv)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._on_export_csv)
        btn_layout.addWidget(export_btn)
        
        download_template_btn = QPushButton("📄 Download Template")
        download_template_btn.clicked.connect(self._on_download_template)
        btn_layout.addWidget(download_template_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        container_layout.addWidget(section)
        return container
    
    def _create_adjustments_group(self) -> QWidget:
        """Create the Adjustments & Corrections section."""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        desc_label = QLabel(
            "Create basis corrections and balance checkpoints. "
            "Basis adjustments affect FIFO cost basis calculations. "
            "Checkpoints override previous balances in expected balance computations."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)
        
        layout.addSpacing(6)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        basis_btn = QPushButton("💵 New Basis Adjustment")
        basis_btn.clicked.connect(self._on_create_basis_adjustment)
        btn_layout.addWidget(basis_btn)
        
        checkpoint_btn = QPushButton("📌 New Balance Checkpoint")
        checkpoint_btn.clicked.connect(self._on_create_checkpoint)
        btn_layout.addWidget(checkpoint_btn)
        
        view_btn = QPushButton("📋 View Adjustments")
        view_btn.clicked.connect(self._on_view_adjustments)
        btn_layout.addWidget(view_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        container_layout.addWidget(section)
        return container
        
    def _create_database_group(self) -> QWidget:
        """Create unified database tools section with streamlined backup controls"""
        from PySide6.QtCore import QTimer
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        desc_label = QLabel(
            "Backup, restore, and reset database. "
            "Always create a backup before restore or reset operations."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)
        
        layout.addSpacing(6)

        # Two simple rows (no grid/columns)
        # Row 1: Backup Location:, backup field, Browse
        backup_row_layout = QHBoxLayout()
        backup_row_layout.setContentsMargins(0, 0, 0, 0)
        backup_row_layout.setSpacing(8)

        backup_label = QLabel("Backup Location:")
        backup_label.setObjectName("FieldLabel")
        backup_row_layout.addWidget(backup_label)

        self.backup_dir_input = QLabel("Not set")
        self.backup_dir_input.setObjectName("InfoField")
        self.backup_dir_input.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.backup_dir_input.setToolTip("Select a backup directory")
        self.backup_dir_input.setFixedWidth(325)
        backup_row_layout.addWidget(self.backup_dir_input)

        browse_btn = QPushButton("📁 Browse")
        browse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        browse_btn.clicked.connect(self._on_select_backup_directory)
        backup_row_layout.addWidget(browse_btn)

        backup_row_widget = QWidget()
        backup_row_widget.setLayout(backup_row_layout)
        backup_row_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        layout.addWidget(backup_row_widget, 0, Qt.AlignLeft)

        # Row 2: Backup Now, Restore, Reset, auto-backup controls (all left-justified; compact sizing)
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        
        # Backup Now button
        self.backup_now_btn = QPushButton("💾 Backup Now")
        self.backup_now_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.backup_now_btn.setEnabled(False)
        self.backup_now_btn.clicked.connect(self._on_backup_now)
        actions_layout.addWidget(self.backup_now_btn)
        
        # Restore button
        restore_btn = QPushButton("♻️ Restore")
        restore_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        restore_btn.clicked.connect(self._on_restore_database)
        actions_layout.addWidget(restore_btn)
        
        # Reset button
        reset_btn = QPushButton("🗑️ Reset")
        reset_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        reset_btn.setObjectName("DangerButton")
        reset_btn.clicked.connect(self._on_reset_database)
        actions_layout.addWidget(reset_btn)

        
        # Automatic backup checkbox
        self.auto_backup_enabled_checkbox = QCheckBox("Auto backup every")
        self.auto_backup_enabled_checkbox.toggled.connect(self._on_auto_backup_toggle)
        actions_layout.addWidget(self.auto_backup_enabled_checkbox)
        
        # Frequency spinbox using global stylesheet
        self.auto_backup_frequency_spinbox = QSpinBox()
        self.auto_backup_frequency_spinbox.setRange(1, 30)  # 1 to 30 days
        self.auto_backup_frequency_spinbox.setValue(1)
        self.auto_backup_frequency_spinbox.setSuffix(" day(s)")
        self.auto_backup_frequency_spinbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.auto_backup_frequency_spinbox.setEnabled(False)
        self.auto_backup_frequency_spinbox.valueChanged.connect(self._on_auto_backup_frequency_changed)
        actions_layout.addWidget(self.auto_backup_frequency_spinbox)

        actions_widget = QWidget()
        actions_widget.setLayout(actions_layout)
        actions_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        layout.addWidget(actions_widget, 0, Qt.AlignLeft)

        # Last backup status (subtle)
        self.last_backup_label = QLabel("Last backup: —")
        self.last_backup_label.setObjectName("HelperText")
        layout.addWidget(self.last_backup_label)
        
        # Timer for checking backup schedule (check every 5 minutes)
        self.backup_check_timer = QTimer(self)
        self.backup_check_timer.timeout.connect(self._check_automatic_backup)
        self.backup_check_timer.setInterval(5 * 60 * 1000)  # 5 minutes
        
        # Load saved settings
        self._load_automatic_backup_settings()
        
        container_layout.addWidget(section)
        return container

    def _set_backup_location_display(self, directory: str):
        """Set backup location display with elided (middle) path and tooltip."""
        directory = directory or ""
        if not directory:
            self.backup_dir_input.setText("Not set")
            self.backup_dir_input.setToolTip("Select a backup directory")
            return

        self.backup_dir_input.setToolTip(directory)
        metrics = QFontMetrics(self.backup_dir_input.font())
        width = max(120, self.backup_dir_input.width() - 16)
        elided = metrics.elidedText(directory, Qt.ElideMiddle, width)
        self.backup_dir_input.setText(elided)
    
    def _create_audit_log_group(self) -> QWidget:
        """Create audit log section (Issue #92)"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        desc_label = QLabel(
            "View audit trail of CRUD operations, including JSON snapshots, undo/redo history, "
            "and database maintenance activities. Use filters to find specific operations or groups."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)
        
        layout.addSpacing(6)
        
        # Action row
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        
        # Open Audit Log button
        open_audit_btn = QPushButton("📋 Open Audit Log…")
        open_audit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        open_audit_btn.clicked.connect(self._on_open_audit_log)
        action_layout.addWidget(open_audit_btn)
        
        action_layout.addStretch()
        
        # Reset button (clear audit log)
        reset_audit_btn = QPushButton("🗑️ Reset")
        reset_audit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        reset_audit_btn.setObjectName("DangerButton")
        reset_audit_btn.clicked.connect(self._on_clear_audit_log)
        action_layout.addWidget(reset_audit_btn)
        
        layout.addLayout(action_layout)
        
        container_layout.addWidget(section)
        return container
        
    def _load_users(self):
        """Load users into combo box"""
        self.user_combo.clear()
        
        try:
            users = self.facade.user_service.list_active_users()
            for user in users:
                self.user_combo.addItem(user.name, user.id)
            self._setup_completer(self.user_combo)
            
            # Set to empty (show placeholder) by default
            self.user_combo.setCurrentIndex(-1)
        except Exception as e:
            print(f"Error loading users: {e}")
            
    def _load_sites(self):
        """Load sites into combo box"""
        self.site_combo.clear()
        
        try:
            sites = self.facade.site_service.list_active_sites()
            for site in sites:
                self.site_combo.addItem(site.name, site.id)
            self._setup_completer(self.site_combo)
            
            # Set to empty (show placeholder) by default
            self.site_combo.setCurrentIndex(-1)
        except Exception as e:
            print(f"Error loading sites: {e}")
    
    def _setup_completer(self, combo: QComboBox):
        """Setup autocomplete for a combo box"""
        if not combo.isEditable():
            return
            
        completer = QCompleter(combo.model())
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(completer)
        line_edit = combo.lineEdit()
        if line_edit:
            line_edit.setCompleter(completer)
            
    def _update_stats(self):
        """Update statistics display"""
        try:
            stats = self.facade.recalculation_service.get_stats()
            
            self.stats_label.setText(
                f"Database: {stats['pairs']} pairs, "
                f"{stats['purchases']} purchases, "
                f"{stats['redemptions']} redemptions, "
                f"{stats['sessions']} sessions, "
                f"{stats['allocations']} allocations"
            )
        except Exception as e:
            self.stats_label.setText(f"Could not load statistics: {e}")
            
    def _on_recalculate_all(self):
        """Handle recalculate everything button click"""
        # Confirmation dialog with correct terminology
        reply = QMessageBox.question(
            self,
            "Recalculate Everything",
            "This will rebuild ALL calculations from scratch:\n\n"
            "1. FIFO cost basis for all redemptions\n"
            "2. Session taxable P/L (gameplay-based)\n"
            "3. Daily totals\n\n"
            "This may take a moment for large databases.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog("Recalculate Everything", self)
        
        # Create worker with database path (creates its own connection for thread safety)
        worker = RecalculationWorker(
            self.facade.db.db_path,
            operation="all",
            settings_dict=self._get_settings_dict()
        )
        
        # Connect signals
        worker.signals.progress.connect(progress_dialog.update_progress)
        worker.signals.finished.connect(lambda result: self._on_recalculation_finished(result, progress_dialog))
        worker.signals.error.connect(lambda error: self._on_recalculation_error(error, progress_dialog))
        worker.signals.cancelled.connect(lambda: self._on_recalculation_cancelled(progress_dialog))
        progress_dialog.cancel_requested.connect(worker.cancel)
        
        # Start worker
        self.thread_pool.start(worker)
        
        # Show progress dialog
        progress_dialog.exec()
    
    # ===== Repair Mode Methods =====
    
    def _update_repair_mode_indicator(self):
        """Update the repair mode status indicator"""
        if not self.facade.repair_mode_service:
            self.repair_mode_indicator.setText("🟢 Disabled")
            self.repair_mode_indicator.setStyleSheet("color: #28a745; font-weight: bold;")
            return
            
        is_enabled = self.facade.repair_mode_service.is_enabled()
        if is_enabled:
            self.repair_mode_indicator.setText("🔴 ENABLED")
            self.repair_mode_indicator.setStyleSheet("color: #cc0000; font-weight: bold;")
        else:
            self.repair_mode_indicator.setText("🟢 Disabled")
            self.repair_mode_indicator.setStyleSheet("color: #28a745; font-weight: bold;")
    
    def _update_repair_mode_button(self):
        """Update the repair mode toggle button text"""
        if not self.facade.repair_mode_service:
            self.repair_mode_toggle_btn.setText("Enable Repair Mode")
            self.repair_mode_toggle_btn.setStyleSheet("background-color: #cc0000; color: white;")
            return
            
        is_enabled = self.facade.repair_mode_service.is_enabled()
        if is_enabled:
            self.repair_mode_toggle_btn.setText("Disable Repair Mode")
            self.repair_mode_toggle_btn.setStyleSheet("")
        else:
            self.repair_mode_toggle_btn.setText("Enable Repair Mode")
            self.repair_mode_toggle_btn.setStyleSheet("background-color: #cc0000; color: white;")
    
    def _update_stale_pairs_count(self):
        """Update the stale pairs count label"""
        if not self.facade.repair_mode_service:
            self.stale_pairs_count_label.setText("0 stale pairs")
            return
            
        stale_pairs = self.facade.repair_mode_service.get_stale_pairs()
        count = len(stale_pairs)
        if count == 0:
            self.stale_pairs_count_label.setText("None")
            self.stale_pairs_count_label.setStyleSheet("")
        else:
            self.stale_pairs_count_label.setText(f"{count} pair(s) need rebuilding")
            self.stale_pairs_count_label.setStyleSheet("color: #cc0000; font-weight: bold;")
    
    def _update_rebuild_stale_button(self):
        """Enable/disable rebuild stale button based on stale pairs count"""
        if not self.facade.repair_mode_service:
            self.rebuild_stale_btn.setEnabled(False)
            return
        # Disable if not in repair mode (stale pairs are historical at this point)
        if not self.facade.repair_mode_service.is_enabled():
            self.rebuild_stale_btn.setEnabled(False)
            return
        stale_pairs = self.facade.repair_mode_service.get_stale_pairs()
        self.rebuild_stale_btn.setEnabled(len(stale_pairs) > 0)
    
    def _update_clear_stale_button(self):
        """Enable/disable clear stale button based on stale pairs count"""
        if not self.facade.repair_mode_service:
            self.clear_stale_btn.setEnabled(False)
            return
        # Disable if not in repair mode (stale pairs are historical at this point)
        if not self.facade.repair_mode_service.is_enabled():
            self.clear_stale_btn.setEnabled(False)
            return
        stale_pairs = self.facade.repair_mode_service.get_stale_pairs()
        self.clear_stale_btn.setEnabled(len(stale_pairs) > 0)
    
    def _refresh_repair_mode_ui(self):
        """Refresh all repair mode UI elements"""
        self._update_repair_mode_indicator()
        self._update_repair_mode_button()
        self._update_stale_pairs_count()
        
        # Show/hide stale pair action buttons based on repair mode state
        if self.facade.repair_mode_service and self.facade.repair_mode_service.is_enabled():
            self.rebuild_stale_btn.show()
            self.clear_stale_btn.show()
            self._update_rebuild_stale_button()
            self._update_clear_stale_button()
        else:
            self.rebuild_stale_btn.hide()
            self.clear_stale_btn.hide()
    
    def _on_repair_mode_toggle(self):
        """Handle repair mode toggle button click"""
        if not self.facade.repair_mode_service:
            return
        is_enabled = self.facade.repair_mode_service.is_enabled()
        
        if is_enabled:
            # Disable repair mode (no confirmation needed)
            self.facade.repair_mode_service.set_enabled(False)
            self._refresh_repair_mode_ui()
            
            # Notify parent to refresh window title and banner
            main_window = self.window()
            if hasattr(main_window, 'refresh_repair_mode_ui'):
                main_window.refresh_repair_mode_ui()
            
            # Show message after refresh (using main_window as parent since self may be deleted)
            QMessageBox.information(
                main_window,
                "Repair Mode Disabled",
                "Repair Mode has been disabled. Automatic derived data rebuilds are now enabled."
            )
        else:
            # Enable repair mode (requires confirmation)
            dialog = RepairModeConfirmDialog(self)
            if dialog.exec() == QDialog.Accepted:
                # Check if maintenance mode is active (blocking condition per Issue #55)
                if self.facade.is_maintenance_mode():
                    QMessageBox.warning(
                        self,
                        "Cannot Enable Repair Mode",
                        "Repair Mode cannot be enabled while Maintenance Mode is active. "
                        "Please disable Maintenance Mode first."
                    )
                    return
                
                self.facade.repair_mode_service.set_enabled(True)
                self._refresh_repair_mode_ui()
                
                # Notify parent to refresh window title and banner
                main_window = self.window()
                if hasattr(main_window, 'refresh_repair_mode_ui'):
                    main_window.refresh_repair_mode_ui()
    
    def _on_rebuild_stale_pairs(self):
        """Handle rebuild stale pairs button click"""
        if not self.facade.repair_mode_service:
            return
        stale_pairs = self.facade.repair_mode_service.get_stale_pairs()
        if not stale_pairs:
            QMessageBox.information(self, "No Stale Pairs", "No stale pairs need rebuilding.")
            return
        
        # Build summary message
        pair_list = "\n".join([f"• {pair.user_name} @ {pair.site_name}" for pair in stale_pairs])
        confirm_msg = (
            f"Rebuild derived data for {len(stale_pairs)} stale pair(s)?\n\n"
            f"{pair_list}\n\n"
            "This will recalculate FIFO allocations, cost basis, and P/L for each pair."
        )
        
        reply = QMessageBox.question(
            self,
            "Rebuild Stale Pairs",
            confirm_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Rebuild each stale pair using existing recalculation worker
            for pair in stale_pairs:
                # Create progress dialog
                title = f"Recalculate {pair.user_name} @ {pair.site_name}"
                progress_dialog = RecalculationProgressDialog(title, self)
                
                # Create worker with database path (creates its own connection for thread safety)
                worker = RecalculationWorker(
                    self.facade.db.db_path,
                    operation="pair",
                    user_id=pair.user_id,
                    site_id=pair.site_id,
                    settings_dict=self._get_settings_dict()
                )
                
                # Connect signals
                worker.signals.progress.connect(progress_dialog.update_progress)
                worker.signals.finished.connect(lambda result, pd=progress_dialog: self._on_recalculation_finished(result, pd))
                worker.signals.error.connect(lambda error, pd=progress_dialog: self._on_recalculation_error(error, pd))
                worker.signals.cancelled.connect(lambda pd=progress_dialog: self._on_recalculation_cancelled(pd))
                progress_dialog.cancel_requested.connect(worker.cancel)
                
                # Start worker
                self.thread_pool.start(worker)
                
                # Show progress dialog (blocks until done)
                progress_dialog.exec()
                
                # Clear the pair from stale list after rebuild
                self.facade.repair_mode_service.clear_pair(pair.user_id, pair.site_id)
            
            # Refresh UI
            self._refresh_repair_mode_ui()
    
    def _on_clear_stale_pairs(self):
        """Handle clear stale pairs button click"""
        if not self.facade.repair_mode_service:
            return
        stale_pairs = self.facade.repair_mode_service.get_stale_pairs()
        if not stale_pairs:
            QMessageBox.information(self, "No Stale Pairs", "No stale pairs to clear.")
            return
        
        confirm_msg = (
            f"Clear the stale pairs list without rebuilding?\n\n"
            f"{len(stale_pairs)} pair(s) will be removed from the list. "
            "Their derived data will NOT be recalculated.\n\n"
            "This is useful if you have manually verified the data is correct."
        )
        
        reply = QMessageBox.question(
            self,
            "Clear Stale Pairs",
            confirm_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.facade.repair_mode_service.clear_all()
            self._refresh_repair_mode_ui()
            QMessageBox.information(
                self,
                "Stale Pairs Cleared",
                "All stale pairs have been cleared from the list."
            )
        
    def _on_recalculate_scoped(self):
        """Handle scoped recalculation button click"""
        # Get current text from editable combo boxes
        user_text = self.user_combo.currentText().strip()
        site_text = self.site_combo.currentText().strip()
        
        # If empty, default to "all"
        if not user_text and not site_text:
            # Both empty - recalculate all
            self._on_recalculate_all()
            return
        
        # Try to find matching IDs from text
        user_id = None
        site_id = None
        user_name = "All Users"
        site_name = "All Sites"
        
        # Find user by name
        if user_text:
            for i in range(self.user_combo.count()):
                if self.user_combo.itemText(i).lower() == user_text.lower():
                    user_id = self.user_combo.itemData(i)
                    user_name = self.user_combo.itemText(i)
                    break
        
        # Find site by name
        if site_text:
            for i in range(self.site_combo.count()):
                if self.site_combo.itemText(i).lower() == site_text.lower():
                    site_id = self.site_combo.itemData(i)
                    site_name = self.site_combo.itemText(i)
                    break
        
        # If both are specified but one is invalid
        if user_text and user_id is None:
            QMessageBox.warning(
                self,
                "Invalid User",
                f"User '{user_text}' not found. Please select from the dropdown."
            )
            return
        
        if site_text and site_id is None:
            QMessageBox.warning(
                self,
                "Invalid Site",
                f"Site '{site_text}' not found. Please select from the dropdown."
            )
            return
        
        # Determine operation type
        if user_id and site_id:
            operation = "pair"
            title = f"Recalculate {user_name} @ {site_name}"
            message = f"Recalculate FIFO cost basis and P/L for:\n  User: {user_name}\n  Site: {site_name}\n\nContinue?"
        elif user_id:
            operation = "user"
            title = f"Recalculate {user_name}"
            message = f"Recalculate FIFO cost basis and P/L for:\n  User: {user_name} (all sites)\n\nContinue?"
        elif site_id:
            operation = "site"
            title = f"Recalculate {site_name}"
            message = f"Recalculate FIFO cost basis and P/L for:\n  Site: {site_name} (all users)\n\nContinue?"
        else:
            # Neither specified
            self._on_recalculate_all()
            return
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Recalculate",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog(title, self)
        
        # Create worker with database path (creates its own connection for thread safety)
        worker = RecalculationWorker(
            self.facade.db.db_path,
            operation=operation,
            user_id=user_id,
            site_id=site_id,
            settings_dict=self._get_settings_dict()
        )
        
        # Connect signals
        worker.signals.progress.connect(progress_dialog.update_progress)
        worker.signals.finished.connect(lambda result: self._on_recalculation_finished(result, progress_dialog))
        worker.signals.error.connect(lambda error: self._on_recalculation_error(error, progress_dialog))
        worker.signals.cancelled.connect(lambda: self._on_recalculation_cancelled(progress_dialog))
        progress_dialog.cancel_requested.connect(worker.cancel)
        
        # Start worker
        self.thread_pool.start(worker)
        
        # Show progress dialog
        progress_dialog.exec()
        
    def _on_recalculation_finished(self, result, progress_dialog: RecalculationProgressDialog):
        """Handle recalculation completion"""
        progress_dialog.set_complete("Recalculation complete!")
        progress_dialog.accept()
        
        # Clear stale pairs if this was a full rebuild (Issue #55)
        result_operation = getattr(result, 'operation', 'all')
        if result_operation == "all" and self.facade.repair_mode_service:
            self.facade.repair_mode_service.clear_all()
        
        # Update stats
        self._update_stats()
        
        # Show results dialog
        result_dialog = RecalculationResultDialog(result, self)
        result_dialog.exec()
        
        # Emit unified data change event (Issue #9)
        from services.data_change_event import DataChangeEvent, OperationType
        operation = OperationType.RECALCULATE_ALL if result_operation == "all" else OperationType.RECALCULATE_SCOPED
        self.facade.emit_data_changed(DataChangeEvent(
            operation=operation,
            scope="all"
        ))
        
    def _on_recalculation_error(self, error: str, progress_dialog: RecalculationProgressDialog):
        """Handle recalculation error"""
        progress_dialog.set_error(error)
        progress_dialog.reject()
        
        QMessageBox.critical(
            self,
            "Recalculation Error",
            f"An error occurred during recalculation:\n\n{error}"
        )
        
    def _on_recalculation_cancelled(self, progress_dialog: RecalculationProgressDialog):
        """Handle recalculation cancellation"""
        progress_dialog.accept()
        
        QMessageBox.information(
            self,
            "Recalculation Cancelled",
            "Recalculation was cancelled. The database may be in an incomplete state.\n\n"
            "Consider running recalculation again to ensure data consistency."
        )
        
    def refresh(self):
        """Refresh the tab (reload dropdowns, update stats)"""
        self._load_users()
        self._load_sites()
        self._update_stats()
        self._refresh_repair_mode_ui()
    
    def refresh_data(self):
        """Standardized refresh method (Issue #9 contract)"""
        self.refresh()
    
    # ========================================================================
    # CSV Import/Export Handlers
    # ========================================================================
    
    def _on_import_csv(self):
        """Handle CSV import button click."""
        # Show entity type selector dialog
        dialog = ExportOptionsDialog(self, mode="import")
        
        if dialog.exec() != QDialog.Accepted or not dialog.selected_entity:
            return
        
        entity_type = dialog.selected_entity
        
        # File picker
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import {entity_type.replace('_', ' ').title()} CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Preview import
            preview = self.facade.csv_import_service.preview_import(
                csv_path=file_path,
                entity_type=entity_type,
                strict_mode=True
            )
            
            # Show preview dialog
            preview_dialog = ImportPreviewDialog(preview, entity_type, self)
            
            if preview_dialog.exec() != QDialog.Accepted:
                return
            
            # User confirmed - perform import with conflict resolution options
            result = self.facade.csv_import_service.execute_import(
                csv_path=file_path,
                entity_type=entity_type,
                skip_conflicts=preview_dialog.skip_conflicts,
                overwrite_conflicts=preview_dialog.overwrite_conflicts
            )
            
            # Show result
            result_dialog = ImportResultDialog(result, self)
            result_dialog.exec()

            # Emit unified data change event (Issue #9)
            if result.success and result.total_processed > 0:
                from services.data_change_event import DataChangeEvent, OperationType
                self.facade.emit_data_changed(DataChangeEvent(
                    operation=OperationType.CSV_IMPORT,
                    scope="transactions" if entity_type in ['purchases', 'redemptions', 'game_sessions'] else "setup",
                    affected_tables=[entity_type]
                ))
            
            # If successful and affects accounting data, prompt for recalculation
            if result.success and result.total_processed > 0:
                accounting_entities = ['purchases', 'redemptions', 'game_sessions']
                if entity_type in accounting_entities:
                    self.prompt_recalculate_after_import(result)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import CSV:\n\n{str(e)}"
            )
    
    def _on_export_csv(self):
        """Handle CSV export button click."""
        # Show entity type selector
        dialog = ExportOptionsDialog(self)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Check if export all was selected
        if dialog.export_all:
            self._export_all_csv()
            return
        
        if not dialog.selected_entity:
            return
        
        entity_type = dialog.selected_entity
        
        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{entity_type}_{timestamp}.csv"
        
        # File picker for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {entity_type.replace('_', ' ').title()} CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Perform export
            result = self.facade.csv_export_service.export_csv(
                entity_type=entity_type,
                output_path=file_path
            )
            
            if result.success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {result.records_exported} records to:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    f"Failed to export data:\n\n{result.error or 'Unknown error'}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV:\n\n{str(e)}"
            )
    
    def _export_all_csv(self):
        """Export all entity types to a ZIP file."""
        # File picker for ZIP save location
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"sezzions_export_all_{timestamp}.zip"
        
        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All Data to ZIP",
            default_filename,
            "ZIP Files (*.zip);;All Files (*)"
        )
        
        if not zip_path:
            return
        
        try:
            # Only entity types that have schemas defined
            entity_types = [
                "purchases", "redemptions", "game_sessions",
                "users", "sites", "cards", "redemption_methods",
                "redemption_method_types", "game_types", "games"
            ]
            
            # Create temporary directory for CSV files
            with tempfile.TemporaryDirectory() as temp_dir:
                exported_count = 0
                failed = []
                
                # Export each entity to temp directory
                for entity_type in entity_types:
                    try:
                        csv_filename = f"{entity_type}.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        result = self.facade.csv_export_service.export_csv(
                            entity_type=entity_type,
                            output_path=csv_path
                        )
                        
                        if result.success:
                            exported_count += 1
                        else:
                            failed.append(f"{entity_type}: {result.error}")
                    
                    except Exception as e:
                        failed.append(f"{entity_type}: {str(e)}")
                
                # Create ZIP file
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for entity_type in entity_types:
                        csv_filename = f"{entity_type}.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        if os.path.exists(csv_path):
                            zipf.write(csv_path, csv_filename)
                
                # Show result
                if failed:
                    QMessageBox.warning(
                        self,
                        "Export Complete with Errors",
                        f"Exported {exported_count} entity types to ZIP.\n\n"
                        f"Failed:\n" + "\n".join(failed)
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Export Successful",
                        f"Exported all {exported_count} entity types to:\n{zip_path}"
                    )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to create ZIP file:\n\n{str(e)}"
            )
    
    def _on_download_template(self):
        """Handle download template button click."""
        # Show entity type selector
        dialog = ExportOptionsDialog(self, mode="template")
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Check if download all was selected
        if dialog.export_all:
            self._download_all_templates()
            return
        
        if not dialog.selected_entity:
            return
        
        entity_type = dialog.selected_entity
        
        # Generate template filename
        default_filename = f"{entity_type}_template.csv"
        
        # File picker for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {entity_type.replace('_', ' ').title()} Template",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Generate template
            result = self.facade.csv_export_service.generate_template(
                entity_type=entity_type,
                output_path=file_path
            )
            
            if result.success:
                QMessageBox.information(
                    self,
                    "Template Created",
                    f"Template saved to:\n{file_path}\n\n"
                    "Fill in your data and use 'Import CSV' to upload it."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Template Generation Failed",
                    f"Failed to create template:\n\n{result.error or 'Unknown error'}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Template Error",
                f"Failed to generate template:\n\n{str(e)}"
            )
    
    def _download_all_templates(self):
        """Download all templates to a ZIP file."""
        # File picker for ZIP save location
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"sezzions_templates_{timestamp}.zip"
        
        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download All Templates to ZIP",
            default_filename,
            "ZIP Files (*.zip);;All Files (*)"
        )
        
        if not zip_path:
            return
        
        try:
            # Only entity types that have schemas defined
            entity_types = [
                "purchases", "redemptions", "game_sessions",
                "users", "sites", "cards", "redemption_methods",
                "redemption_method_types", "game_types", "games"
            ]
            
            # Create temporary directory for template files
            with tempfile.TemporaryDirectory() as temp_dir:
                generated_count = 0
                failed = []
                
                # Generate each template to temp directory
                for entity_type in entity_types:
                    try:
                        csv_filename = f"{entity_type}_template.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        result = self.facade.csv_export_service.generate_template(
                            entity_type=entity_type,
                            output_path=csv_path
                        )
                        
                        if result.success:
                            generated_count += 1
                        else:
                            failed.append(f"{entity_type}: {result.error}")
                    
                    except Exception as e:
                        failed.append(f"{entity_type}: {str(e)}")
                
                # Create ZIP file
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for entity_type in entity_types:
                        csv_filename = f"{entity_type}_template.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        if os.path.exists(csv_path):
                            zipf.write(csv_path, csv_filename)
                
                # Show result
                if failed:
                    QMessageBox.warning(
                        self,
                        "Templates Complete with Errors",
                        f"Generated {generated_count} templates to ZIP.\n\n"
                        f"Failed:\n" + "\n".join(failed)
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Templates Downloaded",
                        f"All {generated_count} templates saved to:\n{zip_path}\n\n"
                        "Fill in your data and use 'Import CSV' to upload them."
                    )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Template Error",
                f"Failed to create template ZIP:\n\n{str(e)}"
            )
    
    # ========================================================================
    # Audit Log Handlers (Issue #92)
    # ========================================================================
    
    def _on_open_audit_log(self):
        """Open the audit log viewer dialog"""
        # For now, delegate to main window's handler (placeholder for Task 7)
        parent = self.parentWidget()
        while parent:
            if hasattr(parent, '_show_audit_log'):
                parent._show_audit_log()
                return
            parent = parent.parentWidget()
        
        # Fallback if main window not found
        QMessageBox.information(
            self,
            "Audit Log",
            "Audit Log viewer coming soon (Task 7)"
        )
    
    def _on_clear_audit_log(self):
        """Handle clearing the audit log"""
        reply = QMessageBox.question(
            self,
            "Clear Audit Log",
            "⚠️ WARNING: This will permanently delete ALL audit log entries.\n\n"
            "This operation is IRREVERSIBLE. All audit history will be lost.\n\n"
            "It is strongly recommended to backup your database before proceeding.\n\n"
            "Are you sure you want to clear the audit log?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                count = self.facade.audit_service.clear_audit_log()
                QMessageBox.information(
                    self,
                    "Audit Log Cleared",
                    f"Successfully cleared {count} audit log entries."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Clearing Audit Log",
                    f"Failed to clear audit log:\n\n{str(e)}"
                )
    
    # ========================================================================
    # Database Tools Handlers
    # ========================================================================
    
    def _on_select_backup_directory(self):
        """Handle backup directory selection"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Directory",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.backup_dir = directory
            self._set_backup_location_display(directory)
            self.backup_now_btn.setEnabled(True)
            
            # Save to settings (shared with automatic backup)
            self._save_automatic_backup_settings()
            
            # If automatic backup is enabled, restart timer
            if self.auto_backup_enabled_checkbox.isChecked():
                self.backup_check_timer.start()
    
    def _on_backup_now(self):
        """Handle manual backup"""
        # Disable button immediately to prevent double-clicks
        self.backup_now_btn.setEnabled(False)
        
        if not hasattr(self, 'backup_dir') or not self.backup_dir:
            self.backup_now_btn.setEnabled(True)
            QMessageBox.warning(
                self,
                "No Directory Selected",
                "Please select a backup directory first."
            )
            return
        
        # Check if another tools operation is running
        if self.facade.is_tools_operation_active():
            self.backup_now_btn.setEnabled(True)
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "Another database tools operation is currently running.\n\n"
                "Please wait for it to complete before starting a new operation."
            )
            return
        
        try:
            from datetime import datetime
            from ui.settings import Settings
            from PySide6.QtWidgets import QProgressDialog
            
            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"sezzions_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Acquire exclusive lock
            if not self.facade.acquire_tools_lock():
                self.backup_now_btn.setEnabled(True)
                QMessageBox.warning(
                    self,
                    "Lock Failed",
                    "Could not acquire exclusive lock for backup operation."
                )
                return
            
            # Create worker
            worker = self.facade.create_backup_worker(backup_path)

            # Keep worker alive; PySide QRunnable wrappers can be GC'd otherwise.
            # Also disable auto-delete so the C++ runnable isn't deleted before queued signals are delivered.
            try:
                worker.setAutoDelete(False)
            except Exception:
                pass
            self._active_tools_worker = worker
            
            # Progress dialog (window-modal): blocks interaction with ToolsTab but does not block the event loop.
            self._active_progress_dialog = QProgressDialog(
                "Creating database backup...",
                None,
                0,
                0,
                self,
            )
            self._active_progress_dialog.setWindowTitle("Backup")
            self._active_progress_dialog.setWindowModality(Qt.WindowModal)
            self._active_progress_dialog.setMinimumDuration(0)
            self._active_progress_dialog.setCancelButton(None)
            self._active_progress_dialog.setValue(0)

            # If the user hits Escape, Qt may treat it as cancel. That's fine: hide the dialog,
            # but keep the operation running; the completion handler will still re-enable UI.
            try:
                self._active_progress_dialog.canceled.connect(self._active_progress_dialog.hide)
            except Exception:
                pass
            
            
            # Connect signals
            def on_finished(result):
                # Close progress dialog first
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None

                # Release lock and re-enable button immediately
                self.facade.release_tools_lock()
                self.backup_now_btn.setEnabled(True)

                # Drop strong ref now that we're done
                self._active_tools_worker = None

                if result.success:
                    size_mb = result.size_bytes / (1024 * 1024)
                    
                    # Save backup time to settings
                    from datetime import datetime
                    from ui.settings import Settings
                    now = datetime.now()
                    settings = Settings()
                    config = settings.get_automatic_backup_config()
                    config['last_backup_time'] = now.isoformat()
                    settings.set_automatic_backup_config(config)
                    
                    # Update last backup display
                    self._update_last_backup_display()
                    
                    QMessageBox.information(
                        self,
                        "Backup Complete",
                        f"Database backed up successfully:\n\n{backup_path}\n\nSize: {size_mb:.2f} MB"
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Backup Failed",
                        f"Failed to create backup:\n\n{result.error}"
                    )
            
            def on_error(error_msg):
                # Close progress dialog first
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None

                # Release lock and re-enable button immediately
                self.facade.release_tools_lock()
                self.backup_now_btn.setEnabled(True)

                # Drop strong ref now that we're done
                self._active_tools_worker = None

                QMessageBox.critical(
                    self,
                    "Backup Error",
                    f"An error occurred:\n\n{error_msg}"
                )
            
            
            worker.signals.finished.connect(on_finished, Qt.QueuedConnection)
            worker.signals.error.connect(on_error, Qt.QueuedConnection)

            # Show dialog and start worker
            self._active_progress_dialog.show()
            self.thread_pool.start(worker)
        
        except Exception as e:
            if self._active_progress_dialog:
                self._active_progress_dialog.close()
                self._active_progress_dialog = None
            self.facade.release_tools_lock()
            self.backup_now_btn.setEnabled(True)
            self._active_tools_worker = None
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred:\n\n{str(e)}"
            )
    
    def _on_restore_database(self):
        """Handle database restore"""
        from PySide6.QtWidgets import QMessageBox, QProgressDialog
        from ui.tools_dialogs import RestoreDialog
        import os
        from datetime import datetime
        
        # Check if another tools operation is running
        if self.facade.is_tools_operation_active():
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "Another database tools operation is currently running.\n\n"
                "Please wait for it to complete before starting a new operation."
            )
            return
        
        # Show restore dialog
        dialog = RestoreDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
            
        backup_path = dialog.backup_path
        restore_mode = dialog.get_restore_mode()
        selected_tables = dialog.get_selected_tables() if restore_mode.name == 'MERGE_SELECTED' else None
        
        # Validate backup file exists
        if not os.path.exists(backup_path):
            QMessageBox.critical(
                self,
                "Error",
                f"Backup file not found: {backup_path}"
            )
            return
            
        # Acquire exclusive lock (held for the whole operation sequence)
        if not self.facade.acquire_tools_lock():
            QMessageBox.warning(
                self,
                "Lock Failed",
                "Could not acquire exclusive lock for restore operation."
            )
            return

        def start_restore_worker():
            # Enter maintenance mode (Issue #9)
            if hasattr(self.facade, "set_maintenance_mode"):
                self.facade.set_maintenance_mode(True)
            
            # Create worker
            worker = self.facade.create_restore_worker(backup_path, restore_mode, selected_tables)

            # Keep worker alive; PySide QRunnable wrappers can be GC'd otherwise.
            # Also disable auto-delete so the C++ runnable isn't deleted before queued signals are delivered.
            try:
                worker.setAutoDelete(False)
            except Exception:
                pass
            self._active_tools_worker = worker

            # Create progress dialog and store as instance variable
            self._active_progress_dialog = QProgressDialog("Restoring database...", None, 0, 0, self)
            self._active_progress_dialog.setWindowTitle("Restore")
            self._active_progress_dialog.setWindowModality(Qt.WindowModal)
            self._active_progress_dialog.setMinimumDuration(0)
            self._active_progress_dialog.setCancelButton(None)  # Disable cancel to prevent premature closure
            # If the user hits Escape, Qt may treat it as cancel. Hide the dialog,
            # but keep the operation running; completion handler will still clean up.
            try:
                self._active_progress_dialog.canceled.connect(self._active_progress_dialog.hide)
            except Exception:
                pass
            self._active_progress_dialog.show()

            # Connect signals
            def on_finished(result):
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None
                
                # Release tools lock and exit maintenance mode
                self.facade.release_tools_lock()
                if hasattr(self.facade, "set_maintenance_mode"):
                    self.facade.set_maintenance_mode(False)

                # Drop strong ref now that we're done
                self._active_tools_worker = None

                if result.success:
                    tables_info = f"\n• ".join(result.tables_affected) if result.tables_affected else "All tables"
                    QMessageBox.information(
                        self,
                        "Restore Complete",
                        f"✓ Database restored successfully!\n\n"
                        f"Mode: {restore_mode.name.replace('_', ' ').title()}\n"
                        f"Records restored: {result.records_restored:,}\n"
                        f"Tables affected:\n• {tables_info}"
                    )
                    
                    # Emit unified data change event (Issue #9)
                    from services.data_change_event import DataChangeEvent, OperationType
                    operation = {
                        "REPLACE": OperationType.RESTORE_REPLACE,
                        "MERGE_ALL": OperationType.RESTORE_MERGE_ALL,
                        "MERGE_SELECTED": OperationType.RESTORE_MERGE_SELECTED
                    }.get(restore_mode.name, OperationType.RESTORE_REPLACE)
                    
                    self.facade.emit_data_changed(DataChangeEvent(
                        operation=operation,
                        scope="all",
                        affected_tables=result.tables_affected
                    ))
                else:
                    QMessageBox.critical(
                        self,
                        "Restore Failed",
                        f"Database restore failed:\n{result.error}"
                    )

            def on_error(error_msg):
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None
                self.facade.release_tools_lock()

                # Drop strong ref now that we're done
                self._active_tools_worker = None
                QMessageBox.critical(
                    self,
                    "Restore Error",
                    f"An error occurred:\n\n{error_msg}"
                )

            worker.signals.finished.connect(on_finished, Qt.QueuedConnection)
            worker.signals.error.connect(on_error, Qt.QueuedConnection)

            # Start worker
            self.thread_pool.start(worker)

        # For replace mode, create safety backup in background first
        if restore_mode.name == "REPLACE":
            # Determine backup directory
            if hasattr(self, 'backup_dir') and self.backup_dir:
                backup_dir = self.backup_dir
            else:
                backup_dir = os.path.dirname(backup_path)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup_path = os.path.join(backup_dir, f"pre_restore_backup_{timestamp}.db")

            safety_worker = self.facade.create_backup_worker(safety_backup_path, include_audit_log=True)
            try:
                safety_worker.setAutoDelete(False)
            except Exception:
                pass
            self._active_tools_worker = safety_worker

            self._active_progress_dialog = QProgressDialog("Creating safety backup...", None, 0, 0, self)
            self._active_progress_dialog.setWindowTitle("Safety Backup")
            self._active_progress_dialog.setWindowModality(Qt.WindowModal)
            self._active_progress_dialog.setMinimumDuration(0)
            self._active_progress_dialog.setCancelButton(None)
            try:
                self._active_progress_dialog.canceled.connect(self._active_progress_dialog.hide)
            except Exception:
                pass
            self._active_progress_dialog.show()

            def on_safety_finished(result):
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None

                # Drop strong ref to safety worker before starting restore worker
                self._active_tools_worker = None

                if not result.success:
                    self.facade.release_tools_lock()
                    QMessageBox.critical(
                        self,
                        "Backup Failed",
                        f"Could not create safety backup before restore:\n{result.error}\n\n"
                        "Restore operation cancelled for safety."
                    )
                    return

                safety_backup_file = os.path.basename(result.backup_path)
                QMessageBox.information(
                    self,
                    "Safety Backup Created",
                    f"Safety backup created: {safety_backup_file}\n\n"
                    "Proceeding with database replacement..."
                )

                start_restore_worker()

            def on_safety_error(error_msg):
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None
                self._active_tools_worker = None
                self.facade.release_tools_lock()
                QMessageBox.critical(
                    self,
                    "Backup Error",
                    f"An error occurred while creating safety backup:\n\n{error_msg}"
                )

            safety_worker.signals.finished.connect(on_safety_finished, Qt.QueuedConnection)
            safety_worker.signals.error.connect(on_safety_error, Qt.QueuedConnection)
            self.thread_pool.start(safety_worker)
            return

        # Non-replace modes start restore immediately
        start_restore_worker()
        return
    
    def _on_reset_database(self):
        """Handle database reset"""
        from PySide6.QtWidgets import QMessageBox
        from ui.tools_dialogs import ResetDialog, RecalculationProgressDialog
        from services.tools.reset_service import ResetService
        import os
        from datetime import datetime
        
        # Check if another tools operation is running
        if self.facade.is_tools_operation_active():
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "Another database tools operation is currently running.\n\n"
                "Please wait for it to complete before starting a new operation."
            )
            return
        
        # Get current table counts
        reset_service = ResetService(self.facade.db)
        table_counts = reset_service.get_table_counts()
        
        # Show reset dialog
        dialog = ResetDialog(table_counts, self)
        if dialog.exec() != QDialog.Accepted:
            return
            
        preserve_setup = dialog.should_preserve_setup()
        
        # Final confirmation
        reset_type = "transactional data only" if preserve_setup else "ALL DATA"
        reply = QMessageBox.warning(
            self,
            "Final Confirmation",
            f"This will permanently delete {reset_type}.\n\n"
            "Are you absolutely sure you want to proceed?\n\n"
            "This action CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        want_safety_backup = False
        if hasattr(self, 'backup_dir') and self.backup_dir:
            backup_reply = QMessageBox.question(
                self,
                "Create Backup First?",
                "Would you like to create a safety backup before resetting?\n\n"
                "This is STRONGLY recommended.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            want_safety_backup = (backup_reply == QMessageBox.Yes)

        # Acquire exclusive lock (held for the whole operation sequence)
        if not self.facade.acquire_tools_lock():
            QMessageBox.warning(
                self,
                "Lock Failed",
                "Could not acquire exclusive lock for reset operation."
            )
            return

        def start_reset_worker():
            # Enter maintenance mode (Issue #9)
            if hasattr(self.facade, "set_maintenance_mode"):
                self.facade.set_maintenance_mode(True)
            
            # Create worker
            worker = self.facade.create_reset_worker(keep_setup_data=preserve_setup, keep_audit_log=True)

            # Keep worker alive; PySide QRunnable wrappers can be GC'd otherwise.
            # Also disable auto-delete so the C++ runnable isn't deleted before queued signals are delivered.
            try:
                worker.setAutoDelete(False)
            except Exception:
                pass
            self._active_tools_worker = worker

            # Create progress dialog
            progress_dialog = ProgressDialog("Reset", allow_cancel=False, parent=self)
            progress_dialog.update_progress(0, 0, "Resetting database...")
            progress_dialog.show()

            # Connect signals
            def on_finished(result):
                progress_dialog.close()
                
                # Release tools lock and exit maintenance mode
                self.facade.release_tools_lock()
                if hasattr(self.facade, "set_maintenance_mode"):
                    self.facade.set_maintenance_mode(False)

                # Drop strong ref now that we're done
                self._active_tools_worker = None

                if result.success:
                    tables_info = "\n• ".join(result.tables_cleared) if result.tables_cleared else "None"
                    QMessageBox.information(
                        self,
                        "Reset Complete",
                        f"✓ Database reset successfully!\n\n"
                        f"Records deleted: {result.records_deleted:,}\n"
                        f"Tables cleared:\n• {tables_info}"
                    )
                    
                    # Emit unified data change event (Issue #9)
                    from services.data_change_event import DataChangeEvent, OperationType
                    operation = OperationType.RESET_PARTIAL if preserve_setup else OperationType.RESET_FULL
                    
                    self.facade.emit_data_changed(DataChangeEvent(
                        operation=operation,
                        scope="all",
                        affected_tables=result.tables_cleared
                    ))
                else:
                    QMessageBox.critical(
                        self,
                        "Reset Failed",
                        f"Database reset failed:\n{result.error}"
                    )

            def on_error(error_msg):
                progress_dialog.close()
                
                # Release tools lock and exit maintenance mode on error
                self.facade.release_tools_lock()
                if hasattr(self.facade, "set_maintenance_mode"):
                    self.facade.set_maintenance_mode(False)

                # Drop strong ref now that we're done
                self._active_tools_worker = None
                QMessageBox.critical(
                    self,
                    "Reset Error",
                    f"An error occurred:\n\n{error_msg}"
                )

            worker.signals.finished.connect(on_finished, Qt.QueuedConnection)
            worker.signals.error.connect(on_error, Qt.QueuedConnection)

            # Start worker
            self.thread_pool.start(worker)

        if want_safety_backup and hasattr(self, 'backup_dir') and self.backup_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup_path = os.path.join(self.backup_dir, f"pre_reset_backup_{timestamp}.db")

            safety_worker = self.facade.create_backup_worker(safety_backup_path, include_audit_log=True)
            try:
                safety_worker.setAutoDelete(False)
            except Exception:
                pass
            self._active_tools_worker = safety_worker

            self._active_progress_dialog = QProgressDialog("Creating safety backup...", None, 0, 0, self)
            self._active_progress_dialog.setWindowTitle("Safety Backup")
            self._active_progress_dialog.setWindowModality(Qt.WindowModal)
            self._active_progress_dialog.setMinimumDuration(0)
            self._active_progress_dialog.setCancelButton(None)
            try:
                self._active_progress_dialog.canceled.connect(self._active_progress_dialog.hide)
            except Exception:
                pass
            self._active_progress_dialog.show()

            def on_safety_finished(result):
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None

                self._active_tools_worker = None

                if not result.success:
                    self.facade.release_tools_lock()
                    QMessageBox.critical(
                        self,
                        "Backup Failed",
                        f"Could not create backup:\n{result.error}\n\n"
                        "Reset cancelled for safety."
                    )
                    return

                backup_file = os.path.basename(result.backup_path)
                QMessageBox.information(
                    self,
                    "Backup Created",
                    f"Safety backup created: {backup_file}\n\n"
                    "Proceeding with reset..."
                )

                start_reset_worker()

            def on_safety_error(error_msg):
                if self._active_progress_dialog:
                    try:
                        self._active_progress_dialog.close()
                        self._active_progress_dialog.deleteLater()
                    except Exception:
                        pass
                    self._active_progress_dialog = None
                self._active_tools_worker = None
                self.facade.release_tools_lock()
                QMessageBox.critical(
                    self,
                    "Backup Error",
                    f"An error occurred while creating safety backup:\n\n{error_msg}"
                )

            safety_worker.signals.finished.connect(on_safety_finished, Qt.QueuedConnection)
            safety_worker.signals.error.connect(on_safety_error, Qt.QueuedConnection)
            self.thread_pool.start(safety_worker)
            return

        start_reset_worker()
        return
    
    # ========================================================================
    # Post-Import Recalculation
    # ========================================================================
    
    def prompt_recalculate_after_import(self, import_result):
        """Show post-import recalculation prompt and trigger if user confirms.
        
        Args:
            import_result: ImportResult with affected_user_ids and affected_site_ids
        """
        # Show prompt dialog
        prompt_dialog = PostImportPromptDialog(self, import_result)
        
        if prompt_dialog.exec() == QDialog.Accepted:
            # User chose to recalculate
            self._trigger_post_import_recalculation(
                import_result.entity_type,
                import_result.affected_user_ids,
                import_result.affected_site_ids
            )
    
    def _trigger_post_import_recalculation(
        self,
        entity_type: str,
        user_ids: list,
        site_ids: list
    ):
        """Trigger recalculation for affected pairs after import.
        
        Args:
            entity_type: Type of entity imported (purchases, redemptions, etc.)
            user_ids: List of affected user IDs
            site_ids: List of affected site IDs
        """
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog("Post-Import Recalculation", parent=self)
        
        # Create worker with database path (creates its own connection for thread safety)
        worker = RecalculationWorker(
            self.facade.db.db_path,
            operation="after_import",
            entity_type=entity_type,
            user_ids=user_ids,
            site_ids=site_ids,
            settings_dict=self._get_settings_dict()
        )
        
        # Connect signals
        worker.signals.progress.connect(progress_dialog.update_progress)
        worker.signals.finished.connect(
            lambda result: self._on_recalculation_finished(result, progress_dialog)
        )
        worker.signals.error.connect(
            lambda error: self._on_recalculation_error(error, progress_dialog)
        )
        worker.signals.cancelled.connect(
            lambda: self._on_recalculation_cancelled(progress_dialog)
        )
        progress_dialog.cancel_requested.connect(worker.cancel)
        
        # Start worker
        self.thread_pool.start(worker)
        
        # Show progress dialog
        progress_dialog.exec()
    
    # ========================================================================
    # Automatic Backup Management
    # ========================================================================
    
    def _load_automatic_backup_settings(self):
        """Load automatic backup settings from JSON"""
        from ui.settings import Settings
        settings = Settings()
        config = settings.get_automatic_backup_config()
        
        # Block signals during load to prevent premature saves
        self.auto_backup_enabled_checkbox.blockSignals(True)
        self.auto_backup_frequency_spinbox.blockSignals(True)
        
        try:
            # Apply settings to UI
            enabled = config.get('enabled', False)
            self.auto_backup_enabled_checkbox.setChecked(enabled)
            
            directory = config.get('directory', '')
            if directory:
                self._set_backup_location_display(directory)
                self.backup_dir = directory
                self.backup_now_btn.setEnabled(True)
            
            # Convert hours to days for spinbox display
            frequency_hours = config.get('frequency_hours', 24)
            frequency_days = max(1, frequency_hours // 24)  # At least 1 day
            self.auto_backup_frequency_spinbox.setValue(frequency_days)
            
            # Set spinbox enabled state based on checkbox (while signals still blocked)
            self.auto_backup_frequency_spinbox.setEnabled(enabled)
            
            # Update last backup label
            self._update_last_backup_display()
            
            # Start timer if enabled
            if enabled and directory:
                self.backup_check_timer.start()
        finally:
            # Always unblock signals
            self.auto_backup_enabled_checkbox.blockSignals(False)
            self.auto_backup_frequency_spinbox.blockSignals(False)
    
    def _save_automatic_backup_settings(self):
        """Save automatic backup settings to JSON"""
        from ui.settings import Settings
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        
        # Update config
        config['enabled'] = self.auto_backup_enabled_checkbox.isChecked()
        config['directory'] = self.backup_dir if self.backup_dir else ''
        # Convert days to hours for storage
        config['frequency_hours'] = self.auto_backup_frequency_spinbox.value() * 24
        
        settings.set_automatic_backup_config(config)
    
    def _on_auto_backup_toggle(self, checked):
        """Handle automatic backup enable/disable"""
        # Enable/disable spinbox
        self.auto_backup_frequency_spinbox.setEnabled(checked)
        
        # Start/stop timer
        if checked and self.backup_dir:
            self.backup_check_timer.start()
        else:
            self.backup_check_timer.stop()
        
        self._save_automatic_backup_settings()
    
    def _on_auto_backup_frequency_changed(self, value):
        """Handle frequency change"""
        self._save_automatic_backup_settings()
    
    def _update_last_backup_display(self):
        """Update the last backup label with most recent backup time"""
        from ui.settings import Settings
        from datetime import datetime
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        last_backup_str = config.get('last_backup_time')
        
        if last_backup_str:
            try:
                last_time = datetime.fromisoformat(last_backup_str)
                time_str = last_time.strftime('%Y-%m-%d %H:%M')
                self.last_backup_label.setText(f"Last backup: {time_str}")
            except:
                self.last_backup_label.setText("Last backup: —")
        else:
            self.last_backup_label.setText("Last backup: —")
    
    def _check_automatic_backup(self):
        """Check if it's time to run an automatic backup"""
        from ui.settings import Settings
        from datetime import datetime, timedelta
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        
        if not config.get('enabled', False):
            return
        
        directory = config.get('directory', '')
        if not directory:
            return
        
        frequency_hours = config.get('frequency_hours', 24)
        last_backup_str = config.get('last_backup_time')
        
        should_backup = False
        if not last_backup_str:
            # Never backed up - do it now
            should_backup = True
        else:
            try:
                last_backup = datetime.fromisoformat(last_backup_str)
                next_backup = last_backup + timedelta(hours=frequency_hours)
                should_backup = datetime.now() >= next_backup
            except:
                # Invalid timestamp - backup now
                should_backup = True
        
        if should_backup:
            self._perform_automatic_backup()
    
    def _perform_automatic_backup(self):
        """Perform an automatic backup"""
        from ui.settings import Settings
        from datetime import datetime
        import os
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        directory = config.get('directory', '')
        
        if not directory:
            return

        # If a tools operation is already active, skip this cycle.
        # (We don't want auto backup competing with restore/reset.)
        if self.facade.is_tools_operation_active():
            print("[Auto-Backup] Skipped (tools operation already active)")
            return

        # Acquire exclusive lock so UI writes are blocked while the snapshot is taken.
        if not self.facade.acquire_tools_lock():
            print("[Auto-Backup] Skipped (could not acquire tools lock)")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(directory, f"auto_backup_{timestamp}.db")

        worker = self.facade.create_backup_worker(backup_path, include_audit_log=True)
        try:
            worker.setAutoDelete(False)
        except Exception:
            pass

        # Keep a strong ref until it finishes; auto backups have no modal dialog to anchor lifetime.
        self._background_tools_workers.append(worker)

        def _cleanup_worker(w):
            try:
                self._background_tools_workers.remove(w)
            except ValueError:
                pass

        def on_finished(result):
            self.facade.release_tools_lock()
            _cleanup_worker(worker)

            if result.success:
                config['last_backup_time'] = datetime.now().isoformat()
                settings.set_automatic_backup_config(config)
                self._update_last_backup_display()

                filename = os.path.basename(result.backup_path)
                size_mb = result.size_bytes / (1024 * 1024)
                print(f"[Auto-Backup] Created: {filename} ({size_mb:.2f} MB)")
                
                # Notify notification rules service of successful backup
                if hasattr(self.facade, 'notification_rules_service'):
                    self.facade.notification_rules_service.on_backup_completed()
            else:
                print(f"[Auto-Backup] Failed: {result.error}")
                
                # Notify notification rules service of backup failure
                if hasattr(self.facade, 'notification_rules_service'):
                    self.facade.notification_rules_service.on_backup_failed(result.error)

        def on_error(error_msg):
            self.facade.release_tools_lock()
            _cleanup_worker(worker)
            print(f"[Auto-Backup] Error: {error_msg}")
            
            # Notify notification rules service of backup failure
            if hasattr(self.facade, 'notification_rules_service'):
                self.facade.notification_rules_service.on_backup_failed(error_msg)

        worker.signals.finished.connect(on_finished, Qt.QueuedConnection)
        worker.signals.error.connect(on_error, Qt.QueuedConnection)
        self.thread_pool.start(worker)
    
    # =========================================================================
    # Adjustments & Corrections Handlers
    # =========================================================================
    
    def _on_create_basis_adjustment(self):
        """Show dialog to create a basis adjustment."""
        from ui.adjustment_dialogs import BasisAdjustmentDialog
        
        dialog = BasisAdjustmentDialog(self.facade, parent=self)
        if dialog.exec() == QDialog.Accepted:
            adjustment = dialog.get_adjustment()
            if adjustment:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Basis adjustment created successfully.\n\n"
                    f"Delta: ${adjustment.delta_basis_usd:,.2f}\n"
                    f"Effective: {adjustment.effective_date} {adjustment.effective_time}"
                )
                self.data_changed.emit()
    
    def _on_create_checkpoint(self):
        """Show dialog to create a balance checkpoint."""
        from ui.adjustment_dialogs import CheckpointDialog
        
        dialog = CheckpointDialog(self.facade, parent=self)
        if dialog.exec() == QDialog.Accepted:
            adjustment = dialog.get_adjustment()
            if adjustment:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Balance checkpoint created successfully.\n\n"
                    f"Total SC: {adjustment.checkpoint_total_sc:,.2f}\n"
                    f"Redeemable SC: {adjustment.checkpoint_redeemable_sc:,.2f}\n"
                    f"Effective: {adjustment.effective_date} {adjustment.effective_time}"
                )
                self.data_changed.emit()
    
    def _on_view_adjustments(self):
        """Show dialog to view and manage adjustments."""
        from ui.adjustment_dialogs import ViewAdjustmentsDialog
        
        dialog = ViewAdjustmentsDialog(self.facade, parent=self)
        dialog.exec()
        
        # Emit data_changed if any modifications were made
        if dialog.was_modified():
            self.data_changed.emit()

