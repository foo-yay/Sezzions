"""
Redemption Methods tab - Manage redemption methods
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.redemption_method import RedemptionMethod
from ui.table_header_filters import TableHeaderFilter


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
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_method)
        layout.addWidget(self.table)
        self.table_filter = TableHeaderFilter(self.table, refresh_callback=self.refresh_data)

        self.refresh_data()

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
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = bool(selected_rows)
        self.view_btn.setVisible(len(selected_rows) == 1)
        self.edit_btn.setVisible(len(selected_rows) == 1)
        self.delete_btn.setVisible(has_selection)

    def _get_selected_method_id(self):
        ids = self._get_selected_method_ids()
        return ids[0] if ids else None

    def _get_selected_method_ids(self):
        ids = []
        for row in self.table.selectionModel().selectedRows():
            item = self.table.item(row.row(), 0)
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
                    self, "Success", f"Method '{method.name}' created"
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
        def handle_edit():
            dialog.close()
            self._edit_method()

        def handle_delete():
            dialog.close()
            self._delete_method()

        dialog = RedemptionMethodDialog(
            self.facade,
            self,
            method,
            read_only=True,
            on_edit=handle_edit,
            on_delete=handle_delete,
        )
        dialog.exec()


class RedemptionMethodDialog(QtWidgets.QDialog):
    """Dialog for adding/editing redemption methods"""

    def __init__(self, facade: AppFacade, parent=None, method: RedemptionMethod = None, read_only: bool = False, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.facade = facade
        self.method = method
        self.read_only = read_only
        self.user_id = method.user_id if method else None
        self._on_edit = on_edit
        self._on_delete = on_delete

        if self.read_only:
            self.setWindowTitle("View Method")
        else:
            self.setWindowTitle("Edit Method" if method else "Add Method")
        self.resize(480, 360)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)

        self.name_edit = QtWidgets.QLineEdit()
        name_label = QtWidgets.QLabel("Name:")
        name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(self.name_edit, 0, 1)

        self.method_type_combo = QtWidgets.QComboBox()
        self.method_type_combo.setEditable(True)
        self.method_type_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        if self.method_type_combo.lineEdit() is not None:
            self.method_type_combo.lineEdit().setPlaceholderText("Select a method type")
        self._load_method_types()
        method_type_label = QtWidgets.QLabel("Method Type:")
        method_type_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(method_type_label, 1, 0)
        layout.addWidget(self.method_type_combo, 1, 1, 1, 3)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        if self.user_combo.lineEdit() is not None:
            self.user_combo.lineEdit().setPlaceholderText("Select a user")
        users = self.facade.get_all_users(active_only=True)
        self.user_map = {}
        for user in users:
            self.user_combo.addItem(user.name, user.id)
            self.user_map[user.id] = user.name
        user_label = QtWidgets.QLabel("User:")
        user_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(user_label, 2, 0)
        layout.addWidget(self.user_combo, 2, 1, 1, 3)

        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)
        active_label = QtWidgets.QLabel("Active")
        active_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(active_label, 0, 2)
        layout.addWidget(self.active_check, 0, 3)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        notes_label = QtWidgets.QLabel("Notes:")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        layout.addWidget(notes_label, 3, 0)
        layout.addWidget(self.notes_edit, 3, 1, 1, 3)

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
            layout.addLayout(btn_row, 4, 0, 1, 4)
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
            layout.addLayout(btn_row, 4, 0, 1, 4)

        if method:
            self._load_method()
        else:
            self._clear_form()

        if self.read_only:
            for widget in (self.name_edit, self.method_type_combo, self.user_combo, self.active_check, self.notes_edit):
                widget.setEnabled(False)
            if not (method and method.notes):
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.notes_edit.setPlaceholderText("-")
                self.notes_edit.setFixedHeight(self.notes_edit.fontMetrics().lineSpacing() + 12)
            else:
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        self.name_edit.textChanged.connect(self._validate_inline)
        self.method_type_combo.currentTextChanged.connect(self._validate_inline)
        self._validate_inline()

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

    def _load_method_types(self):
        self.method_type_combo.clear()
        types = self.facade.get_all_redemption_method_types(active_only=True)
        for method_type in types:
            self.method_type_combo.addItem(method_type.name, method_type.id)
        if self.method is None:
            self.method_type_combo.setCurrentIndex(-1)
            self.method_type_combo.setEditText("")

    def _load_method(self):
        self.name_edit.setText(self.method.name)
        if self.method.method_type:
            idx = self.method_type_combo.findText(self.method.method_type)
            if idx >= 0:
                self.method_type_combo.setCurrentIndex(idx)
        if self.method.user_id is not None:
            idx = self.user_combo.findData(self.method.user_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
        self.active_check.setChecked(bool(self.method.is_active))
        if self.method.notes:
            self.notes_edit.setPlainText(self.method.notes)

    def _clear_form(self):
        self.name_edit.clear()
        self.method_type_combo.setCurrentIndex(-1)
        self.method_type_combo.setEditText("")
        self.user_combo.setCurrentIndex(-1)
        self.user_combo.setEditText("")
        self.active_check.setChecked(True)
        self.notes_edit.clear()

    def _validate_and_accept(self):
        if self.method_type_combo.count() == 0:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please add a Method Type first."
            )
            return
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Name is required")
            return

        method_type = self.method_type_combo.currentText().strip()
        if not method_type:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Method Type is required")
            return

        self.user_id = self.user_combo.currentData()
        if self.user_id is None:
            text = self.user_combo.currentText().strip().lower()
            for uid, name in self.user_map.items():
                if name.lower() == text:
                    self.user_id = uid
                    break
        if self.user_id is None:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "User is required")
            return
        self.accept()

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
        if not self.method_type_combo.currentText().strip():
            self._set_invalid(self.method_type_combo, "Method Type is required")
        else:
            self._set_valid(self.method_type_combo)
        user_text = self.user_combo.currentText().strip()
        user_id = self.user_combo.currentData()
        if user_id is None:
            if user_text:
                for uid, name in self.user_map.items():
                    if name.lower() == user_text.lower():
                        user_id = uid
                        break
        if user_id is None:
            self._set_invalid(self.user_combo, "User is required")
        else:
            self._set_valid(self.user_combo)
