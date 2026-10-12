"""Centralized configuration: defaults, deep merge, and validation.

Validation is implemented in-process (no external schema library) so the
package and tests stay offline-first. A JSON Schema document is also shipped
under ``configs/schemas/default.schema.json`` for documentation/tooling.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, List, Optional

DEFAULT_CONFIG: dict = {
    "camera": {
        "left": 0,
        "right": 1,
        "width": 1280,
        "height": 720,
        "fps": 30,
        "backend": "auto",
        "fourcc": "MJPG",
        "buffer_size": 1,
        "alternate_grab_order": True,
        "selection": {
            # Task 002A: interactive LEFT/RIGHT camera picker offered by RUN_ME.
            "startup_pick": True,
            # Probe OpenCV indexes 0..probe_max_index when discovering cameras.
            # The picker assigns cameras with single-digit number keys, so this
            # is bounded to 0..9 (an index >= 10 could never be selected).
            "probe_max_index": 7,
            # Reads attempted before declaring an opened camera "no frames".
            "first_frame_attempts": 5,
        },
    },
    "pose": {
        "model": "yolo11n-pose.pt",
        "device": "auto",
        "detection_confidence": 0.35,
        "keypoint_confidence": 0.45,
    },
    "stereo": {
        "calibration_dir": "runtime/calibrations",
        "load": "latest",
        "explicit_file": None,
        "board_cols": 9,
        "board_rows": 6,
        "square_mm": 25.0,
    },
    "calibration_runtime": {
        "session_dir": "runtime/sessions",
        "auto_capture": True,
        "auto_capture_interval_s": 0.7,
        "min_pairs_to_solve": 12,
        "target_pairs": 24,
        "recommended_readiness": 75,
        "min_board_area_ratio": 0.012,
        "diversity_threshold": 0.12,
        "stable_dwell_s": 0.30,
        "stable_min_frames": 3,
        "stable_corner_motion_px": 5.0,
        "robust_prune": True,
        "prune_min_epipolar_px": 0.8,
        "prune_max_epipolar_px": 2.5,
        "max_prune_fraction": 0.25,
        "keep_images_after_success": False,
    },
    "quality": {
        "max_epipolar_error_px": 3.0,
        "max_reprojection_error_px": 2.5,
        "min_depth_mm": 250.0,
        "max_depth_mm": 7000.0,
        "min_quality_score": 0.12,
        "max_joint_speed_mm_s": 6000.0,
        "speed_gate_reset_after_s": 0.6,
    },
    "smoothing": {
        "enabled": True,
        "type": "one_euro",
        "min_cutoff": 1.2,
        "beta": 0.015,
        "d_cutoff": 1.0,
        "reset_after_s": 0.6,
    },
    "cleanup": {
        "enabled": True,
        "keep_latest_calibrations": 10,
        "delete_failed_sessions_older_days": 7,
    },
    "output": {
        "joint_group": "ergonomics",
        "joints": [],
        "console": True,
        "console_every_n_frames": 5,
        "jsonl_file": None,
        "udp": {"enabled": False, "host": "127.0.0.1", "port": 5005},
    },
    "readout": {"joint_group": "upper", "joints": []},
    "world": {"dictionary": "DICT_4X4_50", "reference_file": "runtime/world/reference_points.csv",
              "coordinate_name": "WORLD", "max_residual_mm": 10.0},
    "diagnostics": {
        "enabled": False,
        "every_n_frames": 10,
    },
    "runtime": {
        "root": "runtime",
        "show_preview": True,
        "log_dir": "runtime/logs",
    },
}

REQUIRED_SECTIONS = [
    "camera",
    "pose",
    "stereo",
    "calibration_runtime",
    "quality",
    "smoothing",
    "cleanup",
    "output",
    "diagnostics",
    "runtime",
]

_CAMERA_BACKENDS = {"auto", "dshow", "msmf", "v4l2"}


class ConfigError(ValueError):
    """Raised when configuration is structurally or semantically invalid."""


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into a deep copy of ``base``."""
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Optional[Path] = None, validate: bool = True) -> dict:
    """Load merged + optionally validated configuration.

    ``path`` may be a ``pathlib.Path`` or a path string. When ``path`` is
    ``None``, the built-in defaults are returned.
    """
    cfg = deepcopy(DEFAULT_CONFIG)
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ConfigError("Config file must contain a JSON object.")
        cfg = deep_merge(cfg, data)
    if validate:
        validate_config(cfg)
    return cfg


def _err(errors: List[str], path: str, msg: str) -> None:
    errors.append(f"{path}: {msg}")


def _num(cfg_val: Any, path: str, errors: List[str], lo=None, hi=None) -> None:
    if isinstance(cfg_val, bool) or not isinstance(cfg_val, (int, float)):
        _err(errors, path, f"expected a number, got {type(cfg_val).__name__}")
        return
    if lo is not None and cfg_val < lo:
        _err(errors, path, f"must be >= {lo}")
    if hi is not None and cfg_val > hi:
        _err(errors, path, f"must be <= {hi}")


def _bool(val: Any, path: str, errors: List[str]) -> None:
    if not isinstance(val, bool):
        _err(errors, path, f"expected a boolean, got {type(val).__name__}")


def _int(val: Any, path: str, errors: List[str], lo=None, hi=None) -> None:
    if isinstance(val, bool) or not isinstance(val, int):
        _err(errors, path, f"expected an integer, got {type(val).__name__}")
        return
    if lo is not None and val < lo:
        _err(errors, path, f"must be >= {lo}")
    if hi is not None and val > hi:
        _err(errors, path, f"must be <= {hi}")


def _str(val: Any, path: str, errors: List[str], allow_null: bool = False) -> None:
    if allow_null and val is None:
        return
    if not isinstance(val, str):
        _err(errors, path, f"expected a string, got {type(val).__name__}")


def validate_config(cfg: dict) -> None:
    """Validate a configuration dict; raise :class:`ConfigError` with all messages.

    Unknown fields are tolerated for forward compatibility; known fields are
    type/range checked. Invalid values fail with a single aggregated message.
    """
    errors: List[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in cfg:
            _err(errors, "<root>", f"missing required section '{section}'")
            continue
        if not isinstance(cfg[section], dict):
            _err(errors, section, "must be an object")

    c = cfg.get("camera", {})
    _int(c.get("left"), "camera.left", errors, lo=0)
    _int(c.get("right"), "camera.right", errors, lo=0)
    _int(c.get("width"), "camera.width", errors, lo=1)
    _int(c.get("height"), "camera.height", errors, lo=1)
    _num(c.get("fps"), "camera.fps", errors, lo=1)
    backend = c.get("backend")
    if not isinstance(backend, str) or backend.lower() not in _CAMERA_BACKENDS:
        _err(errors, "camera.backend", f"must be one of {sorted(_CAMERA_BACKENDS)}")
    fourcc = c.get("fourcc")
    if not isinstance(fourcc, str) or len(fourcc) != 4 or not all(32 <= ord(ch) < 127 for ch in fourcc):
        _err(errors, "camera.fourcc", "must be a 4-character ASCII code (e.g. 'MJPG')")
    _int(c.get("buffer_size"), "camera.buffer_size", errors, lo=1)
    _bool(c.get("alternate_grab_order"), "camera.alternate_grab_order", errors)
    sel = c.get("selection", {})
    if not isinstance(sel, dict):
        _err(errors, "camera.selection", "must be an object")
    else:
        _bool(sel.get("startup_pick"), "camera.selection.startup_pick", errors)
        _int(sel.get("probe_max_index"), "camera.selection.probe_max_index", errors, lo=0, hi=9)
        _int(sel.get("first_frame_attempts"), "camera.selection.first_frame_attempts", errors, lo=1, hi=60)

    p = cfg.get("pose", {})
    _str(p.get("model"), "pose.model", errors)
    _str(p.get("device"), "pose.device", errors)
    _num(p.get("detection_confidence"), "pose.detection_confidence", errors, 0.0, 1.0)
    _num(p.get("keypoint_confidence"), "pose.keypoint_confidence", errors, 0.0, 1.0)

    s = cfg.get("stereo", {})
    _str(s.get("calibration_dir"), "stereo.calibration_dir", errors)
    load_mode = s.get("load")
    if load_mode not in ("latest", "explicit"):
        _err(errors, "stereo.load", "must be one of ['latest', 'explicit']")
    _str(s.get("explicit_file"), "stereo.explicit_file", errors, allow_null=True)
    _int(s.get("board_cols"), "stereo.board_cols", errors, lo=2)
    _int(s.get("board_rows"), "stereo.board_rows", errors, lo=2)
    sq = s.get("square_mm")
    if isinstance(sq, bool) or not isinstance(sq, (int, float)) or sq <= 0:
        _err(errors, "stereo.square_mm", "must be a number > 0")

    cr = cfg.get("calibration_runtime", {})
    _str(cr.get("session_dir"), "calibration_runtime.session_dir", errors)
    _bool(cr.get("auto_capture"), "calibration_runtime.auto_capture", errors)
    _num(cr.get("auto_capture_interval_s"), "calibration_runtime.auto_capture_interval_s", errors, lo=0.0)
    _int(cr.get("min_pairs_to_solve"), "calibration_runtime.min_pairs_to_solve", errors, lo=2)
    _int(cr.get("target_pairs"), "calibration_runtime.target_pairs", errors, lo=1)
    _num(cr.get("recommended_readiness"), "calibration_runtime.recommended_readiness", errors, 0.0, 100.0)
    _num(cr.get("min_board_area_ratio"), "calibration_runtime.min_board_area_ratio", errors, 0.0, 1.0)
    _num(cr.get("diversity_threshold"), "calibration_runtime.diversity_threshold", errors, lo=0.0)
    _num(cr.get("stable_dwell_s"), "calibration_runtime.stable_dwell_s", errors, lo=0.0)
    _int(cr.get("stable_min_frames"), "calibration_runtime.stable_min_frames", errors, lo=1)
    _num(cr.get("stable_corner_motion_px"), "calibration_runtime.stable_corner_motion_px", errors, lo=0.0)
    _bool(cr.get("robust_prune"), "calibration_runtime.robust_prune", errors)
    _num(cr.get("prune_min_epipolar_px"), "calibration_runtime.prune_min_epipolar_px", errors, lo=0.0)
    _num(cr.get("prune_max_epipolar_px"), "calibration_runtime.prune_max_epipolar_px", errors, lo=0.0)
    _num(cr.get("max_prune_fraction"), "calibration_runtime.max_prune_fraction", errors, 0.0, 1.0)
    _bool(cr.get("keep_images_after_success"), "calibration_runtime.keep_images_after_success", errors)

    q = cfg.get("quality", {})
    _num(q.get("max_epipolar_error_px"), "quality.max_epipolar_error_px", errors, lo=0.0)
    _num(q.get("max_reprojection_error_px"), "quality.max_reprojection_error_px", errors, lo=0.0)
    _num(q.get("min_depth_mm"), "quality.min_depth_mm", errors, lo=0.0)
    _num(q.get("max_depth_mm"), "quality.max_depth_mm", errors, lo=0.0)
    _num(q.get("min_quality_score"), "quality.min_quality_score", errors, 0.0, 1.0)
    _num(q.get("max_joint_speed_mm_s"), "quality.max_joint_speed_mm_s", errors, lo=0.0)
    _num(q.get("speed_gate_reset_after_s"), "quality.speed_gate_reset_after_s", errors, lo=0.0)
    if isinstance(q.get("min_depth_mm"), (int, float)) and isinstance(q.get("max_depth_mm"), (int, float)):
        if q["min_depth_mm"] >= q["max_depth_mm"]:
            _err(errors, "quality", "min_depth_mm must be < max_depth_mm")

    sm = cfg.get("smoothing", {})
    _bool(sm.get("enabled"), "smoothing.enabled", errors)
    if sm.get("type") != "one_euro":
        _err(errors, "smoothing.type", "only 'one_euro' is supported")
    _num(sm.get("min_cutoff"), "smoothing.min_cutoff", errors, lo=0.0)
    _num(sm.get("beta"), "smoothing.beta", errors, lo=0.0)
    _num(sm.get("d_cutoff"), "smoothing.d_cutoff", errors, lo=0.0)
    _num(sm.get("reset_after_s"), "smoothing.reset_after_s", errors, lo=0.0)

    cl = cfg.get("cleanup", {})
    _bool(cl.get("enabled"), "cleanup.enabled", errors)
    _int(cl.get("keep_latest_calibrations"), "cleanup.keep_latest_calibrations", errors, lo=1)
    _num(cl.get("delete_failed_sessions_older_days"), "cleanup.delete_failed_sessions_older_days", errors, lo=0.0)

    o = cfg.get("output", {})
    _str(o.get("joint_group"), "output.joint_group", errors)
    joints = o.get("joints")
    if not isinstance(joints, list) or not all(isinstance(x, str) for x in joints):
        _err(errors, "output.joints", "must be a list of strings")
    _bool(o.get("console"), "output.console", errors)
    _int(o.get("console_every_n_frames"), "output.console_every_n_frames", errors, lo=1)
    _str(o.get("jsonl_file"), "output.jsonl_file", errors, allow_null=True)
    udp = o.get("udp", {})
    if not isinstance(udp, dict):
        _err(errors, "output.udp", "must be an object")
    else:
        _bool(udp.get("enabled"), "output.udp.enabled", errors)
        _str(udp.get("host"), "output.udp.host", errors)
        _int(udp.get("port"), "output.udp.port", errors, lo=1, hi=65535)

    from stereo_pose.joints import resolve_joints
    for section in ("readout", "world"):
        if not isinstance(cfg.get(section), dict):
            _err(errors, section, "must be an object")
    rd = cfg.get("readout") if isinstance(cfg.get("readout"), dict) else {}
    try:
        resolve_joints(rd.get("joint_group", "upper"), rd.get("joints"))
    except (ValueError, TypeError) as e:
        _err(errors, "readout", str(e))
    w = cfg.get("world") if isinstance(cfg.get("world"), dict) else {}
    if w.get("dictionary") not in ("DICT_4X4_50", "DICT_5X5_50"): _err(errors, "world.dictionary", "unsupported dictionary")
    _str(w.get("reference_file"), "world.reference_file", errors)
    _str(w.get("coordinate_name"), "world.coordinate_name", errors)
    _num(w.get("max_residual_mm"), "world.max_residual_mm", errors, lo=0.001)

    d = cfg.get("diagnostics", {})
    _bool(d.get("enabled"), "diagnostics.enabled", errors)
    _int(d.get("every_n_frames"), "diagnostics.every_n_frames", errors, lo=1)

    r = cfg.get("runtime", {})
    _str(r.get("root"), "runtime.root", errors)
    _bool(r.get("show_preview"), "runtime.show_preview", errors)
    _str(r.get("log_dir"), "runtime.log_dir", errors)

    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))
