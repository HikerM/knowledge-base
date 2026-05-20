"""Display formatting helpers for Chinese read-only GUI text."""

from __future__ import annotations

from typing import Any


LAYER_LABELS = {"rules": "规则", "checklists": "清单", "snippets": "片段", "raw": "原始", "distilled": "提炼"}
STATUS_LABELS = {
    "ready": "就绪",
    "missing": "缺失",
    "stale": "过期",
    "partial": "部分可用",
    "failed": "失败",
    "active": "有效",
    "deprecated": "已废弃",
    "rejected": "已拒绝",
    "quarantine": "隔离",
    "pending": "等待中",
    "running": "运行中",
    "succeeded": "成功",
    "cancelled": "已取消",
    "error": "错误",
    "empty": "空",
    "recent": "最近可用",
    "unknown": "不可用",
    "available": "可用",
    "unavailable": "不可用",
}
CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}
SOURCE_TYPE_LABELS = {"official": "官方", "internal_practice": "内部实践", "vendor": "厂商", "blog": "博客", "research": "研究", "unknown": "未知"}
TASK_TYPE_LABELS = {
    "index": "索引",
    "audit": "审核",
    "backup_create": "备份",
    "workspace_status": "工作区状态",
    "noop": "空任务",
}


def layer_label(value: Any) -> str:
    value = str(value or "")
    return LAYER_LABELS.get(value, value or "未知")


def status_label(value: Any) -> str:
    value = str(value or "")
    return STATUS_LABELS.get(value, value or "未知")


def confidence_label(value: Any) -> str:
    value = str(value or "")
    return CONFIDENCE_LABELS.get(value, value or "未知")


def source_type_label(value: Any) -> str:
    value = str(value or "")
    return SOURCE_TYPE_LABELS.get(value, value or "未知")


def task_type_label(value: Any) -> str:
    value = str(value or "")
    return TASK_TYPE_LABELS.get(value, value or "未知")


def bool_label(value: Any) -> str:
    return "是" if bool(value) else "否"


def elapsed_label(value: Any) -> str:
    try:
        ms = int(value or 0)
    except (TypeError, ValueError):
        ms = 0
    return f"{ms} 毫秒" if ms < 1000 else f"{ms / 1000:.1f} 秒"
