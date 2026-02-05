"""Dialogs for creating and managing adjustments (basis corrections & balance checkpoints)."""

from decimal import Decimal, InvalidOperation
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QDateEdit, QTimeEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, QDate, QTime, Signal
from PySide6.QtGui import QColor


class BasisAdjustmentDialog(QDialog):
    """Dialog for creating a basis adjustment (delta to cost basis)."""
    
    def __init__(self, facade, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.adjustment = None
        self.setWindowTitle("New Basis Adjustment")
        self.setMinimumWidth(500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Description
        desc = QLabel(
            "Create a basis adjustment to correct purchase cost basis.\n"
            "Positive values increase basis, negative values decrease it.\n"
            "This will affect FIFO allocations when recalculated."
        )
        desc.setWordWrap(True)
        desc.setObjectName("HelperText")
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Form
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        # User
        self.user_combo = QComboBox()
        self._load_users()
        form.addRow("User:", self.user_combo)
        
        # Site
        self.site_combo = QComboBox()
        self._load_sites()
        form.addRow("Site:", self.site_combo)
        
        # Effective Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Effective Date:", self.date_edit)
        
        # Effective Time
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(0, 0))
        form.addRow("Effective Time:", self.time_edit)
        
        # Delta (positive or negative)
        self.delta_input = QLineEdit()
        self.delta_input.setPlaceholderText("e.g., -20.00 or 15.50")
        form.addRow("Basis Delta (USD):", self.delta_input)
        
        # Reason (required)
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("e.g., Fee correction")
        form.addRow("Reason (required):", self.reason_input)
        
        # Notes (optional)
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Optional additional notes")
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)
        
        layout.addLayout(form)
        layout.addSpacing(10)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        create_btn = QPushButton("Create Adjustment")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(create_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_users(self):
        users = self.facade.user_service.list_active_users()
        for user in users:
            self.user_combo.addItem(user.name, user.id)
    
    def _load_sites(self):
        sites = self.facade.site_service.list_active_sites()
        for site in sites:
            self.site_combo.addItem(site.name, site.id)
    
    def _on_create(self):
        # Validation
        if self.user_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a user.")
            return
        
        if self.site_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a site.")
            return
        
        reason = self.reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Validation Error", "Reason is required.")
            return
        
        try:
            delta = Decimal(self.delta_input.text().strip())
        except (ValueError, InvalidOperation):
            QMessageBox.warning(self, "Validation Error", "Invalid delta value. Enter a number (e.g., -20.00).")
            return
        
        if delta == Decimal("0.00"):
            QMessageBox.warning(self, "Validation Error", "Delta cannot be zero.")
            return
        
        # Create adjustment
        try:
            user_id = self.user_combo.currentData()
            site_id = self.site_combo.currentData()
            effective_date = self.date_edit.date().toString("yyyy-MM-dd")
            effective_time = self.time_edit.time().toString("HH:mm:ss")
            notes = self.notes_input.toPlainText().strip() or None
            
            self.adjustment = self.facade.adjustment_service.create_basis_adjustment(
                user_id=user_id,
                site_id=site_id,
                effective_date=effective_date,
                effective_time=effective_time,
                delta_basis_usd=delta,
                reason=reason,
                notes=notes
            )
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create adjustment:\n{str(e)}")
    
    def get_adjustment(self):
        return self.adjustment


class CheckpointDialog(QDialog):
    """Dialog for creating a balance checkpoint."""
    
    def __init__(self, facade, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.adjustment = None
        self.setWindowTitle("New Balance Checkpoint")
        self.setMinimumWidth(500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Description
        desc = QLabel(
            "Create a balance checkpoint to establish a known balance at a specific time.\n"
            "This will override previous balance calculations and take priority over closed sessions.\n"
            "Useful for correcting balance discrepancies or importing external data."
        )
        desc.setWordWrap(True)
        desc.setObjectName("HelperText")
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Form
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        # User
        self.user_combo = QComboBox()
        self._load_users()
        form.addRow("User:", self.user_combo)
        
        # Site
        self.site_combo = QComboBox()
        self._load_sites()
        form.addRow("Site:", self.site_combo)
        
        # Effective Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Effective Date:", self.date_edit)
        
        # Effective Time
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(0, 0))
        form.addRow("Effective Time:", self.time_edit)
        
        # Total SC Balance
        self.total_sc_input = QLineEdit()
        self.total_sc_input.setPlaceholderText("e.g., 1500.00")
        form.addRow("Total SC Balance:", self.total_sc_input)
        
        # Redeemable SC Balance
        self.redeemable_sc_input = QLineEdit()
        self.redeemable_sc_input.setPlaceholderText("e.g., 1200.00")
        form.addRow("Redeemable SC Balance:", self.redeemable_sc_input)
        
        # Reason (required)
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("e.g., Manual correction after site reconciliation")
        form.addRow("Reason (required):", self.reason_input)
        
        # Notes (optional)
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Optional additional notes")
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)
        
        layout.addLayout(form)
        layout.addSpacing(10)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        create_btn = QPushButton("Create Checkpoint")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(create_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_users(self):
        users = self.facade.user_service.list_active_users()
        for user in users:
            self.user_combo.addItem(user.name, user.id)
    
    def _load_sites(self):
        sites = self.facade.site_service.list_active_sites()
        for site in sites:
            self.site_combo.addItem(site.name, site.id)
    
    def _on_create(self):
        # Validation
        if self.user_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a user.")
            return
        
        if self.site_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a site.")
            return
        
        reason = self.reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Validation Error", "Reason is required.")
            return
        
        try:
            total_sc = Decimal(self.total_sc_input.text().strip() or "0")
        except (ValueError, InvalidOperation):
            QMessageBox.warning(self, "Validation Error", "Invalid Total SC value.")
            return
        
        try:
            redeemable_sc = Decimal(self.redeemable_sc_input.text().strip() or "0")
        except (ValueError, InvalidOperation):
            QMessageBox.warning(self, "Validation Error", "Invalid Redeemable SC value.")
            return
        
        if total_sc == Decimal("0") and redeemable_sc == Decimal("0"):
            QMessageBox.warning(self, "Validation Error", "At least one balance must be non-zero.")
            return
        
        # Create checkpoint
        try:
            user_id = self.user_combo.currentData()
            site_id = self.site_combo.currentData()
            effective_date = self.date_edit.date().toString("yyyy-MM-dd")
            effective_time = self.time_edit.time().toString("HH:mm:ss")
            notes = self.notes_input.toPlainText().strip() or None
            
            self.adjustment = self.facade.adjustment_service.create_balance_checkpoint(
                user_id=user_id,
                site_id=site_id,
                effective_date=effective_date,
                effective_time=effective_time,
                checkpoint_total_sc=total_sc,
                checkpoint_redeemable_sc=redeemable_sc,
                reason=reason,
                notes=notes
            )
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create checkpoint:\n{str(e)}")
    
    def get_adjustment(self):
        return self.adjustment


class ViewAdjustmentsDialog(QDialog):
    """Dialog for viewing and managing adjustments."""
    
    def __init__(self, facade, parent=None):
        super().__init__(parent)
        self.facade = facade
        self._modified = False
        self.setWindowTitle("View Adjustments")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._load_adjustments()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Filters
        filter_layout = QHBoxLayout()
        
        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)
        
        self.user_filter = QComboBox()
        self.user_filter.addItem("All Users", None)
        users = self.facade.user_service.list_active_users()
        for user in users:
            self.user_filter.addItem(user.name, user.id)
        self.user_filter.currentIndexChanged.connect(self._load_adjustments)
        filter_layout.addWidget(self.user_filter)
        
        self.site_filter = QComboBox()
        self.site_filter.addItem("All Sites", None)
        sites = self.facade.site_service.list_active_sites()
        for site in sites:
            self.site_filter.addItem(site.name, site.id)
        self.site_filter.currentIndexChanged.connect(self._load_adjustments)
        filter_layout.addWidget(self.site_filter)
        
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", None)
        self.type_filter.addItem("Basis Corrections", "BASIS_USD_CORRECTION")
        self.type_filter.addItem("Balance Checkpoints", "BALANCE_CHECKPOINT_CORRECTION")
        self.type_filter.currentIndexChanged.connect(self._load_adjustments)
        filter_layout.addWidget(self.type_filter)
        
        self.deleted_filter = QComboBox()
        self.deleted_filter.addItem("Active Only", False)
        self.deleted_filter.addItem("All (Including Deleted)", True)
        self.deleted_filter.currentIndexChanged.connect(self._load_adjustments)
        filter_layout.addWidget(self.deleted_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Type", "User", "Site", "Effective Date", "Effective Time",
            "Delta/Total SC", "Redeemable SC", "Reason", "Status"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)  # Reason column
        layout.addWidget(self.table)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.delete_btn = QPushButton("🗑️ Soft Delete")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        self.restore_btn = QPushButton("♻️ Restore")
        self.restore_btn.clicked.connect(self._on_restore)
        self.restore_btn.setEnabled(False)
        btn_layout.addWidget(self.restore_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Selection changed
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_adjustments(self):
        user_id = self.user_filter.currentData()
        site_id = self.site_filter.currentData()
        adjustment_type = self.type_filter.currentData()
        include_deleted = self.deleted_filter.currentData()
        
        adjustments = self.facade.adjustment_service.get_all(
            user_id=user_id,
            site_id=site_id,
            adjustment_type=adjustment_type,
            include_deleted=include_deleted
        )
        
        self.table.setRowCount(len(adjustments))
        
        for row, adj in enumerate(adjustments):
            # ID
            self.table.setItem(row, 0, QTableWidgetItem(str(adj.id)))
            
            # Type
            type_str = "Basis" if adj.type.value == "BASIS_USD_CORRECTION" else "Checkpoint"
            self.table.setItem(row, 1, QTableWidgetItem(type_str))
            
            # User
            user = self.facade.user_service.get_user_by_id(adj.user_id)
            self.table.setItem(row, 2, QTableWidgetItem(user.name if user else str(adj.user_id)))
            
            # Site
            site = self.facade.site_service.get_site_by_id(adj.site_id)
            self.table.setItem(row, 3, QTableWidgetItem(site.name if site else str(adj.site_id)))
            
            # Effective Date
            self.table.setItem(row, 4, QTableWidgetItem(adj.effective_date))
            
            # Effective Time
            self.table.setItem(row, 5, QTableWidgetItem(adj.effective_time))
            
            # Delta/Total SC
            if adj.type.value == "BASIS_USD_CORRECTION":
                value_str = f"${adj.delta_basis_usd:,.2f}" if adj.delta_basis_usd else ""
            else:
                value_str = f"{adj.checkpoint_total_sc:,.2f}" if adj.checkpoint_total_sc else ""
            self.table.setItem(row, 6, QTableWidgetItem(value_str))
            
            # Redeemable SC
            if adj.type.value == "BALANCE_CHECKPOINT_CORRECTION":
                redeemable_str = f"{adj.checkpoint_redeemable_sc:,.2f}" if adj.checkpoint_redeemable_sc else ""
            else:
                redeemable_str = ""
            self.table.setItem(row, 7, QTableWidgetItem(redeemable_str))
            
            # Reason
            self.table.setItem(row, 8, QTableWidgetItem(adj.reason))
            
            # Status
            if adj.is_deleted():
                status_item = QTableWidgetItem("Deleted")
                status_item.setForeground(QColor("#666666"))
            else:
                status_item = QTableWidgetItem("Active")
            self.table.setItem(row, 9, status_item)
    
    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            self.delete_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            return
        
        row = self.table.currentRow()
        if row < 0:
            self.delete_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            return
        
        adj_id = int(self.table.item(row, 0).text())
        adjustment = self.facade.adjustment_service.get_by_id(adj_id)
        
        if adjustment:
            self.delete_btn.setEnabled(not adjustment.is_deleted())
            self.restore_btn.setEnabled(adjustment.is_deleted())
    
    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        adj_id = int(self.table.item(row, 0).text())
        
        reply = QMessageBox.question(
            self,
            "Confirm Soft Delete",
            "Are you sure you want to soft-delete this adjustment?\n\n"
            "This will remove it from active calculations. You can restore it later.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.facade.adjustment_service.soft_delete(adj_id, "Deleted via UI")
                self._modified = True
                self._load_adjustments()
                QMessageBox.information(self, "Success", "Adjustment soft-deleted successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete adjustment:\n{str(e)}")
    
    def _on_restore(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        adj_id = int(self.table.item(row, 0).text())
        
        try:
            self.facade.adjustment_service.restore(adj_id)
            self._modified = True
            self._load_adjustments()
            QMessageBox.information(self, "Success", "Adjustment restored successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to restore adjustment:\n{str(e)}")
    
    def was_modified(self):
        return self._modified
