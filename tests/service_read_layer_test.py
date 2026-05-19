#!/usr/bin/env python3
"""Service-layer smoke tests for SQLite-hot read paths."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


SOURCE_ROOT = Path(__file__).resolve().parents[1]

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_core import paths as core_paths
from knowledge_app.services.archive_metadata_service import ArchiveMetadataService
from knowledge_app.services.category_service import CategoryService
from knowledge_app.services.document_service import DocumentService
from knowledge_app.services.review_queue_service import ReviewQueueService
from knowledge_app.services.search_service import SearchService


def run(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != expect:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Expected: {expect}, got: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_json(cmd: list[str], cwd: Path, expect: int = 0) -> dict:
    proc = run(cmd, cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout}") from exc


def copy_project(dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".kb", "__pycache__", "*.pyc", "reports", "knowledge")
    shutil.copytree(SOURCE_ROOT, dst, ignore=ignore)


def copy_fixture(project: Path, fixture_name: str, relative_target: str) -> Path:
    src = SOURCE_ROOT / "tests" / "fixtures" / fixture_name
    dst = project / relative_target
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def write_extra_document(project: Path, relative_target: str, title: str, layer: str, status: str = "experimental") -> Path:
    dst = project / relative_target
    dst.parent.mkdir(parents=True, exist_ok=True)
    category = "frontend"
    dst.write_text(
        f"""---
title: {title}
category: {category}
type: rule
status: {status}
confidence: medium
source_type: internal_practice
source_url: "https://example.com/service-read-layer/{title.lower().replace(' ', '-')}"
created_at: "2026-05-19T00:00:00"
last_reviewed: ""
reviewed_by: ""
valid_for: ["service-read-layer"]
not_valid_for: []
project_scope: "tests"
topic_id: "service.read.{layer}"
canonical_id: ""
source_hash: ""
content_hash: ""
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: "{'service quarantine fixture' if layer == 'quarantine' else ''}"
risk_level: medium
verification_method: ""
review_required: true
review_cycle_days: 180
---

# {title}

Service read layer fixture for {layer} metadata listing.
""",
        encoding="utf-8",
        newline="\n",
    )
    return dst


def with_project_root(project: Path, func: Callable[[], None]) -> None:
    original_root = core_paths.ROOT
    core_paths.configure_root(project)
    try:
        func()
    finally:
        core_paths.configure_root(original_root)


def assert_no_markdown_touch(project: Path, func: Callable[[], None]) -> None:
    original_rglob = Path.rglob
    original_read_text = Path.read_text
    original_sha256 = hashlib.sha256
    knowledge_dir = (project / "knowledge").resolve()

    def blocked_rglob(self: Path, pattern: str):
        if self.resolve() == knowledge_dir:
            raise AssertionError("service must not scan knowledge/")
        return original_rglob(self, pattern)

    def blocked_read_text(self: Path, *args, **kwargs):
        if self.suffix.lower() in {".md", ".markdown"}:
            raise AssertionError(f"service must not read Markdown: {self}")
        return original_read_text(self, *args, **kwargs)

    def blocked_sha256(*args, **kwargs):
        raise AssertionError("service must not hash files")

    Path.rglob = blocked_rglob
    Path.read_text = blocked_read_text
    hashlib.sha256 = blocked_sha256
    try:
        func()
    finally:
        Path.rglob = original_rglob
        Path.read_text = original_read_text
        hashlib.sha256 = original_sha256


def assert_document_open_reads_one_markdown(project: Path, relative_path: str) -> None:
    original_rglob = Path.rglob
    original_read_text = Path.read_text
    original_sha256 = hashlib.sha256
    knowledge_dir = (project / "knowledge").resolve()
    expected_path = (project / relative_path).resolve()
    reads: list[Path] = []

    def blocked_rglob(self: Path, pattern: str):
        if self.resolve() == knowledge_dir:
            raise AssertionError("document open must not scan knowledge/")
        return original_rglob(self, pattern)

    def counted_read_text(self: Path, *args, **kwargs):
        if self.suffix.lower() in {".md", ".markdown"}:
            resolved = self.resolve()
            reads.append(resolved)
            if resolved != expected_path:
                raise AssertionError(f"document open read unexpected Markdown: {self}")
            if len(reads) > 1:
                raise AssertionError(f"document open read more than one Markdown file: {reads}")
        return original_read_text(self, *args, **kwargs)

    def blocked_sha256(*args, **kwargs):
        raise AssertionError("document open must not hash files")

    Path.rglob = blocked_rglob
    Path.read_text = counted_read_text
    hashlib.sha256 = blocked_sha256
    try:
        result = DocumentService().open_document(path=relative_path)
        if not result.success or not result.data:
            raise AssertionError(f"document open failed: {result}")
        if "Fixture Security Rule" not in result.data["body"]:
            raise AssertionError(f"document open returned wrong body: {result.data}")
        if reads != [expected_path]:
            raise AssertionError(f"document open should read exactly one Markdown file: {reads}")
    finally:
        Path.rglob = original_rglob
        Path.read_text = original_read_text
        hashlib.sha256 = original_sha256


def assert_direct_services(project: Path, security_path: str) -> None:
    def checks() -> None:
        def read_only_checks() -> None:
            search = SearchService().search("input validation", top_k=5)
            if not search.success or not search.data or not search.data.results:
                raise AssertionError(f"SearchService returned no results: {search}")
            if any(item["layer"] in {"raw", "distilled", "deprecated", "quarantine"} for item in search.data.results):
                raise AssertionError(f"SearchService default search returned non-formal results: {search.data.results}")

            categories = CategoryService().list_categories()
            if not categories.success or not categories.data:
                raise AssertionError(f"CategoryService failed: {categories}")
            by_id = {item["category_id"]: item for item in categories.data["results"]}
            if by_id["security"]["document_count"] != 1:
                raise AssertionError(f"CategoryService did not count indexed security doc: {by_id['security']}")
            if by_id["product"]["document_count"] != 0:
                raise AssertionError(f"CategoryService should include zero-count config categories: {by_id['product']}")

            first_page = ReviewQueueService().list_review_queue(limit=1, offset=0)
            second_page = ReviewQueueService().list_review_queue(limit=1, offset=1)
            if not first_page.success or not second_page.success:
                raise AssertionError(f"ReviewQueueService pagination failed: {first_page} {second_page}")
            if first_page.data["total"] < 2 or second_page.data["total"] < 2:
                raise AssertionError(f"ReviewQueueService expected at least two review items: {first_page.data}")
            if first_page.data["results"][0]["path"] == second_page.data["results"][0]["path"]:
                raise AssertionError("ReviewQueueService offset did not advance the page")

            archived = ArchiveMetadataService().list_archived()
            deprecated = ArchiveMetadataService().list_deprecated()
            quarantine = ArchiveMetadataService().list_quarantine()
            if not archived.success or archived.data["total"] != 1:
                raise AssertionError(f"ArchiveMetadataService archived listing failed: {archived}")
            if not deprecated.success or deprecated.data["total"] != 1:
                raise AssertionError(f"ArchiveMetadataService deprecated listing failed: {deprecated}")
            if not quarantine.success or quarantine.data["total"] != 1:
                raise AssertionError(f"ArchiveMetadataService quarantine listing failed: {quarantine}")

        assert_no_markdown_touch(project, read_only_checks)
        assert_document_open_reads_one_markdown(project, security_path)

    with_project_root(project, checks)


def assert_cli_wrappers(project: Path, security_path: str) -> None:
    search = run_json([sys.executable, "scripts/kb.py", "search-service", "--query", "input validation"], project)
    if not search["results"]:
        raise AssertionError(f"search-service returned no results: {search}")

    categories = run_json([sys.executable, "scripts/kb.py", "category-summary"], project)
    if not any(item["category_id"] == "security" for item in categories["results"]):
        raise AssertionError(f"category-summary missing security category: {categories}")

    review = run_json([sys.executable, "scripts/kb.py", "review-queue-list", "--limit", "1", "--offset", "0"], project)
    if review["count"] != 1 or review["total"] < 2:
        raise AssertionError(f"review-queue-list pagination output unexpected: {review}")

    archived = run_json([sys.executable, "scripts/kb.py", "archive-list"], project)
    if archived["kind"] != "archived" or archived["total"] != 1:
        raise AssertionError(f"archive-list default output unexpected: {archived}")

    document = run_json([sys.executable, "scripts/kb.py", "document-open", "--path", security_path], project)
    if document["path"] != security_path or "Fixture Security Rule" not in document["body"]:
        raise AssertionError(f"document-open returned unexpected payload: {document}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-service-read-layer-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        run_json([sys.executable, "scripts/kb.py", "init"], project)

        security_path = "knowledge/08-security/rules/fixture-security-rule.md"
        copy_fixture(project, "security-rule.md", security_path)
        copy_fixture(project, "frontend-raw.md", "knowledge/01-frontend/raw/fixture-frontend-raw.md")
        copy_fixture(project, "ui-ux-distilled.md", "knowledge/03-ui-ux/distilled/fixture-ui-ux-distilled.md")
        copy_fixture(project, "deprecated-rule.md", "knowledge/02-backend/deprecated/fixture-deprecated-rule.md")
        write_extra_document(project, "knowledge/01-frontend/archive/service-archived.md", "Service Archived", "archive")
        write_extra_document(project, "knowledge/01-frontend/quarantine/service-quarantine.md", "Service Quarantine", "quarantine")

        index = run_json([sys.executable, "scripts/kb.py", "index"], project)
        if index["indexed"] != 6:
            raise AssertionError(f"expected six indexed fixtures: {index}")

        assert_direct_services(project, security_path)
        assert_cli_wrappers(project, security_path)

    print("service read layer tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
