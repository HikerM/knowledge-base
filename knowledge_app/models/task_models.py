"""Task queue models for future GUI/EXE long-running jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


TASK_RECORD_SCHEMA_VERSION = 1
TASK_RESULT_SCHEMA_VERSION = 1


class TaskStatus(str, Enum):
    """Stable task lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Known task types.

    Only a small safe subset is executable in the v1.7.0 baseline. Future
    destructive task types are represented here so callers can create records
    without accidentally enabling execution.
    """

    NOOP = "noop"
    WORKSPACE_STATUS = "workspace_status"
    BACKUP_CREATE = "backup_create"
    AUDIT = "audit"
    INDEX = "index"
    FUTURE_RESTORE = "future_restore"
    FUTURE_ARCHIVE = "future_archive"
    FUTURE_TEMPLATE_APPLY = "future_template_apply"


TASK_STATUS_VALUES = {item.value for item in TaskStatus}
TASK_TYPE_VALUES = {item.value for item in TaskType}


@dataclass
class TaskRecord:
    """Persisted task metadata stored under .kb/tasks/<task_id>/task.json."""

    schema_version: int = TASK_RECORD_SCHEMA_VERSION
    task_id: str = ""
    task_type: str = TaskType.NOOP.value
    status: str = TaskStatus.PENDING.value
    title: str = ""
    description: str = ""
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    progress_percent: int = 0
    progress_message: str = ""
    cancellable: bool = True
    cancel_requested: bool = False
    input: Dict[str, Any] = field(default_factory=dict)
    result_summary: Dict[str, Any] = field(default_factory=dict)
    error: Dict[str, Any] = field(default_factory=dict)
    log_path: str = ""
    elapsed_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.task_type not in TASK_TYPE_VALUES:
            raise ValueError(f"Unknown task_type: {self.task_type}")
        if self.status not in TASK_STATUS_VALUES:
            raise ValueError(f"Unknown task status: {self.status}")
        self.progress_percent = max(0, min(100, int(self.progress_percent)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "cancellable": self.cancellable,
            "cancel_requested": self.cancel_requested,
            "input": dict(self.input),
            "result_summary": dict(self.result_summary),
            "error": dict(self.error),
            "log_path": self.log_path,
            "elapsed_ms": self.elapsed_ms,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TaskRecord":
        return cls(
            schema_version=int(payload.get("schema_version") or TASK_RECORD_SCHEMA_VERSION),
            task_id=str(payload.get("task_id") or ""),
            task_type=str(payload.get("task_type") or TaskType.NOOP.value),
            status=str(payload.get("status") or TaskStatus.PENDING.value),
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            created_at=str(payload.get("created_at") or ""),
            started_at=str(payload.get("started_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            progress_percent=int(payload.get("progress_percent") or 0),
            progress_message=str(payload.get("progress_message") or ""),
            cancellable=bool(payload.get("cancellable", True)),
            cancel_requested=bool(payload.get("cancel_requested", False)),
            input=dict(payload.get("input") or {}),
            result_summary=dict(payload.get("result_summary") or {}),
            error=dict(payload.get("error") or {}),
            log_path=str(payload.get("log_path") or ""),
            elapsed_ms=int(payload.get("elapsed_ms") or 0),
            warnings=[str(item) for item in payload.get("warnings") or []],
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ProgressEvent:
    """Progress event appended to .kb/tasks/<task_id>/progress.jsonl."""

    task_id: str
    timestamp: str
    progress_percent: int
    message: str = ""
    current_step: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "progress_percent": max(0, min(100, int(self.progress_percent))),
            "message": self.message,
            "current_step": self.current_step,
            "detail": dict(self.detail),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ProgressEvent":
        return cls(
            task_id=str(payload.get("task_id") or ""),
            timestamp=str(payload.get("timestamp") or ""),
            progress_percent=int(payload.get("progress_percent") or 0),
            message=str(payload.get("message") or ""),
            current_step=str(payload.get("current_step") or ""),
            detail=dict(payload.get("detail") or {}),
        )


@dataclass(frozen=True)
class TaskResult:
    """Result returned by task-run."""

    success: bool
    task_id: str
    status: str
    result: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0
    schema_version: int = TASK_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in TASK_STATUS_VALUES:
            raise ValueError(f"Unknown task result status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "success": self.success,
            "task_id": self.task_id,
            "status": self.status,
            "result": dict(self.result),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "elapsed_ms": self.elapsed_ms,
        }
