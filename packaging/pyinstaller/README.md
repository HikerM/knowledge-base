# PyInstaller one-folder GUI packaging hardening

This directory contains the `v2.0.0-beta.6` PyInstaller one-folder packaging hardening, icon branding, first-run workspace selection, and workspace creation plan preview baseline for the PySide6 GUI. It is not an installer, not a one-file executable, not a signed release, and not an auto-updater.

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
python tests\icon_asset_test.py
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

The executable icon is loaded from:

```text
assets\app-icon\app-icon.ico
```

The runtime window and taskbar icon uses:

```text
assets\app-icon\app-icon.png
```

Both icon files are bundled into `_internal\assets\app-icon\` for the packaged application. The `.ico` must be present before packaging; the spec fails clearly if it is missing.

## Run the packaged GUI

The packaged GUI can start without a workspace. First-run startup shows a workspace gate where the user can choose an existing knowledge-base folder. It does not treat the install directory or current working directory as a workspace automatically.

You can still pass `--workspace` explicitly:

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
python tests\icon_asset_test.py
python tests\packaging_smoke_test.py
```

For local release validation after building:

```powershell
python packaging\pyinstaller\exe_smoke.py --workspace D:\AI\personal-knowledge-base
```

Manual checks:

1. Start `pkb-gui.exe` without `--workspace` and confirm the workspace gate appears.
2. Choose an existing knowledge-base folder.
3. Confirm startup only shows workspace and index status.
4. Confirm the home summary remains unloaded until clicking `刷新首页摘要`.
5. Confirm no index/reindex task starts automatically.
6. Confirm an empty workspace shows a missing-index message and does not create `.kb\`.
7. Resize the window, close it, and reopen to confirm the window size and position are remembered.
8. Maximize the window, close it, and reopen to confirm maximized state is restored.
9. Confirm the window, taskbar, and `pkb-gui.exe` show the application icon.
10. Confirm the icon does not show a checkerboard background.

## Version info and icon

`version_info.txt` adds Windows metadata including `ProductName`, `FileDescription`, `ProductVersion`, and `CompanyName`. The current values identify the app as `Personal Knowledge Base` and use `ProductVersion` `2.0.0-beta.6`.

Icon assets live in `assets\app-icon\`:

- `app-icon.png`: transparent-background runtime window icon.
- `app-icon.ico`: Windows executable icon with 16, 32, 48, 64, 128, and 256 px entries.

Validate icon transparency and ICO sizes with:

```powershell
python tests\icon_asset_test.py
```

Do not use an image with a checkerboard background as a final icon. Checkerboards are only editor previews for transparency and must not be baked into the PNG or ICO.

## Known limitations

- This build does not build a one-file executable.
- This build does not create an installer.
- This build does not perform code signing.
- This build does not include an auto-update mechanism.
- No mutation UI, RSS, vector search, or AI features are included.
- Creating a new workspace from the GUI is future work; choose an existing folder for now.
