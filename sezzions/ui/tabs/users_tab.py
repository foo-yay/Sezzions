"""
Users tab - Manage users/players
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.user import User
from ui.table_header_filters import TableHeaderFilter


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
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_user)
        layout.addWidget(self.table)
        self.table_filter = TableHeaderFilter(self.table, refresh_callback=self.refresh_data)
        
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
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = bool(selected_rows)
        self.view_btn.setVisible(len(selected_rows) == 1)
        self.edit_btn.setVisible(len(selected_rows) == 1)
        self.delete_btn.setVisible(has_selection)
    
    def _get_selected_user_id(self):
        """Get ID of selected user"""
        ids = self._get_selected_user_ids()
        return ids[0] if ids else None

    def _get_selected_user_ids(self):
        ids = []
        for row in self.table.selectionModel().selectedRows():
            item = self.table.item(row.row(), 0)
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
                    self, "Success", f"User '{user.name}' created"
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
        def handle_edit():
            dialog.close()
            self._edit_user()

        def handle_delete():
            dialog.close()
            self._delete_user()

        dialog = UserDialog(
            self,
            user,
            read_only=True,
            suggestions=self.users,
            on_edit=handle_edit,
            on_delete=handle_delete,
        )
        dialog.exec()


class UserDialog(QtWidgets.QDialog):
    """Dialog for adding/editing users"""
    
    def __init__(self, parent=None, user: User = None, read_only: bool = False, suggestions=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.user = user
        self.read_only = read_only
        self.suggestions = suggestions or []
        self._on_edit = on_edit
        self._on_delete = on_delete
        if self.read_only:
            self.setWindowTitle("View User")
        else:
            self.setWindowTitle("Edit User" if user else "Add User")
        self.resize(500, 300)
        
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)
        
        # Name
        self.name_edit = QtWidgets.QLineEdit()
        if user:
            self.name_edit.setText(user.name)
        name_label = QtWidgets.QLabel("Name:")
        name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(self.name_edit, 0, 1)
        
        # Email
        self.email_edit = QtWidgets.QLineEdit()
        if user and user.email:
            self.email_edit.setText(user.email)
        email_label = QtWidgets.QLabel("Email:")
        email_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(email_label, 1, 0)
        layout.addWidget(self.email_edit, 1, 1, 1, 3)
        
        # Active
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(user.is_active if user else True)
        active_label = QtWidgets.QLabel("Active")
        active_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(active_label, 0, 2)
        layout.addWidget(self.active_check, 0, 3)
        
        # Notes
        self.notes_edit = QtWidgets.QTextEdit()
        if user and user.notes:
            self.notes_edit.setPlainText(user.notes)
        notes_label = QtWidgets.QLabel("Notes:")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        layout.addWidget(notes_label, 2, 0)
        layout.addWidget(self.notes_edit, 2, 1, 1, 3)
        
        # Buttons
        if self.read_only:
            btn_row = QtWidgets.QHBoxLayout()
            btn_row.setSpacing(8)
            if self._on_delete:
                delete_btn = QtWidgets.QPushButton("🗑️ Delete")
                delete_btn.clicked.connect(self._on_delete)
                btn_row.addWidget(delete_btn)
            btn_row.addStretch(1)
            if self._on_edit:
                edit_btn = QtWidgets.QPushButton("✏️ Edit")
                edit_btn.clicked.connect(self._on_edit)
                btn_row.addWidget(edit_btn)
            close_btn = QtWidgets.QPushButton("✖️ Close")
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row, 3, 0, 1, 4)
        else:
            btn_row = QtWidgets.QHBoxLayout()
            btn_row.addStretch(1)
            btn_row.setSpacing(8)
            cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
            save_btn = QtWidgets.QPushButton("💾 Save")
            save_btn.setObjectName("PrimaryButton")
            cancel_btn.clicked.connect(self.reject)
            save_btn.clicked.connect(self._validate_and_accept)
            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(save_btn)
            layout.addLayout(btn_row, 3, 0, 1, 4)

        if self.read_only:
            for widget in (self.name_edit, self.email_edit, self.active_check, self.notes_edit):
                widget.setEnabled(False)
            if not (user and user.notes):
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.notes_edit.setPlaceholderText("-")
                self.notes_edit.setFixedHeight(self.notes_edit.fontMetrics().lineSpacing() + 12)
            else:
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        self.name_edit.textChanged.connect(self._validate_inline)
        self._validate_inline()

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
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Name is required"
            )
            return
        self.accept()
