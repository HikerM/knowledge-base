#!/usr/bin/env python3
"""Local release smoke test for the packaged Windows EXE."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXE_PATH = REPO_ROOT / "dist" / "pkb-gui" / "pkb-gui.exe"


def _run_exe(workspace: Path | None, local_app_data: Path, cwd: Path | None = None) -> None:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local_app_data)
    env["PKB_GUI_AUTO_CLOSE_MS"] = "2500"
    command = [str(EXE_PATH)]
    if workspace is not None:
        command.extend(["--workspace", str(workspace)])
    result = subprocess.run(
        command,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, f"EXE returned {result.returncode}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    assert EXE_PATH.exists(), f"EXE not found: {EXE_PATH}"

    with tempfile.TemporaryDirectory(prefix="pkb-exe-smoke-") as tmp:
        tmp_root = Path(tmp)
        local_app_data = tmp_root / "LocalAppData"
        first_run_local_app_data = tmp_root / "FirstRunLocalAppData"
        empty_workspace = tmp_root / "empty-workspace"
        first_run_cwd = tmp_root / "first-run-cwd"
        empty_workspace.mkdir()
        first_run_cwd.mkdir()

        _run_exe(None, first_run_local_app_data, cwd=first_run_cwd)
        _run_exe(args.workspace.resolve(), local_app_data)
        _run_exe(empty_workspace, local_app_data)

        settings_path = local_app_data / "PersonalKnowledgeBase" / "settings" / "gui-settings.json"
        first_run_settings_path = first_run_local_app_data / "PersonalKnowledgeBase" / "settings" / "gui-settings.json"
        log_path = local_app_data / "PersonalKnowledgeBase" / "logs" / "pkb-gui.log"
        assert settings_path.exists(), f"GUI settings were not written to LocalAppData: {settings_path}"
        assert first_run_settings_path.exists(), f"first-run GUI settings were not written to LocalAppData: {first_run_settings_path}"
        assert log_path.exists(), f"GUI log was not written to LocalAppData: {log_path}"
        assert not (empty_workspace / ".kb").exists(), "empty workspace must not get .kb during startup"
        assert not (first_run_cwd / ".kb").exists(), "first-run without --workspace must not create .kb in cwd"
        assert not (REPO_ROOT / "dist" / "pkb-gui" / "gui-settings.json").exists(), "install dir must not contain GUI settings"
        assert not (REPO_ROOT / "dist" / "pkb-gui" / "pkb-gui.log").exists(), "install dir must not contain GUI logs"

    print("packaged EXE smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
