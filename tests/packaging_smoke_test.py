#!/usr/bin/env python3
"""Static checks for the PyInstaller one-folder packaging spike."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


SPEC_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "pkb-gui.spec"
README_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "README.md"
REQUIREMENTS_PATH = SOURCE_ROOT / "requirements.txt"
ENTRYPOINT_PATH = SOURCE_ROOT / "gui" / "app.py"


def main() -> int:
    assert SPEC_PATH.exists(), "PyInstaller spec is missing"
    assert README_PATH.exists(), "packaging README is missing"
    assert ENTRYPOINT_PATH.exists(), "GUI entrypoint is missing"

    spec = SPEC_PATH.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT_PATH.read_text(encoding="utf-8")
    requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")

    assert "PySide6" in requirements, "requirements.txt must include PySide6"
    assert "spec_dir = Path(SPECPATH).resolve()" in spec, "spec must resolve from its directory"
    assert "project_root = spec_dir.parents[1]" in spec, "spec must resolve repository root from packaging/pyinstaller"
    assert "gui\" / \"app.py" in spec, "spec must use gui/app.py as entrypoint"
    assert "COLLECT(" in spec, "spec must use one-folder COLLECT output"
    assert "collect_submodules(\"gui\")" in spec, "spec must include gui modules"
    assert "collect_submodules(\"knowledge_app\")" in spec, "spec must include knowledge_app modules"
    assert "collect_submodules(\"knowledge_core\")" in spec, "spec must include knowledge_core modules"
    assert "collect_data_files(\"PySide6\")" in spec, "spec must include PySide6 data files"
    assert "console=False" in spec, "GUI executable should be windowed"
    assert "--workspace" in entrypoint, "GUI entrypoint must support explicit workspace selection"
    assert "Path.cwd()" in entrypoint, "GUI entrypoint must default to the current working directory"
    assert "LOCALAPPDATA" in entrypoint, "GUI logs must default to a user-local data directory on Windows"

    forbidden_spec_tokens = [
        "knowledge/",
        "knowledge\\",
        ".kb",
        "backups",
        ".git",
        "__pycache__",
        "tmp/",
        "tmp\\",
        "exports",
    ]
    for token in forbidden_spec_tokens:
        assert token not in spec, f"spec must not bundle workspace/runtime data token: {token}"

    required_readme_phrases = [
        "one-folder",
        "not an installer",
        "--workspace",
        "current working directory",
        "Startup contract",
        "does not build a one-file executable",
        "does not require Git",
    ]
    for phrase in required_readme_phrases:
        assert phrase in readme, f"README missing required packaging note: {phrase}"

    print("packaging smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
