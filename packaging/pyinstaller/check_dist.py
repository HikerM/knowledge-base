#!/usr/bin/env python3
"""Validate the PyInstaller one-folder output without launching it."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist" / "pkb-gui"
EXE_PATH = DIST_DIR / "pkb-gui.exe"
INTERNAL_DIR = DIST_DIR / "_internal"
FORBIDDEN_NAMES = {"knowledge", ".kb", "backups", ".git", "tmp", "exports", "__pycache__"}


def main() -> int:
    assert DIST_DIR.exists(), f"dist directory is missing: {DIST_DIR}"
    assert EXE_PATH.exists(), f"GUI executable is missing: {EXE_PATH}"
    assert INTERNAL_DIR.exists(), "one-folder _internal directory is missing"
    assert (INTERNAL_DIR / "assets" / "app-icon" / "app-icon.png").exists(), "runtime PNG icon is missing from _internal"
    assert (INTERNAL_DIR / "assets" / "app-icon" / "app-icon.ico").exists(), "runtime ICO icon is missing from _internal"

    bundled_names = {path.name for path in DIST_DIR.rglob("*")}
    forbidden_found = sorted(FORBIDDEN_NAMES & bundled_names)
    assert not forbidden_found, f"dist must not bundle workspace/runtime data: {forbidden_found}"

    assert not (DIST_DIR / "gui-settings.json").exists(), "GUI settings must not be written to install dir"
    assert not (DIST_DIR / "pkb-gui.log").exists(), "GUI log must not be written to install dir"
    print("pyinstaller dist checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
