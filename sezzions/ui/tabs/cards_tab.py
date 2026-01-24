"""
Cards tab - Manage payment cards
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.card import Card
from ui.table_header_filters import TableHeaderFilter


class CardsTab(QtWidgets.QWidget):
    """Tab for managing payment cards"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.cards = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Cards")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search cards...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_cards)
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
        
        add_btn = QtWidgets.QPushButton("➕ Add Card")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_card)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_card)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)
        
        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_card)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_card)
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
        self.table.setHorizontalHeaderLabels(["Name", "User", "Last Four", "Cashback %", "Status", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_card)
        layout.addWidget(self.table)
        self.table_filter = TableHeaderFilter(self.table, refresh_callback=self.refresh_data)
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Reload cards from database"""
        self.cards = self.facade.get_all_cards()
        self._populate_table()
    
    def _populate_table(self):
        """Populate table with cards"""
        search_text = self.search_edit.text().lower()
        
        # Filter cards
        if search_text:
            filtered = [c for c in self.cards 
                       if search_text in c.name.lower() 
                       or (hasattr(c, 'user_name') and c.user_name and search_text in c.user_name.lower())
                       or (c.last_four and search_text in c.last_four)
                       or (c.notes and search_text in c.notes.lower())
                       or (str(c.cashback_rate) and search_text in f"{float(c.cashback_rate):.2f}")]
        else:
            filtered = self.cards
        
        self.table.setRowCount(len(filtered))
        
        for row, card in enumerate(filtered):
            # Name
            name_item = QtWidgets.QTableWidgetItem(card.name)
            name_item.setData(QtCore.Qt.UserRole, card.id)
            self.table.setItem(row, 0, name_item)
            
            # User
            user = getattr(card, 'user_name', None) or "—"
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(user))
            
            # Last Four
            last_four = card.last_four or "—"
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(last_four))

            # Cashback %
            cashback_str = f"{float(card.cashback_rate):.2f}%"
            cashback_item = QtWidgets.QTableWidgetItem(cashback_str)
            cashback_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 3, cashback_item)
            
            # Status
            status = "Active" if card.is_active else "Inactive"
            status_item = QtWidgets.QTableWidgetItem(status)
            if not card.is_active:
                status_item.setForeground(QtGui.QColor("#999"))
            self.table.setItem(row, 4, status_item)
            
            # Notes
            notes = (card.notes or "")[:100]
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(notes))
        
        # Column sizing handled by header resize mode
        self.table_filter.apply_filters()
    
    def _filter_cards(self):
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
    
    def _get_selected_card_id(self):
        """Get ID of selected card"""
        ids = self._get_selected_card_ids()
        return ids[0] if ids else None

    def _get_selected_card_ids(self):
        ids = []
        for row in self.table.selectionModel().selectedRows():
            item = self.table.item(row.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids
    
    def _add_card(self):
        """Show dialog to add new card"""
        dialog = CardDialog(self.facade, self)
        if dialog.exec():
            try:
                card = self.facade.create_card(
                    user_id=dialog.user_id,
                    name=dialog.name_edit.text(),
                    last_four=dialog.last_four_edit.text() or None,
                    cashback_rate=dialog.get_cashback_rate(),
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Card '{card.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create card:\n{str(e)}"
                )
    
    def _edit_card(self):
        """Show dialog to edit selected card"""
        card_id = self._get_selected_card_id()
        if not card_id:
            return
        
        card = self.facade.get_card(card_id)
        if not card:
            return
        
        dialog = CardDialog(self.facade, self, card)
        if dialog.exec():
            try:
                updated = self.facade.update_card(
                    card_id,
                    user_id=dialog.user_id,
                    name=dialog.name_edit.text(),
                    last_four=dialog.last_four_edit.text() or None,
                    cashback_rate=dialog.get_cashback_rate(),
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked()
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Card '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update card:\n{str(e)}"
                )
    
    def _delete_card(self):
        """Delete selected card"""
        card_ids = self._get_selected_card_ids()
        if not card_ids:
            return

        cards = []
        for card_id in card_ids:
            card = self.facade.get_card(card_id)
            if card:
                cards.append(card)

        if not cards:
            return

        if len(cards) == 1:
            prompt = f"Delete card '{cards[0].name}'?\n\nThis cannot be undone."
        else:
            prompt = f"Delete {len(cards)} cards?\n\nThis cannot be undone."

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for card in cards:
                    self.facade.delete_card(card.id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Card(s) deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete card(s):\n{str(e)}"
                )

    def _export_csv(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Cards",
            f"cards_{date.today().isoformat()}.csv",
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
                    f"Exported cards to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )

    def _view_card(self):
        card_id = self._get_selected_card_id()
        if not card_id:
            return
        card = self.facade.get_card(card_id)
        if not card:
            return
        def handle_edit():
            dialog.close()
            self._edit_card()

        def handle_delete():
            dialog.close()
            self._delete_card()

        dialog = CardDialog(
            self.facade,
            self,
            card,
            read_only=True,
            on_edit=handle_edit,
            on_delete=handle_delete,
        )
        dialog.exec()


class CardDialog(QtWidgets.QDialog):
    """Dialog for adding/editing cards"""
    
    def __init__(self, facade: AppFacade, parent=None, card: Card = None, read_only: bool = False, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.facade = facade
        self.card = card
        self.read_only = read_only
        self.user_id = card.user_id if card else None
        self._on_edit = on_edit
        self._on_delete = on_delete
        
        if self.read_only:
            self.setWindowTitle("View Card")
        else:
            self.setWindowTitle("Edit Card" if card else "Add Card")
        self.resize(500, 400)
        
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        # Card Name + Active
        self.name_edit = QtWidgets.QLineEdit()
        if card:
            self.name_edit.setText(card.name)
        name_label = QtWidgets.QLabel("Card Name:")
        name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(card.is_active if card else True)
        active_label = QtWidgets.QLabel("Active")
        active_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        name_row = QtWidgets.QHBoxLayout()
        name_row.setSpacing(12)
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(active_label)
        name_row.addWidget(self.active_check)

        layout.addWidget(name_label, 0, 0)
        layout.addLayout(name_row, 0, 1, 1, 3)

        # User
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        user_label = QtWidgets.QLabel("User:")
        user_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(user_label, 1, 0)
        layout.addWidget(self.user_combo, 1, 1, 1, 3)

        # Load users
        users = facade.get_all_users(active_only=True)
        self.user_map = {}
        for user in users:
            self.user_combo.addItem(user.name, user.id)
            self.user_map[user.id] = user.name

        # Set current user if editing
        if card:
            index = self.user_combo.findData(card.user_id)
            if index >= 0:
                self.user_combo.setCurrentIndex(index)
        else:
            self.user_combo.setCurrentIndex(-1)
            if self.user_combo.isEditable():
                self.user_combo.setEditText("")
                self.user_combo.lineEdit().setPlaceholderText("Select a user")

        self.user_combo.currentIndexChanged.connect(self._on_user_changed)

        # Last Four
        self.last_four_edit = QtWidgets.QLineEdit()
        self.last_four_edit.setMaxLength(4)
        if card and card.last_four:
            self.last_four_edit.setText(card.last_four)
        last_four_label = QtWidgets.QLabel("Last Four:")
        last_four_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(last_four_label, 2, 0)
        layout.addWidget(self.last_four_edit, 2, 1)

        # Cashback Rate
        self.cashback_rate_edit = QtWidgets.QLineEdit()
        self.cashback_rate_edit.setPlaceholderText("0.00")
        if card:
            self.cashback_rate_edit.setText(f"{float(card.cashback_rate):.2f}")
        cashback_label = QtWidgets.QLabel("Cashback %:")
        cashback_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(cashback_label, 2, 2)
        layout.addWidget(self.cashback_rate_edit, 2, 3)

        # Notes
        self.notes_edit = QtWidgets.QTextEdit()
        if card and card.notes:
            self.notes_edit.setPlainText(card.notes)
        notes_label = QtWidgets.QLabel("Notes:")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        layout.addWidget(notes_label, 3, 0)
        layout.addWidget(self.notes_edit, 3, 1, 1, 3)
        
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
        
        # Set initial user_id
        self._on_user_changed()

        if self.read_only:
            for widget in (self.user_combo, self.name_edit, self.last_four_edit, self.cashback_rate_edit, self.active_check, self.notes_edit):
                widget.setEnabled(False)
            if not (card and card.notes):
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.notes_edit.setPlaceholderText("-")
                self.notes_edit.setFixedHeight(self.notes_edit.fontMetrics().lineSpacing() + 12)
            else:
                notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        self.name_edit.textChanged.connect(self._validate_inline)
        self.last_four_edit.textChanged.connect(self._validate_inline)
        self.cashback_rate_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self._validate_inline()

        completer = QtWidgets.QCompleter(self.user_combo.model())
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
        self.user_combo.setCompleter(completer)
        if self.user_combo.lineEdit() is not None:
            self.user_combo.lineEdit().setCompleter(completer)
            app = QtWidgets.QApplication.instance()
            if app is not None and hasattr(app, "_completer_filter"):
                self.user_combo.lineEdit().installEventFilter(app._completer_filter)
    
    def _on_user_changed(self):
        """Update user_id when selection changes"""
        self.user_id = self.user_combo.currentData()
        if self.user_id is None:
            text = self.user_combo.currentText().strip().lower()
            for uid, name in self.user_map.items():
                if name.lower() == text:
                    self.user_id = uid
                    break

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
        if not self.user_combo.currentText().strip():
            self._set_invalid(self.user_combo, "User is required")
        else:
            self._set_valid(self.user_combo)
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Card name is required")
        else:
            self._set_valid(self.name_edit)
        last_four = self.last_four_edit.text().strip()
        if last_four and not last_four.isdigit():
            self._set_invalid(self.last_four_edit, "Last four must be numeric")
        else:
            self._set_valid(self.last_four_edit)
        rate_text = self.cashback_rate_edit.text().strip()
        if rate_text:
            try:
                rate_val = float(rate_text)
                if rate_val < 0 or rate_val > 100:
                    raise ValueError("out of range")
                self._set_valid(self.cashback_rate_edit)
            except Exception:
                self._set_invalid(self.cashback_rate_edit, "Cashback % must be 0-100")
        else:
            self._set_valid(self.cashback_rate_edit)
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        if not self.user_id:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "User is required"
            )
            return
        
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Card name is required"
            )
            return
        
        # Validate last four if provided
        last_four = self.last_four_edit.text().strip()
        if last_four and not last_four.isdigit():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Last four must be numeric"
            )
            return

        rate_text = self.cashback_rate_edit.text().strip()
        if rate_text:
            try:
                rate_val = float(rate_text)
                if rate_val < 0 or rate_val > 100:
                    raise ValueError("out of range")
            except Exception:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Cashback % must be between 0 and 100"
                )
                return
        
        self.accept()

    def get_cashback_rate(self) -> float:
        text = self.cashback_rate_edit.text().strip()
        return float(text) if text else 0.0
