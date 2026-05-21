# Common user acceptance report for v2.0.0-rc.2

`v2.0.0-rc.2` is a common-user acceptance polish candidate built on the `v2.0.0-rc.1` Windows installer spike. It is still not the final public release.

## Acceptance environment

- OS: Windows desktop validation environment.
- Shell: PowerShell.
- Repository branch: `main`.
- Baseline installer used for acceptance: `packaging\installer\output\PersonalKnowledgeBase-Setup-v2.0.0-rc.1.exe`.
- Rebuilt rc.2 installer target: `packaging\installer\output\PersonalKnowledgeBase-Setup-v2.0.0-rc.2.exe`.
- Post-polish validation: rc.2 installer build, installer smoke, and shortcut acceptance were rerun against the rebuilt rc.2 installer.
- Install mode covered by automation: per-user Inno Setup install with `PrivilegesRequired=lowest`.
- Human-visual checks still required before final: unsigned Windows warning copy and full double-click wizard screenshots on a clean ordinary user profile.

## Installation result

- Result: pass.
- Silent install completed successfully into a temporary per-user install directory.
- `pkb-gui.exe` was installed.
- The uninstaller was installed.
- The installed app did not require Git.
- The installed app did not require Python.
- Start Menu shortcut was created and targeted the installed `pkb-gui.exe`.
- Optional desktop shortcut was created with `/TASKS=desktopicon` and targeted the installed `pkb-gui.exe`.
- Uninstall removed the shortcuts created by the installer.
- Rebuilt rc.2 installer size: 165,773,486 bytes.

## Launch result

- Result: pass.
- The installed EXE launched with `--workspace <existing test workspace>`.
- The app wrote GUI settings under `%LOCALAPPDATA%\PersonalKnowledgeBase\settings\gui-settings.json`.
- The app wrote logs under `%LOCALAPPDATA%\PersonalKnowledgeBase\logs\pkb-gui.log`.
- Settings and logs were not written to the install directory.
- Version display was aligned to `v2.0.0-rc.2` during this polish pass.

## Workspace selection and creation result

- Result: pass.
- First-run no-workspace state routes to the Workspace Gate.
- Workspace Gate copy includes `请选择一个知识库文件夹`.
- Existing workspace selection succeeds.
- Invalid workspace path remains in the Workspace Gate and shows a friendly unavailable-path message.
- Empty workspace launch does not create `.kb`.
- Empty workspace launch does not create `.kb\index.sqlite`.
- New workspace creation remains plan-first and explicit-confirm.
- Minimal workspace creation creates only planned workspace files and directories.
- New workspace creation does not create formal sample knowledge.
- New workspace creation does not initialize Git.
- New workspace creation does not start indexing.

## Search and document preview result

- Result: pass.
- Search view calls the service adapter instead of direct Markdown or SQLite access.
- Search results are limited to formal layers in the GUI interaction path.
- Selecting a search result opens a single read-only preview.
- Opening a result switches to a read-only document reader.
- Library view opens a single document through the service adapter.
- Settings view shows workspace, settings, and logs path information.
- Disabled/future mutation actions remain absent from the common-user UI.

## Close and restart result

- Result: pass.
- Window settings persist to LocalAppData.
- Last workspace is remembered in GUI settings.
- Restart restores the last available workspace.
- Restart does not create `.kb` for an empty remembered workspace.
- Restart does not automatically index.

## Uninstall result

- Result: pass.
- Silent uninstall completed successfully.
- The main executable was removed from the install directory.
- Installer-created Start Menu and desktop shortcuts were removed.
- User workspace was preserved.
- `workspace.yaml` was preserved.
- `knowledge\`, `config\`, `templates\`, and `reports\` were preserved.
- LocalAppData settings and logs were preserved.

## Reinstall result

- Result: pass.
- Reinstall to the same temporary install directory completed successfully.
- The app launched after reinstall.
- LocalAppData settings remained readable.
- `last_opened_workspace` was preserved.
- Workspace sentinel data was preserved.
- Reinstall did not trigger automatic index/runtime data creation.

## User data preservation result

- Result: pass.
- Workspace data stayed outside the install directory.
- GUI settings and logs stayed in LocalAppData.
- Uninstall did not delete the selected workspace.
- Uninstall did not delete LocalAppData settings or logs.
- Reinstall did not delete workspace data.
- Reinstall did not delete LocalAppData settings or logs.

## Issues found

- P0: none.
- P1: none.
- P2: GUI/window version display and Windows metadata still referenced the earlier beta baseline during rc.1 acceptance. Fixed in rc.2 by aligning the GUI phase label, workspace creation app version, PyInstaller version metadata, installer version, installer output filename, and test expectations to `v2.0.0-rc.2`.
- P3: Fully visual double-click wizard review and unsigned Windows warning screenshots still require a human reviewer on a clean ordinary user profile. Automated checks cover install behavior, shortcut creation, launch, uninstall, reinstall, and data preservation.

## Final release blocking assessment

- Blocks `v2.0.0 final`: no known P0/P1 after rc.2 polish.
- Recommended next step: `v2.0.0 final release preparation` after one clean human visual pass of the unsigned installer wizard and first-run Workspace Gate.

## Validation commands

```powershell
python scripts\kb.py audit
python scripts\kb.py secret-scan
python tests\startup_smoke.py
python tests\gui_settings_test.py
python tests\gui_smoke_test.py
python tests\gui_interaction_test.py
python tests\packaging_smoke_test.py
python tests\workspace_creation_execute_test.py
python tests\gui_workspace_creation_test.py
python tests\service_read_layer_test.py
python tests\smoke_test.py
python tests\governance_test.py
powershell -ExecutionPolicy Bypass -File packaging\installer\inno\build_installer.ps1
powershell -ExecutionPolicy Bypass -File packaging\installer\inno\installer_smoke.ps1
```
