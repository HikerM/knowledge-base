"""Secret scanning patterns and helpers."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from . import paths


SECRET_SCAN_EXCLUDED_DIRS = {".git", ".kb", "__pycache__", ".venv", "tmp", "exports"}
SECRET_SCAN_ALLOW_MARKER = "TEST_ONLY_SECRET_PATTERN"
SECRET_SCAN_BINARY_EXTENSIONS = {
    ".db",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".webp",
    ".zip",
}
SECRET_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b|github_pat_[A-Za-z0-9_]{20,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("api_key_assignment", re.compile(r"(?i)\b(?:api[_-]?key|apikey)\b\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=-]{20,})")),
    ("password_assignment", re.compile(r"(?i)\bpassword\b\s*[:=]\s*[\"']?([^\"'\s]{8,})")),
    ("secret_assignment", re.compile(r"(?i)\bsecret\b\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=-]{12,})")),
]


def should_skip_secret_scan_path(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(paths.ROOT.resolve())
    except ValueError:
        return True
    if any(part in SECRET_SCAN_EXCLUDED_DIRS for part in rel.parts):
        return True
    suffixes = {suffix.lower() for suffix in path.suffixes}
    if suffixes & SECRET_SCAN_BINARY_EXTENSIONS:
        return True
    return False


def redact_secret(value: str) -> str:
    value = value.strip()
    if len(value) <= 10:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def secret_scan_files() -> Iterable[Path]:
    return (
        path
        for path in paths.ROOT.rglob("*")
        if path.is_file() and not should_skip_secret_scan_path(path)
    )


def run_secret_scan(limit: int = 200) -> Dict[str, Any]:
    start = time.perf_counter()
    findings: List[Dict[str, Any]] = []
    scanned_files = 0

    for path in secret_scan_files():
        scanned_files += 1
        rel_path = paths.to_relative_posix(path)
        if path.name == ".env" or (path.name.startswith(".env.") and path.name not in {".env.example", ".env.sample"}):
            findings.append(
                {
                    "path": rel_path,
                    "line": 0,
                    "kind": "env_file",
                    "risk": "high",
                    "match": path.name,
                }
            )
            continue

        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if SECRET_SCAN_ALLOW_MARKER in line:
                        continue
                    for kind, pattern in SECRET_PATTERNS:
                        match = pattern.search(line)
                        if not match:
                            continue
                        findings.append(
                            {
                                "path": rel_path,
                                "line": line_no,
                                "kind": kind,
                                "risk": "high",
                                "match": redact_secret(match.group(0)),
                            }
                        )
                        break
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            findings.append(
                {
                    "path": rel_path,
                    "line": 0,
                    "kind": "read_error",
                    "risk": "low",
                    "match": str(exc),
                }
            )

    high_risk = [finding for finding in findings if finding["risk"] == "high"]
    return {
        "scanned_files": scanned_files,
        "findings_count": len(findings),
        "high_risk_count": len(high_risk),
        "findings": findings[:limit],
        "truncated": len(findings) > limit,
        "allow_marker": SECRET_SCAN_ALLOW_MARKER,
        "elapsed_ms": int((time.perf_counter() - start) * 1000),
    }

