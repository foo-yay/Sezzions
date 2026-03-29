"""
Main application window with tab navigation
"""
from PySide6 import QtWidgets, QtCore, QtGui
from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import zipfile
from app_facade import AppFacade
from ui.tabs.purchases_tab import PurchasesTab
from ui.tabs.redemptions_tab import RedemptionsTab
from ui.tabs.expenses_tab import ExpensesTab
from ui.tabs.game_sessions_tab import GameSessionsTab
from ui.tabs.unrealized_tab import UnrealizedTab
from ui.tabs.realized_tab import RealizedTab
from ui.tabs.daily_sessions_tab import DailySessionsTab
from ui.tabs.reports_tab import ReportsTab
from ui.tabs.setup_tab import SetupTab
from ui.themes import get_theme, get_theme_names
from ui.settings import Settings
from ui.notification_widgets import NotificationBellWidget, NotificationCenterDialog
from ui.settings_dialog import SettingsDialog
from ui.maintenance_mode_dialog import MaintenanceModeDialog
from services.data_integrity_service import DataIntegrityService
from services.repair_mode_service import RepairModeService
from models.notification import NotificationSeverity
from tools.timezone_utils import set_active_settings
import __init__ as sezzions_package


class MainWindow(QtWidgets.QMainWindow):
    """Main application window"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.settings = Settings()
        set_active_settings(self.settings)
        
        # Wire Repair Mode service to facade with settings and db_manager
        from services.repair_mode_service import RepairModeService
        self.facade.repair_mode_service = RepairModeService(self.settings, self.facade.db)
        
        # Check initial repair mode state for window title
        self.repair_mode = self.facade.repair_mode_service.is_enabled()
        window_title = "Sezzions - Casino Session Tracker"
        if self.repair_mode:
            window_title += " - REPAIR MODE"
        self.setWindowTitle(window_title)
        
        # Check data integrity before proceeding
        self.maintenance_mode = False
        self._check_data_integrity()

        # One-time migration to store timestamps in UTC
        try:
            from services.timezone_migration_service import TimezoneMigrationService
            TimezoneMigrationService(self.facade.db, self.settings).migrate_local_timestamps_to_utc()
        except Exception as e:
            print(f"Warning: Could not migrate timestamps to UTC: {e}")

        # Seed accounting time zone history
        try:
            from services.accounting_time_zone_service import AccountingTimeZoneService
            AccountingTimeZoneService(self.facade.db, self.settings).ensure_history_seeded()
        except Exception as e:
            print(f"Warning: Could not seed accounting time zone history: {e}")
        
        # Restore window size
        width = self.settings.get('window_width', 1400)
        height = self.settings.get('window_height', 900)
        self.resize(width, height)
        
        # Allow window to be resized below content minimum size
        self.setMinimumSize(400, 300)
        
        # Create scroll area as central widget to allow resizing below content size
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)
        
        # Create central widget and layout (now inside scroll area)
        central_widget = QtWidgets.QWidget()
        scroll_area.setWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)
        
        # Create main content frame (bordered)
        self.main_content = QtWidgets.QFrame()
        self.main_content.setObjectName("MainContentFrame")
        main_layout = QtWidgets.QVBoxLayout(self.main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Shared inset so top tabs/bell align with tab content edges.
        self._content_inset = 12

        # Notification bell overlay (pinned to top-right of main content)
        # This avoids affecting the tab layout or minimum window size.
        self._notification_bell = NotificationBellWidget(self.main_content)
        self._notification_bell.clicked.connect(self._show_notification_center)
        self._notification_bell.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._notification_bell.raise_()

        # Settings gear overlay (pinned to the right of the notification bell)
        self._settings_gear = QtWidgets.QToolButton(self.main_content)
        # Shared styling with NotificationBellWidget (styled in ui/themes.py)
        self._settings_gear.setObjectName("HeaderIconButton")
        self._settings_gear.setText("⚙")
        self._settings_gear.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._settings_gear.setAutoRaise(True)
        self._settings_gear.setFixedSize(32, 32)
        self._settings_gear.setToolTip("Settings")
        gear_font = QtGui.QFont("Apple Color Emoji")
        gear_font.setPixelSize(16)
        self._settings_gear.setFont(gear_font)
        self._settings_gear.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._settings_gear.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._settings_gear.clicked.connect(self._show_settings_dialog)
        self._settings_gear.raise_()

        # Reserve vertical space so the overlay bell doesn't sit on top of the tab bar.
        self._notification_bell_margin_top = 6
        self._notification_bell_margin_right = 6
        reserved_height = max(self._notification_bell.height(), self._settings_gear.height())
        self._notification_reserved_top = int(self._notification_bell_margin_top + reserved_height + main_layout.spacing())
        main_layout.setContentsMargins(0, self._notification_reserved_top, 0, 0)

        # Travel mode banner (Entry vs Accounting TZ indicator)
        self._travel_mode_banner = QtWidgets.QFrame()
        self._travel_mode_banner.setObjectName("TravelModeBanner")
        self._travel_mode_banner.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self._travel_mode_banner.setStyleSheet(
            "QFrame#TravelModeBanner { background: #1f6f5a; color: white; border-radius: 6px; }"
        )
        self._travel_mode_banner.setVisible(False)
        banner_layout = QtWidgets.QHBoxLayout(self._travel_mode_banner)
        banner_layout.setContentsMargins(self._content_inset, 6, self._content_inset, 6)
        banner_layout.setSpacing(6)
        self._travel_mode_label = QtWidgets.QLabel("")
        self._travel_mode_label.setObjectName("TravelModeLabel")
        banner_layout.addWidget(self._travel_mode_label)
        banner_layout.addStretch(1)
        main_layout.addWidget(self._travel_mode_banner)

        # Create main tab bar + stacked content (centered tabs)
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.setObjectName("MainTabs")
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(False)

        tab_bar_container = QtWidgets.QWidget()
        tab_bar_layout = QtWidgets.QHBoxLayout(tab_bar_container)
        tab_bar_layout.setContentsMargins(self._content_inset, 0, self._content_inset, 0)
        tab_bar_layout.setSpacing(0)
        tab_bar_layout.addStretch(1)
        tab_bar_layout.addWidget(self.tab_bar)
        tab_bar_layout.addStretch(1)
        main_layout.addWidget(tab_bar_container)

        self.stack = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.stack, 1)
        layout.addWidget(self.main_content)
        
        # Create tabs (with error recovery)
        try:
            self._create_tabs()
        except (ValueError, Exception) as e:
            # Data integrity error during tab creation - enter maintenance mode
            print(f"[STARTUP] Data error detected during tab creation: {e}")
            self.maintenance_mode = True
            self.setWindowTitle("Sezzions - MAINTENANCE MODE")
            self._create_tabs()  # Re-create in maintenance mode

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

        # Travel mode banner
        self._update_travel_mode_banner()
        
        # Restore last tab
        last_tab = self.settings.get('last_tab', 0)
        if last_tab < self.tab_bar.count():
            self.tab_bar.setCurrentIndex(last_tab)
        
        # Restore last Setup sub-tab
        if hasattr(self, 'setup_tab') and hasattr(self.setup_tab, 'sub_tabs'):
            last_setup_subtab = self.settings.get('last_setup_subtab', 0)
            if last_setup_subtab < self.setup_tab.sub_tabs.count():
                self.setup_tab.sub_tabs.setCurrentIndex(last_setup_subtab)
            # Connect to track future changes
            self.setup_tab.sub_tabs.currentChanged.connect(self._on_setup_subtab_changed)

        # Register for data change events (unified refresh system)
        if hasattr(self.facade, "add_data_change_listener"):
            self.facade.add_data_change_listener(self._on_data_changed)
        
        # Legacy compatibility: also listen to DatabaseManager changes
        if hasattr(self.facade, "db") and hasattr(self.facade.db, "add_change_listener"):
            self.facade.db.add_change_listener(self._schedule_refresh_all)
        
        # Initialize notification system
        self._init_notification_system()

        # Wire tax withholding service with settings (Issue #29)
        if hasattr(self.facade, 'tax_withholding_service'):
            self.facade.tax_withholding_service.settings = self.settings

        # Update undo/redo states (Issue #92)
        self._update_undo_redo_states()

        # Position bell after initial layout pass
        QtCore.QTimer.singleShot(0, self._position_notification_bell)

    def _on_setup_subtab_changed(self, index: int):
        """Save Setup sub-tab selection when it changes"""
        self.settings.set('last_setup_subtab', index)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_notification_bell()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_notification_bell()

    def _position_notification_bell(self):
        """Pin the notification bell to the top-right of the main content."""
        if not hasattr(self, "_notification_bell") or self._notification_bell is None:
            return
        if not hasattr(self, "main_content") or self.main_content is None:
            return

        bell = self._notification_bell
        parent = self.main_content

        if parent.width() <= 0 or parent.height() <= 0:
            return

        margin_top = getattr(self, "_notification_bell_margin_top", 6)
        margin_right = getattr(self, "_notification_bell_margin_right", 6)
        inset = getattr(self, "_content_inset", 0)
        
        # Position bell at top-right (but with space for gear to its right)
        gear_spacing = 6  # space between bell and gear
        gear_width = self._settings_gear.width() if hasattr(self, "_settings_gear") and self._settings_gear is not None else 0
        bell_x = max(0, parent.width() - inset - bell.width() - gear_spacing - gear_width - margin_right)
        bell_y = max(0, margin_top)
        bell.move(bell_x, bell_y)
        bell.raise_()
        
        # Position gear to the right of the bell
        if hasattr(self, "_settings_gear") and self._settings_gear is not None:
            gear = self._settings_gear
            gear_x = bell_x + bell.width() + gear_spacing
            gear_y = bell_y + max(0, int((bell.height() - gear.height()) / 2))
            gear.move(gear_x, gear_y)
            gear.raise_()

        # Keep the unread badge on top of both header buttons.
        if hasattr(bell, "raise_badge_overlay"):
            bell.raise_badge_overlay()
    
    def closeEvent(self, event):
        """Save settings on close"""
        # Reload settings from disk to get any changes made by other components
        self.settings.settings = self.settings._load_settings()
        
        # Update window geometry
        self.settings.set('window_width', self.width())
        self.settings.set('window_height', self.height())
        self.settings.set('last_tab', self.tab_bar.currentIndex())
        # Save Setup sub-tab if applicable
        if hasattr(self, 'setup_tab') and hasattr(self.setup_tab, 'sub_tabs'):
            self.settings.set('last_setup_subtab', self.setup_tab.sub_tabs.currentIndex())
        event.accept()
    
    def _check_data_integrity(self):
        """Check database integrity at startup and enter maintenance mode if needed."""
        # Create integrity service
        integrity_service = DataIntegrityService(self.facade.db)
        
        # Run quick check (fast, stops at first violation)
        check_result = integrity_service.check_integrity(quick=True)
        
        if not check_result.is_clean:
            # Show maintenance mode dialog
            dialog = MaintenanceModeDialog(check_result, parent=self)
            result = dialog.exec()
            
            if result == QtWidgets.QDialog.DialogCode.Accepted:
                # User chose to continue in maintenance mode
                self.maintenance_mode = True
                self.setWindowTitle("Sezzions - MAINTENANCE MODE")
            else:
                # User chose to exit
                QtWidgets.QApplication.quit()
                import sys
                sys.exit(0)
    
    def _create_tabs(self):
        """Create all application tabs"""
        self._tab_index = {}
        
        if self.maintenance_mode:
            # Maintenance mode: only show Setup tab (which includes Tools)
            self.setup_tab = SetupTab(self.facade, settings=self.settings)
            self.tab_bar.addTab("⚙️ Setup")
            self.stack.addWidget(self.setup_tab)
            self._tab_index["setup"] = 0
            self.tools_tab = self.setup_tab.tools_tab
            
            # Add maintenance mode banner
            banner = QtWidgets.QLabel("⚠️ MAINTENANCE MODE - Data integrity issues detected. Use Tools to recalculate or restore.")
            banner.setStyleSheet("background-color: #ff6b6b; color: white; padding: 8px; font-weight: bold;")
            banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.main_content.layout().insertWidget(0, banner)
            
            return
        
        # Add repair mode banner if enabled (Issue #55)
        if self.repair_mode:
            repair_banner = QtWidgets.QLabel("🔧 REPAIR MODE — Auto-rebuild disabled")
            repair_banner.setStyleSheet("background-color: #cc0000; color: white; padding: 8px; font-weight: bold;")
            repair_banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.main_content.layout().insertWidget(0, repair_banner)
        
        # Normal mode: create all tabs
        # Primary tabs
        self.purchases_tab = PurchasesTab(self.facade, main_window=self)
        self.redemptions_tab = RedemptionsTab(self.facade, main_window=self)
        self.expenses_tab = ExpensesTab(self.facade)
        self.game_sessions_tab = GameSessionsTab(self.facade, main_window=self)
        self.unrealized_tab = UnrealizedTab(self.facade, main_window=self)
        self.realized_tab = RealizedTab(self.facade, main_window=self)
        self.daily_sessions_tab = DailySessionsTab(self.facade, main_window=self)
        self.reports_tab = ReportsTab()
        
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

        self.tab_bar.addTab("📈 Reports")
        self.stack.addWidget(self.reports_tab)
        self._tab_index["reports"] = self.tab_bar.count() - 1

        self.tab_bar.addTab("💸 Expenses")
        self.stack.addWidget(self.expenses_tab)
        self._tab_index["expenses"] = self.tab_bar.count() - 1
        
        # Setup tab (contains Users/Sites/Cards/etc. + Tools)
        self.setup_tab = SetupTab(self.facade, settings=self.settings)
        self.tab_bar.addTab("⚙️ Setup")
        self.stack.addWidget(self.setup_tab)
        self._tab_index["setup"] = self.tab_bar.count() - 1

        # Backward-compat convenience: Tools now lives under Setup.
        self.tools_tab = self.setup_tab.tools_tab

    def switch_to_tab(self, tab_name: str):
        """Switch to a top-level tab or setup sub-tab by name."""
        target = (tab_name or "").strip().lower()
        if target == "tools":
            setup_idx = self._tab_index.get("setup")
            if setup_idx is not None:
                self.tab_bar.setCurrentIndex(setup_idx)
            if hasattr(self, "setup_tab") and hasattr(self.setup_tab, "sub_tabs"):
                for i in range(self.setup_tab.sub_tabs.count()):
                    if "Tools" in self.setup_tab.sub_tabs.tabText(i):
                        self.setup_tab.sub_tabs.setCurrentIndex(i)
                        break
            return

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
        
        summary_action = QtGui.QAction("Data &Summary", self)
        summary_action.triggered.connect(self._show_summary)
        tools_menu.addAction(summary_action)

        tools_menu.addSeparator()

        recalc_action = QtGui.QAction("&Recalculate Everything", self)
        recalc_action.triggered.connect(self._recalculate_everything)
        tools_menu.addAction(recalc_action)
        
        tools_menu.addSeparator()
        
        # Undo/Redo actions (Issue #92)
        self.undo_action = QtGui.QAction("&Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setEnabled(False)  # Initially disabled
        self.undo_action.triggered.connect(self._perform_undo)
        tools_menu.addAction(self.undo_action)
        
        self.redo_action = QtGui.QAction("&Redo", self)
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.setEnabled(False)  # Initially disabled
        self.redo_action.triggered.connect(self._perform_redo)
        tools_menu.addAction(self.redo_action)
        
        tools_menu.addSeparator()
        
        audit_log_action = QtGui.QAction("View &Audit Log…", self)
        audit_log_action.triggered.connect(self._show_audit_log)
        tools_menu.addAction(audit_log_action)
        
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

        self.check_updates_action = QtGui.QAction("Check for &Updates…", self)
        try:
            self.check_updates_action.setMenuRole(QtGui.QAction.MenuRole.ApplicationSpecificRole)
        except Exception:
            pass
        self.check_updates_action.triggered.connect(self._manual_check_for_updates)
        help_menu.addAction(self.check_updates_action)

        help_menu.addSeparator()

        about_action = QtGui.QAction("&About", self)
        # On macOS this may be promoted to the application menu automatically.
        try:
            about_action.setMenuRole(QtGui.QAction.AboutRole)
        except Exception:
            pass
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # Global search shortcut (Issue #99): Cmd+F/Ctrl+F focuses search bar
        find_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Find, self)
        find_shortcut.activated.connect(self._on_find_shortcut)

    def open_tools_tab(self):
        """Navigate to Setup → Tools."""
        self.tab_bar.setCurrentIndex(self._tab_index.get("setup", 0))
        try:
            self.setup_tab.sub_tabs.setCurrentWidget(self.setup_tab.tools_tab)
        except Exception:
            pass

    def _on_find_shortcut(self):
        """Handle Cmd+F/Ctrl+F shortcut: focus the search bar of the current tab."""
        current_idx = self.tab_bar.currentIndex()
        current_widget = self.stack.currentWidget()
        
        # Main tabs: purchases, redemptions, game_sessions, daily_sessions, unrealized, realized, expenses
        if current_widget in [self.purchases_tab, self.redemptions_tab, self.game_sessions_tab, 
                               self.daily_sessions_tab, self.unrealized_tab, self.realized_tab, self.expenses_tab]:
            if hasattr(current_widget, 'focus_search'):
                current_widget.focus_search()
            elif hasattr(current_widget, 'search_edit'):
                current_widget.search_edit.setFocus()
                current_widget.search_edit.selectAll()
        
        # Setup tab: route to the active sub-tab
        elif current_widget == self.setup_tab:
            active_sub_tab = self.setup_tab.sub_tabs.currentWidget()
            # For tools_tab, it's wrapped in QScrollArea, unwrap it
            if isinstance(active_sub_tab, QtWidgets.QScrollArea):
                active_sub_tab = active_sub_tab.widget()
            
            if hasattr(active_sub_tab, 'focus_search'):
                active_sub_tab.focus_search()
            elif hasattr(active_sub_tab, 'search_edit'):
                active_sub_tab.search_edit.setFocus()
                active_sub_tab.search_edit.selectAll()

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
        
        # Update undo/redo button states after data changes (Issue #92)
        self._update_undo_redo_states()
        
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
        # In maintenance mode, only setup_tab exists
        if self.maintenance_mode:
            if hasattr(self.setup_tab, "refresh_data"):
                try:
                    self.setup_tab.refresh_data()
                except Exception as e:
                    print(f"Warning: Failed to refresh {self.setup_tab.__class__.__name__}: {e}")
            return
        
        # Normal mode: refresh all tabs
        for widget in (
            self.purchases_tab,
            self.redemptions_tab,
            self.expenses_tab,
            self.game_sessions_tab,
            self.daily_sessions_tab,
            self.unrealized_tab,
            self.realized_tab,
            self.reports_tab,
            self.setup_tab,
            self.tools_tab,
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
        
        # Update undo/redo button states after refresh (Issue #92)
        self._update_undo_redo_states()
    
    def refresh_repair_mode_ui(self):
        """
        Refresh repair mode UI elements (banner and window title).
        Called from Tools tab when repair mode is toggled.
        """
        # Update repair mode state
        self.repair_mode = self.facade.repair_mode_service.is_enabled()
        
        # Update window title
        window_title = "Sezzions - Casino Session Tracker"
        if self.repair_mode:
            window_title += " - REPAIR MODE"
        self.setWindowTitle(window_title)
        
        # Rebuild tabs to update banner visibility
        # (In a production app, we'd want a more surgical approach, but this is simple and works)
        # Save current tab index
        current_tab_name = None
        for name, index in self._tab_index.items():
            if index == self.tab_bar.currentIndex():
                current_tab_name = name
                break
        
        # Clear existing tabs
        while self.stack.count() > 0:
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)
        
        # Clear any existing banners
        layout = self.main_content.layout()
        # Remove all widgets except the tab bar and stack
        while layout.count() > 2:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Recreate tabs (which will add the banner if needed)
        self._create_tabs()
        
        # Restore tab selection
        if current_tab_name and current_tab_name in self._tab_index:
            self.tab_bar.setCurrentIndex(self._tab_index[current_tab_name])
        
        # Restore Setup sub-tab selection
        if hasattr(self, 'setup_tab') and hasattr(self.setup_tab, 'sub_tabs'):
            last_setup_subtab = self.settings.get('last_setup_subtab', 0)
            if last_setup_subtab < self.setup_tab.sub_tabs.count():
                self.setup_tab.sub_tabs.setCurrentIndex(last_setup_subtab)
            # Reconnect signal handler after tab recreation
            self.setup_tab.sub_tabs.currentChanged.connect(self._on_setup_subtab_changed)
    
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
    
    def _perform_undo(self):
        """Perform undo operation (Issue #92)"""
        try:
            description = self.facade.undo_redo_service.undo()
            if description:
                self.statusBar().showMessage(f"Undid: {description}", 3000)
                self.refresh_all_tabs()
                self._update_undo_redo_states()
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Undo",
                    "Nothing to undo."
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Undo Failed",
                f"Failed to undo operation:\n\n{str(e)}"
            )
    
    def _perform_redo(self):
        """Perform redo operation (Issue #92)"""
        try:
            description = self.facade.undo_redo_service.redo()
            if description:
                self.statusBar().showMessage(f"Redid: {description}", 3000)
                self.refresh_all_tabs()
                self._update_undo_redo_states()
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Redo",
                    "Nothing to redo."
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Redo Failed",
                f"Failed to redo operation:\n\n{str(e)}"
            )
    
    def _show_audit_log(self):
        """Show audit log viewer dialog (Issue #92)"""
        from ui.audit_log_viewer_dialog import AuditLogViewerDialog
        
        dialog = AuditLogViewerDialog(self.facade.audit_service, parent=self)
        dialog.exec()
    
    def _update_undo_redo_states(self):
        """Update undo/redo action enabled states based on stack availability (Issue #92)"""
        can_undo = self.facade.undo_redo_service.can_undo()
        can_redo = self.facade.undo_redo_service.can_redo()
        
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)
        
        # Update text with descriptions
        if can_undo:
            desc = self.facade.undo_redo_service.get_undo_description()
            self.undo_action.setText(f"&Undo {desc}" if desc else "&Undo")
        else:
            self.undo_action.setText("&Undo")
        
        if can_redo:
            desc = self.facade.undo_redo_service.get_redo_description()
            self.redo_action.setText(f"&Redo {desc}" if desc else "&Redo")
        else:
            self.redo_action.setText("&Redo")

    def _update_travel_mode_banner(self):
        travel_mode_enabled = self.settings.get("travel_mode_enabled", False)
        accounting_tz = self.settings.get("accounting_time_zone") or self.settings.get("time_zone")
        entry_tz = self.settings.get("current_time_zone") or accounting_tz

        if travel_mode_enabled and entry_tz and accounting_tz:
            self._travel_mode_label.setText(
                f"Travel Mode ON — Entry TZ: {entry_tz} · Accounting TZ: {accounting_tz}"
            )
            self._travel_mode_banner.setVisible(True)
        else:
            self._travel_mode_banner.setVisible(False)
    
    def _apply_theme(self, theme_name: str):
        """Apply theme to application"""
        theme = get_theme(theme_name)
        css = theme.get_stylesheet()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setStyleSheet(css)
        self.setStyleSheet(css)
    
    def _change_theme(self, theme_name: str):
        """Change application theme"""
        self._apply_theme(theme_name)
        self.settings.set_theme(theme_name)
        self.statusBar().showMessage(f"Theme changed to {theme_name}", 2000)
    
    def apply_theme(self, theme_name: str):
        """Public method for applying theme (called by Settings dialog)"""
        self._apply_theme(theme_name)
        self.settings.set_theme(theme_name)
        self.statusBar().showMessage(f"Theme changed to {theme_name}", 2000)
    
    def _show_about(self):
        """Show about dialog"""
        app_version = getattr(sezzions_package, "__version__", "0.1.0")
        QtWidgets.QMessageBox.about(
            self,
            "About Sezzions",
            "<h2>Sezzions</h2>"
            "<p>Casino Session Tracker with FIFO Cost Basis Accounting</p>"
            f"<p>Version {app_version}</p>"
            "<p>© 2026 Carolina Edge Gaming</p>"
        )
    
    def _init_notification_system(self):
        """Initialize notification system with periodic evaluation"""
        # Wire Settings to rules service for backup configuration access
        if hasattr(self.facade, 'notification_rules_service'):
            self.facade.notification_rules_service.settings = self.settings
        
        # Evaluate core notification rules immediately on startup (no network update check yet)
        self._evaluate_notifications(include_update_checks=False)
        
        # Set up periodic evaluation timer (every hour)
        self._notification_timer = QtCore.QTimer(self)
        self._notification_timer.setInterval(3600000)  # 1 hour in ms
        self._notification_timer.timeout.connect(lambda: self._evaluate_notifications(include_update_checks=True))
        self._notification_timer.start()
        
        # Also evaluate after Tools operations
        if hasattr(self, 'tools_tab'):
            # Connect to backup completion signal if it exists
            pass  # Tools tab will call on_backup_completed
    
    def _evaluate_notifications(self, include_update_checks: bool = True):
        """Evaluate notification rules and update badge"""
        if hasattr(self.facade, 'notification_rules_service') and self.facade.notification_rules_service.settings is not None:
            self.facade.notification_rules_service.evaluate_all_rules()

        if include_update_checks:
            self._run_periodic_update_check()

        self._refresh_notification_badge()

    def _run_periodic_update_check(self):
        """Run periodic update checks based on user settings and configured interval."""
        if not self.settings.get("update_check_enabled", True):
            return

        interval_hours = int(self.settings.get("update_check_interval_hours", 24) or 24)
        interval_hours = max(1, interval_hours)

        last_check_raw = self.settings.get("last_update_check_at")
        if last_check_raw:
            try:
                last_check_dt = datetime.fromisoformat(last_check_raw)
                if datetime.now() - last_check_dt < timedelta(hours=interval_hours):
                    return
            except Exception:
                pass

        self._perform_update_check(show_messages=False)
        self.settings.set("last_update_check_at", datetime.now().isoformat())

    def _manual_check_for_updates(self):
        """Manual menu/settings-triggered update check."""
        self._perform_update_check(show_messages=True)
        self.settings.set("last_update_check_at", datetime.now().isoformat())

    def _dismiss_update_notifications(self):
        notifications = self.facade.notification_service.get_all(
            include_dismissed=True,
            include_deleted=True,
            include_snoozed=True,
        )
        update_notifications = [
            notification
            for notification in notifications
            if notification.type == 'app_update_available'
        ]
        update_notifications.sort(
            key=lambda notification: (
                notification.created_at or datetime.min,
                notification.id or 0,
            ),
            reverse=True,
        )

        for index, notification in enumerate(update_notifications):
            if index == 0:
                if not notification.is_deleted:
                    self.facade.notification_service.delete(notification.id, cooldown_days=0)
                continue

            self.facade.notification_service.hard_delete(notification.id)

    def _perform_update_check(self, show_messages: bool):
        manifest_url = (self.settings.get("update_manifest_url", "") or "").strip()
        if not manifest_url:
            manifest_url = None

        result = self.facade.check_for_app_updates(manifest_url=manifest_url)
        if result.get("error"):
            if show_messages:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Update Check Failed",
                    f"Unable to check for updates:\n\n{result['error']}",
                )
            return

        if result.get("update_available"):
            latest_version = result.get("latest_version") or "unknown"
            self._dismiss_update_notifications()
            self.facade.notification_service.create_or_update(
                type='app_update_available',
                title=f'Update Available: v{latest_version}',
                body='A newer version of Sezzions is available. Open update details and download from the notification action.',
                severity=NotificationSeverity.INFO,
                subject_id=str(latest_version),
                action_key='open_updates',
                action_payload={'latest_version': latest_version},
            )

            if show_messages:
                self._show_update_available_dialog(result)
        else:
            self._dismiss_update_notifications()
            if show_messages:
                QtWidgets.QMessageBox.information(
                    self,
                    "Up to Date",
                    "You are running the latest available version.",
                )

    def _show_update_available_dialog(self, result: dict):
        latest_version = result.get("latest_version") or "unknown"

        if self._is_development_runtime():
            QtWidgets.QMessageBox.information(
                self,
                "Update Available",
                f"Sezzions v{latest_version} is available.\n\n"
                "You are running a development build from source, so auto-update is disabled. "
                "Use your normal git workflow to sync local code, or install from the published release.",
            )
            return

        dialog = QtWidgets.QMessageBox(self)
        dialog.setIcon(QtWidgets.QMessageBox.Icon.Information)
        dialog.setWindowTitle("Update Available")
        dialog.setText(
            f"Sezzions v{latest_version} is available.\n\n"
            "Do you want to download and install it now?"
        )
        update_now_btn = dialog.addButton("Update Now", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Later", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        dialog.exec()

        if dialog.clickedButton() == update_now_btn:
            self._update_now(result)

    def _update_now(self, result: dict):
        asset = result.get("asset")
        latest_version = str(result.get("latest_version") or "unknown")

        if not asset:
            QtWidgets.QMessageBox.warning(
                self,
                "Update Error",
                "No downloadable update asset was provided for this platform.",
            )
            return

        download_dir = Path.home() / "Downloads" / "Sezzions Updates" / f"v{latest_version}"

        try:
            downloaded_file = Path(self.facade.download_app_update(asset, str(download_dir)))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Download Failed",
                f"Could not download update:\n\n{exc}",
            )
            return

        if self._try_auto_install_downloaded_update(downloaded_file):
            QtWidgets.QMessageBox.information(
                self,
                "Installing Update",
                "Sezzions will now close to complete the update. It will relaunch automatically.",
            )
            QtCore.QTimer.singleShot(300, QtWidgets.QApplication.quit)
            return

        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(downloaded_file.parent)))
        failure_reason = getattr(self, "_last_update_install_error", "Automatic install could not be started.")
        log_path = self._update_install_log_path()
        QtWidgets.QMessageBox.information(
            self,
            "Update Downloaded",
            "Update downloaded successfully.\n\n"
            f"File: {downloaded_file.name}\n"
            f"Location: {downloaded_file.parent}\n\n"
            f"Auto-install status: {failure_reason}\n"
            f"Installer log: {log_path}\n\n"
            "Install manually from this folder.",
        )

    def _update_install_log_path(self) -> Path:
        return Path.home() / "Library" / "Application Support" / "Sezzions" / "update-installer.log"

    def _record_update_install_error(self, message: str, details: str | None = None) -> None:
        self._last_update_install_error = message
        if not details:
            return
        self._append_update_install_log(details)

    def _append_update_install_log(self, details: str) -> None:
        log_path = self._update_install_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(details.rstrip() + "\n")

    def _ensure_macos_bundle_launch_permissions(self, app_bundle: Path) -> None:
        if sys.platform != "darwin":
            return

        macos_dir = app_bundle / "Contents" / "MacOS"
        if not macos_dir.exists() or not macos_dir.is_dir():
            return

        for binary_path in macos_dir.iterdir():
            if not binary_path.is_file():
                continue
            current_mode = binary_path.stat().st_mode
            executable_mode = current_mode | 0o111
            if executable_mode != current_mode:
                binary_path.chmod(executable_mode)

    def _try_auto_install_downloaded_update(self, downloaded_file: Path) -> bool:
        running_app_bundle = self._running_app_bundle_path()
        if running_app_bundle is None:
            self._record_update_install_error("Packaged app bundle was not detected.")
            return False

        if downloaded_file.suffix.lower() != ".zip":
            self._record_update_install_error("Downloaded update is not a zip archive.")
            return False

        target_app_bundle = self._resolve_auto_install_target_bundle(running_app_bundle)
        if target_app_bundle is None:
            return False

        try:
            extract_dir = downloaded_file.parent / f"_extract_{downloaded_file.stem}"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            if sys.platform == "darwin" and shutil.which("ditto"):
                extract_result = subprocess.run(
                    ["ditto", "-x", "-k", str(downloaded_file), str(extract_dir)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if extract_result.returncode != 0:
                    self._record_update_install_error(
                        "Failed to extract update archive.",
                        details=(
                            "[Sezzions Updater] ditto extraction failed\n"
                            f"exit_code={extract_result.returncode}\n"
                            f"stdout={extract_result.stdout}\n"
                            f"stderr={extract_result.stderr}"
                        ),
                    )
                    return False
            else:
                with zipfile.ZipFile(downloaded_file, "r") as archive:
                    archive.extractall(extract_dir)

            app_candidates = sorted(extract_dir.rglob("*.app"))
            if not app_candidates:
                self._record_update_install_error("No .app bundle found in downloaded update archive.")
                return False

            candidate = None
            for app_path in app_candidates:
                if app_path.name == running_app_bundle.name:
                    candidate = app_path
                    break
            if candidate is None:
                candidate = app_candidates[0]

            self._ensure_macos_bundle_launch_permissions(candidate)

            script_path = extract_dir / "apply_update.sh"
            log_path = self._update_install_log_path()
            script_path.write_text(
                "#!/bin/bash\n"
                "set -e\n"
                "NEW_APP=\"$1\"\n"
                "TARGET_APP=\"$2\"\n"
                "APP_PID=\"$3\"\n"
                "LOG_FILE=\"$4\"\n"
                "TMP_APP=\"${TARGET_APP}.updating\"\n"
                "mkdir -p \"$(dirname \"$LOG_FILE\")\"\n"
                "exec >> \"$LOG_FILE\" 2>&1\n"
                "echo \"[Sezzions Updater] Starting apply script\"\n"
                "while kill -0 \"$APP_PID\" >/dev/null 2>&1; do sleep 1; done\n"
                "echo \"[Sezzions Updater] Installing update to $TARGET_APP\"\n"
                "rm -rf \"$TMP_APP\"\n"
                "ditto \"$NEW_APP\" \"$TMP_APP\"\n"
                "if [ -d \"$TMP_APP/Contents/MacOS\" ]; then\n"
                "  chmod -R u+rwx,go+rx \"$TMP_APP/Contents/MacOS\" >/dev/null 2>&1 || true\n"
                "fi\n"
                "xattr -dr com.apple.quarantine \"$TMP_APP\" >/dev/null 2>&1 || true\n"
                "rm -rf \"$TARGET_APP\"\n"
                "mv \"$TMP_APP\" \"$TARGET_APP\"\n"
                "if ! open \"$TARGET_APP\"; then\n"
                "  echo \"[Sezzions Updater] open failed, retrying with -n\"\n"
                "  sleep 1\n"
                "  open -n \"$TARGET_APP\"\n"
                "fi\n",
                encoding="utf-8",
            )
            script_path.chmod(0o755)

            subprocess.Popen(
                [
                    "/bin/bash",
                    str(script_path),
                    str(candidate),
                    str(target_app_bundle),
                    str(os.getpid()),
                    str(log_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception as exc:
            self._record_update_install_error(
                f"Automatic install failed to start: {exc}",
                details=traceback.format_exc(),
            )
            return False

    def _is_translocated_app_bundle(self, app_bundle: Path) -> bool:
        return "AppTranslocation" in str(app_bundle)

    def _candidate_auto_install_targets(self, running_app_bundle: Path) -> list[Path]:
        if self._is_translocated_app_bundle(running_app_bundle):
            return [
                Path("/Applications") / running_app_bundle.name,
                Path.home() / "Applications" / running_app_bundle.name,
            ]
        return [running_app_bundle]

    def _can_write_app_target(self, app_bundle: Path) -> bool:
        try:
            app_bundle.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            return False

        if app_bundle.exists():
            return os.access(str(app_bundle.parent), os.W_OK)

        return os.access(str(app_bundle.parent), os.W_OK)

    def _resolve_auto_install_target_bundle(self, running_app_bundle: Path) -> Path | None:
        candidates = self._candidate_auto_install_targets(running_app_bundle)
        for candidate in candidates:
            if self._can_write_app_target(candidate):
                return candidate

        if self._is_translocated_app_bundle(running_app_bundle):
            candidate_dirs = ", ".join(str(path.parent) for path in candidates)
            self._record_update_install_error(
                "No write permission for app destination",
                details=(
                    f"Running app appears translocated: {running_app_bundle}\n"
                    f"Checked destinations: {candidate_dirs}"
                ),
            )
        else:
            self._record_update_install_error(
                f"No write permission for app destination: {running_app_bundle.parent}"
            )
        return None

    def _running_app_bundle_path(self) -> Path | None:
        executable = Path(sys.executable).resolve()
        for parent in executable.parents:
            if parent.suffix.lower() == ".app":
                return parent
        return None

    def _is_development_runtime(self) -> bool:
        return self._running_app_bundle_path() is None

    def _refresh_notification_badge(self):
        """Update the bell badge from current notification state (no rule evaluation)."""
        unread_count = self.facade.notification_service.get_unread_count()
        self._notification_bell.set_unread_count(unread_count)
    
    def _show_notification_center(self):
        """Show notification center dialog"""
        dialog = NotificationCenterDialog(self.facade, self)
        dialog.exec()
        
        # Refresh badge after dialog closes
        self._evaluate_notifications(include_update_checks=False)
    
    def _show_settings_dialog(self):
        """Show Settings dialog (Issue #31)"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Settings were saved; optionally trigger re-evaluation of notification rules
            # if threshold changed
            self._evaluate_notifications(include_update_checks=False)

            # Update travel mode banner if time zone settings changed
            self._update_travel_mode_banner()
            
            # Rebuild Daily Sessions columns if tax withholding settings changed
            if hasattr(self, 'daily_sessions_tab') and hasattr(self.daily_sessions_tab, 'rebuild_columns'):
                self.daily_sessions_tab.rebuild_columns()

    def restart_application(self):
        """Relaunch Sezzions and quit the current process."""
        try:
            QtCore.QProcess.startDetached(sys.executable, sys.argv)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Restart Failed",
                f"Could not restart Sezzions automatically.\n\n{exc}",
            )
            return
        QtWidgets.QApplication.quit()
    
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
