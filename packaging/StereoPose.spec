# -*- mode: python ; coding: utf-8 -*-
"""Windows portable build from PyArmor's obfuscated application sources."""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).resolve().parent
obfuscated = root / "build" / "obfuscated"
sys.path.insert(0, str(obfuscated))

ultra_data, ultra_bins, ultra_hidden = collect_all("ultralytics")
protected_hidden = collect_submodules("stereo_pose")
pyarmor_runtime = [p.name for p in obfuscated.glob("pyarmor_runtime_*") if p.is_dir()]
protected_hidden += pyarmor_runtime
protected_hidden += ["cv2.aruco", "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.font"]

a = Analysis(
    [str(obfuscated / "RUN_ME.py")],
    pathex=[str(obfuscated)],
    binaries=ultra_bins,
    datas=ultra_data,
    hiddenimports=sorted(set(protected_hidden + ultra_hidden)),
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
