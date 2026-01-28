"""
Reusable date filter widget for Qt tabs
"""
from PySide6 import QtWidgets, QtCore
from datetime import date, timedelta, datetime
from ui.input_parsers import parse_date_input


class DateFilterWidget(QtWidgets.QGroupBox):
    """Reusable date filter with From/To dates and quick buttons"""
    
    # Signal emitted when filter changes
    filter_changed = QtCore.Signal()
    
    def __init__(self, title="🎯 Date Filter", parent=None, default_start=None, default_end=None):
        super().__init__(title, parent)
        self._default_start = default_start
        self._default_end = default_end
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QtWidgets.QHBoxLayout()
        
        # From date
        layout.addWidget(QtWidgets.QLabel("From:"))
        self.start_date = QtWidgets.QLineEdit()
        self.start_date.setPlaceholderText("MM/DD/YY")
        self.start_date.textChanged.connect(lambda _t: self.filter_changed.emit())
        self.start_calendar = QtWidgets.QPushButton("📅")
        self.start_calendar.setFixedWidth(44)
        self.start_calendar.clicked.connect(lambda: self._pick_date(self.start_date))
        layout.addWidget(self.start_date)
        layout.addWidget(self.start_calendar)
        
        # To date
        layout.addWidget(QtWidgets.QLabel("To:"))
        self.end_date = QtWidgets.QLineEdit()
        self.end_date.setPlaceholderText("MM/DD/YY")
        self.end_date.textChanged.connect(lambda _t: self.filter_changed.emit())
        self.end_calendar = QtWidgets.QPushButton("📅")
        self.end_calendar.setFixedWidth(44)
        self.end_calendar.clicked.connect(lambda: self._pick_date(self.end_date))
        layout.addWidget(self.end_date)
        layout.addWidget(self.end_calendar)
        
        # Apply button
        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self.filter_changed.emit)
        layout.addWidget(apply_btn)
        
        # Clear button
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filter)
        layout.addWidget(clear_btn)
        
        # Quick buttons
        today_btn = QtWidgets.QPushButton("Today")
        today_btn.clicked.connect(self._filter_today)
        layout.addWidget(today_btn)
        
        last30_btn = QtWidgets.QPushButton("Last 30 Days")
        last30_btn.clicked.connect(self._filter_last_30)
        layout.addWidget(last30_btn)
        
        this_month_btn = QtWidgets.QPushButton("This Month")
        this_month_btn.clicked.connect(self._filter_this_month)
        layout.addWidget(this_month_btn)
        
        this_year_btn = QtWidgets.QPushButton("This Year")
        this_year_btn.clicked.connect(self._filter_this_year)
        layout.addWidget(this_year_btn)

        all_time_btn = QtWidgets.QPushButton("All Time")
        all_time_btn.clicked.connect(self.set_all_time)
        layout.addWidget(all_time_btn)
        
        layout.addStretch()
        self.setLayout(layout)

        today = date.today()
        if self._default_start and self._default_end:
            self.start_date.setText(self._default_start.strftime("%m/%d/%y"))
            self.end_date.setText(self._default_end.strftime("%m/%d/%y"))
        else:
            self.start_date.setText((today - timedelta(days=30)).strftime("%m/%d/%y"))
            self.end_date.setText(today.strftime("%m/%d/%y"))
    
    def get_date_range(self):
        """Get the selected date range as Python dates"""
        return (
            parse_date_input(self.start_date.text()),
            parse_date_input(self.end_date.text()),
        )
    
    def _clear_filter(self):
        """Clear the date filter"""
        if self._default_start and self._default_end:
            self.start_date.setText(self._default_start.strftime("%m/%d/%y"))
            self.end_date.setText(self._default_end.strftime("%m/%d/%y"))
        else:
            today = date.today()
            self.start_date.setText((today.replace(year=today.year - 1)).strftime("%m/%d/%y"))
            self.end_date.setText(today.strftime("%m/%d/%y"))
        self.filter_changed.emit()

    def set_all_time(self):
        """Set an all-time date range"""
        today = date.today()
        self.start_date.setText(date(2000, 1, 1).strftime("%m/%d/%y"))
        self.end_date.setText(today.strftime("%m/%d/%y"))
        self.filter_changed.emit()
    
    def _filter_today(self):
        """Filter to today only"""
        today = date.today()
        self.start_date.setText(today.strftime("%m/%d/%y"))
        self.end_date.setText(today.strftime("%m/%d/%y"))
        self.filter_changed.emit()
    
    def _filter_last_30(self):
        """Filter to last 30 days"""
        today = date.today()
        self.start_date.setText((today - timedelta(days=30)).strftime("%m/%d/%y"))
        self.end_date.setText(today.strftime("%m/%d/%y"))
        self.filter_changed.emit()
    
    def _filter_this_month(self):
        """Filter to current month"""
        today = date.today()
        first_of_month = date(today.year, today.month, 1)
        self.start_date.setText(first_of_month.strftime("%m/%d/%y"))
        self.end_date.setText(today.strftime("%m/%d/%y"))
        self.filter_changed.emit()
    
    def _filter_this_year(self):
        """Filter to current year"""
        today = date.today()
        first_of_year = date(today.year, 1, 1)
        self.start_date.setText(first_of_year.strftime("%m/%d/%y"))
        self.end_date.setText(today.strftime("%m/%d/%y"))
        self.filter_changed.emit()

    def _pick_date(self, target_edit: QtWidgets.QLineEdit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))
