"""Small status badge widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel


TONE_COLORS = {
    "ready": ("#E7F6EC", "#166534"),
    "warning": ("#FFF7E6", "#B45309"),
    "danger": ("#FDECEC", "#B91C1C"),
    "info": ("#E7F2FA", "#0369A1"),
    "muted": ("#EEF1F5", "#5B6678"),
}


def tone_for_status(value: str) -> str:
    value = (value or "").lower()
    if value in {"ready", "active", "succeeded", "recent"}:
        return "ready"
    if value in {"missing", "stale", "partial", "running", "required", "pending"}:
        return "warning"
    if value in {"failed", "error", "rejected", "quarantine"}:
        return "danger"
    if value in {"cancelled", "deprecated", "unknown"}:
        return "muted"
    return "info"


class StatusBadge(QLabel):
    def __init__(self, text: str = "", tone: str = "muted"):
        super().__init__()
        self.set_badge(text, tone)

    def set_badge(self, text: str, tone: str = "muted") -> None:
        bg, fg = TONE_COLORS.get(tone, TONE_COLORS["muted"])
        self.setText(text)
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {fg}; border: 1px solid {fg}; "
            "border-radius: 8px; padding: 2px 8px; font-size: 12px; }}"
        )
