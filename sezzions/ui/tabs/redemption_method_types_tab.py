"""
Redemption Method Types tab - Manage method types
"""
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.redemption_method_type import RedemptionMethodType


class RedemptionMethodTypesTab(QtWidgets.QWidget):
    """Tab for managing redemption method types"""

    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.types = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Method Types")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search method types...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_types)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)
        layout.addLayout(header_layout)

        toolbar = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("➕ Add Type")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_type)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_type)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)

        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_type)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_type)
        self.delete_btn.setVisible(False)
        toolbar.addWidget(self.delete_btn)

        toolbar.addStretch()

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._edit_type)
        layout.addWidget(self.table)

        self.refresh_data()

    def refresh_data(self):
        self.types = self.facade.get_all_redemption_method_types(active_only=False)
        self._populate_table()

    def _populate_table(self):
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered = [t for t in self.types
                        if search_text in t.name.lower()
                        or (t.notes and search_text in t.notes.lower())]
        else:
            filtered = self.types

        self.table.setRowCount(len(filtered))

        for row, method_type in enumerate(filtered):
            name_item = QtWidgets.QTableWidgetItem(method_type.name)
            name_item.setData(QtCore.Qt.UserRole, method_type.id)
            self.table.setItem(row, 0, name_item)

            status = "Active" if method_type.is_active else "Inactive"
            status_item = QtWidgets.QTableWidgetItem(status)
            if not method_type.is_active:
                status_item.setForeground(QtGui.QColor("#999"))
            self.table.setItem(row, 1, status_item)

            notes = (method_type.notes or "")[:100]
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(notes))

        # Column sizing handled by header resize mode

    def _filter_types(self):
        self._populate_table()

    def _clear_search(self):
        self.search_edit.clear()
        self._populate_table()

    def _clear_all_filters(self):
        self._clear_search()

    def _on_selection_changed(self):
        has_selection = len(self.table.selectedItems()) > 0
        self.view_btn.setVisible(has_selection)
        self.edit_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)

    def _get_selected_type_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        return self.table.item(row, 0).data(QtCore.Qt.UserRole)

    def _add_type(self):
        dialog = RedemptionMethodTypeDialog(self.facade, self)
        if dialog.exec():
            try:
                method_type = self.facade.create_redemption_method_type(
                    name=dialog.name_edit.text(),
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Type '{method_type.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create type:\n{str(e)}"
                )

    def _edit_type(self):
        type_id = self._get_selected_type_id()
        if not type_id:
            return

        method_type = self.facade.get_redemption_method_type(type_id)
        if not method_type:
            return

        dialog = RedemptionMethodTypeDialog(self.facade, self, method_type)
        if dialog.exec():
            try:
                updated = self.facade.update_redemption_method_type(
                    type_id,
                    name=dialog.name_edit.text(),
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked()
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Type '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update type:\n{str(e)}"
                )

    def _delete_type(self):
        type_id = self._get_selected_type_id()
        if not type_id:
            return

        method_type = self.facade.get_redemption_method_type(type_id)
        if not method_type:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete method type '{method_type.name}'?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.facade.delete_redemption_method_type(type_id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(self, "Success", "Type deleted")
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete type:\n{str(e)}"
                )

    def _view_type(self):
        type_id = self._get_selected_type_id()
        if not type_id:
            return
        method_type = self.facade.get_redemption_method_type(type_id)
        if not method_type:
            return
        def handle_edit():
            dialog.close()
            self._edit_type()

        def handle_delete():
            dialog.close()
            self._delete_type()

        dialog = RedemptionMethodTypeDialog(
            self.facade,
            self,
            method_type,
            read_only=True,
            on_edit=handle_edit,
            on_delete=handle_delete,
        )
        dialog.exec()


class RedemptionMethodTypeDialog(QtWidgets.QDialog):
    """Dialog for adding/editing redemption method types"""

    def __init__(self, facade: AppFacade, parent=None, method_type: RedemptionMethodType = None, read_only: bool = False, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.facade = facade
        self.method_type = method_type
        self.read_only = read_only
        self._on_edit = on_edit
        self._on_delete = on_delete

        if self.read_only:
            self.setWindowTitle("View Method Type")
        else:
            self.setWindowTitle("Edit Method Type" if method_type else "Add Method Type")
        self.resize(420, 300)

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
        layout.addWidget(notes_label, 1, 0, QtCore.Qt.AlignTop)
        layout.addWidget(self.notes_edit, 1, 1, 1, 3)

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
            layout.addLayout(btn_row, 2, 0, 1, 4)
        else:
            button_box = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
            )
            button_box.accepted.connect(self._validate_and_accept)
            button_box.rejected.connect(self.reject)
            layout.addWidget(button_box, 2, 0, 1, 4)

        if method_type:
            self._load_type()
        else:
            self._clear_form()

        if self.read_only:
            for widget in (self.name_edit, self.active_check, self.notes_edit):
                widget.setEnabled(False)
            if not (method_type and method_type.notes):
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.notes_edit.setPlaceholderText("-")
                self.notes_edit.setFixedHeight(self.notes_edit.fontMetrics().lineSpacing() + 12)

        self.name_edit.textChanged.connect(self._validate_inline)
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
        name = self.name_edit.text().strip()
        if not name:
            self._set_invalid(self.name_edit, "Name is required")
        else:
            self._set_valid(self.name_edit)

    def _load_type(self):
        self.name_edit.setText(self.method_type.name)
        self.active_check.setChecked(bool(self.method_type.is_active))
        if self.method_type.notes:
            self.notes_edit.setPlainText(self.method_type.notes)

    def _clear_form(self):
        self.name_edit.clear()
        self.active_check.setChecked(True)
        self.notes_edit.clear()

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Name is required")
            return
        self.accept()
