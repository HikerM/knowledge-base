# Common user acceptance report for v2.0.0

`v2.0.0` is the first Windows installer baseline for Personal Knowledge Base. It is based on the `v2.0.0-rc.1` installer spike and `v2.0.0-rc.2` common-user acceptance polish.

## Acceptance environment

- OS: Windows desktop validation environment.
- Shell: PowerShell.
- Repository branch: `main`.
- Final installer target: `packaging\installer\output\PersonalKnowledgeBase-Setup-v2.0.0.exe`.
- Install mode covered by automation: per-user Inno Setup install with `PrivilegesRequired=lowest`.
- Visual status: P3 visual verification pending for final screenshots of the double-click installer wizard and unsigned Windows warning on a clean ordinary user profile.

## Double-click install

- Result: automated silent install passed.
- P3 visual verification pending: full double-click wizard screenshots and unsigned warning screenshots were not captured in this run.
- The installer is unsigned; Windows may show a security warning. This is documented as an expected limitation for v2.0.0.

## Shortcuts

- Result: pass.
- Start Menu shortcut creation was verified.
- Optional desktop shortcut creation was verified with `/TASKS=desktopicon`.
- Shortcut targets pointed to the installed `pkb-gui.exe`.
- Uninstall removed installer-created shortcuts.

## First launch

- Result: pass.
- First launch without a workspace routes to the Workspace Gate.
- Workspace Gate copy tells the user to select a knowledge-base folder.
- The app does not treat the install directory or current working directory as a workspace automatically.
- The app does not require Git.
- The app does not require Python.

## Existing workspace

- Result: pass.
- Opening an existing workspace succeeds.
- GUI settings record `last_opened_workspace` under LocalAppData.
- Startup with an existing workspace writes logs under LocalAppData.
- Settings and logs are not written to the install directory.

## New workspace

- Result: pass.
- New workspace creation remains plan-first.
- The user must explicitly confirm creation.
- Minimal workspace creation writes only planned workspace files and directories.
- It creates `workspace.yaml`, `knowledge\`, `config\`, `templates\`, and `reports\`.
- It does not create formal sample knowledge.
- It does not initialize Git.
- It does not create `.kb`.
- It does not create `.kb\index.sqlite`.
- It does not automatically index.
- It does not automatically import files.

## Search and document reading

- Result: pass.
- Search uses the service adapter path.
- Search remains limited to formal knowledge layers in the GUI interaction path.
- Selecting a result opens a single read-only preview.
- Opening a result switches to a read-only document reader.
- Library view opens a single document through the service adapter.

## Settings page paths

- Result: pass.
- Settings page exposes workspace path, LocalAppData settings path, and logs path as read-only information.
- GUI settings path remains `%LOCALAPPDATA%\PersonalKnowledgeBase\settings\gui-settings.json`.
- GUI log path remains `%LOCALAPPDATA%\PersonalKnowledgeBase\logs\pkb-gui.log`.

## Close and restart

- Result: pass.
- Window settings persist to LocalAppData.
- The last workspace is remembered.
- Restart restores the last available workspace.
- Restart does not create `.kb` for an empty remembered workspace.
- Restart does not automatically index.

## Uninstall

- Result: pass.
- Uninstall removes the main executable.
- Uninstall removes installer-created shortcuts.
- Uninstall does not delete the selected workspace.
- Uninstall does not delete `workspace.yaml`.
- Uninstall does not delete `knowledge\`, `config\`, `templates\`, or `reports\`.
- Uninstall does not delete LocalAppData settings or logs.

## Reinstall

- Result: pass.
- Reinstall to the same install directory succeeds.
- The app launches after reinstall.
- LocalAppData settings remain readable.
- `last_opened_workspace` remains readable.
- Workspace sentinel data remains present.
- Reinstall does not trigger automatic index/runtime data creation.

## User data preservation

- Result: pass.
- Workspace data stays outside the install directory.
- GUI settings and logs stay in LocalAppData.
- Uninstall preserves workspace data.
- Uninstall preserves LocalAppData settings and logs.
- Reinstall preserves workspace data.
- Reinstall preserves LocalAppData settings and logs.

## Not required

- Git: not required for installed-app runtime use.
- Python: not required for installed-app runtime use.

## Should not appear

- AI assistant.
- RSS.
- Vector search.
- Mutation UI.
- Archive/delete/merge/template apply/restore/promote execute.
- Auto update.

## Issues found

- P0: none.
- P1: none.
- P3: visual verification pending for double-click wizard screenshots and unsigned Windows warning screenshots on a clean ordinary user profile.

## Final release blocking assessment

- Blocks `v2.0.0 final`: no known P0/P1.
- Recommended next step after v2.0.0: `v2.1.0 AI Assistant Control Plane design`.
