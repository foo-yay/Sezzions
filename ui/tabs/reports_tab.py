"""
Reports tab - dashboard-first layout (Issue #102 wireframe).
Placeholders only; no data fetching.
"""
from typing import List, Optional
from PySide6 import QtWidgets, QtCore, QtGui


class FlowLayout(QtWidgets.QLayout):
    """Qt Flow Layout port (wraps children like a flow layout)."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, margin: int = 0, hspacing: int = 8, vspacing: int = 8):
        super().__init__(parent)
        self._items: List[QtWidgets.QLayoutItem] = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QtWidgets.QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QtWidgets.QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> QtCore.Qt.Orientations:
        return QtCore.Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QtCore.QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QtCore.QSize:
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QtCore.QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget is None or not widget.isVisible():
                continue

            space_x = self._hspacing
            space_y = self._vspacing
            next_x = x + item.sizeHint().width() + space_x

            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()


class ClickableFrame(QtWidgets.QFrame):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _card(title: str, value: str = "—", subtitle: str = "") -> ClickableFrame:
    frame = ClickableFrame()
    frame.setObjectName("KpiCard")
    frame.setFrameShape(QtWidgets.QFrame.StyledPanel)

    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)

    label_title = QtWidgets.QLabel(title)
    label_title.setObjectName("KpiTitle")
    label_value = QtWidgets.QLabel(value)
    label_value.setObjectName("KpiValue")
    label_sub = QtWidgets.QLabel(subtitle)
    label_sub.setObjectName("KpiSub")

    layout.addWidget(label_title)
    layout.addWidget(label_value)
    if subtitle:
        layout.addWidget(label_sub)
    layout.addStretch(1)
    return frame


def _panel(title: str) -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setObjectName("Panel")
    frame.setFrameShape(QtWidgets.QFrame.StyledPanel)

    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    header = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(title)
    label.setObjectName("PanelTitle")
    header.addWidget(label)
    header.addStretch(1)
    layout.addLayout(header)

    body = QtWidgets.QFrame()
    body.setObjectName("PanelBody")
    body.setFrameShape(QtWidgets.QFrame.NoFrame)
    layout.addWidget(body)

    return frame


class ReportsTab(QtWidgets.QWidget):
    filter_applied = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportsTab")

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Sidebar
        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("ReportsSidebar")
        self.nav.setFixedWidth(190)
        self.nav.addItems([
            "Overview",
            "By User",
            "By Site",
            "Games",
            "Cashback",
            "Time & Flow",
            "Balances",
            "Tax Analysis",
            "Custom Builder",
        ])
        root.addWidget(self.nav)

        # Main column
        main = QtWidgets.QVBoxLayout()
        main.setSpacing(10)

        # Filter toolbar (single row)
        self.filter_toolbar = QtWidgets.QFrame()
        self.filter_toolbar.setObjectName("FilterToolbar")
        self.filter_toolbar.setFrameShape(QtWidgets.QFrame.StyledPanel)
        toolbar_layout = QtWidgets.QHBoxLayout(self.filter_toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(8)

        self.from_date = QtWidgets.QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QtCore.QDate.currentDate().addDays(-30))
        self.to_date = QtWidgets.QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QtCore.QDate.currentDate())

        self.btn_7d = self._chip_button("7d")
        self.btn_30d = self._chip_button("30d")
        self.btn_mtd = self._chip_button("MTD")
        self.btn_ytd = self._chip_button("YTD")
        self.btn_all = self._chip_button("All")

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setMinimumWidth(140)
        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setMinimumWidth(140)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search…")
        self.search_edit.setMinimumWidth(160)
        self.search_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.more_filters_btn = QtWidgets.QToolButton()
        self.more_filters_btn.setText("More Filters ▾")
        self.more_filters_btn.setCheckable(True)
        self.more_filters_btn.setObjectName("MoreFiltersButton")
        self.more_filters_btn.toggled.connect(self._toggle_more_filters)

        toolbar_layout.addWidget(QtWidgets.QLabel("From"))
        toolbar_layout.addWidget(self.from_date)
        toolbar_layout.addWidget(QtWidgets.QLabel("To"))
        toolbar_layout.addWidget(self.to_date)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self.btn_7d)
        toolbar_layout.addWidget(self.btn_30d)
        toolbar_layout.addWidget(self.btn_mtd)
        toolbar_layout.addWidget(self.btn_ytd)
        toolbar_layout.addWidget(self.btn_all)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self._labeled_combo("User", self.user_combo))
        toolbar_layout.addWidget(self._labeled_combo("Site", self.site_combo))
        toolbar_layout.addWidget(self.search_edit, 1)
        toolbar_layout.addWidget(self.more_filters_btn)

        main.addWidget(self.filter_toolbar)

        # More Filters Drawer
        self.more_filters_drawer = QtWidgets.QFrame()
        self.more_filters_drawer.setObjectName("MoreFiltersDrawer")
        self.more_filters_drawer.setVisible(False)
        drawer_layout = QtWidgets.QHBoxLayout(self.more_filters_drawer)
        drawer_layout.setContentsMargins(10, 8, 10, 8)
        drawer_layout.setSpacing(12)

        self.card_combo = QtWidgets.QComboBox()
        self.game_type_combo = QtWidgets.QComboBox()
        self.game_combo = QtWidgets.QComboBox()
        self.include_deleted = QtWidgets.QCheckBox("Include soft-deleted")
        self.include_anomalies = QtWidgets.QCheckBox("Include anomalies")
        self.save_view_btn = QtWidgets.QPushButton("Save View")
        self.load_view_btn = QtWidgets.QPushButton("Load View")

        drawer_layout.addWidget(self._labeled_combo("Card", self.card_combo))
        drawer_layout.addWidget(self._labeled_combo("Game Type", self.game_type_combo))
        drawer_layout.addWidget(self._labeled_combo("Game", self.game_combo))
        drawer_layout.addWidget(self.include_deleted)
        drawer_layout.addWidget(self.include_anomalies)
        drawer_layout.addStretch(1)
        drawer_layout.addWidget(self.save_view_btn)
        drawer_layout.addWidget(self.load_view_btn)

        main.addWidget(self.more_filters_drawer)

        # KPI area
        kpi_grid = QtWidgets.QGridLayout()
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)

        self.kpi_net = _card("Net P/L (pre-tax)", "$—")
        self.kpi_net_cb = _card("Net P/L + Cashback", "$—")
        self.kpi_post = _card("Net P/L (post-tax)", "$—")
        self.kpi_post_cb = _card("Post-tax + Cashback", "$—")

        for idx, card in enumerate([self.kpi_net, self.kpi_net_cb, self.kpi_post, self.kpi_post_cb]):
            card.clicked.connect(lambda _=None, target=0: self._navigate_to(target))
            kpi_grid.addWidget(card, 0, idx)

        main.addLayout(kpi_grid)

        chip_wrap = QtWidgets.QWidget()
        chip_layout = FlowLayout(chip_wrap, margin=0, hspacing=8, vspacing=8)

        self.kpi_chips = {
            "Cashback": self._chip("Cashback", "$—"),
            "Fees": self._chip("Fees", "$—"),
            "Purchased": self._chip("Purchased", "$—"),
            "Redeemed": self._chip("Redeemed", "$—"),
            "Outstanding": self._chip("Outstanding", "$—"),
            "Avg RTP": self._chip("Avg RTP", "—"),
            "Avg Redemption Time": self._chip("Avg Redemption Time", "—"),
        }

        for chip in self.kpi_chips.values():
            chip_layout.addWidget(chip)

        self.kpi_chips["Outstanding"].clicked.connect(lambda: self._navigate_to(6))
        self.kpi_chips["Avg Redemption Time"].clicked.connect(lambda: self._navigate_to(5))

        main.addWidget(chip_wrap)

        # Pages
        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self._build_overview_page())
        self.pages.addWidget(self._build_by_user_page())
        self.pages.addWidget(self._build_by_site_page())
        self.pages.addWidget(self._build_games_page())
        self.pages.addWidget(self._build_cashback_page())
        self.pages.addWidget(self._build_time_flow_page())
        self.pages.addWidget(self._build_balances_page())
        self.pages.addWidget(self._build_tax_page())
        self.pages.addWidget(self._build_builder_page())

        main.addWidget(self.pages, 1)

        main_wrap = QtWidgets.QWidget()
        main_wrap.setLayout(main)
        root.addWidget(main_wrap, 1)

        # Wire nav
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # Signals
        for widget in (self.from_date, self.to_date, self.user_combo, self.site_combo, self.search_edit):
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(self.filter_applied)
            else:
                widget.editingFinished.connect(self.filter_applied) if hasattr(widget, "editingFinished") else widget.currentIndexChanged.connect(self.filter_applied)

        for btn in (self.btn_7d, self.btn_30d, self.btn_mtd, self.btn_ytd, self.btn_all):
            btn.clicked.connect(self.filter_applied)

    def _chip_button(self, text: str) -> QtWidgets.QToolButton:
        btn = QtWidgets.QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setObjectName("PresetChip")
        return btn

    def _chip(self, label: str, value: str) -> ClickableFrame:
        chip = ClickableFrame()
        chip.setObjectName("KpiChip")
        layout = QtWidgets.QHBoxLayout(chip)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        lbl = QtWidgets.QLabel(label)
        val = QtWidgets.QLabel(value)
        val.setObjectName("KpiChipValue")
        layout.addWidget(lbl)
        layout.addWidget(val)
        return chip

    def _labeled_combo(self, label: str, combo: QtWidgets.QComboBox) -> QtWidgets.QWidget:
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        lbl = QtWidgets.QLabel(label)
        lbl.setObjectName("FilterLabel")
        layout.addWidget(lbl)
        layout.addWidget(combo)
        return wrapper

    def _toggle_more_filters(self, checked: bool) -> None:
        self.more_filters_drawer.setVisible(checked)

    def _navigate_to(self, index: int) -> None:
        self.nav.setCurrentRow(index)

    def _build_overview_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        trend = _panel("Net P/L Trend")
        trend.layout().addWidget(QtWidgets.QLabel("Trend placeholder"))
        composition = _panel("Composition")
        composition.layout().addWidget(QtWidgets.QLabel("Composition placeholder"))

        drivers = _panel("Top Drivers")
        tabs = QtWidgets.QTabWidget()

        self.top_users_list = QtWidgets.QListWidget()
        self.top_sites_list = QtWidgets.QListWidget()
        self.top_games_list = QtWidgets.QListWidget()
        for i in range(1, 11):
            self.top_users_list.addItem(f"User {i}  •  $—")
            self.top_sites_list.addItem(f"Site {i}  •  $—")
            self.top_games_list.addItem(f"Game {i}  •  $—")

        tabs.addTab(self.top_users_list, "Top Users")
        tabs.addTab(self.top_sites_list, "Top Sites")
        tabs.addTab(self.top_games_list, "Top Games")

        view_all = QtWidgets.QPushButton("View all")
        view_all.setObjectName("ViewAllButton")
        view_all.clicked.connect(lambda: self._navigate_from_tab(tabs.currentIndex()))

        drivers.layout().addWidget(tabs)
        drivers.layout().addWidget(view_all)

        grid.addWidget(trend, 0, 0, 1, 2)
        grid.addWidget(composition, 0, 2, 1, 2)
        grid.addWidget(drivers, 1, 0, 1, 4)
        return w

    def _navigate_from_tab(self, tab_index: int) -> None:
        if tab_index == 0:
            self._navigate_to(1)
        elif tab_index == 1:
            self._navigate_to(2)
        else:
            self._navigate_to(3)

    def _build_by_user_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        leaderboard = _panel("User Leaderboard")
        leaderboard.layout().addWidget(QtWidgets.QTableView())

        details = _panel("Selected User Details")
        details.layout().addWidget(QtWidgets.QLabel("Details placeholder"))

        grid.addWidget(leaderboard, 0, 0, 1, 3)
        grid.addWidget(details, 0, 3, 1, 1)
        return w

    def _build_by_site_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        leaderboard = _panel("Site Leaderboard")
        leaderboard.layout().addWidget(QtWidgets.QTableView())

        redeem_time = _panel("Redemption Time by Site")
        redeem_time.layout().addWidget(QtWidgets.QLabel("Placeholder"))

        grid.addWidget(leaderboard, 0, 0, 1, 3)
        grid.addWidget(redeem_time, 0, 3, 1, 1)
        return w

    def _build_games_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        for name in ("Game Types", "Games"):
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.addWidget(_panel(f"{name} Leaderboard"))
            page_layout.addWidget(QtWidgets.QTableView())
            tabs.addTab(page, name)

        layout.addWidget(tabs)
        return w

    def _build_cashback_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        for name in ("By Site", "By Card", "By User"):
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.addWidget(_panel(f"Cashback {name}"))
            page_layout.addWidget(QtWidgets.QTableView())
            tabs.addTab(page, name)

        layout.addWidget(tabs)
        return w

    def _build_time_flow_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        for name in ("Redemption Time", "Cadence"):
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.addWidget(_panel(name))
            page_layout.addWidget(QtWidgets.QTableView())
            tabs.addTab(page, name)

        layout.addWidget(tabs)
        return w

    def _build_balances_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        for name in ("Outstanding", "Aging"):
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.addWidget(_panel(name))
            page_layout.addWidget(QtWidgets.QTableView())
            tabs.addTab(page, name)

        layout.addWidget(tabs)
        return w

    def _build_tax_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        inputs = _panel("Tax Settings")
        inputs.layout().addWidget(QtWidgets.QLabel("Inputs placeholder"))
        outputs = _panel("Outputs")
        outputs.layout().addWidget(QtWidgets.QLabel("Outputs placeholder"))

        grid.addWidget(inputs, 0, 0, 1, 2)
        grid.addWidget(outputs, 0, 2, 1, 2)
        return w

    def _build_builder_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_panel("Custom Builder (phase 2)"))
        layout.addWidget(QtWidgets.QLabel("Choose grouping + measures + save report"))
        return w
