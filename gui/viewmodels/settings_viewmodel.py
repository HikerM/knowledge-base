"""Read-only settings entry ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class SettingsViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.entry: Dict[str, Any] | None = None

    def load_entry(self) -> Dict[str, Any]:
        self.entry = self.adapter.load_settings_entry()
        return self.entry
