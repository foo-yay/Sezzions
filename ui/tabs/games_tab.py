"""
Games tab - Manage individual games
"""
from datetime import date
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from models.game import Game
from ui.table_header_filters import TableHeaderFilter
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar


class GamesTab(QtWidgets.QWidget):
    """Tab for managing games"""

    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.games = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Games")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search games...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_games)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)

        layout.addLayout(header_layout)

        toolbar = QtWidgets.QHBoxLayout()

        add_btn = QtWidgets.QPushButton("➕ Add Game")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_game)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_game)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)

        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_game)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_game)
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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Game Type", "Expected RTP", "Actual RTP", "Status", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_game)
        
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

    def refresh_data(self):
        self.games = self.facade.list_all_games()
        self._populate_table()

    def _populate_table(self):
        search_text = self.search_edit.text().lower()
        game_types = {t.id: t.name for t in self.facade.get_all_game_types()}

        if search_text:
            filtered = [g for g in self.games
                        if search_text in g.name.lower()
                        or (g.notes and search_text in g.notes.lower())
                        or (game_types.get(g.game_type_id, "").lower().find(search_text) >= 0)
                        or (g.rtp is not None and search_text in f"{g.rtp:.2f}" )
                        or (getattr(g, "actual_rtp", None) is not None and search_text in f"{float(getattr(g, 'actual_rtp')):.2f}")]
        else:
            filtered = self.games

        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(filtered))
            for row, game in enumerate(filtered):
                name_item = QtWidgets.QTableWidgetItem(game.name)
                name_item.setData(QtCore.Qt.UserRole, game.id)
                self.table.setItem(row, 0, name_item)

                game_type_name = game_types.get(game.game_type_id, "—")
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(game_type_name))

                rtp_display = f"{game.rtp:.2f}%" if game.rtp is not None else "—"
                rtp_item = QtWidgets.QTableWidgetItem(rtp_display)
                rtp_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 2, rtp_item)

                actual_rtp = getattr(game, "actual_rtp", None)
                actual_display = f"{float(actual_rtp):.2f}%" if actual_rtp is not None else "—"
                actual_item = QtWidgets.QTableWidgetItem(actual_display)
                actual_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 3, actual_item)

                status = "Active" if game.is_active else "Inactive"
                status_item = QtWidgets.QTableWidgetItem(status)
                if not game.is_active:
                    status_item.setForeground(QtGui.QColor("#999"))
                self.table.setItem(row, 4, status_item)

                notes = (game.notes or "")[:100]
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

        self.table_filter.apply_filters()

        # Column sizing handled by header resize mode

    def _filter_games(self):
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

    def _get_selected_game_id(self):
        ids = self._get_selected_game_ids()
        return ids[0] if ids else None

    def _get_selected_game_ids(self):
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def _add_game(self):
        dialog = GameDialog(self, self.facade)
        if dialog.exec():
            try:
                created = self.facade.create_game(
                    name=dialog.name_edit.text(),
                    game_type_id=dialog.type_combo.currentData(),
                    rtp=dialog.get_rtp_value(),
                    notes=dialog.notes_edit.toPlainText() or None,
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self.window() or self, "Success", f"Game '{created.name}' created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create game:\n{str(e)}"
                )

    def _edit_game(self):
        game_id = self._get_selected_game_id()
        if not game_id:
            return

        game = self.facade.get_game(game_id)
        if not game:
            return

        dialog = GameDialog(self, self.facade, game)
        if dialog.exec():
            try:
                updated = self.facade.update_game(
                    game_id,
                    name=dialog.name_edit.text(),
                    game_type_id=dialog.type_combo.currentData(),
                    rtp=dialog.get_rtp_value(),
                    notes=dialog.notes_edit.toPlainText() or None,
                    is_active=dialog.active_check.isChecked(),
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Game '{updated.name}' updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update game:\n{str(e)}"
                )

    def _delete_game(self):
        game_ids = self._get_selected_game_ids()
        if not game_ids:
            return

        games = []
        for game_id in game_ids:
            game = self.facade.get_game(game_id)
            if game:
                games.append(game)

        if not games:
            return

        if len(games) == 1:
            prompt = f"Delete game '{games[0].name}'?\n\nThis cannot be undone."
        else:
            prompt = f"Delete {len(games)} games?\n\nThis cannot be undone."

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for game in games:
                    self.facade.delete_game(game.id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Game(s) deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete game(s):\n{str(e)}"
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
            "Export Games",
            f"games_{date.today().isoformat()}.csv",
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
                    f"Exported games to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )

    def _view_game(self):
        game_id = self._get_selected_game_id()
        if not game_id:
            return
        game = self.facade.get_game(game_id)
        if not game:
            return
        
        dialog = GameViewDialog(
            game,
            parent=self,
            on_edit=self._edit_game,
            on_delete=self._delete_game,
        )
        dialog.exec()
        self.refresh_data()


class GameDialog(QtWidgets.QDialog):
    """Dialog for adding/editing games"""

    def __init__(self, parent, facade: AppFacade, game: Game = None):
        super().__init__(parent)
        self.facade = facade
        self.game = game
        self.setWindowTitle("Edit Game" if game else "Add Game")
        self.setMinimumSize(400, 380)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Section header
        header = QtWidgets.QLabel("🎮 Game Details")
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
        self.active_check.setChecked(game.is_active if game else True)
        main_grid.addWidget(active_label, 0, 0)
        main_grid.addWidget(self.active_check, 0, 1)
        
        # Name (required)
        name_label = QtWidgets.QLabel("Name:")
        name_label.setObjectName("FieldLabel")
        name_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        if game:
            self.name_edit.setText(game.name)
        main_grid.addWidget(name_label, 1, 0)
        main_grid.addWidget(self.name_edit, 1, 1)
        
        # Game Type (required)
        game_type_label = QtWidgets.QLabel("Game Type:")
        game_type_label.setObjectName("FieldLabel")
        game_type_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setEditable(True)
        self.type_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        types = self.facade.get_all_game_types()
        for game_type in types:
            self.type_combo.addItem(game_type.name, game_type.id)
        
        if game:
            idx = self.type_combo.findData(game.game_type_id)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        else:
            self.type_combo.setCurrentIndex(-1)
            self.type_combo.setEditText("")
            if self.type_combo.lineEdit() is not None:
                self.type_combo.lineEdit().setPlaceholderText("Required")
        
        main_grid.addWidget(game_type_label, 2, 0)
        main_grid.addWidget(self.type_combo, 2, 1)
        
        # RTP row - RTP input and Actual RTP display on same line
        rtp_label = QtWidgets.QLabel("RTP (%):")
        rtp_label.setObjectName("FieldLabel")
        rtp_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.rtp_edit = QtWidgets.QLineEdit()
        self.rtp_edit.setPlaceholderText("Optional (0-100)")
        self.rtp_edit.setFixedWidth(140)
        if game and game.rtp is not None:
            self.rtp_edit.setText(str(game.rtp))
        main_grid.addWidget(rtp_label, 3, 0)
        
        # Horizontal layout for RTP input and Actual RTP display
        rtp_row = QtWidgets.QHBoxLayout()
        rtp_row.addWidget(self.rtp_edit)
        rtp_row.addSpacing(30)
        
        actual_rtp_label = QtWidgets.QLabel("Actual RTP:")
        actual_rtp_label.setObjectName("FieldLabel")
        rtp_row.addWidget(actual_rtp_label)
        rtp_row.addSpacing(8)
        
        actual_rtp_val = f"{float(getattr(game, 'actual_rtp', 0) or 0):.2f}%" if game and getattr(game, "actual_rtp", None) is not None else "—"
        self.actual_rtp_value = QtWidgets.QLabel(actual_rtp_val)
        self.actual_rtp_value.setObjectName("MutedLabel")
        actual_rtp_font = self.actual_rtp_value.font()
        actual_rtp_font.setItalic(True)
        self.actual_rtp_value.setFont(actual_rtp_font)
        rtp_row.addWidget(self.actual_rtp_value)
        rtp_row.addStretch(1)
        
        main_grid.addLayout(rtp_row, 3, 1)
        
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
        if game and game.notes:
            self.notes_edit.setPlainText(game.notes)
        notes_layout.addWidget(self.notes_edit)
        self.notes_section.setVisible(False)
        main_layout.addWidget(self.notes_section)
        
        # Expand notes if editing and notes exist
        if game and game.notes:
            self._toggle_notes()
        
        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        
        # Add Recalculate RTP button if editing existing game
        if game:
            recalc_btn = QtWidgets.QPushButton("🔄 Recalculate RTP")
            recalc_btn.setToolTip("Rebuild Actual RTP from all closed game sessions")
            recalc_btn.clicked.connect(self._recalculate_rtp)
            btn_row.addWidget(recalc_btn)
        
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
        self.type_combo.currentTextChanged.connect(self._validate_inline)
        self.rtp_edit.textChanged.connect(self._validate_inline)
        self._validate_inline()
        
        # Autocomplete
        completer = QtWidgets.QCompleter(self.type_combo.model())
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
        self.type_combo.setCompleter(completer)
        if self.type_combo.lineEdit() is not None:
            self.type_combo.lineEdit().setCompleter(completer)
            app = QtWidgets.QApplication.instance()
            if app is not None and hasattr(app, "_completer_filter"):
                self.type_combo.lineEdit().installEventFilter(app._completer_filter)
        
        # Tab order
        self.setTabOrder(self.name_edit, self.active_check)
        self.setTabOrder(self.active_check, self.type_combo)
        self.setTabOrder(self.type_combo, self.rtp_edit)
        self.setTabOrder(self.rtp_edit, self.notes_edit)
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
        
        if not self.type_combo.currentText().strip():
            self._set_invalid(self.type_combo, "Game Type is required.")
            valid = False
        else:
            self._set_valid(self.type_combo)
        
        rtp_text = self.rtp_edit.text().strip()
        if rtp_text:
            try:
                rtp = float(rtp_text)
                if rtp < 0 or rtp > 100:
                    raise ValueError("Out of range")
                self._set_valid(self.rtp_edit)
            except Exception:
                self._set_invalid(self.rtp_edit, "RTP must be between 0 and 100.")
                valid = False
        else:
            self._set_valid(self.rtp_edit)
        
        self.save_btn.setEnabled(valid)
        return valid
    
    def _recalculate_rtp(self):
        """Recalculate actual RTP for this game from session data"""
        if not self.game or not self.game.id:
            return
        
        try:
            # Recalculate RTP using facade method
            self.facade.recalculate_game_rtp(self.game.id)
            
            # Refresh the game data to get updated RTP
            updated_game = self.facade.get_game(self.game.id)
            if updated_game:
                self.game = updated_game
                # Update the display
                actual_rtp_val = f"{float(getattr(updated_game, 'actual_rtp', 0) or 0):.2f}%" if getattr(updated_game, "actual_rtp", None) is not None else "—"
                self.actual_rtp_value.setText(actual_rtp_val)
            
            QtWidgets.QMessageBox.information(
                self, "Success", "Actual RTP has been recalculated from session data."
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to recalculate RTP:\n{str(e)}"
            )
    
    def _validate_and_accept(self):
        """Final validation before accepting"""
        if not self._validate_inline():
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please correct the highlighted fields."
            )
            return
        
        if self.type_combo.currentIndex() < 0:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please select a valid Game Type."
            )
            return
        
        self.accept()
    
    def get_rtp_value(self):
        """Get RTP as float or None"""
        text = self.rtp_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None


class GameViewDialog(QtWidgets.QDialog):
    """Dialog for viewing game details"""
    
    def __init__(self, game: Game, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.game = game
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Game")
        self.setMinimumSize(620, 360)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # Game details section header
        details_header = QtWidgets.QLabel("🎮 Game Details")
        details_header.setObjectName("SectionHeader")
        main_layout.addWidget(details_header)
        
        # Game details section
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
        name_val = self._make_selectable_label(game.name)
        left_grid.addWidget(name_lbl, 0, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(name_val, 0, 1)
        
        game_type_lbl = QtWidgets.QLabel("Game Type:")
        game_type_lbl.setObjectName("MutedLabel")
        game_type_name = getattr(game, 'game_type_name', None)
        game_type_display = game_type_name if game_type_name else "Unknown Type" if game.game_type_id else "—"
        game_type_val = self._make_selectable_label(game_type_display)
        left_grid.addWidget(game_type_lbl, 1, 0, QtCore.Qt.AlignRight)
        left_grid.addWidget(game_type_val, 1, 1)
        
        columns.addLayout(left_grid, 1)
        
        # Right column
        right_grid = QtWidgets.QGridLayout()
        right_grid.setHorizontalSpacing(12)
        right_grid.setVerticalSpacing(6)
        right_grid.setColumnStretch(1, 1)
        
        rtp_lbl = QtWidgets.QLabel("RTP (%):")
        rtp_lbl.setObjectName("MutedLabel")
        rtp_val = self._make_selectable_label(str(game.rtp) if game.rtp is not None else "—")
        right_grid.addWidget(rtp_lbl, 0, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(rtp_val, 0, 1)
        
        actual_rtp_lbl = QtWidgets.QLabel("Actual RTP:")
        actual_rtp_lbl.setObjectName("MutedLabel")
        actual_rtp_val_text = f"{float(getattr(game, 'actual_rtp', 0) or 0):.2f}%" if getattr(game, "actual_rtp", None) is not None else "—"
        actual_rtp_val = self._make_selectable_label(actual_rtp_val_text)
        right_grid.addWidget(actual_rtp_lbl, 1, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(actual_rtp_val, 1, 1)
        
        status_lbl = QtWidgets.QLabel("Status:")
        status_lbl.setObjectName("MutedLabel")
        status_val = self._make_selectable_label("Active" if game.is_active else "Inactive")
        right_grid.addWidget(status_lbl, 2, 0, QtCore.Qt.AlignRight)
        right_grid.addWidget(status_val, 2, 1)
        
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
        
        if game.notes:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(game.notes)
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
    
    def _recalculate_rtp(self):
        """Recalculate actual RTP for this game from session data"""
        try:
            # Get parent's facade
            parent_tab = self.parent()
            if not parent_tab or not hasattr(parent_tab, 'facade'):
                QtWidgets.QMessageBox.warning(
                    self, "Error", "Unable to access application facade"
                )
                return
            
            # Recalculate RTP using facade method
            parent_tab.facade.recalculate_game_rtp(self.game.id)
            
            # Show success and close to refresh
            result = QtWidgets.QMessageBox.information(
                self, "RTP Recalculated",
                f"Actual RTP successfully recalculated for '{self.game.name}'.\n\n"
                "The dialog will close to refresh data.",
                QtWidgets.QMessageBox.Ok
            )
            
            # Close dialog and trigger parent refresh
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Failed to recalculate RTP:\n{str(e)}"
            )
    
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
