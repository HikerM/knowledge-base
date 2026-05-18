#!/usr/bin/env python3
"""Governance smoke tests for dedupe/conflicts.

Uses a temporary knowledge base root and does not touch the real knowledge/ tree.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
KB_PATH = REPO_ROOT / "scripts" / "kb.py"


def load_kb_module() -> Any:
    spec = importlib.util.spec_from_file_location("kb_module", KB_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load kb.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_temp_root(kb: Any, root: Path) -> None:
    if hasattr(kb, "configure_core_root"):
        kb.configure_core_root(root)
        return
    kb.ROOT = root
    kb.KNOWLEDGE_DIR = root / "knowledge"
    kb.CONFIG_DIR = root / "config"
    kb.TEMPLATES_DIR = root / "templates"
    kb.REPORTS_DIR = root / "reports"
    kb.KB_DIR = root / ".kb"
    kb.DB_PATH = kb.KB_DIR / "index.sqlite"


def run_cli(kb: Any, args: List[str]) -> Dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = kb.main(args)
    if code != 0:
        raise AssertionError(f"command failed: {' '.join(args)}\nstdout={stdout.getvalue()}\nstderr={stderr.getvalue()}")
    text = stdout.getvalue().strip()
    return json.loads(text) if text.startswith("{") else {"output": text}


def write_rule(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
title: "{title}"
category: frontend
type: rule
status: active
confidence: high
source_type: official
source_url: "https://react.dev/learn/managing-state"
created_at: "2026-05-18T00:00:00"
last_reviewed: "2026-05-18"
reviewed_by: "test"
reviewed_at: "2026-05-18T00:00:00"
valid_for: ["react"]
not_valid_for: []
project_scope: "test"
topic_id: "frontend.react-state"
canonical_id: ""
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: "test fixture"
review_required: false
review_cycle_days: 180
---

{body}
""",
        encoding="utf-8",
    )


def main() -> None:
    kb = load_kb_module()
    with tempfile.TemporaryDirectory(prefix="kb-governance-") as tmp:
        root = Path(tmp)
        configure_temp_root(kb, root)
        run_cli(kb, ["init"])

        body = "# React State Rule\n\n必须集中管理跨组件共享状态，并避免重复来源规则。"
        write_rule(root / "knowledge" / "01-frontend" / "rules" / "react-state-a.md", "React State Rule", body)
        write_rule(root / "knowledge" / "01-frontend" / "rules" / "react-state-b.md", "React State Rule", body)

        index = run_cli(kb, ["index"])
        assert index["indexed"] == 2, index

        dedupe = run_cli(kb, ["dedupe"])
        kinds = {group["kind"] for group in dedupe["duplicate_groups"]}
        assert {"source_url", "normalized_title", "content_hash", "topic_id"} <= kinds, dedupe

        conflicts = run_cli(kb, ["conflicts"])
        conflict_kinds = {item["kind"] for item in conflicts["results"]}
        assert "multiple_active_rules_same_topic_id" in conflict_kinds, conflicts


if __name__ == "__main__":
    main()
    print("governance tests passed")
