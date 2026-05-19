"""Filesystem-backed task queue baseline for long-running operations."""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from knowledge_core import paths as core_paths
from knowledge_core import quality
from knowledge_core.indexer import connect_db, ensure_schema, perform_index, query_documents

from knowledge_app.models.task_models import (
    TASK_TYPE_VALUES,
    ProgressEvent,
    TaskRecord,
    TaskResult,
    TaskStatus,
    TaskType,
)
from knowledge_app.services.backup_service import BackupService
from knowledge_app.services.workspace_status_service import WorkspaceStatusService


SAFE_EXECUTABLE_TASK_TYPES = {
    TaskType.NOOP.value,
    TaskType.WORKSPACE_STATUS.value,
    TaskType.BACKUP_CREATE.value,
    TaskType.AUDIT.value,
    TaskType.INDEX.value,
}


class TaskQueueError(Exception):
    """Controlled task queue service error."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def elapsed_between_ms(started_at: str, finished_at: str) -> int:
    try:
        start = parse_iso(started_at)
        finish = parse_iso(finished_at)
    except ValueError:
        return 0
    return max(0, int((finish - start).total_seconds() * 1000))


def parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


class TaskQueueService:
    """Create, persist, list, cancel, and synchronously run task records."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else core_paths.ROOT.resolve()
        self.tasks_root = self.workspace_path / ".kb" / "tasks"

    def create_task(
        self,
        task_type: str | TaskType,
        title: str,
        input: Optional[Dict[str, Any]] = None,
        description: str = "",
        cancellable: bool = True,
    ) -> TaskRecord:
        task_type_value = self._task_type_value(task_type)
        title = title.strip()
        if not title:
            raise TaskQueueError("task title must not be empty")

        task_id = self._new_task_id(task_type_value)
        task_dir = self._task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=False)
        log_path = task_dir / "task.log"
        record = TaskRecord(
            task_id=task_id,
            task_type=task_type_value,
            status=TaskStatus.PENDING.value,
            title=title,
            description=description,
            created_at=now_iso(),
            progress_percent=0,
            progress_message="pending",
            cancellable=cancellable,
            cancel_requested=False,
            input=dict(input or {}),
            log_path=str(log_path),
            metadata={
                "workspace_path": str(self.workspace_path),
                "queue_storage": ".kb/tasks",
                "safe_executable": task_type_value in SAFE_EXECUTABLE_TASK_TYPES,
                "git_required": False,
            },
        )
        self._write_task(record)
        self._append_log(record.task_id, "created", {"task_type": task_type_value})
        return record

    def get_task(self, task_id: str) -> TaskRecord:
        path = self._task_json_path(task_id)
        if not path.exists():
            raise TaskQueueError(f"task not found: {task_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TaskQueueError(f"could not read task record {task_id}: {exc}") from exc
        if not isinstance(payload, dict):
            raise TaskQueueError(f"task record must be a JSON object: {task_id}")
        return TaskRecord.from_dict(payload)

    def list_tasks(self, status: str | TaskStatus | None = None, limit: int = 50) -> List[TaskRecord]:
        status_value = self._status_value(status) if status else None
        limit = max(1, int(limit))
        records: List[TaskRecord] = []
        if not self.tasks_root.exists():
            return []
        for path in self.tasks_root.glob("*/task.json"):
            try:
                record = TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if status_value and record.status != status_value:
                continue
            records.append(record)
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def request_cancel(self, task_id: str) -> TaskRecord:
        record = self.get_task(task_id)
        if record.status in {TaskStatus.SUCCEEDED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}:
            return record
        if not record.cancellable:
            record.error = {
                "code": "task_not_cancellable",
                "message": "task is not cancellable",
            }
            self._write_task(record)
            self._append_log(task_id, "cancel rejected", record.error)
            return record
        record.cancel_requested = True
        if record.status == TaskStatus.PENDING.value:
            return self.mark_cancelled(task_id)
        self._write_task(record)
        self._append_log(task_id, "cancel requested", {})
        return record

    def append_progress(
        self,
        task_id: str,
        percent: int,
        message: str,
        current_step: str = "",
        detail: Optional[Dict[str, Any]] = None,
    ) -> ProgressEvent:
        record = self.get_task(task_id)
        event = ProgressEvent(
            task_id=task_id,
            timestamp=now_iso(),
            progress_percent=max(0, min(100, int(percent))),
            message=message,
            current_step=current_step,
            detail=dict(detail or {}),
        )
        self._append_progress_event(event)
        record.progress_percent = event.progress_percent
        record.progress_message = message
        self._write_task(record)
        self._append_log(task_id, "progress", event.to_dict())
        return event

    def mark_running(self, task_id: str) -> TaskRecord:
        record = self.get_task(task_id)
        if record.status != TaskStatus.PENDING.value:
            raise TaskQueueError(f"only pending tasks can be started: {task_id}")
        record.status = TaskStatus.RUNNING.value
        record.started_at = now_iso()
        record.progress_percent = max(record.progress_percent, 1)
        record.progress_message = "running"
        self._write_task(record)
        self._append_log(task_id, "running", {})
        return record

    def mark_succeeded(self, task_id: str, result_summary: Dict[str, Any]) -> TaskRecord:
        record = self.get_task(task_id)
        finished_at = now_iso()
        record.status = TaskStatus.SUCCEEDED.value
        record.finished_at = finished_at
        record.progress_percent = 100
        record.progress_message = "succeeded"
        record.result_summary = dict(result_summary)
        record.error = {}
        record.elapsed_ms = elapsed_between_ms(record.started_at or record.created_at, finished_at)
        self._write_task(record)
        self._append_log(task_id, "succeeded", {"result_summary": result_summary})
        return record

    def mark_failed(self, task_id: str, error: Dict[str, Any] | str) -> TaskRecord:
        record = self.get_task(task_id)
        finished_at = now_iso()
        record.status = TaskStatus.FAILED.value
        record.finished_at = finished_at
        record.progress_message = "failed"
        if isinstance(error, str):
            record.error = {"code": "task_failed", "message": error}
        else:
            record.error = dict(error)
        record.elapsed_ms = elapsed_between_ms(record.started_at or record.created_at, finished_at)
        self._write_task(record)
        self._append_log(task_id, "failed", record.error)
        return record

    def mark_cancelled(self, task_id: str) -> TaskRecord:
        record = self.get_task(task_id)
        finished_at = now_iso()
        record.status = TaskStatus.CANCELLED.value
        record.finished_at = finished_at
        record.cancel_requested = True
        record.progress_message = "cancelled"
        record.elapsed_ms = elapsed_between_ms(record.started_at or record.created_at, finished_at)
        self._write_task(record)
        self._append_log(task_id, "cancelled", {})
        return record

    def run_task(self, task_id: str) -> TaskResult:
        start = time.perf_counter()
        record = self.get_task(task_id)
        if record.status == TaskStatus.CANCELLED.value:
            return self._task_result(record, success=False, errors=["task is cancelled"])
        if record.status == TaskStatus.SUCCEEDED.value:
            return self._task_result(record, success=True)
        if record.status == TaskStatus.FAILED.value:
            return self._task_result(record, success=False, errors=[record.error.get("message", "task failed")])
        if record.status != TaskStatus.PENDING.value:
            raise TaskQueueError(f"task is not runnable from status={record.status}: {task_id}")
        if record.cancel_requested:
            cancelled = self.mark_cancelled(task_id)
            return self._task_result(cancelled, success=False, errors=["task cancellation was requested"])

        self.mark_running(task_id)
        self.append_progress(task_id, 5, "task started", current_step="start")
        try:
            running = self.get_task(task_id)
            if running.cancel_requested:
                cancelled = self.mark_cancelled(task_id)
                return self._task_result(cancelled, success=False, errors=["task cancellation was requested"])
            result_summary = self._execute_task(running)
            if self.get_task(task_id).cancel_requested:
                cancelled = self.mark_cancelled(task_id)
                return self._task_result(cancelled, success=False, errors=["task cancellation was requested"])
            succeeded = self.mark_succeeded(task_id, result_summary)
            return self._task_result(succeeded, success=True, elapsed_override=elapsed_ms(start))
        except Exception as exc:  # noqa: BLE001 - preserve failures in task record instead of crashing callers.
            failed = self.mark_failed(
                task_id,
                {
                    "code": getattr(exc, "code", "task_failed"),
                    "message": str(exc),
                    "type": exc.__class__.__name__,
                },
            )
            return self._task_result(failed, success=False, errors=[str(exc)], elapsed_override=elapsed_ms(start))

    def _execute_task(self, record: TaskRecord) -> Dict[str, Any]:
        if record.task_type not in SAFE_EXECUTABLE_TASK_TYPES:
            raise UnsupportedTaskTypeError(
                f"unsupported task type in v1.7.0 baseline: {record.task_type}",
                code="unsupported_task_type",
            )
        if record.task_type == TaskType.NOOP.value:
            return self._run_noop(record)
        if record.task_type == TaskType.WORKSPACE_STATUS.value:
            return self._run_workspace_status(record)
        if record.task_type == TaskType.BACKUP_CREATE.value:
            return self._run_backup_create(record)
        if record.task_type == TaskType.AUDIT.value:
            return self._run_audit(record)
        if record.task_type == TaskType.INDEX.value:
            return self._run_index(record)
        raise UnsupportedTaskTypeError(f"unsupported task type: {record.task_type}", code="unsupported_task_type")

    def _run_noop(self, record: TaskRecord) -> Dict[str, Any]:
        self.append_progress(record.task_id, 50, "noop task running", current_step="noop")
        self.append_progress(record.task_id, 95, "noop task complete", current_step="noop")
        return {"message": "noop completed", "destructive": False}

    def _run_workspace_status(self, record: TaskRecord) -> Dict[str, Any]:
        self.append_progress(record.task_id, 25, "reading workspace status", current_step="workspace_status")
        result = WorkspaceStatusService(self.workspace_path).get_status()
        if result.data is None:
            raise TaskExecutionError("; ".join(result.errors) or "workspace status failed")
        self.append_progress(record.task_id, 90, "workspace status complete", current_step="workspace_status")
        return {
            "task_type": record.task_type,
            "workspace_status": result.data.to_dict(),
            "warnings": list(result.warnings),
            "destructive": False,
        }

    def _run_backup_create(self, record: TaskRecord) -> Dict[str, Any]:
        task_input = dict(record.input)
        reason = str(task_input.get("reason") or record.title).strip()
        include_index = bool(task_input.get("include_index", False))
        self.append_progress(record.task_id, 20, "creating local backup", current_step="backup_create")
        with self._workspace_root():
            result = BackupService(self.workspace_path).create_backup(reason=reason, include_index=include_index)
        if not result.success:
            raise TaskExecutionError("; ".join(result.errors) or "backup create failed")
        self.append_progress(record.task_id, 90, "backup created", current_step="backup_create")
        return {
            "task_type": record.task_type,
            "backup_path": result.backup_path,
            "manifest": result.manifest.to_dict() if result.manifest else None,
            "warnings": list(result.warnings),
            "destructive": False,
        }

    def _run_audit(self, record: TaskRecord) -> Dict[str, Any]:
        task_input = dict(record.input)
        days = int(task_input.get("days") or 180)
        limit = int(task_input.get("limit") or 50)
        self.append_progress(record.task_id, 25, "loading index metadata", current_step="audit")
        with self._workspace_root():
            conn = connect_db(must_exist=True)
            try:
                ensure_schema(conn)
                rows = query_documents(conn)
                self.append_progress(record.task_id, 60, "running audit checks", current_step="audit")
                result = quality.audit(conn, rows, days, limit)
            finally:
                conn.close()
        self.append_progress(record.task_id, 90, "audit complete", current_step="audit")
        return {
            "task_type": record.task_type,
            "audit": result,
            "destructive": False,
        }

    def _run_index(self, record: TaskRecord) -> Dict[str, Any]:
        force_hash = bool(record.input.get("force_hash", False))
        self.append_progress(record.task_id, 20, "indexing Markdown into SQLite", current_step="index")
        with self._workspace_root():
            result = perform_index(force_hash=force_hash)
        self.append_progress(record.task_id, 90, "index complete", current_step="index")
        return {
            "task_type": record.task_type,
            "index": result,
            "writes": [".kb/index.sqlite"],
            "destructive": False,
        }

    def _task_result(
        self,
        record: TaskRecord,
        success: bool,
        errors: Optional[List[str]] = None,
        elapsed_override: Optional[int] = None,
    ) -> TaskResult:
        warnings = list(record.warnings)
        summary_warnings = record.result_summary.get("warnings")
        if isinstance(summary_warnings, list):
            warnings.extend(str(item) for item in summary_warnings)
        return TaskResult(
            success=success,
            task_id=record.task_id,
            status=record.status,
            result=record.result_summary,
            warnings=warnings,
            errors=list(errors or []),
            elapsed_ms=elapsed_override if elapsed_override is not None else record.elapsed_ms,
        )

    def _append_progress_event(self, event: ProgressEvent) -> None:
        path = self._task_dir(event.task_id) / "progress.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def _append_log(self, task_id: str, message: str, detail: Dict[str, Any]) -> None:
        path = self._task_dir(task_id) / "task.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": now_iso(), "message": message, "detail": detail}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def _write_task(self, record: TaskRecord) -> None:
        path = self._task_json_path(record.task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        temp_path.replace(path)

    def _task_json_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "task.json"

    def _task_dir(self, task_id: str) -> Path:
        task_id = task_id.strip()
        if not task_id or any(part in task_id for part in ["/", "\\", ".."]):
            raise TaskQueueError(f"invalid task_id: {task_id}")
        return self.tasks_root / task_id

    @staticmethod
    def _task_type_value(task_type: str | TaskType) -> str:
        value = task_type.value if isinstance(task_type, TaskType) else str(task_type)
        if value not in TASK_TYPE_VALUES:
            raise TaskQueueError(f"unknown task type: {value}")
        return value

    @staticmethod
    def _status_value(status: str | TaskStatus) -> str:
        value = status.value if isinstance(status, TaskStatus) else str(status)
        if value not in {item.value for item in TaskStatus}:
            raise TaskQueueError(f"unknown task status: {value}")
        return value

    @staticmethod
    def _new_task_id(task_type: str) -> str:
        return f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{task_type}-{uuid.uuid4().hex[:8]}"

    @contextmanager
    def _workspace_root(self) -> Iterator[None]:
        original_root = core_paths.ROOT
        if self.workspace_path.resolve() == original_root.resolve():
            yield
            return
        core_paths.configure_root(self.workspace_path)
        try:
            yield
        finally:
            core_paths.configure_root(original_root)


class TaskExecutionError(Exception):
    """Task execution failed but the queue can persist the error safely."""


class UnsupportedTaskTypeError(TaskExecutionError):
    """Task exists only as a future placeholder and is blocked in this baseline."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code
