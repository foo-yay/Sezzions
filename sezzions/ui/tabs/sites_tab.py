"""
Sites tab - Manage casino sites
"""
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.site import Site


class SitesTab(QtWidgets.QWidget):
    """Tab for managing sites"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.sites = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Sites")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search sites...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_sites)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)
        
        layout.addLayout(header_layout)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        add_btn = QtWidgets.QPushButton("➕ Add Site")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_site)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_site)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)
        
        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_site)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_site)
        self.delete_btn.setVisible(False)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "URL", "SC Rate", "Status", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._edit_site)
        layout.addWidget(self.table)
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Reload sites from database"""
        self.sites = self.facade.get_all_sites()
        self._populate_table()
    
    def _populate_table(self):
        """Populate table with sites"""
        search_text = self.search_edit.text().lower()
        
        # Filter sites
        if search_text:
            filtered = [s for s in self.sites 
                       if search_text in s.name.lower() 
                       or (s.url and search_text in s.url.lower())
                       or (s.notes and search_text in s.notes.lower())]
        else:
            filtered = self.sites
        
        self.table.setRowCount(len(filtered))
        
        for row, site in enumerate(filtered):
            # Name
            name_item = QtWidgets.QTableWidgetItem(site.name)
            name_item.setData(QtCore.Qt.UserRole, site.id)
            self.table.setItem(row, 0, name_item)
            
            # URL
            url = site.url or ""
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(url))
            
            # SC Rate
            rate_item = QtWidgets.QTableWidgetItem(f"{site.sc_rate:.4f}")
            rate_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 2, rate_item)
            
            # Status
            status = "Active" if site.is_active else "Inactive"
            status_item = QtWidgets.QTableWidgetItem(status)
            if not site.is_active:
                status_item.setForeground(QtGui.QColor("#999"))
            self.table.setItem(row, 3, status_item)
            
            # Notes
            notes = (site.notes or "")[:100]
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(notes))
        
        # Column sizing handled by header resize mode
    
    def _filter_sites(self):
        """Filter table based on search"""
        self._populate_table()

    def _clear_search(self):
        self.search_edit.clear()
        self._populate_table()

    def _clear_all_filters(self):
        self._clear_search()
    
    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        has_selection = len(self.table.selectedItems()) > 0
        self.view_btn.setVisible(has_selection)
        self.edit_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)
    
    def _get_selected_site_id(self):
        """Get ID of selected site"""
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        return self.table.item(row, 0).data(QtCore.Qt.UserRole)
    
    def _add_site(self):
        """Show dialog to add new site"""
        dialog = SiteDialog(self)
        if dialog.exec():
            try:
                site = self.facade.create_site(
                    name=dialog.name_edit.text(),
                    url=dialog.url_edit.text() or None,
                    sc_rate=float(dialog.rate_edit.text()),
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Site '{site.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create site:\n{str(e)}"
                )
    
    def _edit_site(self):
        """Show dialog to edit selected site"""
        site_id = self._get_selected_site_id()
        if not site_id:
            return
        
        site = self.facade.get_site(site_id)
        if not site:
            return
        
        dialog = SiteDialog(self, site)
        if dialog.exec():
            try:
                updated = self.facade.update_site(
                    site_id,
                    name=dialog.name_edit.text(),
                    url=dialog.url_edit.text() or None,
                    sc_rate=float(dialog.rate_edit.text()),
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked()
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Site '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update site:\n{str(e)}"
                )
    
    def _delete_site(self):
        """Delete selected site"""
        site_id = self._get_selected_site_id()
        if not site_id:
            return
        
        site = self.facade.get_site(site_id)
        if not site:
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete site '{site.name}'?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.facade.delete_site(site_id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Site '{site.name}' deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete site:\n{str(e)}"
                )

    def _view_site(self):
        site_id = self._get_selected_site_id()
        if not site_id:
            return
        site = self.facade.get_site(site_id)
        if not site:
            return
        def handle_edit():
            dialog.close()
            self._edit_site()

        def handle_delete():
            dialog.close()
            self._delete_site()

        dialog = SiteDialog(
            self,
            site,
            read_only=True,
            on_edit=handle_edit,
            on_delete=handle_delete,
        )
        dialog.exec()


class SiteDialog(QtWidgets.QDialog):
    """Dialog for adding/editing sites"""
    
    def __init__(self, parent=None, site: Site = None, read_only: bool = False, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.site = site
        self.read_only = read_only
        self._on_edit = on_edit
        self._on_delete = on_delete
        if self.read_only:
            self.setWindowTitle("View Site")
        else:
            self.setWindowTitle("Edit Site" if site else "Add Site")
        self.resize(500, 350)
        
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)
        
        # Name
        self.name_edit = QtWidgets.QLineEdit()
        if site:
            self.name_edit.setText(site.name)
        name_label = QtWidgets.QLabel("Name:")
        name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(self.name_edit, 0, 1)
        
        # URL
        self.url_edit = QtWidgets.QLineEdit()
        if site and site.url:
            self.url_edit.setText(site.url)
        url_label = QtWidgets.QLabel("URL:")
        url_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(url_label, 1, 0)
        layout.addWidget(self.url_edit, 1, 1, 1, 3)
        
        # SC Rate
        self.rate_edit = QtWidgets.QLineEdit()
        self.rate_edit.setText(str(site.sc_rate if site else "1.0"))
        self.rate_edit.setMaximumWidth(150)
        rate_label = QtWidgets.QLabel("SC Rate:")
        rate_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(rate_label, 2, 0)
        layout.addWidget(self.rate_edit, 2, 1, 1, 3)
        
        # Active
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(site.is_active if site else True)
        active_label = QtWidgets.QLabel("Active")
        active_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(active_label, 0, 2)
        layout.addWidget(self.active_check, 0, 3)
        
        # Notes
        self.notes_edit = QtWidgets.QTextEdit()
        if site and site.notes:
            self.notes_edit.setPlainText(site.notes)
        notes_label = QtWidgets.QLabel("Notes:")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        layout.addWidget(notes_label, 3, 0, QtCore.Qt.AlignTop)
        layout.addWidget(self.notes_edit, 3, 1, 1, 3)
        
        # Buttons
        if self.read_only:
            btn_row = QtWidgets.QHBoxLayout()
            if self._on_delete:
                delete_btn = QtWidgets.QPushButton("Delete")
                delete_btn.clicked.connect(self._on_delete)
                btn_row.addWidget(delete_btn)
            btn_row.addStretch(1)
            if self._on_edit:
                edit_btn = QtWidgets.QPushButton("Edit")
                edit_btn.clicked.connect(self._on_edit)
                btn_row.addWidget(edit_btn)
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row, 4, 0, 1, 4)
        else:
            button_box = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
            )
            button_box.accepted.connect(self._validate_and_accept)
            button_box.rejected.connect(self.reject)
            layout.addWidget(button_box, 4, 0, 1, 4)

        if self.read_only:
            for widget in (self.name_edit, self.url_edit, self.rate_edit, self.active_check, self.notes_edit):
                widget.setEnabled(False)
            if not (site and site.notes):
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.notes_edit.setPlaceholderText("-")
                self.notes_edit.setFixedHeight(self.notes_edit.fontMetrics().lineSpacing() + 12)

        self.name_edit.textChanged.connect(self._validate_inline)
        self.rate_edit.textChanged.connect(self._validate_inline)
        self._validate_inline()

    def _set_invalid(self, widget, message):
        widget.setProperty("invalid", True)
        widget.setToolTip(message)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _set_valid(self, widget):
        widget.setProperty("invalid", False)
        widget.setToolTip("")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _validate_inline(self):
        if self.read_only:
            return
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Name is required")
        else:
            self._set_valid(self.name_edit)
        try:
            rate = float(self.rate_edit.text())
            if rate <= 0:
                raise ValueError
            self._set_valid(self.rate_edit)
        except Exception:
            self._set_invalid(self.rate_edit, "Enter a positive rate")
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Name is required"
            )
            return
        
        try:
            rate = float(self.rate_edit.text())
            if rate <= 0:
                raise ValueError("Rate must be positive")
        except ValueError as e:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", f"Invalid SC Rate: {str(e)}"
            )
            return
        
        self.accept()
