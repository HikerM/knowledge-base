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
BUILD_SCRIPT_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "build.ps1"
CLEAN_SCRIPT_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "clean.ps1"
CHECK_DIST_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "check_dist.py"
EXE_SMOKE_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "exe_smoke.py"
VERSION_INFO_PATH = SOURCE_ROOT / "packaging" / "pyinstaller" / "version_info.txt"
ICON_PNG_PATH = SOURCE_ROOT / "assets" / "app-icon" / "app-icon.png"
ICON_ICO_PATH = SOURCE_ROOT / "assets" / "app-icon" / "app-icon.ico"
REQUIREMENTS_PATH = SOURCE_ROOT / "requirements.txt"
ENTRYPOINT_PATH = SOURCE_ROOT / "gui" / "app.py"


def main() -> int:
    assert SPEC_PATH.exists(), "PyInstaller spec is missing"
    assert README_PATH.exists(), "packaging README is missing"
    assert BUILD_SCRIPT_PATH.exists(), "build.ps1 is missing"
    assert CLEAN_SCRIPT_PATH.exists(), "clean.ps1 is missing"
    assert CHECK_DIST_PATH.exists(), "check_dist.py is missing"
    assert EXE_SMOKE_PATH.exists(), "exe_smoke.py is missing"
    assert VERSION_INFO_PATH.exists(), "version_info.txt is missing"
    assert ICON_PNG_PATH.exists(), "app-icon.png is missing"
    assert ICON_ICO_PATH.exists(), "app-icon.ico is missing"
    assert ENTRYPOINT_PATH.exists(), "GUI entrypoint is missing"

    spec = SPEC_PATH.read_text(encoding="utf-8")
    build_script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")
    clean_script = CLEAN_SCRIPT_PATH.read_text(encoding="utf-8")
    check_dist = CHECK_DIST_PATH.read_text(encoding="utf-8")
    exe_smoke = EXE_SMOKE_PATH.read_text(encoding="utf-8")
    version_info = VERSION_INFO_PATH.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT_PATH.read_text(encoding="utf-8")
    requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")

    assert "PySide6" in requirements, "requirements.txt must include PySide6"
    assert "spec_dir = Path(SPECPATH).resolve()" in spec, "spec must resolve from its directory"
    assert "project_root = spec_dir.parents[1]" in spec, "spec must resolve repository root from packaging/pyinstaller"
    assert "gui\" / \"app.py" in spec, "spec must use gui/app.py as entrypoint"
    assert "COLLECT(" in spec, "spec must use one-folder COLLECT output"
    assert "onefile" not in spec.lower(), "spec must not enable one-file mode"
    assert "version_info.txt" in spec, "spec must include Windows version info"
    assert "app-icon.ico" in spec, "spec must include the Windows application icon"
    assert "app-icon.png" in spec, "spec must include the runtime window icon"
    assert "icon=str(icon_path)" in spec, "EXE must use app-icon.ico"
    assert "collect_submodules(\"gui\")" in spec, "spec must include gui modules"
    assert "collect_submodules(\"knowledge_app\")" in spec, "spec must include knowledge_app modules"
    assert "collect_submodules(\"knowledge_core\")" in spec, "spec must include knowledge_core modules"
    assert "collect_data_files(\"PySide6\")" in spec, "spec must include PySide6 data files"
    assert "console=False" in spec, "GUI executable should be windowed"
    assert "--workspace" in entrypoint, "GUI entrypoint must support explicit workspace selection"
    assert "workspace_path = parsed.workspace.resolve() if parsed.workspace else None" in entrypoint, "GUI entrypoint must not default first-run to cwd"
    assert "MainWindow(workspace_path=workspace_path" in entrypoint, "GUI entrypoint must pass explicit or empty workspace state"
    assert "LOCALAPPDATA" in entrypoint, "GUI logs must default to a user-local data directory on Windows"
    assert "python -m PyInstaller" in build_script, "build script must run PyInstaller"
    assert "check_dist.py" in build_script, "build script must validate dist output"
    assert "Remove-Item" in clean_script and "dist" in clean_script and "build" in clean_script, "clean script must remove build/dist"
    assert "pkb-gui.exe" in check_dist, "dist checker must validate pkb-gui.exe"
    assert "LOCALAPPDATA" in exe_smoke, "EXE smoke must redirect LocalAppData"
    assert "gui-settings.json" in exe_smoke, "EXE smoke must validate GUI settings path"
    for field in ["ProductName", "FileDescription", "ProductVersion", "CompanyName"]:
        assert field in version_info, f"version info missing {field}"
    assert "Personal Knowledge Base" in version_info, "version info must use the product name"
    assert "2.0.0" in version_info, "version info must match the v2.0.0 final installer baseline"

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
        "workspace gate",
        "Startup contract",
        "does not build a one-file executable",
        "does not require Git",
        "GUI settings",
        "LocalAppData",
        "window size and position",
        "app-icon.ico",
        "checkerboard",
    ]
    for phrase in required_readme_phrases:
        assert phrase in readme, f"README missing required packaging note: {phrase}"

    print("packaging smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
