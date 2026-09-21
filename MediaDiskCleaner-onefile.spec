# -*- mode: python ; coding: utf-8 -*-
"""Один EXE для флешки. Без UAC, без папки _internal."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT = Path(SPECPATH).resolve()
ICON = PROJECT / "resources" / "icons" / "app.ico"
RESOURCES = PROJECT / "resources"

datas = []
if RESOURCES.is_dir():
    datas.append((str(RESOURCES), "resources"))

hiddenimports = collect_submodules("send2trash")

a = Analysis(
    [str(PROJECT / "main.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MediaDiskCleaner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(ICON) if ICON.is_file() else None,
    uac_admin=False,
    uac_uiaccess=False,
)
