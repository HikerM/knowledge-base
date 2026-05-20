"""Primary navigation configuration shared by shell components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationRoute:
    route_id: str
    label: str
    shortcut: str
    enabled: bool
    disabled_reason: str = ""


NAVIGATION_ROUTES: tuple[NavigationRoute, ...] = (
    NavigationRoute("dashboard", "首页", "Alt+1", True),
    NavigationRoute("search", "搜索", "Alt+2", True),
    NavigationRoute("library", "知识库", "Alt+3", True),
    NavigationRoute("review", "审核", "Alt+4", False, "第一阶段只读 MVP 暂不开放"),
    NavigationRoute("tasks", "任务中心", "Alt+5", True),
    NavigationRoute("maintenance", "维护", "Alt+6", False, "第一阶段只读 MVP 暂不开放"),
    NavigationRoute("settings", "设置", "Alt+7", True),
)

NAVIGATION_ROUTE_BY_ID: dict[str, NavigationRoute] = {route.route_id: route for route in NAVIGATION_ROUTES}
