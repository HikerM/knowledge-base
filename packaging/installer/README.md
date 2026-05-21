# Windows installer spike

This directory contains the `v2.0.0-rc.2` Windows installer acceptance baseline for the PySide6 one-folder GUI. It builds on the `v2.0.0-rc.1` installer spike and remains a release-candidate installer, not the final public release.

## Technical choice

The installer uses Inno Setup 6 because it is simple, stable, supports per-user installs, supports silent install/uninstall smoke tests, does not require administrator privileges, and can install the existing PyInstaller one-folder output without switching to one-file packaging.

The installer keeps three locations separate:

- Install directory: program files under `%LOCALAPPDATA%\Programs\PersonalKnowledgeBase` by default.
- LocalAppData: GUI settings and logs under `%LOCALAPPDATA%\PersonalKnowledgeBase\`.
- Workspace: user-selected knowledge-base data, outside the install directory.

Uninstall removes only installed program files and shortcuts. It must not remove LocalAppData settings/logs or user workspaces.

## Prerequisites

Install packaging dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt pyinstaller
```

Install Inno Setup 6 and make sure `ISCC.exe` is available on `PATH`, or installed in one of the standard user or Program Files locations. If `ISCC` is missing, the build script reports a blocker and does not claim installer success.

## Build

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\installer\inno\clean_installer.ps1
powershell -ExecutionPolicy Bypass -File packaging\installer\inno\build_installer.ps1
```

`build_installer.ps1` first runs `packaging\pyinstaller\build.ps1`, verifies `dist\pkb-gui\pkb-gui.exe`, invokes `ISCC`, then runs `check_installer.py`.

The installer output is:

```text
packaging\installer\output\PersonalKnowledgeBase-Setup-v2.0.0-rc.2.exe
```

The output directory is ignored by Git.

## Checks

Static installer check:

```powershell
python packaging\installer\inno\check_installer.py
```

The check verifies that the installer exists, has the expected filename and non-trivial size, that `dist\pkb-gui` is still a one-folder app, and that the Inno source only installs the PyInstaller dist content. The Inno script excludes the PySide6 `objects-Debug` artifact under the dist tree because that development-only path can exceed Windows installer path limits and is not needed by the Qt Widgets GUI runtime.

Installer smoke:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\installer\inno\installer_smoke.ps1
```

The smoke test verifies silent install, launch with selected workspaces, empty workspace startup without `.kb` creation, service-level minimal workspace creation, uninstall, reinstall, LocalAppData preservation, and workspace preservation. It also launches the packaged app with Git and Python removed from `PATH` to verify they are not runtime requirements.

Manual checks still required for final common-user acceptance:

- Double-click wizard copy and visual flow on a clean ordinary Windows profile.
- First-run workspace picker wording and new-workspace wizard interaction with a human reviewer.
- Windows SmartScreen / unsigned-installer wording, because rc.2 is still unsigned.
