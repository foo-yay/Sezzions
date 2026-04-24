"""
Setup tab - Container for setup/configuration sub-tabs
"""
from PySide6 import QtWidgets
from app_facade import AppFacade
from desktop.ui.tabs.users_tab import UsersTab
from desktop.ui.tabs.sites_tab import SitesTab
from desktop.ui.tabs.cards_tab import CardsTab
from desktop.ui.tabs.redemption_methods_tab import RedemptionMethodsTab
from desktop.ui.tabs.redemption_method_types_tab import RedemptionMethodTypesTab
from desktop.ui.tabs.game_types_tab import GameTypesTab
from desktop.ui.tabs.games_tab import GamesTab
from desktop.ui.tabs.reports_tab import ReportsTab
from desktop.ui.tabs.tools_tab import ToolsTab


class SetupTab(QtWidgets.QWidget):
    """Container tab for all setup/configuration tabs"""
    
    def __init__(self, facade: AppFacade, settings=None):
        super().__init__()
        self.facade = facade
        self.settings = settings
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Setup")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_spacer = QtWidgets.QWidget()
        header_spacer.setFixedSize(300, 32)
        header_layout.addWidget(header_spacer)
        layout.addLayout(header_layout)

        layout.addSpacing(2)

        info = QtWidgets.QLabel("Manage users, sites, cards, redemption methods, game types, and games.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Create sub-tab widget
        self.sub_tabs = QtWidgets.QTabWidget()
        self.sub_tabs.setObjectName("SetupSubTabs")
        self.sub_tabs.setUsesScrollButtons(False)
        if self.sub_tabs.tabBar():
            self.sub_tabs.tabBar().setExpanding(False)
        
        # Add setup tabs
        self.users_tab = UsersTab(facade)
        self.sites_tab = SitesTab(facade)
        self.cards_tab = CardsTab(facade)
        self.redemption_methods_tab = RedemptionMethodsTab(facade)
        self.redemption_method_types_tab = RedemptionMethodTypesTab(facade)
        self.game_types_tab = GameTypesTab(facade)
        self.games_tab = GamesTab(facade)
        # Pass settings to ToolsTab for section state persistence
        self.tools_tab = ToolsTab(facade, settings=self.settings)
        self.reports_tab = ReportsTab(facade)

        # Keep Setup data views consistent after DB restore/reset from Tools.
        # ToolsTab emits data_changed after destructive DB operations.
        self.tools_tab.data_changed.connect(self.refresh_all)
        
        self.sub_tabs.addTab(self.users_tab, "👤 Users")
        self.sub_tabs.addTab(self.sites_tab, "🏢 Sites")
        self.sub_tabs.addTab(self.cards_tab, "💳 Cards")
        self.sub_tabs.addTab(self.redemption_method_types_tab, "🏷️ Method Types")
        self.sub_tabs.addTab(self.redemption_methods_tab, "💵 Redemption Methods")
        self.sub_tabs.addTab(self.game_types_tab, "🎯 Game Types")
        self.sub_tabs.addTab(self.games_tab, "🎮 Games")
        
        # Wrap Tools tab in scroll area to prevent window expansion (Issue #76)
        tools_scroll = QtWidgets.QScrollArea()
        tools_scroll.setWidget(self.tools_tab)
        tools_scroll.setWidgetResizable(True)
        tools_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.sub_tabs.addTab(tools_scroll, "🔧 Tools")

        reports_scroll = QtWidgets.QScrollArea()
        reports_scroll.setWidget(self.reports_tab)
        reports_scroll.setWidgetResizable(True)
        reports_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.sub_tabs.addTab(reports_scroll, "📊 Reports")
        
        card = QtWidgets.QFrame()
        card.setObjectName("SetupCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addWidget(self.sub_tabs)

        layout.addWidget(card, 1)
    
    def refresh_all(self):
        """Refresh all setup tabs"""
        self.users_tab.refresh_data()
        self.sites_tab.refresh_data()
        self.cards_tab.refresh_data()
        self.redemption_method_types_tab.refresh_data()
        self.redemption_methods_tab.refresh_data()
        self.game_types_tab.refresh_data()
        self.games_tab.refresh_data()
        self.reports_tab.refresh_data()

    def refresh_data(self):
        """Alias for refresh_all (used by generic refresh flows)."""
        self.refresh_all()
