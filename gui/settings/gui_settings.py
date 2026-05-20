"""Local GUI settings stored outside workspaces."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
APP_DIR_NAME = "PersonalKnowledgeBase"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800
MIN_WIDTH = 920
MIN_HEIGHT = 640


@dataclass
class GuiWindowSettings:
    schema_version: int = SCHEMA_VERSION
    window_width: int = DEFAULT_WIDTH
    window_height: int = DEFAULT_HEIGHT
    window_x: int | None = None
    window_y: int | None = None
    maximized: bool = False
    last_opened_workspace: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuiWindowSettings":
        return cls(
            schema_version=int(data.get("schema_version") or SCHEMA_VERSION),
            window_width=max(MIN_WIDTH, int(data.get("window_width") or DEFAULT_WIDTH)),
            window_height=max(MIN_HEIGHT, int(data.get("window_height") or DEFAULT_HEIGHT)),
            window_x=_optional_int(data.get("window_x")),
            window_y=_optional_int(data.get("window_y")),
            maximized=bool(data.get("maximized", False)),
            last_opened_workspace=str(data.get("last_opened_workspace") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def default_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME / "settings" / "gui-settings.json"
    return Path.home() / ".personal-knowledge-base" / "settings" / "gui-settings.json"


def resolve_settings_path(path: Path | str | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else default_settings_path()


def load_window_settings(path: Path | str | None = None) -> GuiWindowSettings:
    settings_path = resolve_settings_path(path)
    if not settings_path.exists():
        return GuiWindowSettings()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings root must be an object")
        return GuiWindowSettings.from_dict(data)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("failed to load GUI settings from %s: %s", settings_path, exc)
        return GuiWindowSettings()


def save_window_settings(settings: GuiWindowSettings, path: Path | str | None = None) -> bool:
    settings_path = resolve_settings_path(path)
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = settings_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(settings_path)
        return True
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("failed to save GUI settings to %s: %s", settings_path, exc)
        return False


def reset_window_settings(path: Path | str | None = None) -> bool:
    settings_path = resolve_settings_path(path)
    try:
        settings_path.unlink(missing_ok=True)
        return True
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("failed to reset GUI settings at %s: %s", settings_path, exc)
        return False

