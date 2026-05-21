# Application icon assets

This directory contains the temporary application icon for the Windows PySide6 GUI packaging baseline.

Files:

- `app-icon.png`: transparent-background PNG used by `QApplication` and `MainWindow` at runtime.
- `app-icon.ico`: Windows ICO used by PyInstaller for `pkb-gui.exe`.

The ICO must contain common Windows sizes: 16, 32, 48, 64, 128, and 256 px. The PNG must have a real alpha channel and must not use a checkerboard background to fake transparency.

Validate the assets from the repository root:

```powershell
python tests\icon_asset_test.py
python tests\packaging_smoke_test.py
```

This is an app branding baseline, not a final identity system. Installer artwork, high-DPI splash assets, code signing, and auto-update branding remain future work.
