"""
Users tab - Manage users/players
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.user import User
from ui.table_header_filters import TableHeaderFilter
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar


class UsersTab(QtWidgets.QWidget):
    """Tab for managing users"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.users = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Users")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search users...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_users)
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
        
        add_btn = QtWidgets.QPushButton("➕ Add User")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_user)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_user)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)
        
        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_user)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_user)
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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Email", "Status", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_user)
        
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
    
    def refresh_data(self):
        """Reload users from database"""
        self.users = self.facade.get_all_users()
        self._populate_table()
    
    def _populate_table(self):
        """Populate table with users"""
        # Clear search when refreshing
        search_text = self.search_edit.text().lower()
        
        # Filter users
        if search_text:
            filtered = [u for u in self.users 
                       if search_text in u.name.lower() 
                       or (u.email and search_text in u.email.lower())
                       or (u.notes and search_text in u.notes.lower())]
        else:
            filtered = self.users
        
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(filtered))
        
            for row, user in enumerate(filtered):
                # Name
                name_item = QtWidgets.QTableWidgetItem(user.name)
                name_item.setData(QtCore.Qt.UserRole, user.id)
                self.table.setItem(row, 0, name_item)
                
                # Email
                email = user.email or ""
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(email))
                
                # Status
                status = "Active" if user.is_active else "Inactive"
                status_item = QtWidgets.QTableWidgetItem(status)
                if not user.is_active:
                    status_item.setForeground(QtGui.QColor("#999"))
                self.table.setItem(row, 2, status_item)
                
                # Notes
                notes = (user.notes or "")[:100]
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(notes))

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
    
    def _filter_users(self):
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
    
    def _get_selected_user_id(self):
        """Get ID of selected user"""
        ids = self._get_selected_user_ids()
        return ids[0] if ids else None

    def _get_selected_user_ids(self):
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids
    
    def _add_user(self):
        """Show dialog to add new user"""
        dialog = UserDialog(self, suggestions=self.users)
        if dialog.exec():
            try:
                user = self.facade.create_user(
                    name=dialog.name_edit.text(),
                    email=dialog.email_edit.text() or None,
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self.window() or self, "Success", f"User '{user.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create user:\n{str(e)}"
                )
    
    def _edit_user(self):
        """Show dialog to edit selected user"""
        user_id = self._get_selected_user_id()
        if not user_id:
            return
        
        user = self.facade.get_user(user_id)
        if not user:
            return
        
        dialog = UserDialog(self, user, suggestions=self.users)
        if dialog.exec():
            try:
                updated = self.facade.update_user(
                    user_id,
                    name=dialog.name_edit.text(),
                    email=dialog.email_edit.text() or None,
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked()
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"User '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update user:\n{str(e)}"
                )
    
    def _delete_user(self):
        """Delete selected user"""
        user_ids = self._get_selected_user_ids()
        if not user_ids:
            return

        users = []
        for user_id in user_ids:
            user = self.facade.get_user(user_id)
            if user:
                users.append(user)

        if not users:
            return

        if len(users) == 1:
            prompt = f"Delete user '{users[0].name}'?\n\nThis cannot be undone."
        else:
            prompt = f"Delete {len(users)} users?\n\nThis cannot be undone."

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for user in users:
                    self.facade.delete_user(user.id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "User(s) deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete user(s):\n{str(e)}"
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
            "Export Users",
            f"users_{date.today().isoformat()}.csv",
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
                    f"Exported users to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )

    def _view_user(self):
        user_id = self._get_selected_user_id()
        if not user_id:
            return
        user = self.facade.get_user(user_id)
        if not user:
            return
        
        dialog = UserViewDialog(
            user,
            parent=self,
            on_edit=self._edit_user,
            on_delete=self._delete_user,
        )
        dialog.exec()
        self.refresh_data()


class UserDialog(QtWidgets.QDialog):
    """Dialog for adding/editing users"""
    
    def __init__(self, parent=None, user: User = None, suggestions=None):
        super().__init__(parent)
        self.user = user
        self.suggestions = suggestions or []
        self.setWindowTitle("Edit User" if user else "Add User")
        self.setMinimumSize(400, 300)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Section header
        header = QtWidgets.QLabel("👤 User Details")
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
        self.active_check.setChecked(user.is_active if user else True)
        main_grid.addWidget(active_label, 0, 0)
        main_grid.addWidget(self.active_check, 0, 1)
        
        # Name (required) - same width as Email
        name_label = QtWidgets.QLabel("Name:")
        name_label.setObjectName("FieldLabel")
        name_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        if user:
            self.name_edit.setText(user.name)
        main_grid.addWidget(name_label, 1, 0)
        main_grid.addWidget(self.name_edit, 1, 1)
        
        # Email (optional) - same width as Name
        email_label = QtWidgets.QLabel("Email:")
        email_label.setObjectName("FieldLabel")
        email_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.email_edit = QtWidgets.QLineEdit()
        self.email_edit.setPlaceholderText("Optional")
        if user and user.email:
            self.email_edit.setText(user.email)
        main_grid.addWidget(email_label, 2, 0)
        main_grid.addWidget(self.email_edit, 2, 1)
        
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
        if user and user.notes:
            self.notes_edit.setPlainText(user.notes)
        notes_layout.addWidget(self.notes_edit)
        self.notes_section.setVisible(False)
        main_layout.addWidget(self.notes_section)
        
        # Expand notes if editing and notes exist
        if user and user.notes:
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
        self._validate_inline()
        
        # Autocomplete
        if self.suggestions:
            name_model = QtCore.QStringListModel([u.name for u in self.suggestions if u and u.name])
            name_completer = QtWidgets.QCompleter(name_model)
            name_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            name_completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            name_completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            self.name_edit.setCompleter(name_completer)
            
            emails = [u.email for u in self.suggestions if u and u.email]
            if emails:
                email_model = QtCore.QStringListModel(emails)
                email_completer = QtWidgets.QCompleter(email_model)
                email_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                email_completer.setFilterMode(QtCore.Qt.MatchStartsWith)
                email_completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
                self.email_edit.setCompleter(email_completer)
        
        # Tab order
        self.setTabOrder(self.name_edit, self.active_check)
        self.setTabOrder(self.active_check, self.email_edit)
        self.setTabOrder(self.email_edit, self.notes_edit)
        self.setTabOrder(self.notes_edit, self.save_btn)
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(350)
            self.setMaximumHeight(350)
            self.resize(self.width(), 350)
        else:
            self.notes_toggle.setText("📝 Hide Notes")
            self.setMinimumHeight(430)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), 430)
    
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


class UserViewDialog(QtWidgets.QDialog):
    """Dialog for viewing user details"""
    
    def __init__(self, user: User, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.user = user
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View User")
        self.setMinimumSize(520, 300)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # User details section header
        details_header = QtWidgets.QLabel("👤 User Details")
        details_header.setObjectName("SectionHeader")
        main_layout.addWidget(details_header)
        
        # User details section
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
        name_val = self._make_selectable_label(user.name)
        left_grid.addWidget(name_lbl, 0, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(name_val, 0, 1)
        
        email_lbl = QtWidgets.QLabel("Email:")
        email_lbl.setObjectName("MutedLabel")
        email_val = self._make_selectable_label(user.email or "—")
        left_grid.addWidget(email_lbl, 1, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(email_val, 1, 1)
        
        columns.addLayout(left_grid, 1)
        
        # Right column
        right_grid = QtWidgets.QGridLayout()
        right_grid.setHorizontalSpacing(12)
        right_grid.setVerticalSpacing(6)
        right_grid.setColumnStretch(1, 1)
        
        status_lbl = QtWidgets.QLabel("Status:")
        status_lbl.setObjectName("MutedLabel")
        status_val = self._make_selectable_label("Active" if user.is_active else "Inactive")
        right_grid.addWidget(status_lbl, 0, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(status_val, 0, 1)
        
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
        
        if user.notes:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(user.notes)
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
