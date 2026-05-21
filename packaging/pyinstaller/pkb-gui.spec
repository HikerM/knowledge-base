# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


spec_dir = Path(SPECPATH).resolve()
project_root = spec_dir.parents[1]
icon_path = project_root / "assets" / "app-icon" / "app-icon.ico"
icon_png_path = project_root / "assets" / "app-icon" / "app-icon.png"

if not icon_path.exists():
    raise FileNotFoundError(f"Application icon is missing: {icon_path}")
if not icon_png_path.exists():
    raise FileNotFoundError(f"Application PNG icon is missing: {icon_png_path}")

hiddenimports = (
    collect_submodules("gui")
    + collect_submodules("knowledge_app")
    + collect_submodules("knowledge_core")
)

datas = collect_data_files("PySide6") + [
    (str(icon_path), "assets/app-icon"),
    (str(icon_png_path), "assets/app-icon"),
]

a = Analysis(
    [str(project_root / "gui" / "app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pkb-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
    version=str(spec_dir / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pkb-gui",
)
