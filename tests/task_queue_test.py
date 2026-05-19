#!/usr/bin/env python3
"""TaskQueue baseline tests."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict


SOURCE_ROOT = Path(__file__).resolve().parents[1]

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.models.task_models import ProgressEvent, TaskRecord, TaskResult, TaskStatus, TaskType
from knowledge_app.services.task_queue_service import TaskQueueService


TASK_RECORD_KEYS = {
    "schema_version",
    "task_id",
    "task_type",
    "status",
    "title",
    "description",
    "created_at",
    "started_at",
    "finished_at",
    "progress_percent",
    "progress_message",
    "cancellable",
    "cancel_requested",
    "input",
    "result_summary",
    "error",
    "log_path",
    "elapsed_ms",
    "warnings",
    "metadata",
}

PROGRESS_EVENT_KEYS = {"task_id", "timestamp", "progress_percent", "message", "current_step", "detail"}

TASK_RESULT_KEYS = {
    "schema_version",
    "success",
    "task_id",
    "status",
    "result",
    "warnings",
    "errors",
    "elapsed_ms",
}


def run(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != expect:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Expected: {expect}, got: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_json(cmd: list[str], cwd: Path, expect: int = 0) -> Dict[str, Any]:
    proc = run(cmd, cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout}") from exc


def copy_project(dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".kb", "backups", "__pycache__", "*.pyc", "reports")
    shutil.copytree(SOURCE_ROOT, dst, ignore=ignore)


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def assert_task_record_schema(record: Dict[str, Any]) -> None:
    if set(record) != TASK_RECORD_KEYS:
        raise AssertionError(f"TaskRecord schema changed: {sorted(record)}")
    if record["status"] not in {item.value for item in TaskStatus}:
        raise AssertionError(f"unknown task status: {record}")
    if record["task_type"] not in {item.value for item in TaskType}:
        raise AssertionError(f"unknown task type: {record}")
    if not isinstance(record["input"], dict) or not isinstance(record["metadata"], dict):
        raise AssertionError(f"TaskRecord mapping fields should be dicts: {record}")
    if not isinstance(record["warnings"], list):
        raise AssertionError(f"TaskRecord warnings should be a list: {record}")


def assert_model_schemas() -> None:
    record = TaskRecord(task_id="schema", created_at="2026-05-19T00:00:00Z", log_path=".kb/tasks/schema/task.log")
    event = ProgressEvent(task_id="schema", timestamp="2026-05-19T00:00:00Z", progress_percent=1)
    result = TaskResult(success=True, task_id="schema", status=TaskStatus.SUCCEEDED.value)
    if set(record.to_dict()) != TASK_RECORD_KEYS:
        raise AssertionError(f"TaskRecord keys changed: {record.to_dict()}")
    if set(event.to_dict()) != PROGRESS_EVENT_KEYS:
        raise AssertionError(f"ProgressEvent keys changed: {event.to_dict()}")
    if set(result.to_dict()) != TASK_RESULT_KEYS:
        raise AssertionError(f"TaskResult keys changed: {result.to_dict()}")


def assert_no_markdown_touch(project: Path, func: Callable[[], None]) -> None:
    original_rglob = Path.rglob
    original_read_text = Path.read_text
    original_sha256 = hashlib.sha256
    knowledge_dir = (project / "knowledge").resolve()

    def blocked_rglob(self: Path, pattern: str):
        if self.resolve() == knowledge_dir:
            raise AssertionError("workspace_status task must not scan knowledge/")
        return original_rglob(self, pattern)

    def blocked_read_text(self: Path, *args, **kwargs):
        if self.suffix.lower() in {".md", ".markdown"}:
            raise AssertionError(f"workspace_status task must not read Markdown: {self}")
        return original_read_text(self, *args, **kwargs)

    def blocked_sha256(*args, **kwargs):
        raise AssertionError("workspace_status task must not hash files")

    Path.rglob = blocked_rglob
    Path.read_text = blocked_read_text
    hashlib.sha256 = blocked_sha256
    try:
        func()
    finally:
        Path.rglob = original_rglob
        Path.read_text = original_read_text
        hashlib.sha256 = original_sha256


def assert_ignored_paths(project: Path) -> None:
    gitignore = (project / ".gitignore").read_text(encoding="utf-8")
    if ".kb/" not in gitignore and ".kb/tasks/" not in gitignore:
        raise AssertionError(".kb/tasks must be covered by .gitignore")
    if "backups/" not in gitignore:
        raise AssertionError("backups/ must be covered by .gitignore")


def task_log_path(project: Path, task_id: str) -> Path:
    return project / ".kb" / "tasks" / task_id / "task.log"


def main() -> int:
    assert_model_schemas()
    with tempfile.TemporaryDirectory(prefix="pkb-task-queue-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        run_json([sys.executable, "scripts/kb.py", "init"], project)
        run_json([sys.executable, "scripts/kb.py", "index"], project)

        noop = run_json([sys.executable, "scripts/kb.py", "task-create", "--type", "noop", "--title", "Test noop"], project)
        assert_task_record_schema(noop)
        if noop["status"] != "pending" or noop["task_type"] != "noop":
            raise AssertionError(f"noop task should be pending: {noop}")

        pending = run_json([sys.executable, "scripts/kb.py", "task-list", "--status", "pending"], project)
        if noop["task_id"] not in {item["task_id"] for item in pending["results"]}:
            raise AssertionError(f"task-list did not include pending noop task: {pending}")

        noop_run = run_json([sys.executable, "scripts/kb.py", "task-run", "--task-id", noop["task_id"]], project)
        if not noop_run["success"] or noop_run["status"] != "succeeded":
            raise AssertionError(f"noop task did not succeed: {noop_run}")
        if set(noop_run) != TASK_RESULT_KEYS:
            raise AssertionError(f"TaskResult CLI schema changed: {noop_run}")

        noop_status = run_json([sys.executable, "scripts/kb.py", "task-status", "--task-id", noop["task_id"]], project)
        assert_task_record_schema(noop_status)
        if noop_status["status"] != "succeeded" or noop_status["progress_percent"] != 100:
            raise AssertionError(f"task-status should show succeeded noop: {noop_status}")
        if not task_log_path(project, noop["task_id"]).exists():
            raise AssertionError("noop task log was not created")

        pending_cancel = run_json(
            [sys.executable, "scripts/kb.py", "task-create", "--type", "noop", "--title", "Cancel pending"],
            project,
        )
        cancelled = run_json([sys.executable, "scripts/kb.py", "task-cancel", "--task-id", pending_cancel["task_id"]], project)
        if cancelled["status"] != "cancelled" or cancelled["cancel_requested"] is not True:
            raise AssertionError(f"pending task was not cancelled: {cancelled}")

        service = TaskQueueService(project)

        def run_workspace_status_task() -> None:
            record = service.create_task(TaskType.WORKSPACE_STATUS, "Workspace status", {})
            result = service.run_task(record.task_id)
            if not result.success or result.status != "succeeded":
                raise AssertionError(f"workspace_status task failed: {result.to_dict()}")
            status = service.get_task(record.task_id).result_summary["workspace_status"]
            if status["index_status"] != "ready" or status["document_count"] <= 0:
                raise AssertionError(f"workspace_status task returned unexpected status: {status}")

        assert_no_markdown_touch(project, run_workspace_status_task)

        backup_task = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "task-create",
                "--type",
                "backup_create",
                "--title",
                "Backup before mutation",
                "--reason",
                "task queue test",
            ],
            project,
        )
        backup_run = run_json([sys.executable, "scripts/kb.py", "task-run", "--task-id", backup_task["task_id"]], project)
        backup_path = Path(backup_run["result"].get("backup_path", ""))
        backup_root = (project / "backups").resolve()
        try:
            backup_path.resolve().relative_to(backup_root)
            backup_under_root = True
        except ValueError:
            backup_under_root = False
        if not backup_run["success"] or not backup_path.exists() or not backup_under_root:
            raise AssertionError(f"backup_create task did not create an ignored backup: {backup_run}")
        assert_ignored_paths(project)

        audit_task = run_json([sys.executable, "scripts/kb.py", "task-create", "--type", "audit", "--title", "Audit task"], project)
        audit_run = run_json([sys.executable, "scripts/kb.py", "task-run", "--task-id", audit_task["task_id"]], project)
        if not audit_run["success"] or "audit" not in audit_run["result"]:
            raise AssertionError(f"audit task failed: {audit_run}")

        before_index_hash = hash_tree(project / "knowledge")
        index_task = run_json([sys.executable, "scripts/kb.py", "task-create", "--type", "index", "--title", "Index task"], project)
        index_run = run_json([sys.executable, "scripts/kb.py", "task-run", "--task-id", index_task["task_id"]], project)
        after_index_hash = hash_tree(project / "knowledge")
        if not index_run["success"] or "index" not in index_run["result"]:
            raise AssertionError(f"index task failed: {index_run}")
        if before_index_hash != after_index_hash:
            raise AssertionError("index task modified knowledge/**/*.md")

        before_future_hash = hash_tree(project / "knowledge")
        before_backup_count = len(list((project / "backups").rglob("*.zip")))
        future = run_json(
            [sys.executable, "scripts/kb.py", "task-create", "--type", "future_archive", "--title", "Future archive"],
            project,
        )
        future_run = run_json([sys.executable, "scripts/kb.py", "task-run", "--task-id", future["task_id"]], project)
        after_future_hash = hash_tree(project / "knowledge")
        after_backup_count = len(list((project / "backups").rglob("*.zip")))
        if future_run["success"] is not False or future_run["status"] != "failed":
            raise AssertionError(f"future task should be blocked/unsupported: {future_run}")
        future_status = run_json([sys.executable, "scripts/kb.py", "task-status", "--task-id", future["task_id"]], project)
        if future_status["error"].get("code") != "unsupported_task_type":
            raise AssertionError(f"future task error should be unsupported_task_type: {future_status}")
        if before_future_hash != after_future_hash or before_backup_count != after_backup_count:
            raise AssertionError("unsupported future task performed a destructive operation")

        for task_id in [noop["task_id"], backup_task["task_id"], audit_task["task_id"], index_task["task_id"], future["task_id"]]:
            if not task_log_path(project, task_id).exists():
                raise AssertionError(f"task log missing for {task_id}")

    print("task queue tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
