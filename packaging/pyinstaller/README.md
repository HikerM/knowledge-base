# PyInstaller one-folder GUI packaging hardening

This directory contains the `v2.0.0-beta.2` PyInstaller one-folder packaging hardening for the PySide6 read-only GUI. It is not an installer, not a one-file executable, not a signed release, and not an auto-updater.

## Install packaging dependencies

Use a clean virtual environment from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
```

`requirements.txt` contains the runtime GUI dependency (`PySide6`). `pyinstaller` is installed explicitly for packaging so normal CI does not need to build the EXE.

## Scripts

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\pyinstaller\clean.ps1
powershell -ExecutionPolicy Bypass -File packaging\pyinstaller\build.ps1
python packaging\pyinstaller\check_dist.py
```

`build.ps1` runs `python -m PyInstaller packaging\pyinstaller\pkb-gui.spec --noconfirm` and then runs `check_dist.py`. `clean.ps1` removes only repository-local `build\` and `dist\`.

## Output

The output is a one-folder application:

```text
dist\pkb-gui\
  pkb-gui.exe
  _internal\
```

The spec uses `COLLECT`, does not enable one-file mode, and does not build an installer. The bundle must not contain workspace/runtime data such as `knowledge\`, `.kb\`, `backups\`, `.git\`, `tmp\`, or `exports\`.

## Run the packaged GUI

The packaged GUI treats the current working directory as the default workspace. Prefer passing `--workspace` explicitly:

```powershell
.\dist\pkb-gui\pkb-gui.exe --workspace D:\AI\personal-knowledge-base
```

Git is optional and not required. The packaged GUI does not require Git and does not invoke Git during startup.

## User data locations

User knowledge data is never stored in the application install directory. Workspace data remains in the selected workspace, for example `.kb\index.sqlite` and `.kb\tasks\`.

GUI settings are stored as ordinary JSON under LocalAppData:

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\settings\gui-settings.json
```

The GUI settings file remembers window size and position, maximized state, and the last opened workspace path. It must not be written to the workspace, `knowledge\`, `.kb\`, `config\`, or `dist\pkb-gui\`.

Logs are written under LocalAppData:

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\logs\pkb-gui.log
```

## Startup contract verification

Before and after packaging, run:

```powershell
python tests\startup_smoke.py
python tests\gui_smoke_test.py
python tests\gui_interaction_test.py
python tests\packaging_smoke_test.py
```

For local release validation after building:

```powershell
python packaging\pyinstaller\exe_smoke.py --workspace D:\AI\personal-knowledge-base
```

Manual checks:

1. Start `pkb-gui.exe` with `--workspace`.
2. Confirm startup only shows workspace and index status.
3. Confirm the home summary remains unloaded until clicking `刷新首页摘要`.
4. Confirm no index/reindex task starts automatically.
5. Confirm an empty workspace shows `index_status=missing` and does not create `.kb\`.
6. Resize the window, close it, and reopen to confirm the window size and position are remembered.
7. Maximize the window, close it, and reopen to confirm maximized state is restored.

## Version info and icon

`version_info.txt` adds Windows metadata including `ProductName`, `FileDescription`, `ProductVersion`, and `CompanyName`. A final transparent `.ico` is not bundled yet; icon polish is a later packaging task.

## Known limitations

- This build does not build a one-file executable.
- This build does not create an installer.
- This build does not perform code signing.
- This build does not include an auto-update mechanism.
- No mutation UI, RSS, vector search, or AI features are included.
- A graphical workspace picker is future work; use `--workspace PATH` for now.
