"""
Cards tab - Manage payment cards
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.card import Card
from ui.table_header_filters import TableHeaderFilter
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar


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
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_card)
        
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
    
    def _get_selected_card_id(self):
        """Get ID of selected card"""
        ids = self._get_selected_card_ids()
        return ids[0] if ids else None

    def _get_selected_card_ids(self):
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
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
                    self.window() or self, "Success", f"Card '{card.name}' created"
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

    def _copy_selection(self):
        """Copy selected cells to clipboard as TSV"""
        SpreadsheetUXController.copy_to_clipboard(self.table)

    def _copy_with_headers(self):
        """Copy selected cells to clipboard with column headers"""
        SpreadsheetUXController.copy_to_clipboard(self.table, include_headers=True)

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
        
        dialog = CardViewDialog(
            card,
            parent=self,
            on_edit=self._edit_card,
            on_delete=self._delete_card,
        )
        dialog.exec()
        self.refresh_data()


class CardDialog(QtWidgets.QDialog):
    """Dialog for adding/editing cards"""
    
    def __init__(self, facade: AppFacade, parent=None, card: Card = None):
        super().__init__(parent)
        self.facade = facade
        self.card = card
        self.user_id = card.user_id if card else None
        self.setWindowTitle("Edit Card" if card else "Add Card")
        self.setMinimumSize(400, 340)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Section header
        header = QtWidgets.QLabel("💳 Card Details")
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
        self.active_check.setChecked(card.is_active if card else True)
        main_grid.addWidget(active_label, 0, 0)
        main_grid.addWidget(self.active_check, 0, 1)
        
        # User (required) - increased from 200px to 250px
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        user_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.user_combo.setFixedWidth(250)
        
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
                if self.user_combo.lineEdit() is not None:
                    self.user_combo.lineEdit().setPlaceholderText("Required")
        
        self.user_combo.currentIndexChanged.connect(self._on_user_changed)
        main_grid.addWidget(user_label, 1, 0)
        main_grid.addWidget(self.user_combo, 1, 1)
        
        # Card Name (required) - increased from 200px to 250px
        name_label = QtWidgets.QLabel("Card Name:")
        name_label.setObjectName("FieldLabel")
        name_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        self.name_edit.setFixedWidth(250)
        if card:
            self.name_edit.setText(card.name)
        main_grid.addWidget(name_label, 2, 0)
        main_grid.addWidget(self.name_edit, 2, 1)
        
        # Cashback Rate (optional) - increased to 160px to fit placeholder
        cashback_label = QtWidgets.QLabel("Cashback %:")
        cashback_label.setObjectName("FieldLabel")
        cashback_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.cashback_rate_edit = QtWidgets.QLineEdit()
        self.cashback_rate_edit.setPlaceholderText("Optional (0.00)")
        self.cashback_rate_edit.setFixedWidth(160)
        if card:
            self.cashback_rate_edit.setText(f"{float(card.cashback_rate):.2f}")
        main_grid.addWidget(cashback_label, 3, 0)
        main_grid.addWidget(self.cashback_rate_edit, 3, 1)
        
        # Last Four (optional)
        last_four_label = QtWidgets.QLabel("Last 4:")
        last_four_label.setObjectName("FieldLabel")
        last_four_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.last_four_edit = QtWidgets.QLineEdit()
        self.last_four_edit.setMaxLength(4)
        self.last_four_edit.setPlaceholderText("Optional")
        self.last_four_edit.setFixedWidth(80)
        if card and card.last_four:
            self.last_four_edit.setText(card.last_four)
        main_grid.addWidget(last_four_label, 4, 0)
        main_grid.addWidget(self.last_four_edit, 4, 1)
        
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
        if card and card.notes:
            self.notes_edit.setPlainText(card.notes)
        notes_layout.addWidget(self.notes_edit)
        self.notes_section.setVisible(False)
        main_layout.addWidget(self.notes_section)
        
        # Expand notes if editing and notes exist
        if card and card.notes:
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
        
        # Set initial user_id
        self._on_user_changed()
        
        # Validation
        self.name_edit.textChanged.connect(self._validate_inline)
        self.last_four_edit.textChanged.connect(self._validate_inline)
        self.cashback_rate_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self._validate_inline()
        
        # User combo autocomplete
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
        
        # Tab order
        self.setTabOrder(self.user_combo, self.active_check)
        self.setTabOrder(self.active_check, self.name_edit)
        self.setTabOrder(self.name_edit, self.last_four_edit)
        self.setTabOrder(self.last_four_edit, self.cashback_rate_edit)
        self.setTabOrder(self.cashback_rate_edit, self.notes_edit)
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
    
    def _validate_inline(self) -> bool:
        """Validate all fields and return True if valid"""
        valid = True
        
        if not self.user_combo.currentText().strip():
            self._set_invalid(self.user_combo, "User is required.")
            valid = False
        else:
            self._set_valid(self.user_combo)
        
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Card name is required.")
            valid = False
        else:
            self._set_valid(self.name_edit)
        
        last_four = self.last_four_edit.text().strip()
        if last_four and not last_four.isdigit():
            self._set_invalid(self.last_four_edit, "Last four must be numeric")
            valid = False
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
                valid = False
        else:
            self._set_valid(self.cashback_rate_edit)
        
        self.save_btn.setEnabled(valid)
        return valid
    
    def _validate_and_accept(self):
        """Final validation before accepting"""
        if not self._validate_inline():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please correct the highlighted fields."
            )
            return
        
        if not self.user_id:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please select a valid user."
            )
            return
        
        self.accept()
    
    def get_cashback_rate(self) -> float:
        text = self.cashback_rate_edit.text().strip()
        return float(text) if text else 0.0


class CardViewDialog(QtWidgets.QDialog):
    """Dialog for viewing card details"""
    
    def __init__(self, card: Card, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.card = card
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Card")
        self.setMinimumSize(600, 360)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # Card details section header
        details_header = QtWidgets.QLabel("💳 Card Details")
        details_header.setObjectName("SectionHeader")
        main_layout.addWidget(details_header)
        
        # Card details section
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
        
        user_lbl = QtWidgets.QLabel("User:")
        user_lbl.setStyleSheet("color: palette(mid);")
        user_name = getattr(card, 'user_name', None)
        user_display = user_name if user_name else "Unknown User" if card.user_id else "—"
        user_val = self._make_selectable_label(user_display)
        left_grid.addWidget(user_lbl, 0, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(user_val, 0, 1)
        
        name_lbl = QtWidgets.QLabel("Card Name:")
        name_lbl.setStyleSheet("color: palette(mid);")
        name_val = self._make_selectable_label(card.name)
        left_grid.addWidget(name_lbl, 1, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(name_val, 1, 1)
        
        last_four_lbl = QtWidgets.QLabel("Last Four:")
        last_four_lbl.setStyleSheet("color: palette(mid);")
        last_four_val = self._make_selectable_label(card.last_four or "—")
        left_grid.addWidget(last_four_lbl, 2, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(last_four_val, 2, 1)
        
        columns.addLayout(left_grid, 1)
        
        # Right column
        right_grid = QtWidgets.QGridLayout()
        right_grid.setHorizontalSpacing(12)
        right_grid.setVerticalSpacing(6)
        right_grid.setColumnStretch(1, 1)
        
        status_lbl = QtWidgets.QLabel("Status:")
        status_lbl.setStyleSheet("color: palette(mid);")
        status_val = self._make_selectable_label("Active" if card.is_active else "Inactive")
        right_grid.addWidget(status_lbl, 0, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(status_val, 0, 1)
        
        cashback_lbl = QtWidgets.QLabel("Cashback %:")
        cashback_lbl.setStyleSheet("color: palette(mid);")
        cashback_val = self._make_selectable_label(f"{float(card.cashback_rate):.2f}" if card.cashback_rate else "0.00")
        right_grid.addWidget(cashback_lbl, 1, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(cashback_val, 1, 1)
        
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
        
        if card.notes:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(card.notes)
            notes_display.setMaximumHeight(80)
            notes_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            notes_layout.addWidget(notes_display)
        else:
            notes_empty = QtWidgets.QLabel("—")
            notes_empty.setStyleSheet("color: palette(mid); font-style: italic;")
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
