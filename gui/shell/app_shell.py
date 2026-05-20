"""App shell that wires navigation to read-only views."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from gui.shell.navigation import NAVIGATION_ROUTE_BY_ID, NAVIGATION_ROUTES
from gui.shell.sidebar import Sidebar
from gui.shell.statusbar import StatusBar
from gui.shell.topbar import TopBar
from gui.viewmodels.dashboard_viewmodel import DashboardViewModel
from gui.viewmodels.document_viewmodel import DocumentViewModel
from gui.viewmodels.library_viewmodel import LibraryViewModel
from gui.viewmodels.search_viewmodel import SearchViewModel
from gui.viewmodels.settings_viewmodel import SettingsViewModel
from gui.viewmodels.task_viewmodel import TaskViewModel
from gui.viewmodels.workspace_viewmodel import WorkspaceViewModel
from gui.views.dashboard_view import DashboardView
from gui.views.library_view import LibraryView
from gui.views.search_view import SearchView
from gui.views.settings_entry_view import SettingsEntryView
from gui.views.task_summary_view import TaskSummaryView


class AppShell(QWidget):
    """Desktop shell with TopBar, Sidebar, main content, and StatusBar."""

    def __init__(self, adapter: Any, gui_settings_provider: Any | None = None, reset_window_layout: Any | None = None):
        super().__init__()
        self.setObjectName("AppShell")
        self.adapter = adapter
        self.workspace_vm = WorkspaceViewModel(adapter)
        self.dashboard_vm = DashboardViewModel(adapter)
        self.search_vm = SearchViewModel(adapter)
        self.library_vm = LibraryViewModel(adapter)
        self.document_vm = DocumentViewModel(adapter)
        self.task_vm = TaskViewModel(adapter)
        self.settings_vm = SettingsViewModel(adapter)
        self.reset_window_layout = reset_window_layout
        self.loaded_routes: set[str] = set()
        self.current_route: str | None = None
        self.navigation_shortcuts: dict[str, QShortcut] = {}

        self.topbar = TopBar()
        self.sidebar = Sidebar()
        self.statusbar = StatusBar()
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")

        self.dashboard_view = DashboardView(self.dashboard_vm)
        self.search_view = SearchView(self.search_vm, self.document_vm)
        self.library_view = LibraryView(self.library_vm, self.document_vm)
        self.task_view = TaskSummaryView(self.task_vm)
        self.settings_view = SettingsEntryView(self.settings_vm, gui_settings_provider=gui_settings_provider, reset_window_layout=self._reset_window_layout)

        self.routes = {
            "dashboard": self.dashboard_view,
            "search": self.search_view,
            "library": self.library_view,
            "tasks": self.task_view,
            "settings": self.settings_view,
        }
        for widget in self.routes.values():
            self.stack.addWidget(widget)

        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.addWidget(self.sidebar)
        main_row.addWidget(self.stack, 1)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.topbar)
        root.addLayout(main_row, 1)
        root.addWidget(self.statusbar)

        self._register_navigation_shortcuts()
        self.sidebar.route_changed.connect(self.navigate)
        self.topbar.settings_requested.connect(lambda: self.navigate("settings"))
        self.topbar.search_submitted.connect(self._run_global_search)
        self._load_startup_status()
        self.navigate("dashboard")

    def _load_startup_status(self) -> None:
        model = self.workspace_vm.load_status()
        self.topbar.update_workspace(model)
        self.statusbar.update_workspace(model)
        self.dashboard_view.render_startup_status(model)

    def navigate(self, route: str) -> bool:
        route_config = NAVIGATION_ROUTE_BY_ID.get(route)
        if route_config is None or not route_config.enabled:
            self.statusbar.show_notice("该功能当前未启用")
            return False
        widget = self.routes.get(route)
        if widget is None:
            self.statusbar.show_notice("该页面当前不可用")
            return False
        self.sidebar.set_active(route, emit=False)
        self._show_route(route, widget)
        self.statusbar.show_notice("")
        return True

    def show_route(self, route: str) -> bool:
        return self.navigate(route)

    def _show_route(self, route: str, widget: QWidget) -> None:
        self.stack.setCurrentWidget(widget)
        self.current_route = route
        if route == "library" and route not in self.loaded_routes:
            self.library_view.load_summary()
            self.loaded_routes.add(route)
        if route == "tasks" and route not in self.loaded_routes:
            self.task_view.load_tasks()
            self.loaded_routes.add(route)
        if route == "settings":
            self.settings_view.load_settings()
            self.loaded_routes.add(route)
        if hasattr(widget, "focus_primary"):
            widget.focus_primary()

    def _register_navigation_shortcuts(self) -> None:
        for item in NAVIGATION_ROUTES:
            shortcut = QShortcut(QKeySequence(item.shortcut), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda key=item.route_id: self.navigate(key))
            shortcut.activatedAmbiguously.connect(lambda key=item.route_id: self.navigate(key))
            self.navigation_shortcuts[item.route_id] = shortcut

    def _run_global_search(self, query: str) -> None:
        if self.navigate("search"):
            self.search_view.set_query_and_run(query)

    def _reset_window_layout(self) -> None:
        if self.reset_window_layout is None:
            self.statusbar.show_notice("窗口布局重置暂不可用")
            return
        ok, message = self.reset_window_layout()
        self.statusbar.show_notice(message)
        if ok:
            self.settings_view.load_settings()
