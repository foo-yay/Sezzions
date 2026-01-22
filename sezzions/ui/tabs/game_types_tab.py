"""
Game Types tab - Manage game categories
"""
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.game_type import GameType


class GameTypesTab(QtWidgets.QWidget):
    """Tab for managing game types"""

    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.game_types = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Game Types")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search game types...")
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

        add_btn = QtWidgets.QPushButton("➕ Add Game Type")
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
        self.game_types = self.facade.get_all_game_types()
        self._populate_table()

    def _populate_table(self):
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered = [t for t in self.game_types
                        if search_text in t.name.lower()
                        or (t.notes and search_text in t.notes.lower())]
        else:
            filtered = self.game_types

        self.table.setRowCount(len(filtered))
        for row, game_type in enumerate(filtered):
            name_item = QtWidgets.QTableWidgetItem(game_type.name)
            name_item.setData(QtCore.Qt.UserRole, game_type.id)
            self.table.setItem(row, 0, name_item)

            status = "Active" if game_type.is_active else "Inactive"
            status_item = QtWidgets.QTableWidgetItem(status)
            if not game_type.is_active:
                status_item.setForeground(QtGui.QColor("#999"))
            self.table.setItem(row, 1, status_item)

            notes = (game_type.notes or "")[:100]
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
        dialog = GameTypeDialog(self)
        if dialog.exec():
            try:
                created = self.facade.create_game_type(
                    name=dialog.name_edit.text(),
                    notes=dialog.notes_edit.toPlainText() or None,
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Game type '{created.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create game type:\n{str(e)}"
                )

    def _edit_type(self):
        type_id = self._get_selected_type_id()
        if not type_id:
            return

        game_type = self.facade.get_game_type(type_id)
        if not game_type:
            return

        dialog = GameTypeDialog(self, game_type)
        if dialog.exec():
            try:
                updated = self.facade.update_game_type(
                    type_id,
                    name=dialog.name_edit.text(),
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked(),
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Game type '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update game type:\n{str(e)}"
                )

    def _delete_type(self):
        type_id = self._get_selected_type_id()
        if not type_id:
            return

        game_type = self.facade.get_game_type(type_id)
        if not game_type:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete game type '{game_type.name}'?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.facade.delete_game_type(type_id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Game type '{game_type.name}' deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete game type:\n{str(e)}"
                )

    def _view_type(self):
        type_id = self._get_selected_type_id()
        if not type_id:
            return
        game_type = self.facade.get_game_type(type_id)
        if not game_type:
            return
        def handle_edit():
            dialog.close()
            self._edit_type()

        def handle_delete():
            dialog.close()
            self._delete_type()

        dialog = GameTypeDialog(self, game_type, read_only=True, on_edit=handle_edit, on_delete=handle_delete)
        dialog.exec()


class GameTypeDialog(QtWidgets.QDialog):
    """Dialog for adding/editing game types"""

    def __init__(self, parent=None, game_type: GameType = None, read_only: bool = False, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.game_type = game_type
        self.read_only = read_only
        self._on_edit = on_edit
        self._on_delete = on_delete
        if self.read_only:
            self.setWindowTitle("View Game Type")
        else:
            self.setWindowTitle("Edit Game Type" if game_type else "Add Game Type")
        self.resize(480, 300)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)

        self.name_edit = QtWidgets.QLineEdit()
        if game_type:
            self.name_edit.setText(game_type.name)
        name_label = QtWidgets.QLabel("Name:")
        name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(self.name_edit, 0, 1)

        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(game_type.is_active if game_type else True)
        active_label = QtWidgets.QLabel("Active")
        active_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(active_label, 0, 2)
        layout.addWidget(self.active_check, 0, 3)

        self.notes_edit = QtWidgets.QTextEdit()
        if game_type and game_type.notes:
            self.notes_edit.setPlainText(game_type.notes)
        notes_label = QtWidgets.QLabel("Notes:")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        layout.addWidget(notes_label, 1, 0, QtCore.Qt.AlignTop)
        layout.addWidget(self.notes_edit, 1, 1, 1, 3)

        button_layout = QtWidgets.QHBoxLayout()
        if self.read_only:
            if self._on_delete:
                delete_btn = QtWidgets.QPushButton("Delete")
                delete_btn.clicked.connect(self._on_delete)
                button_layout.addWidget(delete_btn)
            button_layout.addStretch(1)
            if self._on_edit:
                edit_btn = QtWidgets.QPushButton("Edit")
                edit_btn.clicked.connect(self._on_edit)
                button_layout.addWidget(edit_btn)
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(self.accept)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout, 2, 0, 1, 4)
        else:
            save_btn = QtWidgets.QPushButton("Save")
            cancel_btn = QtWidgets.QPushButton("Cancel")
            save_btn.setObjectName("PrimaryButton")
            save_btn.clicked.connect(self.accept)
            cancel_btn.clicked.connect(self.reject)
            button_layout.addStretch(1)
            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(save_btn)
            layout.addLayout(button_layout, 2, 0, 1, 4)

        if self.read_only:
            for widget in (self.name_edit, self.active_check, self.notes_edit):
                widget.setEnabled(False)
            if not (game_type and game_type.notes):
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
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Name is required")
        else:
            self._set_valid(self.name_edit)

    def accept(self):
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Name is required")
            return
        super().accept()
