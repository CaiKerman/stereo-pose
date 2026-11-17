# -*- mode: python ; coding: utf-8 -*-
"""Package the complete obfuscated PR10 application as a portable Windows EXE."""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parent
obfuscated = root / "build" / "obfuscated"
protected_package = obfuscated / "stereo_pose"
sys.path.insert(0, str(obfuscated))

# PyArmor replaces module bodies with runtime calls. PyInstaller cannot infer
# their transitive imports by reading those protected bodies; collect_submodules
# can also resolve against the original editable install instead of PyArmor's
# output. Enumerate the obfuscated files themselves, preserving the package tree.
def protected_module_names():
    modules = {"stereo_pose"}
    for source in protected_package.rglob("*.py"):
        parts = list(source.relative_to(obfuscated).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            modules.add(".".join(parts))
    for runtime_package in obfuscated.glob("pyarmor_runtime_*"):
        if runtime_package.is_dir():
            modules.add(runtime_package.name)
    print("[packaging] PyArmor Python modules:", len(modules))
    return sorted(modules)

ultra_data, ultra_bins, ultra_hidden = collect_all("ultralytics")
protected_hidden = protected_module_names()
other_hidden = ["cv2.aruco", "tkinter", "tkinter.ttk",
                "tkinter.filedialog", "tkinter.font"]

a = Analysis(
    [str(obfuscated / "RUN_ME.py")],
    pathex=[str(obfuscated)],
    binaries=ultra_bins,
    datas=ultra_data,
    hiddenimports=sorted(set(protected_hidden + ultra_hidden + other_hidden)),
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
