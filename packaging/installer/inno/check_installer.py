#!/usr/bin/env python3
"""Validate the Inno Setup installer output and installer script boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALLER_DIR = REPO_ROOT / "packaging" / "installer"
OUTPUT_DIR = INSTALLER_DIR / "output"
INSTALLER_PATH = OUTPUT_DIR / "PersonalKnowledgeBase-Setup-v2.0.0-rc.1.exe"
ISS_PATH = INSTALLER_DIR / "inno" / "pkb-gui.iss"
DIST_DIR = REPO_ROOT / "dist" / "pkb-gui"
DIST_EXE = DIST_DIR / "pkb-gui.exe"
INTERNAL_DIR = DIST_DIR / "_internal"
FORBIDDEN_DIST_NAMES = {"knowledge", ".kb", "backups", ".git", "tmp", "exports", "__pycache__"}
FORBIDDEN_SOURCE_FRAGMENTS = (
    "\\knowledge\\",
    "/knowledge/",
    "\\.kb\\",
    "/.kb/",
    "\\backups\\",
    "/backups/",
    "\\.git\\",
    "/.git/",
    "\\tmp\\",
    "/tmp/",
    "\\exports\\",
    "/exports/",
)


def check(condition: bool, name: str, details: dict[str, Any], errors: list[str], message: str) -> None:
    details[name] = condition
    if not condition:
        errors.append(message)


def source_lines(script_text: str) -> list[str]:
    return [line.strip() for line in script_text.splitlines() if line.strip().lower().startswith("source:")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-installer", action="store_true")
    args = parser.parse_args(argv)

    errors: list[str] = []
    details: dict[str, Any] = {}

    installer_exists = INSTALLER_PATH.exists()
    check(
        installer_exists or args.allow_missing_installer,
        "installer_exists",
        details,
        errors,
        f"installer is missing: {INSTALLER_PATH}",
    )
    if installer_exists:
        installer_size = INSTALLER_PATH.stat().st_size
        details["installer_size_bytes"] = installer_size
        check(installer_size > 1_000_000, "installer_size_reasonable", details, errors, "installer size is too small")
    else:
        details["installer_size_bytes"] = 0
        details["installer_size_reasonable"] = bool(args.allow_missing_installer)

    check(INSTALLER_PATH.name == "PersonalKnowledgeBase-Setup-v2.0.0-rc.1.exe", "installer_filename", details, errors, "installer filename is incorrect")
    check(DIST_DIR.exists() and DIST_DIR.is_dir(), "dist_dir_exists", details, errors, f"dist directory is missing: {DIST_DIR}")
    check(DIST_EXE.exists(), "dist_exe_exists", details, errors, f"dist executable is missing: {DIST_EXE}")
    check(INTERNAL_DIR.exists() and INTERNAL_DIR.is_dir(), "dist_one_folder", details, errors, "dist is not a one-folder PyInstaller output")

    bundled_names = {path.name for path in DIST_DIR.rglob("*")} if DIST_DIR.exists() else set()
    forbidden_dist = sorted(FORBIDDEN_DIST_NAMES & bundled_names)
    details["forbidden_dist_entries"] = forbidden_dist
    check(not forbidden_dist, "dist_has_no_workspace_runtime_data", details, errors, f"dist contains forbidden runtime data: {forbidden_dist}")

    check(ISS_PATH.exists(), "iss_exists", details, errors, f"Inno script is missing: {ISS_PATH}")
    script_text = ISS_PATH.read_text(encoding="utf-8") if ISS_PATH.exists() else ""
    normalized_script = script_text.replace("/", "\\").lower()
    forbidden_script_fragments = [item for item in FORBIDDEN_SOURCE_FRAGMENTS if item.replace("/", "\\").lower() in normalized_script]
    details["forbidden_script_fragments"] = forbidden_script_fragments
    check(not forbidden_script_fragments, "iss_has_no_workspace_paths", details, errors, f"Inno script includes forbidden workspace path fragments: {forbidden_script_fragments}")

    sources = source_lines(script_text)
    details["source_lines"] = sources
    check(bool(sources), "iss_has_sources", details, errors, "Inno script has no Source entries")
    check(all("{#DistDir}" in line for line in sources), "iss_sources_only_dist", details, errors, "Inno Source entries must use the PyInstaller dist directory only")
    check(all("localappdata" not in line.lower() for line in sources), "iss_sources_not_localappdata", details, errors, "Inno Source entries must not include LocalAppData")
    check(all("build" not in line.lower() for line in sources), "iss_sources_not_build", details, errors, "Inno Source entries must not include build output")

    runtime_files_in_install_dir = [
        path.name
        for path in (DIST_DIR.rglob("*") if DIST_DIR.exists() else [])
        if path.name in {"gui-settings.json", "pkb-gui.log"}
    ]
    details["runtime_files_in_dist"] = runtime_files_in_install_dir
    check(not runtime_files_in_install_dir, "dist_has_no_user_settings_or_logs", details, errors, "dist contains user settings or logs")

    result = {
        "ok": not errors,
        "installer_path": str(INSTALLER_PATH),
        "dist_path": str(DIST_DIR),
        "script_path": str(ISS_PATH),
        "checks": details,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
