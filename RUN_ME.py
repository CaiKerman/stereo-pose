from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
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
            module = importlib.import_module(module_name)
            if module_name == 'cv2':
                gui = next((line.split(':', 1)[1].strip() for line in module.getBuildInformation().splitlines()
                            if line.strip().startswith('GUI:')), '')
                if gui.upper() in ('NONE', 'NO'):
                    missing.append('OpenCV GUI is unavailable (headless build); use the GUI-enabled Python environment that ran your previous version.')
        except Exception as exc:
            missing.append(f"{label} ({module_name}): {exc}")

    if missing:
        stop(
            "This Python environment is missing dependencies required for the live test.",
            "\n".join(missing),
        )


def main() -> None:
    print(f'[setup] Python: {sys.executable}')
    if not getattr(sys, "frozen", False):
        check_dependencies()
    cfg_path = ensure_config()

    try:
        from stereo_pose.config import load_config
        from stereo_pose.diagnostics.doctor import render_doctor, run_doctor

        cfg = load_config(cfg_path)
        model = Path(cfg['pose']['model'])
        if not model.is_absolute():
            model = ROOT / model
        if not model.is_file():
            stop('The configured local pose weight file is missing.',
                 f'pose.model={cfg["pose"]["model"]}\nExpected file: {model}\n'
                 'Keep the model from your working version at this path, or update pose.model in config.json.')
        from stereo_pose.calibration.package import restore_moved_calibration
        restore_moved_calibration(cfg_path, cfg)

        # Task 002A: visually identify all camera feeds and pick LEFT/RIGHT
        # before the stereo tracking loop opens its two cameras. The choice is
        # saved to config.json. This gate fails closed: if the operator cancels,
        # or the picker cannot run / persist the choice, startup aborts instead
        # of silently reusing possibly-stale config.json indexes (which could,
        # e.g., open the built-in laptop camera as one stereo input).
        from stereo_pose.capture.selection import run_camera_selection, selection_requested

        if selection_requested(cfg):
            print("=" * 72)
            print("Camera selection - identify your cameras by their live preview.")
            print("A window will show every usable camera as 'CAM <number>'.")
            print("Press the number keys to assign LEFT first, then RIGHT;")
            print("U=undo  R=rescan (after plug/unplug)  ENTER=confirm  Q/ESC=cancel.")
            print("=" * 72 + "\n")
            try:
                choice = run_camera_selection(cfg_path)
            except Exception as e:  # noqa: BLE001 — surface, but never continue with stale indexes
                print(f"[setup] camera selection failed ({e});")
                print("[setup] no cameras were opened and no stereo tracking was started.")
                raise SystemExit(1)
            if choice is None:
                print("[setup] camera selection was cancelled or could not be saved.")
                print("[setup] no cameras were opened and no stereo tracking was started.")
                print("[setup] run RUN_ME again to pick your LEFT/RIGHT cameras.")
                raise SystemExit(1)
            cfg = load_config(cfg_path)  # reload: the confirmed choice was persisted
            print(f"[setup] cameras confirmed: LEFT=CAM {choice.left}  RIGHT=CAM {choice.right}")

        print(render_doctor(run_doctor(cfg)))

        print("\n" + "=" * 72)
        print("Stereo Pose live test")
        print(f"Cameras: LEFT={cfg['camera']['left']}  RIGHT={cfg['camera']['right']}")
        print("C=calibration  AUTO waits for STABLE  SPACE=manual capture")
        print("R=solve  X=discard  P=pin/save  F=filter on/off")
        print("D=per-joint diagnostics  V=validate board  G=cleanup  Q/ESC=quit")
        print("W=world/zero setup  T=manual CSV start/stop (default OFF, 5 Hz export)")
        print("=" * 72 + "\n")

        from stereo_pose.app.runner import main as run_main

        old_argv = sys.argv
        sys.argv = ["stereo_pose run", "--config", str(cfg_path)]
        try:
            run_main()
        finally:
            sys.argv = old_argv
    except SystemExit:
        raise
    except Exception:
        stop("The program stopped with an error.", traceback.format_exc())


if __name__ == "__main__":
    main()
