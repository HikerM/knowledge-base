"""Backward-compatible badge aliases."""

from __future__ import annotations

from gui.widgets.status_chip import StatusChip, tone_for_status


class StatusBadge(StatusChip):
    def set_badge(self, text: str, tone: str = "muted") -> None:
        self.set_chip(text, tone)
