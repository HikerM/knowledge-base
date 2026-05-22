#!/usr/bin/env python3
"""AI persistence bootstrap service tests."""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.persistence_service import (  # noqa: E402
    AIPersistenceServiceError,
    AIStorageBootstrapService,
)
from knowledge_app.services.workspace_status_service import WorkspaceStatusService  # noqa: E402


def expect_service_error(callable_) -> None:
    try:
        callable_()
    except AIPersistenceServiceError:
        return
    raise AssertionError("expected AIPersistenceServiceError")


def relative_tree(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def assert_plan_is_dry_run_and_does_not_write() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        service = AIStorageBootstrapService()
        plan = service.plan_bootstrap(workspace)
        payload = plan.to_dict()
        if payload["dry_run"] is not True:
            raise AssertionError("bootstrap plan must be dry_run=true")
        if payload["would_modify"] is not False:
            raise AssertionError("bootstrap plan must be would_modify=false")
        if payload["plan_first"] is not True:
            raise AssertionError("bootstrap plan must be plan_first=true")
        if (workspace / "ai").exists():
            raise AssertionError("plan_bootstrap must not create workspace/ai")


def assert_bootstrap_requires_confirmation() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        service = AIStorageBootstrapService()
        expect_service_error(lambda: service.bootstrap_storage(workspace, confirmed=False))
        if (workspace / "ai").exists():
            raise AssertionError("unconfirmed bootstrap must not create workspace/ai")


def assert_bootstrap_creates_only_allowed_layout() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        service = AIStorageBootstrapService()
        manifest = service.bootstrap_storage(workspace, confirmed=True)

        expected = [
            "ai",
            "ai/conversations",
            "ai/drafts",
            "ai/indexes",
            "ai/manifest.json",
            "ai/memory",
        ]
        actual = relative_tree(workspace)
        if actual != expected:
            raise AssertionError(f"bootstrap created unexpected paths: {actual}")
        if list((workspace / "ai" / "conversations").iterdir()):
            raise AssertionError("bootstrap must not create conversation files")
        if list((workspace / "ai" / "memory").iterdir()):
            raise AssertionError("bootstrap must not create memory files")
        if (workspace / ".kb").exists():
            raise AssertionError("bootstrap must not create .kb")
        if (workspace / "knowledge").exists():
            raise AssertionError("bootstrap must not write knowledge/")
        payload = manifest.to_dict()
        if payload["created_at"] is None:
            raise AssertionError("bootstrap manifest must include created_at")
        if payload["directories"]["indexes"] != "ai/indexes/":
            raise AssertionError("bootstrap manifest must include ai/indexes directory")
        if payload["derived_indexes"]["rebuildable"] is not True:
            raise AssertionError("bootstrap manifest indexes must be rebuildable")
        if payload["backup_defaults"]["include_ai_conversations"] is not False:
            raise AssertionError("backup defaults must exclude AI conversations")
        if payload["privacy_defaults"]["long_term_memory_requires_confirmation"] is not True:
            raise AssertionError("privacy defaults must require memory confirmation")


def assert_existing_valid_manifest_can_be_read() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        service = AIStorageBootstrapService()
        first = service.bootstrap_storage(workspace, confirmed=True).to_dict()
        second = service.bootstrap_storage(workspace, confirmed=True).to_dict()
        if second != first:
            raise AssertionError("existing valid manifest should be read without overwrite")


def assert_corrupt_manifest_blocked() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "workspace"
        (workspace / "ai").mkdir(parents=True)
        (workspace / "ai" / "manifest.json").write_text("{not json", encoding="utf-8")
        service = AIStorageBootstrapService()
        expect_service_error(lambda: service.bootstrap_storage(workspace, confirmed=True))


def assert_workspace_root_must_exist() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "missing"
        service = AIStorageBootstrapService()
        expect_service_error(lambda: service.plan_bootstrap(workspace))
        expect_service_error(lambda: service.bootstrap_storage(workspace, confirmed=True))


def assert_startup_status_does_not_bootstrap_ai() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-bootstrap-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        result = WorkspaceStatusService(workspace).get_status()
        if result.data is None:
            raise AssertionError("workspace status returned no data")
        if (workspace / "ai").exists():
            raise AssertionError("workspace status must not bootstrap AI storage")


def assert_no_forbidden_imports() -> None:
    forbidden = {"sqlite3", "subprocess", "knowledge_core"}
    for relative_path in [
        "knowledge_app/ai/persistence_io.py",
        "knowledge_app/ai/persistence_service.py",
    ]:
        source = (SOURCE_ROOT / relative_path).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if not re.match(r"^(import|from)\s+", stripped):
                continue
            for name in forbidden:
                if re.search(rf"\b{name}\b", stripped):
                    raise AssertionError(f"{relative_path} imports forbidden dependency {name}: {stripped}")


def main() -> int:
    assert_plan_is_dry_run_and_does_not_write()
    assert_bootstrap_requires_confirmation()
    assert_bootstrap_creates_only_allowed_layout()
    assert_existing_valid_manifest_can_be_read()
    assert_corrupt_manifest_blocked()
    assert_workspace_root_must_exist()
    assert_startup_status_does_not_bootstrap_ai()
    assert_no_forbidden_imports()

    print("AI persistence bootstrap tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
