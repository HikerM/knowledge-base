# PyInstaller one-folder GUI packaging spike

This directory contains the `v2.0.0-beta.1` packaging spike for the PySide6 read-only GUI. It verifies that the app can be built as a Windows one-folder executable directory. It is not an installer, one-file bundle, signed release, auto-updater, or formal end-user distribution.

## Install packaging dependencies

Use a clean virtual environment from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
```

`requirements.txt` contains the runtime GUI dependency (`PySide6`). `pyinstaller` is installed explicitly for the packaging job so normal development and CI do not need to build the EXE.

## Build

Run from the repository root:

```powershell
pyinstaller packaging\pyinstaller\pkb-gui.spec
```

The output is a one-folder application:

```text
dist\pkb-gui\
  pkb-gui.exe
  _internal\
```

## Run the packaged GUI

The packaged GUI treats the current working directory as the default workspace. To keep workspace data isolated from the application directory, run it from a workspace directory or pass `--workspace` explicitly:

```powershell
cd D:\AI\personal-knowledge-base
.\dist\pkb-gui\pkb-gui.exe
```

or:

```powershell
.\dist\pkb-gui\pkb-gui.exe --workspace D:\AI\personal-knowledge-base
```

The app log is written under the current user's local data directory, for example:

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\logs\pkb-gui.log
```

The executable must not store user knowledge, backups, task records, or the SQLite hot index inside the installed application folder. Workspace runtime data remains in the selected workspace, such as `.kb\index.sqlite` and `.kb\tasks\`.

## Startup contract verification

Before and after packaging, run:

```powershell
python tests\startup_smoke.py
python tests\gui_smoke_test.py
python tests\gui_interaction_test.py
python tests\packaging_smoke_test.py
```

For a manual EXE check:

1. Start `pkb-gui.exe` from a workspace or with `--workspace`.
2. Confirm the first screen is the home page.
3. Confirm startup only shows workspace and index status.
4. Confirm the home summary remains unloaded until clicking `刷新首页摘要`.
5. Confirm no index/reindex task starts automatically.
6. Confirm search, knowledge library, and document preview work against the selected workspace when its index exists.
7. Confirm an index-missing workspace shows a missing state instead of auto-indexing.

## Known limitations

- This spike does not build a one-file executable.
- This spike does not build an installer.
- This spike does not perform code signing.
- This spike does not include an auto-update mechanism.
- No mutation UI, RSS, vector search, or AI features are included.
- The packaged app currently uses the working directory or `--workspace`; a graphical workspace picker is future work.
- Git is optional. The GUI does not require Git and must run without invoking Git commands.
