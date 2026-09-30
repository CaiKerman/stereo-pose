from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
os.chdir(ROOT)


def stop(msg: str, details: str = "") -> None:
    print("\n" + "=" * 72)
    print("STEREO POSE - CANNOT START")
    print("=" * 72)
    print(msg)
    if details:
        print("\n" + details)
    print("\nNo pip install was performed. No project files were installed into Python.")
    print("Please use the same Python environment that previously ran your stereo-pose PoC.")
    print("=" * 72)
    try:
        input("\nPress Enter to close...")
    except EOFError:
        pass
    raise SystemExit(1)


def ensure_config() -> Path:
    cfg = ROOT / "config.json"
    if cfg.exists():
        return cfg

    default_cfg = ROOT / "configs" / "default.json"
    if not default_cfg.exists():
        stop("configs/default.json is missing from this ZIP.")
    shutil.copy2(default_cfg, cfg)
    print(f"[setup] Created local config: {cfg.name}")
    return cfg


def check_dependencies() -> None:
    missing = []
    for module_name, label in [
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("torch", "PyTorch"),
        ("ultralytics", "Ultralytics"),
    ]:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            missing.append(f"{label} ({module_name}): {exc}")

    if missing:
        stop(
            "This Python environment is missing dependencies required for the live test.",
            "\n".join(missing),
        )


def main() -> None:
    check_dependencies()
    cfg_path = ensure_config()

    model = ROOT / "yolo11n-pose.pt"
    if not model.exists():
        stop(
            "yolo11n-pose.pt is missing.",
            "Copy the same yolo11n-pose.pt you used before into this folder, next to RUN_ME.py.",
        )

    try:
        from stereo_pose.config import load_config
        from stereo_pose.diagnostics.doctor import render_doctor, run_doctor

        cfg = load_config(cfg_path)
        print(render_doctor(run_doctor(cfg)))

        print("\n" + "=" * 72)
        print("Stereo Pose live test")
        print("C=calibration | SPACE=capture | R=solve | P=pin/save")
        print("F=filter on/off | G=cleanup | Q/ESC=quit")
        print("=" * 72 + "\n")

        from stereo_pose.app.runner import main as run_main

        sys.argv = ["stereo_pose run", "--config", str(cfg_path)]
        run_main()
    except SystemExit:
        raise
    except Exception:
        stop("The program stopped with an error.", traceback.format_exc())


if __name__ == "__main__":
    main()
