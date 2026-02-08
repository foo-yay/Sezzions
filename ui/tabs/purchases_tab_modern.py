"""
Modern Purchase Dialog - Alternative layout exploration
Based on current working design with incremental improvements
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from app_facade import AppFacade
from models.purchase import Purchase


class ModernPurchaseDialog(QtWidgets.QDialog):
    """Modern purchase dialog with streamlined layout"""
    
    def __init__(self, facade: AppFacade, parent=None, purchase: Purchase = None):
        super().__init__(parent)
        self.facade = facade
        self.purchase = purchase
        self.user_id = purchase.user_id if purchase else None
        self.site_id = purchase.site_id if purchase else None
        self.card_id = purchase.card_id if purchase else None
        
        self.setWindowTitle("Edit Purchase" if purchase else "Add Purchase")
        self.setMinimumWidth(650)
        self.setMinimumHeight(700)  # Ensure dialog is tall enough for all sections
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Add subtle section separators using frames
        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)  # Increased for shadow space
        form.setContentsMargins(10, 10, 10, 10)  # Add margins for shadow rendering

        # Initialize widgets
        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM:SS")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.lineEdit().setPlaceholderText("Choose...")
        users = facade.get_all_users(active_only=True)
        self._user_lookup = {u.name.lower(): u.id for u in users}
        self.user_combo.addItems([u.name for u in users])

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.lineEdit().setPlaceholderText("Choose...")
        sites = facade.get_all_sites(active_only=True)
        self._site_lookup = {s.name.lower(): s.id for s in sites}
        self.site_combo.addItems([s.name for s in sites])

        self.card_combo = QtWidgets.QComboBox()
        self.card_combo.setEditable(True)
        self.card_combo.lineEdit().setPlaceholderText("Choose user first...")

        self.amount_edit = QtWidgets.QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        
        self.sc_edit = QtWidgets.QLineEdit()
        self.sc_edit.setPlaceholderText("0.00")
        
        self.start_sc_edit = QtWidgets.QLineEdit()
        self.start_sc_edit.setPlaceholderText("0.00")
        
        self.balance_check_label = QtWidgets.QLabel("—")
        self.balance_check_label.setObjectName("HelperText")
        self.balance_check_label.setProperty("status", "neutral")
        self.balance_check_label.setWordWrap(True)

        self.cashback_rate_label = QtWidgets.QLabel("Cashback: —")
        self.cashback_rate_label.setObjectName("HelperText")
        self.cashback_edit = QtWidgets.QLineEdit()
        self.cashback_edit.setPlaceholderText("Auto-calculated")
        self.cashback_edit.setVisible(False)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Section 1: When (Date/Time) with background
        section1_header = self._create_section_header("📅  When")
        form.addWidget(section1_header, 0, 0, 1, 7)
        
        when_section = QtWidgets.QWidget()
        when_section.setObjectName("SectionBackground")
        when_section.setAutoFillBackground(True)
        when_layout = QtWidgets.QGridLayout(when_section)
        when_layout.setContentsMargins(12, 12, 12, 12)
        when_layout.setHorizontalSpacing(12)
        when_layout.setVerticalSpacing(5)
        
        # Row 0: Date label | Time label
        date_label = QtWidgets.QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        when_layout.addWidget(date_label, 0, 0, 1, 4)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        when_layout.addWidget(time_label, 0, 4, 1, 3)
        
        # Row 1: Date + buttons | Time + button
        when_layout.addWidget(self.date_edit, 1, 0, 1, 2)
        when_layout.addWidget(self.calendar_btn, 1, 2)
        when_layout.addWidget(self.today_btn, 1, 3)
        when_layout.addWidget(self.time_edit, 1, 4, 1, 2)
        when_layout.addWidget(self.now_btn, 1, 6)
        
        when_layout.setColumnStretch(0, 1)
        when_layout.setColumnStretch(1, 1)
        when_layout.setColumnStretch(4, 1)
        when_layout.setColumnStretch(5, 1)
        
        form.addWidget(when_section, 1, 0, 1, 7)

        # Section 2: Transaction Details with background
        section2_header = self._create_section_header("🏪  Transaction")
        form.addWidget(section2_header, 2, 0, 1, 7)
        
        trans_section = QtWidgets.QWidget()
        trans_section.setObjectName("SectionBackground")
        trans_layout = QtWidgets.QGridLayout(trans_section)
        trans_layout.setContentsMargins(12, 12, 12, 12)
        trans_layout.setHorizontalSpacing(12)
        trans_layout.setVerticalSpacing(5)
        
        # Row 1: User label | Site label
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        trans_layout.addWidget(user_label, 1, 0, 1, 3)
        
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("FieldLabel")
        trans_layout.addWidget(site_label, 1, 4, 1, 3)
        
        # Row 2: User | Site
        trans_layout.addWidget(self.user_combo, 2, 0, 1, 3)
        trans_layout.addWidget(self.site_combo, 2, 4, 1, 3)
        
        # Add vertical spacer between field groups
        spacer1 = QtWidgets.QSpacerItem(1, 10, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        trans_layout.addItem(spacer1, 3, 0)

        # Row 4: Card label | Amount label
        card_label = QtWidgets.QLabel("Payment Card:")
        card_label.setObjectName("FieldLabel")
        trans_layout.addWidget(card_label, 3, 0, 1, 2)
        
        amount_label = QtWidgets.QLabel("Amount ($):")
        amount_label.setObjectName("FieldLabel")
        trans_layout.addWidget(amount_label, 3, 4, 1, 3)
        
        # Row 4: Card | Amount
        trans_layout.addWidget(self.card_combo, 4, 0, 1, 2)
        trans_layout.addWidget(self.amount_edit, 4, 4, 1, 3)
        
        # Row 4: Cashback display (two lines, right of card field)
        self.cashback_rate_label.setObjectName("CashbackLabel")
        self.cashback_rate_label.setWordWrap(True)
        self.cashback_rate_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        trans_layout.addWidget(self.cashback_rate_label, 4, 2, 1, 2)
        
        trans_layout.setColumnStretch(0, 1)
        trans_layout.setColumnStretch(1, 1)
        trans_layout.setColumnStretch(4, 1)
        trans_layout.setColumnStretch(5, 1)
        
        form.addWidget(trans_section, 3, 0, 1, 7)

        # Section 3: Sweep Coins with background
        section3_header = self._create_section_header("🪙  Sweep Coins")
        form.addWidget(section3_header, 4, 0, 1, 7)
        
        sc_section = QtWidgets.QWidget()
        sc_section.setObjectName("SectionBackground")
        sc_layout = QtWidgets.QGridLayout(sc_section)
        sc_layout.setContentsMargins(12, 12, 12, 12)
        sc_layout.setHorizontalSpacing(12)
        sc_layout.setVerticalSpacing(5)
        
        # Row 1: SC Received label | Starting SC label
        sc_label = QtWidgets.QLabel("SC Received:")
        sc_label.setObjectName("FieldLabel")
        sc_layout.addWidget(sc_label, 1, 0, 1, 3)
        
        start_sc_label = QtWidgets.QLabel("Starting SC Balance:")
        start_sc_label.setObjectName("FieldLabel")
        sc_layout.addWidget(start_sc_label, 1, 4, 1, 3)
        
        # Row 2: SC Received | Starting SC
        sc_layout.addWidget(self.sc_edit, 2, 0, 1, 3)
        sc_layout.addWidget(self.start_sc_edit, 2, 4, 1, 3)
        
        # Add vertical spacer between field groups
        spacer2 = QtWidgets.QSpacerItem(1, 10, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sc_layout.addItem(spacer2, 3, 0)

        # Row 3: Balance check (full width with styled background)
        balance_container = QtWidgets.QWidget()
        balance_container.setObjectName("BalanceCheck")
        balance_layout = QtWidgets.QHBoxLayout(balance_container)
        balance_layout.setContentsMargins(8, 8, 8, 8)
        balance_layout.addWidget(self.balance_check_label)
        sc_layout.addWidget(balance_container, 3, 0, 1, 7)
        
        sc_layout.setColumnStretch(0, 1)
        sc_layout.setColumnStretch(1, 1)
        sc_layout.setColumnStretch(4, 1)
        sc_layout.setColumnStretch(5, 1)
        
        form.addWidget(sc_section, 5, 0, 1, 7)

        # Section 4: Notes with background
        section4_header = self._create_section_header("📝  Notes")
        form.addWidget(section4_header, 6, 0, 1, 7)
        
        notes_section = QtWidgets.QWidget()
        notes_section.setObjectName("SectionBackground")
        notes_layout = QtWidgets.QVBoxLayout(notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(5)
        
        # Add notes field (height already set at initialization)
        notes_layout.addWidget(self.notes_edit)
        
        form.addWidget(notes_section, 7, 0, 1, 7)

        # Set column stretches
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)
        form.setColumnStretch(5, 1)

        layout.addLayout(form)
        
        # Add stretch to push buttons to bottom when dialog is resized
        layout.addStretch(1)

        # Action buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        self.clear_btn = QtWidgets.QPushButton("🧹 Clear")
        self.save_btn = QtWidgets.QPushButton("💾 Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._validate_and_accept)

        self.user_combo.currentTextChanged.connect(self._on_user_changed)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.card_combo.currentTextChanged.connect(self._on_card_changed)
        self.amount_edit.textChanged.connect(self._on_amount_changed)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.card_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.sc_edit.textChanged.connect(self._validate_inline)
        self.start_sc_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._update_balance_check)
        self.site_combo.currentTextChanged.connect(self._update_balance_check)
        self.date_edit.textChanged.connect(self._update_balance_check)
        self.time_edit.textChanged.connect(self._update_balance_check)
        self.start_sc_edit.textChanged.connect(self._update_balance_check)

        if purchase:
            self._load_purchase()
        else:
            self._clear_form()

        self._update_completers()
        self._validate_inline()
        self._update_balance_check()
    
    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        """Create a section header"""
        label = QtWidgets.QLabel(text)
        label.setObjectName("SectionHeader")
        return label
    
    def _update_completers(self):
        for combo in (self.user_combo, self.site_combo, self.card_combo):
            if not combo.isEditable():
                combo.setCompleter(None)
                continue
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: palette(base); color: palette(text); }"
                "QListView::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

    def _set_invalid(self, widget, message: str):
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
        valid = True

        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
            valid = False
        else:
            try:
                parsed = self.get_date()
                if parsed > date.today():
                    self._set_invalid(self.date_edit, "Date cannot be in the future.")
                    valid = False
                else:
                    self._set_valid(self.date_edit)
            except Exception:
                self._set_invalid(self.date_edit, "Enter a valid date.")
                valid = False

        time_text = self.time_edit.text().strip()
        if time_text:
            try:
                if len(time_text) == 5:
                    datetime.strptime(time_text, "%H:%M")
                elif len(time_text) == 8:
                    datetime.strptime(time_text, "%H:%M:%S")
                else:
                    raise ValueError("Invalid format")
                self._set_valid(self.time_edit)
            except Exception:
                self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
                valid = False
        else:
            self._set_valid(self.time_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
            valid = False
        else:
            self._set_valid(self.user_combo)

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
            valid = False
        else:
            self._set_valid(self.site_combo)

        card_text = self.card_combo.currentText().strip()
        if not card_text:
            self._set_invalid(self.card_combo, "Card is required.")
            valid = False
        elif not hasattr(self, "_card_map") or card_text.lower() not in self._card_map:
            self._set_invalid(self.card_combo, "Select a valid Card for the chosen User.")
            valid = False
        else:
            self._set_valid(self.card_combo)

        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
            valid = False
        else:
            try:
                amount_val = Decimal(amount_text)
                if amount_val <= 0:
                    raise ValueError("non-positive")
                self._set_valid(self.amount_edit)
            except Exception:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
                valid = False

        sc_text = self.sc_edit.text().strip()
        if not sc_text:
            self._set_invalid(self.sc_edit, "SC Received is required.")
            valid = False
        else:
            try:
                sc_val = Decimal(sc_text)
                if sc_val < 0:
                    raise ValueError("negative")
                self._set_valid(self.sc_edit)
            except Exception:
                self._set_invalid(self.sc_edit, "Enter a valid SC amount (max 2 decimals).")
                valid = False

        start_sc_text = self.start_sc_edit.text().strip()
        if not start_sc_text:
            self._set_invalid(self.start_sc_edit, "Starting SC is required.")
            valid = False
        else:
            try:
                start_sc_val = Decimal(start_sc_text)
                if start_sc_val < 0:
                    raise ValueError("negative")
                self._set_valid(self.start_sc_edit)
            except Exception:
                self._set_invalid(self.start_sc_edit, "Enter a valid Starting SC (max 2 decimals).")
                valid = False

        return valid

    def _update_balance_check(self):
        site_text = self.site_combo.currentText().strip()
        user_text = self.user_combo.currentText().strip()
        start_sc_text = self.start_sc_edit.text().strip()

        if not site_text or not user_text or not start_sc_text:
            self.balance_check_label.setText("—")
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.style().unpolish(self.balance_check_label)
            self.balance_check_label.style().polish(self.balance_check_label)
            return

        if user_text.lower() not in self._user_lookup or site_text.lower() not in self._site_lookup:
            self.balance_check_label.setText("—")
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.style().unpolish(self.balance_check_label)
            self.balance_check_label.style().polish(self.balance_check_label)
            return

        try:
            start_sc_val = Decimal(start_sc_text)
        except Exception:
            self.balance_check_label.setText("—")
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.style().unpolish(self.balance_check_label)
            self.balance_check_label.style().polish(self.balance_check_label)
            return

        date_text = self.date_edit.text().strip()
        if date_text:
            parsed_date = None
            for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
                try:
                    parsed_date = datetime.strptime(date_text, fmt).date()
                    break
                except ValueError:
                    continue
            if parsed_date is None:
                self.balance_check_label.setText("—")
                self.balance_check_label.setProperty("status", "neutral")
                self.balance_check_label.style().unpolish(self.balance_check_label)
                self.balance_check_label.style().polish(self.balance_check_label)
                return
        else:
            parsed_date = date.today()

        time_text = self.time_edit.text().strip()
        if time_text:
            try:
                if len(time_text) == 5:
                    datetime.strptime(time_text, "%H:%M")
                    parsed_time = f"{time_text}:00"
                elif len(time_text) == 8:
                    datetime.strptime(time_text, "%H:%M:%S")
                    parsed_time = time_text
                else:
                    raise ValueError("Invalid format")
            except Exception:
                self.balance_check_label.setText("—")
                self.balance_check_label.setProperty("status", "neutral")
                self.balance_check_label.style().unpolish(self.balance_check_label)
                self.balance_check_label.style().polish(self.balance_check_label)
                return
        else:
            parsed_time = datetime.now().strftime("%H:%M:%S")

        user_id = self._user_lookup[user_text.lower()]
        site_id = self._site_lookup[site_text.lower()]
        expected_total, _expected_redeem = self.facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=parsed_date,
            session_time=parsed_time,
        )
        
        # DEBUG
        print(f"[BALANCE CHECK DEBUG] user_id={user_id}, site_id={site_id}")
        print(f"[BALANCE CHECK DEBUG] date={parsed_date}, time={parsed_time}")
        print(f"[BALANCE CHECK DEBUG] expected_total={expected_total}, start_sc_val={start_sc_val}")

        delta = Decimal(str(start_sc_val)) - Decimal(str(expected_total))
        if delta > Decimal("0.01"):
            self.balance_check_label.setProperty("status", "positive")
            self.balance_check_label.setText(
                f"+ Detected {float(delta):.2f} SC above expected ({float(expected_total):.2f} SC)"
            )
        elif delta < Decimal("-0.01"):
            self.balance_check_label.setProperty("status", "negative")
            self.balance_check_label.setText(
                f"- WARNING: Starting SC is {float(abs(delta)):.2f} less than expected ({float(expected_total):.2f} SC)"
            )
        else:
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.setText(
                f"Matches expected balance ({float(expected_total):.2f} SC)"
            )

        self.balance_check_label.style().unpolish(self.balance_check_label)
        self.balance_check_label.style().polish(self.balance_check_label)
    
    def _on_user_changed(self, _value: str = ""):
        """Update user_id when selection changes"""
        user_name = self.user_combo.currentText().strip()
        if not user_name or user_name.lower() not in self._user_lookup:
            self.user_id = None
            self.card_combo.blockSignals(True)
            self.card_combo.clear()
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
            self.card_combo.lineEdit().setPlaceholderText("Select a user first")
            self.card_combo.blockSignals(False)
            self.cashback_rate_label.setText("Cashback: —")
            self._card_map = {}
            return

        self.user_id = self._user_lookup[user_name.lower()]
        self.cashback_edit.clear()
        self._load_cards_for_user()

    def _on_card_changed(self, value: str):
        """Update card_id and cashback display when selection changes"""
        card_name = value.strip()
        if not card_name:
            self.card_id = None
            self.cashback_rate_label.setText("Cashback: —")
            self.cashback_edit.clear()
            return

        if not hasattr(self, "_card_map") or card_name.lower() not in self._card_map:
            self.card_id = None
            self.cashback_rate_label.setText("Cashback: —")
            self.cashback_edit.clear()
            return

        card = self._card_map[card_name.lower()]
        self.card_id = card.id
        self._recalculate_cashback(card.cashback_rate)

    def _on_amount_changed(self, _value: str):
        """Recalculate cashback when amount changes"""
        if not self.card_id:
            return
        card = self.facade.get_card(self.card_id)
        if card:
            self._recalculate_cashback(card.cashback_rate)

    def _recalculate_cashback(self, cashback_rate: float):
        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self.cashback_edit.clear()
            self.cashback_rate_label.setText(f"Cashback: {cashback_rate:.2f}%")
            return
        try:
            amount_val = Decimal(amount_text)
            cashback = (amount_val * Decimal(str(cashback_rate)) / Decimal("100")).quantize(Decimal("0.01"))
            self.cashback_edit.setText(f"{cashback:.2f}")
            self.cashback_rate_label.setText(
                f"Cashback: {cashback_rate:.2f}% → ${cashback:.2f}"
            )
        except Exception:
            self.cashback_edit.clear()
            self.cashback_rate_label.setText(f"Cashback: {cashback_rate:.2f}%")

    def _load_cards_for_user(self):
        """Load cards for selected user"""
        self._card_map = {}
        self.card_combo.blockSignals(True)
        self.card_combo.clear()

        if self.user_id:
            cards = self.facade.get_all_cards(user_id=self.user_id, active_only=True)
            for card in cards:
                display_name = card.display_name()
                self._card_map[display_name.lower()] = card
                self.card_combo.addItem(display_name)

        self.card_combo.blockSignals(False)
        self.card_combo.setCurrentIndex(-1)
        self.card_combo.setEditText("")
        self.card_combo.lineEdit().setPlaceholderText("")
        self._update_completers()
    
    def _pick_date(self):
        """Show date picker dialog"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M:%S"))
    
    def get_date(self) -> date:
        """Parse and return date"""
        date_str = self.date_edit.text().strip()
        if not date_str:
            return date.today()
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return date.today()

    def get_time(self) -> Optional[str]:
        time_str = self.time_edit.text().strip()
        if not time_str:
            return datetime.now().strftime("%H:%M:%S")
        if len(time_str) == 5:
            return f"{time_str}:00"
        return time_str
    
    def get_amount(self) -> Decimal:
        """Parse and return amount"""
        return Decimal(self.amount_edit.text().strip())

    def get_sc_received(self) -> Decimal:
        return Decimal(self.sc_edit.text().strip())

    def get_starting_sc_balance(self) -> Decimal:
        return Decimal(self.start_sc_edit.text().strip())

    def get_cashback_earned(self) -> Decimal:
        text = self.cashback_edit.text().strip()
        return Decimal(text) if text else Decimal("0.00")
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        if not self._validate_inline():
            return
        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "User is required"
            )
            return

        self.user_id = self._user_lookup[user_text.lower()]
        
        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Site is required"
            )
            return

        self.site_id = self._site_lookup[site_text.lower()]

        card_text = self.card_combo.currentText().strip()
        if not card_text or not hasattr(self, "_card_map") or card_text.lower() not in self._card_map:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Card is required"
            )
            return

        self.card_id = self._card_map[card_text.lower()].id
        
        # Validate amount
        amount_str = self.amount_edit.text().strip()
        if not amount_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Amount is required"
            )
            return
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Amount must be greater than zero"
                )
                return
        except:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Amount must be a valid number"
            )
            return

        # Validate SC received
        sc_str = self.sc_edit.text().strip()
        if not sc_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "SC Received is required"
            )
            return
        try:
            sc_val = Decimal(sc_str)
            if sc_val < 0:
                raise ValueError("negative")
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "SC Received must be a valid number"
            )
            return

        # Validate starting SC
        start_sc_str = self.start_sc_edit.text().strip()
        if not start_sc_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Starting SC is required"
            )
            return
        try:
            start_sc_val = Decimal(start_sc_str)
            if start_sc_val < 0:
                raise ValueError("negative")
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Starting SC must be a valid number"
            )
            return
        
        # Validate date
        date_str = self.date_edit.text().strip()
        if not date_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Date is required"
            )
            return
        
        try:
            self.get_date()
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Date must be in MM/DD/YY format"
            )
            return
        
        # Validate time if provided
        time_str = self.time_edit.text().strip()
        if time_str:
            try:
                if len(time_str) == 5:
                    datetime.strptime(time_str, "%H:%M")
                elif len(time_str) == 8:
                    datetime.strptime(time_str, "%H:%M:%S")
                else:
                    raise ValueError("Invalid format")
            except Exception:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Time must be in HH:MM format"
                )
                return
        
        self.accept()

    def _clear_form(self):
        self.user_id = None
        self.site_id = None
        self.card_id = None
        self.date_edit.clear()
        self.time_edit.clear()
        self.user_combo.setCurrentIndex(-1)
        self.user_combo.setEditText("")
        self.site_combo.setCurrentIndex(-1)
        self.site_combo.setEditText("")
        self.card_combo.clear()
        self.card_combo.setCurrentIndex(-1)
        self.card_combo.setEditText("")
        self.card_combo.lineEdit().setPlaceholderText("Select user first...")
        self.cashback_rate_label.setText("Cashback: —")
        self.cashback_edit.clear()
        self.amount_edit.clear()
        self.sc_edit.clear()
        self.start_sc_edit.clear()
        self.notes_edit.clear()
        self._set_today()
        self.balance_check_label.setText("—")
        self.balance_check_label.setProperty("status", "neutral")
        self.balance_check_label.style().unpolish(self.balance_check_label)
        self.balance_check_label.style().polish(self.balance_check_label)

    def _load_purchase(self):
        self.date_edit.setText(self.purchase.purchase_date.strftime("%m/%d/%y"))
        if self.purchase.purchase_time:
            time_str = self.purchase.purchase_time
            if len(time_str) > 5:
                time_str = time_str
            self.time_edit.setText(time_str)

        user_name = getattr(self.purchase, "user_name", None)
        if not user_name:
            user = self.facade.get_user(self.purchase.user_id)
            user_name = user.name if user else ""
        if user_name:
            self.user_combo.setCurrentText(user_name)
            self._on_user_changed()

        site_name = getattr(self.purchase, "site_name", None)
        if not site_name:
            site = self.facade.get_site(self.purchase.site_id)
            site_name = site.name if site else ""
        if site_name:
            self.site_combo.setCurrentText(site_name)

        if self.purchase.card_id:
            card = self.facade.get_card(self.purchase.card_id)
            if card:
                display = card.display_name()
                self.card_combo.setCurrentText(display)

        self.amount_edit.setText(f"{float(self.purchase.amount):.2f}")
        self.sc_edit.setText(f"{float(self.purchase.sc_received):.2f}")
        self.start_sc_edit.setText(f"{float(self.purchase.starting_sc_balance):.2f}")

        if self.purchase.notes:
            self.notes_edit.setPlainText(self.purchase.notes)


class ModernPurchaseViewDialog(QtWidgets.QDialog):
    """Modern view-only purchase dialog with sectioned layout"""
    
    def __init__(self, facade: AppFacade, purchase: Purchase, parent=None,
                 user_name: str = "", site_name: str = "", card_name: str = "",
                 on_edit=None, on_delete=None):
        super().__init__(parent)
        self.facade = facade
        self.purchase = purchase
        self._on_edit = on_edit
        self._on_delete = on_delete
        
        self.setWindowTitle(f"Purchase Details (ID: {purchase.id})")
        self.setMinimumWidth(700)
        self.setMinimumHeight(750)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.linked_sessions = self._get_linked_sessions()
        self.linked_redemptions = self._get_linked_redemptions()
        self._game_types = {t.id: t.name for t in self.facade.get_all_game_types()}
        self._games = {g.id: g for g in self.facade.list_all_games()}

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("SetupSubTabs")
        tabs.addTab(self._create_details_tab(user_name, site_name, card_name), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        btn_row = QtWidgets.QHBoxLayout()
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

        layout.addLayout(btn_row)

    def _create_details_tab(self, user_name: str, site_name: str, card_name: str) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)

        def make_value_label(value, wrap=False):
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label.setWordWrap(wrap)
            value_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            return value_label

        def format_date(value):
            if not value:
                return "—"
            if isinstance(value, date):
                return value.strftime("%m/%d/%y")
            try:
                return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%y")
            except ValueError:
                return str(value)

        def format_time(value):
            """Format time for display with full HH:MM:SS precision (Issue #90)"""
            return value if value else "—"

        # Section 1: When (Date/Time)
        section1_header = self._create_section_header("📅  When")
        form.addWidget(section1_header, 0, 0, 1, 7)
        
        when_section = QtWidgets.QWidget()
        when_section.setObjectName("SectionBackground")
        when_layout = QtWidgets.QGridLayout(when_section)
        when_layout.setContentsMargins(12, 12, 12, 12)
        when_layout.setHorizontalSpacing(12)
        when_layout.setVerticalSpacing(5)
        
        # Row 0: Date label | Time label
        date_label = QtWidgets.QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        when_layout.addWidget(date_label, 0, 0, 1, 3)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        when_layout.addWidget(time_label, 0, 4, 1, 3)
        
        # Row 1: Date value | Time value
        date_val = format_date(self.purchase.purchase_date)
        time_val = format_time(self.purchase.purchase_time)
        date_value = make_value_label(date_val)
        when_layout.addWidget(date_value, 1, 0, 1, 3)
        time_value = make_value_label(time_val)
        when_layout.addWidget(time_value, 1, 4, 1, 3)
        
        when_layout.setColumnStretch(0, 1)
        when_layout.setColumnStretch(1, 1)
        when_layout.setColumnStretch(4, 1)
        when_layout.setColumnStretch(5, 1)
        
        form.addWidget(when_section, 1, 0, 1, 7)

        # Section 2: Transaction Details
        section2_header = self._create_section_header("🏪  Transaction")
        form.addWidget(section2_header, 2, 0, 1, 7)
        
        trans_section = QtWidgets.QWidget()
        trans_section.setObjectName("SectionBackground")
        trans_layout = QtWidgets.QGridLayout(trans_section)
        trans_layout.setContentsMargins(12, 12, 12, 12)
        trans_layout.setHorizontalSpacing(12)
        trans_layout.setVerticalSpacing(5)
        
        # Row 0: User label | Site label
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        trans_layout.addWidget(user_label, 0, 0, 1, 3)
        
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("FieldLabel")
        trans_layout.addWidget(site_label, 0, 4, 1, 3)
        
        # Row 1: User value | Site value
        trans_layout.addWidget(make_value_label(user_name or "—"), 1, 0, 1, 3)
        trans_layout.addWidget(make_value_label(site_name or "—"), 1, 4, 1, 3)
        
        # Add vertical spacer
        spacer1 = QtWidgets.QSpacerItem(1, 10, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        trans_layout.addItem(spacer1, 2, 0)

        # Row 3: Card label | Amount label
        card_label = QtWidgets.QLabel("Payment Card:")
        card_label.setObjectName("FieldLabel")
        trans_layout.addWidget(card_label, 3, 0, 1, 2)
        
        amount_label = QtWidgets.QLabel("Amount ($):")
        amount_label.setObjectName("FieldLabel")
        trans_layout.addWidget(amount_label, 3, 4, 1, 3)
        
        # Row 4: Card value | Amount value + Cashback
        amount_val = f"${float(self.purchase.amount):.2f}"
        cashback_val = f"${float(self.purchase.cashback_earned):.2f}"
        trans_layout.addWidget(make_value_label(card_name or "—"), 4, 0, 1, 2)
        trans_layout.addWidget(make_value_label(amount_val), 4, 4, 1, 3)
        
        # Cashback display
        cashback_label = QtWidgets.QLabel(f"Cashback: {cashback_val}")
        cashback_label.setObjectName("CashbackLabel")
        trans_layout.addWidget(cashback_label, 4, 2, 1, 2)
        
        trans_layout.setColumnStretch(0, 1)
        trans_layout.setColumnStretch(1, 1)
        trans_layout.setColumnStretch(4, 1)
        trans_layout.setColumnStretch(5, 1)
        
        form.addWidget(trans_section, 3, 0, 1, 7)

        # Section 3: Sweep Coins
        section3_header = self._create_section_header("🪙  Sweep Coins")
        form.addWidget(section3_header, 4, 0, 1, 7)
        
        sc_section = QtWidgets.QWidget()
        sc_section.setObjectName("SectionBackground")
        sc_layout = QtWidgets.QGridLayout(sc_section)
        sc_layout.setContentsMargins(12, 12, 12, 12)
        sc_layout.setHorizontalSpacing(12)
        sc_layout.setVerticalSpacing(5)
        
        # Row 0: SC Received label | Starting SC label
        sc_label = QtWidgets.QLabel("SC Received:")
        sc_label.setObjectName("FieldLabel")
        sc_layout.addWidget(sc_label, 0, 0, 1, 3)
        
        start_sc_label = QtWidgets.QLabel("Starting SC Balance:")
        start_sc_label.setObjectName("FieldLabel")
        sc_layout.addWidget(start_sc_label, 0, 4, 1, 3)
        
        # Row 1: SC values
        sc_received_val = f"{float(self.purchase.sc_received):.2f}"
        starting_sc_val = f"{float(self.purchase.starting_sc_balance):.2f}"
        sc_layout.addWidget(make_value_label(sc_received_val), 1, 0, 1, 3)
        sc_layout.addWidget(make_value_label(starting_sc_val), 1, 4, 1, 3)
        
        # Add vertical spacer
        spacer2 = QtWidgets.QSpacerItem(1, 10, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sc_layout.addItem(spacer2, 2, 0)

        # Row 3: Remaining (full width with styled background)
        remaining_container = QtWidgets.QWidget()
        remaining_container.setObjectName("RemainingBasis")
        remaining_layout = QtWidgets.QHBoxLayout(remaining_container)
        remaining_layout.setContentsMargins(8, 8, 8, 8)
        remaining_label = QtWidgets.QLabel("Remaining Basis:")
        remaining_label.setObjectName("FieldLabel")
        remaining_value = QtWidgets.QLabel(f"${float(self.purchase.remaining_amount):.2f}")
        remaining_layout.addWidget(remaining_label)
        remaining_layout.addWidget(remaining_value)
        remaining_layout.addStretch(1)
        sc_layout.addWidget(remaining_container, 3, 0, 1, 7)
        
        sc_layout.setColumnStretch(0, 1)
        sc_layout.setColumnStretch(1, 1)
        sc_layout.setColumnStretch(4, 1)
        sc_layout.setColumnStretch(5, 1)
        
        form.addWidget(sc_section, 5, 0, 1, 7)

        # Section 4: Notes (always shown)
        section4_header = self._create_section_header("📝  Notes")
        form.addWidget(section4_header, 6, 0, 1, 7)
        
        notes_section = QtWidgets.QWidget()
        notes_section.setObjectName("SectionBackground")
        notes_layout = QtWidgets.QVBoxLayout(notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(5)
        
        notes_value = self.purchase.notes or ""
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setPlainText(notes_value)
            notes_edit.setFixedHeight(80)
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_layout.addWidget(notes_edit)
        else:
            notes_empty = QtWidgets.QLabel("—")
            notes_empty.setObjectName("InfoField")
            notes_layout.addWidget(notes_empty)
        
        form.addWidget(notes_section, 7, 0, 1, 7)

        # Set column stretches
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)
        form.setColumnStretch(5, 1)

        layout.addLayout(form)
        layout.addStretch(1)
        return widget

    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        """Create a section header"""
        label = QtWidgets.QLabel(text)
        label.setObjectName("SectionHeader")
        return label

    def _create_related_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        allocations = self._fetch_allocated_redemptions()

        if not self.linked_sessions and not allocations:
            placeholder = QtWidgets.QLabel("No related sessions or redemptions found.")
            placeholder.setObjectName("MutedLabel")
            placeholder_font = placeholder.font()
            placeholder_font.setItalic(True)
            placeholder.setFont(placeholder_font)
            layout.addWidget(placeholder)
            layout.addStretch()
            return widget

        if allocations:
            summary_layout = QtWidgets.QHBoxLayout()
            allocated_total = sum(Decimal(str(a.get("allocated_amount") or "0")) for a in allocations)
            original_amount = Decimal(str(self.purchase.amount or 0))
            remaining_amount = Decimal(str(self.purchase.remaining_amount or 0))
            summary_layout.addWidget(QtWidgets.QLabel(f"Original Amount: ${original_amount:.2f}"))
            summary_layout.addSpacing(12)
            summary_layout.addWidget(QtWidgets.QLabel(f"Allocated: ${allocated_total:.2f}"))
            summary_layout.addSpacing(12)
            summary_layout.addWidget(QtWidgets.QLabel(f"Remaining Basis: ${remaining_amount:.2f}"))
            summary_layout.addStretch(1)
            layout.addLayout(summary_layout)

            redemptions_group = QtWidgets.QGroupBox("Allocated Redemptions")
            redemptions_layout = QtWidgets.QVBoxLayout(redemptions_group)
            redemptions_layout.setContentsMargins(8, 10, 8, 8)

            table = QtWidgets.QTableWidget(0, 4)
            table.setHorizontalHeaderLabels([
                "Redemption Date/Time", "Redemption Amount", "Allocated", "View Redemption"
            ])
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(0, 160)
            table.setColumnWidth(1, 140)
            table.setColumnWidth(2, 110)
            table.setColumnWidth(3, 120)
            
            row_height = table.verticalHeader().defaultSectionSize()
            header_height = table.horizontalHeader().height()
            table.setMaximumHeight(header_height + (row_height * 3) + 10)

            table.setRowCount(len(allocations))
            for row, alloc in enumerate(allocations):
                date_val = str(alloc.get("redemption_date") or "—")
                time_val = (alloc.get("redemption_time") or "00:00:00")[:5]
                date_time_display = f"{date_val} {time_val}" if date_val != "—" else time_val
                date_item = QtWidgets.QTableWidgetItem(date_time_display)
                date_item.setData(QtCore.Qt.UserRole, alloc.get("redemption_id"))
                table.setItem(row, 0, date_item)
                table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"${float(alloc.get('amount') or 0):.2f}"))
                table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"${float(alloc.get('allocated_amount') or 0):.2f}"))

                view_btn = QtWidgets.QPushButton("👁️ View Redemption")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
                rid = alloc.get("redemption_id")
                view_btn.clicked.connect(lambda _checked=False, rid=rid: self._open_redemption_by_id(rid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row, 3, view_container)
                table.setRowHeight(
                    row,
                    max(table.rowHeight(row), view_btn.sizeHint().height() + 16),
                )

            redemptions_layout.addWidget(table)
            layout.addWidget(redemptions_group)

        if self.linked_sessions:
            sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
            sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
            sessions_layout.setContentsMargins(8, 10, 8, 8)

            table = QtWidgets.QTableWidget(0, 5)
            table.setHorizontalHeaderLabels([
                "Session Date/Time", "End Date/Time", "Game", "Status", "View Session"
            ])
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(0, 160)
            table.setColumnWidth(1, 140)
            table.setColumnWidth(2, 150)
            table.setColumnWidth(3, 90)
            table.setColumnWidth(4, 120)
            
            row_height = table.verticalHeader().defaultSectionSize()
            header_height = table.horizontalHeader().height()
            table.setMaximumHeight(header_height + (row_height * 3) + 10)

            table.setRowCount(len(self.linked_sessions))
            for row, session in enumerate(self.linked_sessions):
                session_date = str(session.session_date)
                start_time = (session.session_time or "")[:5]
                start_display = f"{session_date} {start_time}" if session_date else "—"
                date_item = QtWidgets.QTableWidgetItem(start_display)
                date_item.setData(QtCore.Qt.UserRole, session.id)
                table.setItem(row, 0, date_item)
                end_display = "—"
                if getattr(session, "end_date", None):
                    end_time = (getattr(session, "end_time", None) or "00:00:00")[:5]
                    end_display = f"{session.end_date} {end_time}"
                table.setItem(row, 1, QtWidgets.QTableWidgetItem(end_display))

                game = self._games.get(session.game_id)
                game_name = game.name if game else "—"
                table.setItem(row, 2, QtWidgets.QTableWidgetItem(game_name))
                table.setItem(row, 3, QtWidgets.QTableWidgetItem(session.status or "Active"))

                view_btn = QtWidgets.QPushButton("👁️ View Session")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
                view_btn.clicked.connect(lambda _checked=False, sid=session.id: self._open_session_by_id(sid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row, 4, view_container)
                table.setRowHeight(
                    row,
                    max(table.rowHeight(row), view_btn.sizeHint().height() + 16),
                )

            sessions_layout.addWidget(table)
            layout.addWidget(sessions_group)

        layout.addStretch()
        return widget

    def _fetch_allocated_redemptions(self):
        if not getattr(self.purchase, "id", None):
            return []
        query = """
            SELECT r.id as redemption_id, r.redemption_date, r.redemption_time, r.amount, ra.allocated_amount
            FROM redemption_allocations ra
            JOIN redemptions r ON r.id = ra.redemption_id
            WHERE ra.purchase_id = ?
            ORDER BY r.redemption_date ASC, COALESCE(r.redemption_time,'00:00:00') ASC, r.id ASC
        """
        return self.facade.db.fetch_all(query, (self.purchase.id,))

    def _open_session_by_id(self, session_id: int):
        parent = self.parent()
        if parent and hasattr(parent, "main_window"):
            main_window = parent.main_window
            if main_window and hasattr(main_window, "open_session"):
                self.accept()
                main_window.open_session(session_id)
                return

        session = self.facade.get_game_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Warning", "Session not found")
            return
        from ui.tabs.game_sessions_tab import ViewSessionDialog

        self.accept()
        dialog = ViewSessionDialog(self.facade, session=session, parent=self)
        dialog.exec()

    def _open_redemption_by_id(self, redemption_id: int):
        from ui.tabs.redemptions_tab import RedemptionViewDialog
        parent = self.parent()
        if parent and hasattr(parent, "main_window"):
            main_window = parent.main_window
            if main_window and hasattr(main_window, "open_redemption"):
                self.accept()
                main_window.open_redemption(redemption_id)
                return

        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            QtWidgets.QMessageBox.warning(self, "Warning", "Redemption not found")
            return

        self.accept()
        dialog = RedemptionViewDialog(redemption=redemption, facade=self.facade, parent=self)
        dialog.exec()

    def _get_linked_sessions(self):
        return self.facade.get_linked_sessions_for_purchase(self.purchase.id)

    def _get_linked_redemptions(self):
        return self.facade.get_redemptions_allocated_to_purchase(self.purchase.id)
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        if not self._validate_inline():
            return
        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "User is required"
            )
            return

        self.user_id = self._user_lookup[user_text.lower()]
        
        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Site is required"
            )
            return

        self.site_id = self._site_lookup[site_text.lower()]

        card_text = self.card_combo.currentText().strip()
        if not card_text or not hasattr(self, "_card_map") or card_text.lower() not in self._card_map:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Card is required"
            )
            return

        self.card_id = self._card_map[card_text.lower()].id
        
        # Validate amount
        amount_str = self.amount_edit.text().strip()
        if not amount_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Amount is required"
            )
            return
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Amount must be greater than zero"
                )
                return
        except:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Amount must be a valid number"
            )
            return

        # Validate SC received
        sc_str = self.sc_edit.text().strip()
        if not sc_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "SC Received is required"
            )
            return
        try:
            sc_val = Decimal(sc_str)
            if sc_val < 0:
                raise ValueError("negative")
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "SC Received must be a valid number"
            )
            return

        # Validate starting SC
        start_sc_str = self.start_sc_edit.text().strip()
        if not start_sc_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Starting SC is required"
            )
            return
        try:
            start_sc_val = Decimal(start_sc_str)
            if start_sc_val < 0:
                raise ValueError("negative")
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Starting SC must be a valid number"
            )
            return
        
        # Validate date
        date_str = self.date_edit.text().strip()
        if not date_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Date is required"
            )
            return
        
        try:
            self.get_date()
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Date must be in MM/DD/YY format"
            )
            return
        
        # Validate time if provided
        time_str = self.time_edit.text().strip()
        if time_str:
            try:
                if len(time_str) == 5:
                    datetime.strptime(time_str, "%H:%M")
                elif len(time_str) == 8:
                    datetime.strptime(time_str, "%H:%M:%S")
                else:
                    raise ValueError("Invalid format")
            except Exception:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Time must be in HH:MM format"
                )
                return
        
        self.accept()

    def _clear_form(self):
        self.user_id = None
        self.site_id = None
        self.card_id = None
        self.date_edit.clear()
        self.time_edit.clear()
        self.user_combo.setCurrentIndex(-1)
        self.user_combo.setEditText("")
        self.site_combo.setCurrentIndex(-1)
        self.site_combo.setEditText("")
        self.card_combo.clear()
        self.card_combo.setCurrentIndex(-1)
        self.card_combo.setEditText("")
        self.card_combo.lineEdit().setPlaceholderText("Select user first...")
        self.cashback_rate_label.setText("Cashback: —")
        self.cashback_edit.clear()
        self.amount_edit.clear()
        self.sc_edit.clear()
        self.start_sc_edit.clear()
        self.notes_edit.clear()
        self._set_today()
        self.balance_check_label.setText("—")
        self.balance_check_label.setProperty("status", "neutral")
        self.balance_check_label.style().unpolish(self.balance_check_label)
        self.balance_check_label.style().polish(self.balance_check_label)

    def _load_purchase(self):
        self.date_edit.setText(self.purchase.purchase_date.strftime("%m/%d/%y"))
        if self.purchase.purchase_time:
            time_str = self.purchase.purchase_time
            if len(time_str) > 5:
                time_str = time_str
            self.time_edit.setText(time_str)

        user_name = getattr(self.purchase, "user_name", None)
        if not user_name:
            user = self.facade.get_user(self.purchase.user_id)
            user_name = user.name if user else ""
        if user_name:
            self.user_combo.setCurrentText(user_name)
            self._on_user_changed()

        site_name = getattr(self.purchase, "site_name", None)
        if not site_name:
            site = self.facade.get_site(self.purchase.site_id)
            site_name = site.name if site else ""
        if site_name:
            self.site_combo.setCurrentText(site_name)

        if self.purchase.card_id:
            card = self.facade.get_card(self.purchase.card_id)
            if card:
                display = card.display_name()
                self.card_combo.setCurrentText(display)

        self.amount_edit.setText(f"{float(self.purchase.amount):.2f}")
        self.sc_edit.setText(f"{float(self.purchase.sc_received):.2f}")
        self.start_sc_edit.setText(f"{float(self.purchase.starting_sc_balance):.2f}")

        if self.purchase.notes:
            self.notes_edit.setPlainText(self.purchase.notes)
    
    def _pick_date(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("Select")
        ok_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))
    
    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))
    
    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M:%S"))
    
    def _on_user_changed(self, _value: str = ""):
        user_name = self.user_combo.currentText().strip()
        if not user_name or user_name.lower() not in self._user_lookup:
            self.user_id = None
            self.card_combo.clear()
            self.card_combo.lineEdit().setPlaceholderText("Select a user first")
            return
        
        self.user_id = self._user_lookup[user_name.lower()]
        self._load_cards_for_user()
        self._update_balance_check()
    
    def _load_cards_for_user(self):
        self._card_map = {}
        self.card_combo.clear()
        
        if self.user_id:
            cards = self.facade.get_all_cards(user_id=self.user_id, active_only=True)
            for card in cards:
                display_name = card.display_name()
                self._card_map[display_name.lower()] = card
                self.card_combo.addItem(display_name)
        
        self.card_combo.setCurrentIndex(-1)
        self._update_completers()
    
    def _on_card_changed(self, value: str):
        card_name = value.strip()
        if not card_name or not hasattr(self, "_card_map") or card_name.lower() not in self._card_map:
            self.card_id = None
            self.cashback_rate_label.setText("Cashback: —")
            return
        
        card = self._card_map[card_name.lower()]
        self.card_id = card.id
        self._recalculate_cashback(card.cashback_rate)
    
    def _on_amount_changed(self, _value: str):
        if not self.card_id:
            return
        card = self.facade.get_card(self.card_id)
        if card:
            self._recalculate_cashback(card.cashback_rate)
    
    def _recalculate_cashback(self, cashback_rate: float):
        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self.cashback_rate_label.setText(f"Cashback: {cashback_rate:.2f}%")
            return
        try:
            amount_val = Decimal(amount_text)
            cashback = (amount_val * Decimal(str(cashback_rate)) / Decimal("100")).quantize(Decimal("0.01"))
            self.cashback_rate_label.setText(f"Cashback: {cashback_rate:.2f}% → ${cashback:.2f}")
        except Exception:
            self.cashback_rate_label.setText(f"Cashback: {cashback_rate:.2f}%")
    
    def _clear_form(self):
        self.user_id = None
        self.site_id = None
        self.card_id = None
        self.date_edit.clear()
        self.time_edit.clear()
        self.user_combo.setCurrentIndex(-1)
        self.site_combo.setCurrentIndex(-1)
        self.card_combo.clear()
        self.amount_edit.clear()
        self.sc_edit.clear()
        self.start_sc_edit.clear()
        self.notes_edit.clear()
        self._set_today()
        self.cashback_rate_label.setText("Cashback: —")
        self.balance_check_label.setText("—")
        self.balance_check_label.setProperty("status", "neutral")
        self.balance_check_label.style().unpolish(self.balance_check_label)
        self.balance_check_label.style().polish(self.balance_check_label)
    
    def get_date(self) -> date:
        date_str = self.date_edit.text().strip()
        if not date_str:
            return date.today()
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return date.today()
    
    def get_time(self) -> Optional[str]:
        time_str = self.time_edit.text().strip()
        if not time_str:
            return datetime.now().strftime("%H:%M:%S")
        if len(time_str) == 5:
            return f"{time_str}:00"
        return time_str
    
    def get_amount(self) -> Decimal:
        return Decimal(self.amount_edit.text().strip())
    
    def get_sc_received(self) -> Decimal:
        return Decimal(self.sc_edit.text().strip())
    
    def get_starting_sc_balance(self) -> Decimal:
        return Decimal(self.start_sc_edit.text().strip())
    
    def get_cashback_earned(self) -> Decimal:
        # Extract from label or calculate
        return Decimal("0.00")
