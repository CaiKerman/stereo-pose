"""Offline ``doctor`` command: report environment health without downloading.

Run::

    python -m stereo_pose doctor [--config PATH] [--json]

The doctor never downloads anything and must work on a machine without CUDA,
torch, or ultralytics.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from stereo_pose.config import ConfigError, load_config


def _pkg_version(name: str) -> str:
    try:
        import importlib

        return importlib.import_module(name).__version__
    except Exception:
        return None


def _torch_info() -> dict:
    info = {"installed": False, "version": None, "cuda_available": False, "cuda_device_count": 0}
    try:
        import torch  # noqa: F401
    except Exception:
        return info
    info["installed"] = True
    try:
        info["version"] = torch.__version__
    except Exception:
        pass
    try:
        info["cuda_available"] = bool(torch.cuda.is_available())
        info["cuda_device_count"] = int(torch.cuda.device_count()) if info["cuda_available"] else 0
    except Exception:
        pass
    return info


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def run_doctor(cfg) -> dict:
    """Collect environment/health info into a dict."""
    pose_model = Path(cfg["pose"]["model"])
    cal_dir = Path(cfg["stereo"]["calibration_dir"])
    log_dir = Path(cfg["runtime"].get("log_dir", "runtime/logs"))

    if cal_dir.exists():
        cal_files = sorted(cal_dir.glob("stereo_*.npz"))
        cal_status = {
            "exists": True,
            "versioned_calibrations": len(cal_files),
            "latest": str(cal_files[-1]) if cal_files else None,
        }
    else:
        cal_status = {"exists": False, "versioned_calibrations": 0, "latest": None}

    config_status = "valid"
    try:
        from stereo_pose.config import validate_config

        validate_config(cfg)
    except ConfigError as e:
        config_status = f"invalid: {e}"

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "opencv_version": _pkg_version("cv2"),
        "numpy_version": _pkg_version("numpy"),
        "torch": _torch_info(),
        "pose_model": {
            "configured_path": str(pose_model),
            "exists": pose_model.exists(),
        },
        "calibration_dir": cal_status,
        "config_status": config_status,
        "runtime_writable": {
            "calibrations": _writable(Path(cfg["stereo"]["calibration_dir"])),
            "sessions": _writable(Path(cfg["calibration_runtime"]["session_dir"])),
            "logs": _writable(log_dir),
        },
    }


def render_doctor(info: dict) -> str:
    t = info["torch"]
    lines = [
        "Stereo Pose doctor",
        f"  python            : {info['python_version']} ({info['python_implementation']})",
        f"  opencv            : {info['opencv_version'] or 'NOT INSTALLED'}",
        f"  numpy             : {info['numpy_version'] or 'NOT INSTALLED'}",
    ]
    if t["installed"]:
        cuda = f"available, {t['cuda_device_count']} device(s)" if t["cuda_available"] else "not available"
        lines.append(f"  torch             : {t['version']} (CUDA {cuda})")
    else:
        lines.append("  torch             : NOT INSTALLED")
    lines.append(f"  pose model        : {info['pose_model']['configured_path']} "
                 f"({'present' if info['pose_model']['exists'] else 'MISSING'})")
    cd = info["calibration_dir"]
    if cd["exists"]:
        lines.append(f"  calibration dir   : present ({cd['versioned_calibrations']} versioned calibration(s))")
    else:
        lines.append("  calibration dir   : absent (will be created) -> no 3D output until calibration")
    lines.append(f"  config            : {info['config_status']}")
    rw = info["runtime_writable"]
    for name, ok in rw.items():
        lines.append(f"  writable[{name}]  : {'yes' if ok else 'NO'}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Offline environment health check")
    ap.add_argument("--config", default=None, help="path to a config JSON (optional)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    cfg = load_config(None)
    config_load_error = None
    if args.config:
        try:
            cfg = load_config(args.config)
        except Exception as e:  # noqa: BLE001
            config_load_error = str(e)
            cfg = load_config(None)

    info = run_doctor(cfg)
    if config_load_error:
        info["config_status"] = f"cannot load config: {config_load_error}"

    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        print(render_doctor(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())