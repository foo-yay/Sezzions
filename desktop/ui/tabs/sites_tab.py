"""
Sites tab - Manage casino sites
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.site import Site
from desktop.ui.table_header_filters import TableHeaderFilter
from desktop.ui.spreadsheet_ux import SpreadsheetUXController
from desktop.ui.spreadsheet_stats_bar import SpreadsheetStatsBar


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

        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)
        
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "URL", "SC Rate", "Playthrough", "Status", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_site)
        
        # Context menu setup
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # Stats bar and keyboard shortcut
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)
        
        self.table_filter = TableHeaderFilter(self.table, refresh_callback=self.refresh_data)
        
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self._copy_selection)
        
        # Load data
        self.refresh_data()
    
    def focus_search(self):
        """Focus the search bar (for Cmd+F/Ctrl+F shortcut - Issue #99)"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

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
        
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
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

                # Playthrough requirement
                playthrough_item = QtWidgets.QTableWidgetItem(f"{site.playthrough_requirement:.4f}")
                playthrough_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 3, playthrough_item)
                
                # Status
                status = "Active" if site.is_active else "Inactive"
                status_item = QtWidgets.QTableWidgetItem(status)
                if not site.is_active:
                    status_item.setForeground(QtGui.QColor("#999"))
                self.table.setItem(row, 4, status_item)
                
                # Notes
                notes = (site.notes or "")[:100]
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(notes))

        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        if getattr(self, "table_filter", None) is not None and self.table_filter.sort_column is not None:
            self.table_filter.sort_by_column(self.table_filter.sort_column, self.table_filter.sort_order)
        else:
            self.table.setSortingEnabled(sorting_was_enabled)
            header = self.table.horizontalHeader()
            if header is not None:
                header.setSortIndicatorShown(False)
        
        # Column sizing handled by header resize mode
        self.table_filter.apply_filters()
    
    def _filter_sites(self):
        """Filter table based on search"""
        self._populate_table()

    def _clear_search(self):
        self.search_edit.clear()
        self.table.clearSelection()
        self._on_selection_changed()
        self._populate_table()

    def _clear_all_filters(self):
        self.search_edit.clear()
        self.table.clearSelection()
        self._on_selection_changed()
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()
        self._populate_table()
    
    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        # Check if any cells are selected
        has_selection = self.table.selectionModel().hasSelection()
        
        # Get unique rows that have any selected cells
        selected_rows = self._get_selected_row_numbers()
        self.view_btn.setVisible(len(selected_rows) == 1)
        self.edit_btn.setVisible(len(selected_rows) == 1)
        self.delete_btn.setVisible(len(selected_rows) > 0)
        
        # Update spreadsheet stats bar
        if has_selection:
            grid = SpreadsheetUXController.extract_selection_grid(self.table)
            stats = SpreadsheetUXController.compute_stats(grid)
            self.stats_bar.update_stats(stats)
        else:
            self.stats_bar.clear_stats()

    def _get_selected_row_numbers(self):
        """Get list of unique row numbers that have any selected cells"""
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            return []
        return sorted(set(index.row() for index in selected_indexes))
    
    def _get_selected_site_id(self):
        """Get ID of selected site"""
        ids = self._get_selected_site_ids()
        return ids[0] if ids else None

    def _get_selected_site_ids(self):
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids
    
    def _add_site(self):
        """Show dialog to add new site"""
        dialog = SiteDialog(self)
        if dialog.exec():
            try:
                site = self.facade.create_site(
                    name=dialog.name_edit.text(),
                    url=dialog.url_edit.text() or None,
                    sc_rate=float(dialog.rate_edit.text()),
                    playthrough_requirement=float(dialog.playthrough_edit.text()),
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self.window() or self, "Success", f"Site '{site.name}' created"
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
                    playthrough_requirement=float(dialog.playthrough_edit.text()),
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
        site_ids = self._get_selected_site_ids()
        if not site_ids:
            return

        sites = []
        for site_id in site_ids:
            site = self.facade.get_site(site_id)
            if site:
                sites.append(site)

        if not sites:
            return

        if len(sites) == 1:
            prompt = f"Delete site '{sites[0].name}'?\n\nThis cannot be undone."
        else:
            prompt = f"Delete {len(sites)} sites?\n\nThis cannot be undone."

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for site in sites:
                    self.facade.delete_site(site.id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Site(s) deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete site(s):\n{str(e)}"
                )

    def _copy_selection(self):
        """Copy selected cells to clipboard as TSV"""
        grid = SpreadsheetUXController.extract_selection_grid(self.table)
        SpreadsheetUXController.copy_to_clipboard(grid)

    def _copy_with_headers(self):
        """Copy selected cells to clipboard with column headers"""
        grid = SpreadsheetUXController.extract_selection_grid(self.table, include_headers=True)
        SpreadsheetUXController.copy_to_clipboard(grid)

    def _show_context_menu(self, position):
        """Show context menu for table"""
        if not self.table.selectionModel().hasSelection():
            return
        
        menu = QtWidgets.QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)
        
        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))

    def _export_csv(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Sites",
            f"sites_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            try:
                import csv
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
                    writer.writerow(headers)
                    for row in range(self.table.rowCount()):
                        if self.table.isRowHidden(row):
                            continue
                        row_values = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_values.append(item.text() if item else "")
                        writer.writerow(row_values)

                QtWidgets.QMessageBox.information(
                    self, "Export Complete",
                    f"Exported sites to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )

    def _view_site(self):
        site_id = self._get_selected_site_id()
        if not site_id:
            return
        site = self.facade.get_site(site_id)
        if not site:
            return
        
        dialog = SiteViewDialog(
            site,
            parent=self,
            on_edit=self._edit_site,
            on_delete=self._delete_site,
        )
        dialog.exec()
        self.refresh_data()


class SiteDialog(QtWidgets.QDialog):
    """Dialog for adding/editing sites"""
    
    def __init__(self, parent=None, site: Site = None):
        super().__init__(parent)
        self.site = site
        self.setWindowTitle("Edit Site" if site else "Add Site")
        self.setMinimumSize(420, 420)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Section header
        header = QtWidgets.QLabel("🏢 Site Details")
        header.setObjectName("SectionHeader")
        main_layout.addWidget(header)
        
        # Main section
        main_section = QtWidgets.QWidget()
        main_section.setObjectName("SectionBackground")
        main_grid = QtWidgets.QGridLayout(main_section)
        main_grid.setContentsMargins(12, 12, 12, 12)
        main_grid.setHorizontalSpacing(20)
        main_grid.setVerticalSpacing(10)
        
        # Active checkbox - row 0 (alone)
        active_label = QtWidgets.QLabel("Active:")
        active_label.setObjectName("FieldLabel")
        active_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(site.is_active if site else True)
        main_grid.addWidget(active_label, 0, 0)
        main_grid.addWidget(self.active_check, 0, 1)
        
        # Name (required)
        name_label = QtWidgets.QLabel("Name:")
        name_label.setObjectName("FieldLabel")
        name_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        if site:
            self.name_edit.setText(site.name)
        main_grid.addWidget(name_label, 1, 0)
        main_grid.addWidget(self.name_edit, 1, 1)
        
        # URL (optional)
        url_label = QtWidgets.QLabel("URL:")
        url_label.setObjectName("FieldLabel")
        url_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.setPlaceholderText("Optional")
        if site and site.url:
            self.url_edit.setText(site.url)
        main_grid.addWidget(url_label, 2, 0)
        main_grid.addWidget(self.url_edit, 2, 1)
        
        # SC Rate (required)
        rate_label = QtWidgets.QLabel("SC Rate:")
        rate_label.setObjectName("FieldLabel")
        rate_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.rate_edit = QtWidgets.QLineEdit()
        self.rate_edit.setPlaceholderText("Required (e.g., 1.0)")
        self.rate_edit.setFixedWidth(140)
        self.rate_edit.setText(str(site.sc_rate if site else "1.0"))
        main_grid.addWidget(rate_label, 3, 0)
        main_grid.addWidget(self.rate_edit, 3, 1)

        # Playthrough Requirement (required)
        playthrough_label = QtWidgets.QLabel("Playthrough Requirement:")
        playthrough_label.setObjectName("FieldLabel")
        playthrough_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.playthrough_edit = QtWidgets.QLineEdit()
        self.playthrough_edit.setPlaceholderText("Required (e.g., 1.0)")
        self.playthrough_edit.setFixedWidth(140)
        self.playthrough_edit.setText(str(site.playthrough_requirement if site else "1.0"))
        main_grid.addWidget(playthrough_label, 4, 0)
        main_grid.addWidget(self.playthrough_edit, 4, 1)
        
        main_layout.addWidget(main_section)
        
        # Notes section (collapsible)
        self.notes_collapsed = True
        self.notes_toggle = QtWidgets.QPushButton("📝 Add Notes...")
        self.notes_toggle.setObjectName("SectionHeader")
        self.notes_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.notes_toggle.setFlat(True)
        self.notes_toggle.clicked.connect(self._toggle_notes)
        main_layout.addWidget(self.notes_toggle)
        
        self.notes_section = QtWidgets.QWidget()
        self.notes_section.setObjectName("SectionBackground")
        notes_layout = QtWidgets.QVBoxLayout(self.notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(80)
        if site and site.notes:
            self.notes_edit.setPlainText(site.notes)
        notes_layout.addWidget(self.notes_edit)
        self.notes_section.setVisible(False)
        main_layout.addWidget(self.notes_section)
        
        # Expand notes if editing and notes exist
        if site and site.notes:
            self._toggle_notes()
        
        # Stretch
        main_layout.addStretch(1)
        
        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        
        cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        
        self.save_btn = QtWidgets.QPushButton("💾 Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(self.save_btn)
        
        main_layout.addLayout(btn_row)
        
        # Validation
        self.name_edit.textChanged.connect(self._validate_inline)
        self.rate_edit.textChanged.connect(self._validate_inline)
        self.playthrough_edit.textChanged.connect(self._validate_inline)
        self._validate_inline()
        
        # Tab order
        self.setTabOrder(self.name_edit, self.active_check)
        self.setTabOrder(self.active_check, self.url_edit)
        self.setTabOrder(self.url_edit, self.rate_edit)
        self.setTabOrder(self.rate_edit, self.playthrough_edit)
        self.setTabOrder(self.playthrough_edit, self.notes_edit)
        self.setTabOrder(self.notes_edit, self.save_btn)
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(420)
            self.setMaximumHeight(420)
            self.resize(self.width(), 420)
        else:
            self.notes_toggle.setText("📝 Hide Notes")
            self.setMinimumHeight(500)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), 500)
    
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
    
    def _validate_inline(self) -> bool:
        """Validate all fields and return True if valid"""
        valid = True
        
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Name is required.")
            valid = False
        else:
            self._set_valid(self.name_edit)
        
        try:
            rate = float(self.rate_edit.text())
            if rate <= 0:
                raise ValueError("Rate must be positive")
            self._set_valid(self.rate_edit)
        except Exception:
            self._set_invalid(self.rate_edit, "Enter a positive rate")
            valid = False

        try:
            playthrough = float(self.playthrough_edit.text())
            if playthrough <= 0:
                raise ValueError("Playthrough requirement must be positive")
            self._set_valid(self.playthrough_edit)
        except Exception:
            self._set_invalid(self.playthrough_edit, "Enter a positive playthrough requirement")
            valid = False
        
        self.save_btn.setEnabled(valid)
        return valid
    
    def _validate_and_accept(self):
        """Final validation before accepting"""
        if not self._validate_inline():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please correct the highlighted fields."
            )
            return
        self.accept()


class SiteViewDialog(QtWidgets.QDialog):
    """Dialog for viewing site details"""
    
    def __init__(self, site: Site, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.site = site
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Site")
        self.setMinimumSize(550, 300)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # Site details section header
        details_header = QtWidgets.QLabel("🏛️ Site Details")
        details_header.setObjectName("SectionHeader")
        main_layout.addWidget(details_header)
        
        # Site details section
        details_section = QtWidgets.QWidget()
        details_section.setObjectName("SectionBackground")
        details_layout = QtWidgets.QVBoxLayout(details_section)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(6)
        
        # Two-column layout
        columns = QtWidgets.QHBoxLayout()
        columns.setSpacing(30)
        
        # Left column
        left_grid = QtWidgets.QGridLayout()
        left_grid.setHorizontalSpacing(12)
        left_grid.setVerticalSpacing(6)
        left_grid.setColumnStretch(1, 1)
        
        name_lbl = QtWidgets.QLabel("Name:")
        name_lbl.setObjectName("MutedLabel")
        name_val = self._make_selectable_label(site.name)
        left_grid.addWidget(name_lbl, 0, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(name_val, 0, 1)
        
        url_lbl = QtWidgets.QLabel("URL:")
        url_lbl.setObjectName("MutedLabel")
        url_val = self._make_selectable_label(site.url or "—")
        left_grid.addWidget(url_lbl, 1, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(url_val, 1, 1)
        
        columns.addLayout(left_grid, 1)
        
        # Right column
        right_grid = QtWidgets.QGridLayout()
        right_grid.setHorizontalSpacing(12)
        right_grid.setVerticalSpacing(6)
        right_grid.setColumnStretch(1, 1)
        
        status_lbl = QtWidgets.QLabel("Status:")
        status_lbl.setObjectName("MutedLabel")
        status_val = self._make_selectable_label("Active" if site.is_active else "Inactive")
        right_grid.addWidget(status_lbl, 0, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(status_val, 0, 1)
        
        rate_lbl = QtWidgets.QLabel("SC Rate:")
        rate_lbl.setObjectName("MutedLabel")
        rate_val = self._make_selectable_label(str(site.sc_rate))
        right_grid.addWidget(rate_lbl, 1, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(rate_val, 1, 1)

        playthrough_lbl = QtWidgets.QLabel("Playthrough:")
        playthrough_lbl.setObjectName("MutedLabel")
        playthrough_val = self._make_selectable_label(str(site.playthrough_requirement))
        right_grid.addWidget(playthrough_lbl, 2, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(playthrough_val, 2, 1)
        
        columns.addLayout(right_grid, 1)
        
        details_layout.addLayout(columns)
        main_layout.addWidget(details_section)
        
        # Notes section header
        notes_header = QtWidgets.QLabel("📝 Notes")
        notes_header.setObjectName("SectionHeader")
        main_layout.addWidget(notes_header)
        
        # Notes section
        notes_section = QtWidgets.QWidget()
        notes_section.setObjectName("SectionBackground")
        notes_layout = QtWidgets.QVBoxLayout(notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(6)
        
        if site.notes:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(site.notes)
            notes_display.setMaximumHeight(80)
            notes_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            notes_layout.addWidget(notes_display)
        else:
            notes_empty = QtWidgets.QLabel("—")
            notes_empty.setObjectName("MutedLabel")
            notes_font = notes_empty.font()
            notes_font.setItalic(True)
            notes_empty.setFont(notes_font)
            notes_layout.addWidget(notes_empty)
        main_layout.addWidget(notes_section)
        
        # Stretch
        main_layout.addStretch(1)
        
        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("🗑️ Delete")
            delete_btn.clicked.connect(self._handle_delete)
            btn_row.addWidget(delete_btn)
        
        btn_row.addStretch(1)
        
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("✏️ Edit")
            edit_btn.clicked.connect(self._handle_edit)
            btn_row.addWidget(edit_btn)
        
        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        
        main_layout.addLayout(btn_row)
    
    def _create_section(self, title):
        """Create a section with header"""
        header = QtWidgets.QLabel(title)
        header.setObjectName("SectionHeader")
        
        section = QtWidgets.QWidget()
        section.setObjectName("SectionBackground")
        layout = QtWidgets.QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        return section, layout
    
    def _make_selectable_label(self, text):
        """Create selectable text label"""
        label = QtWidgets.QLabel(text)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        label.setCursor(QtCore.Qt.IBeamCursor)
        return label
    
    def _handle_edit(self):
        """Close dialog before triggering edit callback"""
        self.accept()
        if self._on_edit:
            self._on_edit()
    
    def _handle_delete(self):
        """Close dialog before triggering delete callback"""
        self.accept()
        if self._on_delete:
            self._on_delete()
