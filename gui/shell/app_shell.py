"""App shell that wires navigation to read-only views."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from gui.shell.sidebar import Sidebar
from gui.shell.statusbar import StatusBar
from gui.shell.topbar import TopBar
from gui.viewmodels.document_viewmodel import DocumentViewModel
from gui.viewmodels.library_viewmodel import LibraryViewModel
from gui.viewmodels.search_viewmodel import SearchViewModel
from gui.viewmodels.task_viewmodel import TaskViewModel
from gui.viewmodels.workspace_viewmodel import WorkspaceViewModel
from gui.views.dashboard_view import DashboardView
from gui.views.library_view import LibraryView
from gui.views.search_view import SearchView
from gui.views.settings_entry_view import SettingsEntryView
from gui.views.task_summary_view import TaskSummaryView


class AppShell(QWidget):
    """Desktop shell with TopBar, Sidebar, main content, and StatusBar."""

    def __init__(self, adapter: Any):
        super().__init__()
        self.adapter = adapter
        self.workspace_vm = WorkspaceViewModel(adapter)
        self.search_vm = SearchViewModel(adapter)
        self.library_vm = LibraryViewModel(adapter)
        self.document_vm = DocumentViewModel(adapter)
        self.task_vm = TaskViewModel(adapter)

        self.topbar = TopBar()
        self.sidebar = Sidebar()
        self.statusbar = StatusBar()
        self.stack = QStackedWidget()

        self.dashboard_view = DashboardView(self.task_vm)
        self.search_view = SearchView(self.search_vm, self.document_vm)
        self.library_view = LibraryView(self.library_vm)
        self.task_view = TaskSummaryView(self.task_vm)
        self.settings_view = SettingsEntryView(self.workspace_vm)

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

        self.sidebar.route_changed.connect(self.show_route)
        self.topbar.settings_requested.connect(lambda: self.sidebar.set_active("settings"))
        self.topbar.search_submitted.connect(self._run_global_search)
        self._load_startup_status()
        self.sidebar.set_active("dashboard")

    def _load_startup_status(self) -> None:
        model = self.workspace_vm.load_status()
        self.topbar.update_workspace(model)
        self.statusbar.update_workspace(model)
        self.dashboard_view.render_status(model)
        self.settings_view.render_settings(model)

    def show_route(self, route: str) -> None:
        widget = self.routes.get(route)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        if route == "settings":
            self.settings_view.render_settings()

    def _run_global_search(self, query: str) -> None:
        self.sidebar.set_active("search")
        self.search_view.set_query_and_run(query)
