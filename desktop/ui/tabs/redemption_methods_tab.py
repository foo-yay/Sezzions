"""
Redemption Methods tab - Manage redemption methods
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.redemption_method import RedemptionMethod
from desktop.ui.table_header_filters import TableHeaderFilter
from desktop.ui.spreadsheet_ux import SpreadsheetUXController
from desktop.ui.spreadsheet_stats_bar import SpreadsheetStatsBar


class RedemptionMethodsTab(QtWidgets.QWidget):
    """Tab for managing redemption methods"""

    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.methods = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Redemption Methods")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search methods...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_methods)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)
        layout.addLayout(header_layout)

        toolbar = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("➕ Add Method")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_method)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_method)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)

        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_method)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_method)
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

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Name", "Method Type", "User", "Status", "Notes"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_method)
        
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

        self.refresh_data()

    def focus_search(self):
        """Focus the search bar (for Cmd+F/Ctrl+F shortcut - Issue #99)"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def refresh_data(self):
        self.methods = self.facade.get_all_redemption_methods(active_only=False)
        users = {u.id: u.name for u in self.facade.get_all_users(active_only=False)}
        for method in self.methods:
            if method.user_id is not None:
                method.user_name = users.get(method.user_id, "")
        self._populate_table()

    def _populate_table(self):
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered = [m for m in self.methods
                        if search_text in m.name.lower()
                        or (m.method_type and search_text in m.method_type.lower())
                        or (getattr(m, 'user_name', None) and search_text in m.user_name.lower())
                        or (m.notes and search_text in m.notes.lower())]
        else:
            filtered = self.methods

        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(filtered))

            for row, method in enumerate(filtered):
                name_item = QtWidgets.QTableWidgetItem(method.name)
                name_item.setData(QtCore.Qt.UserRole, method.id)
                self.table.setItem(row, 0, name_item)

                method_type = method.method_type or "—"
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(method_type))

                user_name = getattr(method, 'user_name', None) or "—"
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(user_name))

                status = "Active" if method.is_active else "Inactive"
                status_item = QtWidgets.QTableWidgetItem(status)
                if not method.is_active:
                    status_item.setForeground(QtGui.QColor("#999"))
                self.table.setItem(row, 3, status_item)

                notes = (method.notes or "")[:100]
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(notes))

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

        self.table_filter.apply_filters()

        # Column sizing handled by header resize mode

    def _filter_methods(self):
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

    def _get_selected_method_id(self):
        ids = self._get_selected_method_ids()
        return ids[0] if ids else None

    def _get_selected_method_ids(self):
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def _add_method(self):
        dialog = RedemptionMethodDialog(self.facade, self)
        if dialog.exec():
            try:
                method = self.facade.create_redemption_method(
                    name=dialog.name_edit.text(),
                    method_type=dialog.method_type_combo.currentText() or None,
                    user_id=dialog.user_id,
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self.window() or self, "Success", f"Method '{method.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create method:\n{str(e)}"
                )

    def _edit_method(self):
        method_id = self._get_selected_method_id()
        if not method_id:
            return

        method = self.facade.get_redemption_method(method_id)
        if not method:
            return

        dialog = RedemptionMethodDialog(self.facade, self, method)
        if dialog.exec():
            try:
                updated = self.facade.update_redemption_method(
                    method_id,
                    name=dialog.name_edit.text(),
                    method_type=dialog.method_type_combo.currentText() or None,
                    user_id=dialog.user_id,
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked()
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Method '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update method:\n{str(e)}"
                )

    def _delete_method(self):
        method_ids = self._get_selected_method_ids()
        if not method_ids:
            return

        methods = []
        for method_id in method_ids:
            method = self.facade.get_redemption_method(method_id)
            if method:
                methods.append(method)

        if not methods:
            return

        if len(methods) == 1:
            prompt = f"Delete redemption method '{methods[0].name}'?\n\nThis cannot be undone."
        else:
            prompt = f"Delete {len(methods)} redemption methods?\n\nThis cannot be undone."

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for method in methods:
                    self.facade.delete_redemption_method(method.id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(self, "Success", "Method(s) deleted")
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete method(s):\n{str(e)}"
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
            "Export Redemption Methods",
            f"redemption_methods_{date.today().isoformat()}.csv",
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
                    f"Exported redemption methods to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )

    def _view_method(self):
        method_id = self._get_selected_method_id()
        if not method_id:
            return
        method = self.facade.get_redemption_method(method_id)
        if not method:
            return
        
        dialog = RedemptionMethodViewDialog(
            method,
            parent=self,
            on_edit=self._edit_method,
            on_delete=self._delete_method,
        )
        dialog.exec()
        self.refresh_data()


class RedemptionMethodDialog(QtWidgets.QDialog):
    """Dialog for adding/editing redemption methods"""

    def __init__(self, facade: AppFacade, parent=None, method: RedemptionMethod = None):
        super().__init__(parent)
        self.facade = facade
        self.method = method
        self.user_id = method.user_id if method else None
        self.setWindowTitle("Edit Method" if method else "Add Method")
        self.setMinimumSize(400, 350)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Section header
        header = QtWidgets.QLabel("💳 Redemption Method Details")
        header.setObjectName("SectionHeader")
        main_layout.addWidget(header)
        
        # Main section
        main_section = QtWidgets.QWidget()
        main_section.setObjectName("SectionBackground")
        main_grid = QtWidgets.QGridLayout(main_section)
        main_grid.setContentsMargins(12, 12, 12, 12)
        main_grid.setHorizontalSpacing(20)
        main_grid.setVerticalSpacing(10)
        main_grid.setColumnStretch(0, 0)  # Label column doesn't stretch
        
        # Active checkbox - row 0 (alone)
        active_label = QtWidgets.QLabel("Active:")
        active_label.setObjectName("FieldLabel")
        active_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(method.is_active if method else True)
        main_grid.addWidget(active_label, 0, 0)
        main_grid.addWidget(self.active_check, 0, 1, alignment=QtCore.Qt.AlignLeft)
        
        # Name (required) - increased to 300px
        name_label = QtWidgets.QLabel("Name:")
        name_label.setObjectName("FieldLabel")
        name_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        self.name_edit.setFixedWidth(300)
        if method:
            self.name_edit.setText(method.name)
        main_grid.addWidget(name_label, 1, 0)
        main_grid.addWidget(self.name_edit, 1, 1, alignment=QtCore.Qt.AlignLeft)
        
        # Method Type (required) - increased to 300px
        method_type_label = QtWidgets.QLabel("Method Type:")
        method_type_label.setObjectName("FieldLabel")
        method_type_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.method_type_combo = QtWidgets.QComboBox()
        self.method_type_combo.setEditable(True)
        self.method_type_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.method_type_combo.setFixedWidth(300)
        self._load_method_types()
        main_grid.addWidget(method_type_label, 2, 0)
        main_grid.addWidget(self.method_type_combo, 2, 1, alignment=QtCore.Qt.AlignLeft)
        
        # User (required) - increased to 300px
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        user_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.user_combo.setFixedWidth(300)
        users = self.facade.get_all_users(active_only=True)
        self.user_map = {}
        for user in users:
            self.user_combo.addItem(user.name, user.id)
            self.user_map[user.id] = user.name
        
        if method and method.user_id is not None:
            idx = self.user_combo.findData(method.user_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
        else:
            self.user_combo.setCurrentIndex(-1)
            self.user_combo.setEditText("")
            if self.user_combo.lineEdit() is not None:
                self.user_combo.lineEdit().setPlaceholderText("Required")
        
        main_grid.addWidget(user_label, 3, 0)
        main_grid.addWidget(self.user_combo, 3, 1)
        
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
        if method and method.notes:
            self.notes_edit.setPlainText(method.notes)
        notes_layout.addWidget(self.notes_edit)
        self.notes_section.setVisible(False)
        main_layout.addWidget(self.notes_section)
        
        # Expand notes if editing and notes exist
        if method and method.notes:
            self._toggle_notes()
        
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
        self.method_type_combo.currentTextChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self._validate_inline()
        
        # Autocomplete
        for combo in (self.method_type_combo, self.user_combo):
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            combo.setCompleter(completer)
            if combo.lineEdit() is not None:
                combo.lineEdit().setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    combo.lineEdit().installEventFilter(app._completer_filter)
        
        # Tab order
        self.setTabOrder(self.name_edit, self.active_check)
        self.setTabOrder(self.active_check, self.method_type_combo)
        self.setTabOrder(self.method_type_combo, self.user_combo)
        self.setTabOrder(self.user_combo, self.notes_edit)
        self.setTabOrder(self.notes_edit, self.save_btn)
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(450)
            self.setMaximumHeight(450)
            self.resize(self.width(), 450)
        else:
            self.notes_toggle.setText("📝 Hide Notes")
            self.setMinimumHeight(530)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), 530)
    
    def _load_method_types(self):
        self.method_type_combo.clear()
        types = self.facade.get_all_redemption_method_types(active_only=True)
        for method_type in types:
            self.method_type_combo.addItem(method_type.name, method_type.id)
        
        if self.method and self.method.method_type:
            idx = self.method_type_combo.findText(self.method.method_type)
            if idx >= 0:
                self.method_type_combo.setCurrentIndex(idx)
        else:
            self.method_type_combo.setCurrentIndex(-1)
            self.method_type_combo.setEditText("")
            if self.method_type_combo.lineEdit() is not None:
                self.method_type_combo.lineEdit().setPlaceholderText("Required")
    
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
        
        if not self.method_type_combo.currentText().strip():
            self._set_invalid(self.method_type_combo, "Method Type is required.")
            valid = False
        else:
            self._set_valid(self.method_type_combo)
        
        # Update user_id
        self.user_id = self.user_combo.currentData()
        if self.user_id is None:
            text = self.user_combo.currentText().strip().lower()
            for uid, name in self.user_map.items():
                if name.lower() == text:
                    self.user_id = uid
                    break
        
        if self.user_id is None:
            self._set_invalid(self.user_combo, "User is required.")
            valid = False
        else:
            self._set_valid(self.user_combo)
        
        self.save_btn.setEnabled(valid)
        return valid
    
    def _validate_and_accept(self):
        """Final validation before accepting"""
        if self.method_type_combo.count() == 0:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please add a Method Type first."
            )
            return
        
        if not self._validate_inline():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please correct the highlighted fields."
            )
            return
        
        self.accept()


class RedemptionMethodViewDialog(QtWidgets.QDialog):
    """Dialog for viewing redemption method details"""
    
    def __init__(self, method: RedemptionMethod, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.method = method
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Redemption Method")
        self.setMinimumSize(600, 360)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # Redemption Method details section header
        details_header = QtWidgets.QLabel("💳 Redemption Method Details")
        details_header.setObjectName("SectionHeader")
        main_layout.addWidget(details_header)
        
        # Redemption Method details section
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
        name_val = self._make_selectable_label(method.name)
        left_grid.addWidget(name_lbl, 0, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(name_val, 0, 1)
        
        method_type_lbl = QtWidgets.QLabel("Method Type:")
        method_type_lbl.setObjectName("MutedLabel")
        method_type_val = self._make_selectable_label(method.method_type or "—")
        left_grid.addWidget(method_type_lbl, 1, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(method_type_val, 1, 1)
        
        columns.addLayout(left_grid, 1)
        
        # Right column
        right_grid = QtWidgets.QGridLayout()
        right_grid.setHorizontalSpacing(12)
        right_grid.setVerticalSpacing(6)
        right_grid.setColumnStretch(1, 1)
        
        user_lbl = QtWidgets.QLabel("User:")
        user_lbl.setObjectName("MutedLabel")
        user_name = getattr(method, 'user_name', None)
        user_display = user_name if user_name else "Unknown User" if method.user_id else "—"
        user_val = self._make_selectable_label(user_display)
        right_grid.addWidget(user_lbl, 0, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(user_val, 0, 1)
        
        status_lbl = QtWidgets.QLabel("Status:")
        status_lbl.setObjectName("MutedLabel")
        status_val = self._make_selectable_label("Active" if method.is_active else "Inactive")
        right_grid.addWidget(status_lbl, 1, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(status_val, 1, 1)
        
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
        
        if method.notes:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(method.notes)
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
