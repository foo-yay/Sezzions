"""
Main application window with tab navigation
"""
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from ui.tabs.purchases_tab import PurchasesTab
from ui.tabs.redemptions_tab import RedemptionsTab
from ui.tabs.expenses_tab import ExpensesTab
from ui.tabs.game_sessions_tab import GameSessionsTab
from ui.tabs.unrealized_tab import UnrealizedTab
from ui.tabs.realized_tab import RealizedTab
from ui.tabs.daily_sessions_tab import DailySessionsTab
from ui.tabs.setup_tab import SetupTab
from ui.themes import get_theme, get_theme_names
from ui.settings import Settings
from ui.notification_widgets import NotificationBellWidget, NotificationCenterDialog


class MainWindow(QtWidgets.QMainWindow):
    """Main application window"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.settings = Settings()
        self.setWindowTitle("Sezzions - Casino Session Tracker")
        
        # Restore window size
        width = self.settings.get('window_width', 1400)
        height = self.settings.get('window_height', 900)
        self.resize(width, height)
        
        # Create central widget and layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)
        
        # Create main content frame (bordered)
        self.main_content = QtWidgets.QFrame()
        self.main_content.setObjectName("MainContentFrame")
        main_layout = QtWidgets.QVBoxLayout(self.main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Notification bell (top-right, does not affect minimum window width)
        bell_container = QtWidgets.QWidget()
        bell_layout = QtWidgets.QHBoxLayout(bell_container)
        bell_layout.setContentsMargins(0, 0, 0, 0)
        bell_layout.setSpacing(0)
        bell_layout.addStretch(1)
        self._notification_bell = NotificationBellWidget(self)
        self._notification_bell.clicked.connect(self._show_notification_center)
        bell_layout.addWidget(self._notification_bell)
        main_layout.addWidget(bell_container)

        # Create main tab bar + stacked content (centered tabs)
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.setObjectName("MainTabs")
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(False)

        tab_bar_container = QtWidgets.QWidget()
        tab_bar_layout = QtWidgets.QHBoxLayout(tab_bar_container)
        tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        tab_bar_layout.setSpacing(0)
        tab_bar_layout.addStretch(1)
        tab_bar_layout.addWidget(self.tab_bar)
        tab_bar_layout.addStretch(1)
        main_layout.addWidget(tab_bar_container)

        self.stack = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.stack, 1)
        layout.addWidget(self.main_content)
        
        # Create tabs
        self._create_tabs()

        self.tab_bar.currentChanged.connect(self.stack.setCurrentIndex)
        
        # Status bar handled in __init__
        
        # Create menu bar
        self._create_menu_bar()

        # Passive indicator for Tools maintenance operations (backup/restore/reset).
        # Uses a small indeterminate progress bar + label in the status bar.
        self._tools_busy_label = QtWidgets.QLabel("Database maintenance in progress…")
        self._tools_busy_label.setVisible(False)
        self._tools_busy_progress = QtWidgets.QProgressBar()
        self._tools_busy_progress.setTextVisible(False)
        self._tools_busy_progress.setFixedWidth(120)
        self._tools_busy_progress.setRange(0, 0)  # indeterminate
        self._tools_busy_progress.setVisible(False)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.addPermanentWidget(self._tools_busy_label)
        status.addPermanentWidget(self._tools_busy_progress)

        self._tools_busy_timer = QtCore.QTimer(self)
        self._tools_busy_timer.setInterval(250)
        self._tools_busy_timer.timeout.connect(self._update_tools_busy_indicator)
        self._tools_busy_timer.start()

        # Initial state
        self._update_tools_busy_indicator()
        
        # Debounced refresh system (Issue #9)
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)  # 250ms debounce window
        self._refresh_timer.timeout.connect(self._execute_refresh)
        self._pending_refresh_event = None
        
        # Apply saved theme
        self._apply_theme(self.settings.get_theme())
        
        # Restore last tab
        last_tab = self.settings.get('last_tab', 0)
        if last_tab < self.tab_bar.count():
            self.tab_bar.setCurrentIndex(last_tab)

        # Register for data change events (unified refresh system)
        if hasattr(self.facade, "add_data_change_listener"):
            self.facade.add_data_change_listener(self._on_data_changed)
        
        # Legacy compatibility: also listen to DatabaseManager changes
        if hasattr(self.facade, "db") and hasattr(self.facade.db, "add_change_listener"):
            self.facade.db.add_change_listener(self._schedule_refresh_all)
        
        # Initialize notification system
        self._init_notification_system()
    
    def closeEvent(self, event):
        """Save settings on close"""
        # Reload settings from disk to get any changes made by other components
        self.settings.settings = self.settings._load_settings()
        
        # Update window geometry
        self.settings.set('window_width', self.width())
        self.settings.set('window_height', self.height())
        self.settings.set('last_tab', self.tab_bar.currentIndex())
        event.accept()
    
    def _create_tabs(self):
        """Create all application tabs"""
        self._tab_index = {}
        # Primary tabs
        self.purchases_tab = PurchasesTab(self.facade, main_window=self)
        self.redemptions_tab = RedemptionsTab(self.facade, main_window=self)
        self.expenses_tab = ExpensesTab(self.facade)
        self.game_sessions_tab = GameSessionsTab(self.facade, main_window=self)
        self.unrealized_tab = UnrealizedTab(self.facade, main_window=self)
        self.realized_tab = RealizedTab(self.facade, main_window=self)
        self.daily_sessions_tab = DailySessionsTab(self.facade, main_window=self)
        
        self.tab_bar.addTab("💰 Purchases")
        self.stack.addWidget(self.purchases_tab)
        self._tab_index["purchases"] = self.tab_bar.count() - 1
        self.tab_bar.addTab("💵 Redemptions")
        self.stack.addWidget(self.redemptions_tab)
        self._tab_index["redemptions"] = self.tab_bar.count() - 1
        self.tab_bar.addTab("🎮 Game Sessions")
        self.stack.addWidget(self.game_sessions_tab)
        self._tab_index["game_sessions"] = self.tab_bar.count() - 1
        self.tab_bar.addTab("📅 Daily Sessions")
        self.stack.addWidget(self.daily_sessions_tab)
        self._tab_index["daily_sessions"] = self.tab_bar.count() - 1
        self.tab_bar.addTab("📊 Unrealized")
        self.stack.addWidget(self.unrealized_tab)
        self._tab_index["unrealized"] = self.tab_bar.count() - 1
        self.tab_bar.addTab("✅ Realized")
        self.stack.addWidget(self.realized_tab)
        self._tab_index["realized"] = self.tab_bar.count() - 1

        self.tab_bar.addTab("💸 Expenses")
        self.stack.addWidget(self.expenses_tab)
        self._tab_index["expenses"] = self.tab_bar.count() - 1
        
        # Setup tab (contains Users/Sites/Cards/etc. + Tools)
        self.setup_tab = SetupTab(self.facade)
        self.tab_bar.addTab("⚙️ Setup")
        self.stack.addWidget(self.setup_tab)
        self._tab_index["setup"] = self.tab_bar.count() - 1

        # Backward-compat convenience: Tools now lives under Setup.
        self.tools_tab = self.setup_tab.tools_tab

    def open_purchase(self, purchase_id: int):
        self.tab_bar.setCurrentIndex(self._tab_index.get("purchases", 0))
        if hasattr(self.purchases_tab, "open_purchase_by_id"):
            QtCore.QTimer.singleShot(
                0, lambda: self.purchases_tab.open_purchase_by_id(purchase_id)
            )

    def open_redemption(self, redemption_id: int):
        self.tab_bar.setCurrentIndex(self._tab_index.get("redemptions", 1))
        if hasattr(self.redemptions_tab, "view_redemption_by_id"):
            QtCore.QTimer.singleShot(
                0, lambda: self.redemptions_tab.view_redemption_by_id(redemption_id)
            )

    def open_session(self, session_id: int):
        self.tab_bar.setCurrentIndex(self._tab_index.get("game_sessions", 2))
        if hasattr(self.game_sessions_tab, "open_session_by_id"):
            QtCore.QTimer.singleShot(
                0, lambda: self.game_sessions_tab.open_session_by_id(session_id)
            )

    def open_realized_by_redemption(self, redemption_id: int):
        self.tab_bar.setCurrentIndex(self._tab_index.get("realized", 5))
        if hasattr(self.realized_tab, "view_realized_by_redemption_id"):
            QtCore.QTimer.singleShot(
                0, lambda: self.realized_tab.view_realized_by_redemption_id(redemption_id)
            )

    def open_daily_sessions_by_date(self, session_date):
        self.tab_bar.setCurrentIndex(self._tab_index.get("daily_sessions", 3))
        if hasattr(self.daily_sessions_tab, "view_daily_by_date"):
            QtCore.QTimer.singleShot(
                0, lambda: self.daily_sessions_tab.view_daily_by_date(session_date)
            )
    
    def _create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        theme_menu = view_menu.addMenu("Theme")
        theme_group = QtGui.QActionGroup(self)
        theme_group.setExclusive(True)
        
        current_theme = self.settings.get_theme()
        for theme_name in get_theme_names():
            theme_action = QtGui.QAction(theme_name, self)
            theme_action.setCheckable(True)
            if theme_name == current_theme:
                theme_action.setChecked(True)
            theme_action.triggered.connect(lambda checked, name=theme_name: self._change_theme(name))
            theme_group.addAction(theme_action)
            theme_menu.addAction(theme_action)
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        refresh_action = QtGui.QAction("&Refresh All", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_all)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        exit_action = QtGui.QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        validate_action = QtGui.QAction("&Validate Data", self)
        validate_action.triggered.connect(self._validate_data)
        tools_menu.addAction(validate_action)
        
        summary_action = QtGui.QAction("Data &Summary", self)
        summary_action.triggered.connect(self._show_summary)
        tools_menu.addAction(summary_action)

        tools_menu.addSeparator()

        recalc_action = QtGui.QAction("&Recalculate Everything", self)
        recalc_action.triggered.connect(self._recalculate_everything)
        tools_menu.addAction(recalc_action)
        
        tools_menu.addSeparator()
        
        open_tools_action = QtGui.QAction("Open &Tools Tab", self)
        open_tools_action.triggered.connect(self.open_tools_tab)
        tools_menu.addAction(open_tools_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        help_action = QtGui.QAction("Sezzions &Help…", self)
        # Keep this in the Help menu (non-standard), so the Help menu is never empty.
        try:
            help_action.setMenuRole(QtGui.QAction.NoRole)
        except Exception:
            pass
        help_action.triggered.connect(self._show_help)
        help_menu.addAction(help_action)

        help_menu.addSeparator()

        about_action = QtGui.QAction("&About", self)
        # On macOS this may be promoted to the application menu automatically.
        try:
            about_action.setMenuRole(QtGui.QAction.AboutRole)
        except Exception:
            pass
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def open_tools_tab(self):
        """Navigate to Setup → Tools."""
        self.tab_bar.setCurrentIndex(self._tab_index.get("setup", 0))
        try:
            self.setup_tab.sub_tabs.setCurrentWidget(self.setup_tab.tools_tab)
        except Exception:
            pass

    def _update_tools_busy_indicator(self):
        """Show/hide passive busy indicator when tools operations are active."""
        try:
            active = bool(self.facade.is_tools_operation_active())
        except Exception:
            active = False

        if self._tools_busy_label is not None:
            self._tools_busy_label.setVisible(active)
        if self._tools_busy_progress is not None:
            self._tools_busy_progress.setVisible(active)
    
    # ==========================================================================
    # Debounced Refresh System (Issue #9)
    # ==========================================================================
    
    def _on_data_changed(self, event) -> None:
        """
        Handle data change events from AppFacade.
        
        Debounces refresh requests: multiple events in 250ms → one refresh.
        Blocks refresh during maintenance phase "start".
        """
        from services.data_change_event import DataChangeEvent
        
        # Don't refresh during maintenance start phase
        if event.maintenance_phase == "start":
            return
        
        # Store the latest event and restart the debounce timer
        self._pending_refresh_event = event
        self._refresh_timer.stop()
        self._refresh_timer.start()
    
    def _execute_refresh(self) -> None:
        """Execute the actual refresh after debounce window expires."""
        # Check if maintenance is still active
        if hasattr(self.facade, "is_maintenance_mode") and self.facade.is_maintenance_mode():
            # Reschedule for later
            self._refresh_timer.start()
            return
        
        # Execute the refresh
        self.refresh_all_tabs()
        
        # Optional status message
        if self._pending_refresh_event:
            # Only show message for major operations (not manual edits)
            if self._pending_refresh_event.operation in [
                "csv_import", "restore_replace", "restore_merge_all", 
                "restore_merge_selected", "reset_full", "reset_partial",
                "recalculate_all", "recalculate_scoped"
            ]:
                self.statusBar().showMessage("Data refreshed", 2000)
        
        self._pending_refresh_event = None
    
    def _refresh_all(self):
        """Manual refresh action from menu."""
        # Block if maintenance is active
        if hasattr(self.facade, "is_maintenance_mode") and self.facade.is_maintenance_mode():
            QtWidgets.QMessageBox.information(
                self,
                "Maintenance in Progress",
                "Database maintenance is currently running.\n\n"
                "Please wait for it to complete before refreshing."
            )
            return
        
        self.refresh_all_tabs()
        self.statusBar().showMessage("Refreshed", 2000)

    def _schedule_refresh_all(self):
        """Legacy compatibility: schedule refresh from DatabaseManager listener."""
        # Use the new debounced system
        from services.data_change_event import DataChangeEvent, OperationType
        self._on_data_changed(DataChangeEvent(operation=OperationType.MANUAL_EDIT))

    def refresh_all_tabs(self):
        """
        Refresh all tabs using standardized refresh_data() contract.
        
        Every tab must implement refresh_data() for the global refresh system (Issue #9).
        """
        for widget in (
            self.purchases_tab,
            self.redemptions_tab,
            self.expenses_tab,
            self.game_sessions_tab,
            self.daily_sessions_tab,
            self.unrealized_tab,
            self.realized_tab,
            self.setup_tab,
        ):
            if hasattr(widget, "refresh_data"):
                try:
                    widget.refresh_data()
                except Exception as e:
                    # Don't let one broken tab crash the entire refresh
                    print(f"Warning: Failed to refresh {widget.__class__.__name__}: {e}")
                    continue
            # Legacy fallback for tabs that haven't been updated yet
            elif hasattr(widget, "load_data"):
                try:
                    widget.load_data()
                except Exception:
                    continue
    
    def _validate_data(self):
        """Run data validation"""
        result = self.facade.validate_all_data()
        
        if result['is_valid']:
            QtWidgets.QMessageBox.information(
                self,
                "Validation Complete",
                f"✓ Data validation passed\n\n"
                f"Checked: {result['total_checks']} items\n"
                f"Errors: {len(result['errors'])}\n"
                f"Warnings: {len(result['warnings'])}"
            )
        else:
            error_text = "\n".join(result['errors'][:10])  # Show first 10
            if len(result['errors']) > 10:
                error_text += f"\n... and {len(result['errors']) - 10} more"
            
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Issues Found",
                f"Found {len(result['errors'])} errors:\n\n{error_text}"
            )
    
    def _show_summary(self):
        """Show data summary"""
        summary = self.facade.get_data_summary()
        
        text = "Database Summary:\n\n"
        text += f"Users: {summary['users']}\n"
        text += f"Sites: {summary['sites']}\n"
        text += f"Cards: {summary['cards']}\n"
        text += f"Games: {summary['games']}\n"
        text += f"Purchases: {summary['purchases']}\n"
        text += f"Redemptions: {summary['redemptions']}\n"
        text += f"Sessions: {summary['sessions']}\n"
        
        QtWidgets.QMessageBox.information(
            self,
            "Data Summary",
            text
        )

    def _recalculate_everything(self):
        """Delegate to Tools tab for recalculation"""
        # Navigate to Setup → Tools and trigger recalculation.
        self.open_tools_tab()
        # Use QTimer to ensure tab is visible before triggering
        QtCore.QTimer.singleShot(100, self.tools_tab._on_recalculate_all)
    
    def _apply_theme(self, theme_name: str):
        """Apply theme to application"""
        theme = get_theme(theme_name)
        self.setStyleSheet(theme.get_stylesheet())
    
    def _change_theme(self, theme_name: str):
        """Change application theme"""
        self._apply_theme(theme_name)
        self.settings.set_theme(theme_name)
        self.statusBar().showMessage(f"Theme changed to {theme_name}", 2000)
    
    def _show_about(self):
        """Show about dialog"""
        QtWidgets.QMessageBox.about(
            self,
            "About Sezzions",
            "<h2>Sezzions</h2>"
            "<p>Casino Session Tracker with FIFO Cost Basis Accounting</p>"
            "<p>Version 2.0 - OOP Backend</p>"
            "<p>© 2026 Carolina Edge Gaming</p>"
        )
    
    def _init_notification_system(self):
        """Initialize notification system with periodic evaluation"""
        # Wire Settings to rules service for backup configuration access
        if hasattr(self.facade, 'notification_rules_service'):
            self.facade.notification_rules_service.settings = self.settings
        
        # Evaluate immediately on startup
        self._evaluate_notifications()
        
        # Set up periodic evaluation timer (every hour)
        self._notification_timer = QtCore.QTimer(self)
        self._notification_timer.setInterval(3600000)  # 1 hour in ms
        self._notification_timer.timeout.connect(self._evaluate_notifications)
        self._notification_timer.start()
        
        # Also evaluate after Tools operations
        if hasattr(self, 'tools_tab'):
            # Connect to backup completion signal if it exists
            pass  # Tools tab will call on_backup_completed
    
    def _evaluate_notifications(self):
        """Evaluate notification rules and update badge"""
        if hasattr(self.facade, 'notification_rules_service'):
            self.facade.notification_rules_service.evaluate_all_rules()
        
        # Update bell badge
        unread_count = self.facade.notification_service.get_unread_count()
        self._notification_bell.set_unread_count(unread_count)
    
    def _show_notification_center(self):
        """Show notification center dialog"""
        dialog = NotificationCenterDialog(self.facade, self)
        dialog.exec()
        
        # Refresh badge after dialog closes
        self._evaluate_notifications()
    
    def on_backup_completed(self):
        """Called by Tools tab after backup completion"""
        if hasattr(self.facade, 'notification_rules_service'):
            self.facade.notification_rules_service.on_backup_completed()
            self._evaluate_notifications()
    
    def on_redemption_received(self, redemption_id: int):
        """Called when a redemption is marked as received"""
        if hasattr(self.facade, 'notification_rules_service'):
            self.facade.notification_rules_service.on_redemption_received(redemption_id)
            self._evaluate_notifications()

    def _show_help(self):
        QtWidgets.QMessageBox.information(
            self,
            "Sezzions Help",
            "Help is limited in this build.\n\n"
            "- Database tools live in Setup → Tools\n"
            "- While database maintenance runs, the status bar shows a busy indicator",
        )
