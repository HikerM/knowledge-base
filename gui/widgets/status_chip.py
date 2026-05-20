"""Reusable soft status chip."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy


def tone_for_status(value: object) -> str:
    value = str(value or "").lower()
    if value in {"ready", "active", "succeeded", "recent", "available", "success", "就绪", "有效", "成功", "最近可用", "可用"}:
        return "ready"
    if value in {"missing", "stale", "partial", "running", "required", "pending", "缺失", "过期", "部分可用", "运行中", "等待中"}:
        return "warning"
    if value in {"failed", "error", "rejected", "quarantine", "danger", "失败", "错误", "已拒绝", "隔离"}:
        return "danger"
    if value in {"cancelled", "deprecated", "unknown", "unavailable", "", "已取消", "已废弃", "不可用"}:
        return "muted"
    return "info"


class StatusChip(QLabel):
    def __init__(self, text: str = "", tone: str = "muted"):
        super().__init__()
        self.setObjectName("statusChip")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_chip(text, tone)

    def set_chip(self, text: str, tone: str = "muted") -> None:
        self.setText(text)
        self.setProperty("chipTone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
