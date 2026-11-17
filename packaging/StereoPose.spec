# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the PLAIN staged source; PyArmor --pack patches it.

Do not analyze an obfuscated entrypoint directly: PyInstaller cannot see
imports inside PyArmor wrappers. This spec analyzes ALL original modules,
then PyArmor's --pack replaces the bundled code with protected equivalents.
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path.cwd().resolve()
source = root / "build" / "package_source"
sys.path.insert(0, str(source))

# Explicit enumeration is based on the original source files, NOT PyArmor's
# generated files. It covers all package and subpackage modules (including
# dynamically imported calibration, diagnostics, UI, camera, and output code).
first_party = {"stereo_pose"}
for file in (source / "stereo_pose").rglob("*.py"):
    parts = file.relative_to(source).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if parts:
        first_party.add(".".join(parts))

ultra_data, ultra_bins, ultra_hidden = collect_all("ultralytics")
other_hidden = [
    "cv2.aruco", "tkinter", "tkinter.ttk",
    "tkinter.filedialog", "tkinter.font",
]

a = Analysis(
    [str(source / "RUN_ME.py")],
    pathex=[str(source)],
    binaries=ultra_bins,
    datas=ultra_data,
    hiddenimports=sorted(first_party.union(ultra_hidden, other_hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "IPython", "jupyterlab", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StereoPose",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="StereoPose",
)
