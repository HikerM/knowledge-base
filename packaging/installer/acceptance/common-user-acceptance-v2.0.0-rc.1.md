# Common user acceptance checklist for v2.0.0-rc.1

`v2.0.0-rc.1` is a Windows installer release candidate for common-user validation. It is not the final public release.

## 1. Install

- [ ] Double-click `PersonalKnowledgeBase-Setup-v2.0.0-rc.1.exe`.
- [ ] The installer opens and completes normally.
- [ ] The installer does not ask the user to install Git.
- [ ] The installer does not ask the user to install Python.
- [ ] The Start Menu contains a Personal Knowledge Base entry.
- [ ] If selected, the optional desktop shortcut is created.

## 2. First launch

- [ ] Open Personal Knowledge Base.
- [ ] When no workspace is selected, the app shows "请选择一个知识库文件夹".
- [ ] The user can choose an existing knowledge-base folder.
- [ ] The user can start the new-workspace flow.
- [ ] The app does not automatically scan or modify user files.

## 3. Create a workspace

- [ ] Choose a creation location.
- [ ] Enter a workspace name.
- [ ] Select a template.
- [ ] Review the creation plan preview.
- [ ] Confirm creation.
- [ ] The app enters the home/workspace flow after creation.
- [ ] The app shows that the search index is not built yet.
- [ ] The app does not automatically index.

## 4. Open an existing workspace

- [ ] The app shows workspace status.
- [ ] The user can search formal knowledge.
- [ ] The user can open a single document for preview/reading.
- [ ] The user can view the task center summary.
- [ ] The settings page shows workspace, settings, and logs paths.

## 5. Close and restart

- [ ] Window size and position are restored.
- [ ] The last workspace is remembered.
- [ ] The app does not automatically index after restart.

## 6. Uninstall

- [ ] The app can be uninstalled from Windows.
- [ ] The user workspace still exists after uninstall.
- [ ] LocalAppData settings and logs are not removed by default.

## 7. Reinstall

- [ ] The app can be installed again.
- [ ] The app launches after reinstall.
- [ ] The last workspace can be restored.
- [ ] User data is not lost.

## 8. Should not appear

- [ ] The app should not require Git.
- [ ] The app should not require Python.
- [ ] The app should not place a workspace inside the install directory.
- [ ] The app should not automatically index.
- [ ] The app should not show mutation, RSS, vector, or AI feature entry points.

## Acceptance result template

- Result: pass / fail
- Issue screenshot:
- Reproduction steps:
- Notes:

## Automated support checks

```powershell
powershell -ExecutionPolicy Bypass -File packaging\installer\inno\installer_smoke.ps1
python packaging\installer\inno\check_installer.py
```

The automated smoke covers install, launch, empty-workspace no-index behavior, service-level minimal workspace creation, uninstall, reinstall, LocalAppData preservation, workspace preservation, and Git/Python runtime independence. It does not replace the visual double-click wizard and first-run copy checks above.
