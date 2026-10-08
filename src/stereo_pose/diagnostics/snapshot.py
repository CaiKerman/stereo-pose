"""On-demand stereo diagnostic snapshot (Task 002B, Part A).

Writes one self-contained, inspectable folder from the **already captured**
left/right frame pair and the **already completed** pose inference. It never
reads a second camera pair and never runs YOLO again; the raw frames and
keypoints are the exact objects from the current tracking iteration.

Output layout (under the managed runtime root)::

    <runtime_root>/diagnostics/snapshots/<timestamp>_<seq>/
        left_raw.png            right_raw.png
        left_annotated.png      right_annotated.png
        manifest.json
        calibration_snapshot.npz   (only when a calibration is active)
        README.txt                 (always, to explain file semantics)

The manifest plus ``calibration_snapshot.npz`` are sufficient to re-evaluate
rectified keypoints and epipolar errors offline with only NumPy and OpenCV
(see ``tools/inspect_snapshot.py``). The snapshot never overwrites a prior
snapshot or any calibration artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import cv2
import numpy as np

from stereo_pose.joints import JOINT_INDEX, JOINT_NAMES

SNAPSHOT_SCHEMA = "stereo_pose_3d/snapshot/v1"

# Keypoints drawn on the annotated preview with their name + compact confidence.
ANNOTATED_JOINTS = (
    "nose",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
)

# The self-contained geometry bundle needed to reproduce rectified keypoints
# and epipolar errors offline. These are the exact matrices the live
# triangulator consumes.
_CAL_KEYS = ("K1", "D1", "K2", "D2", "R1", "R2", "P1", "P2")


class SnapshotPathError(RuntimeError):
    """Raised when a snapshot path would escape the managed snapshot root."""


@dataclass
class SnapshotPose:
    """The already-completed pose result for one camera, kept as raw data.

    ``keypoints`` and ``confidence`` are the chosen person's per-keypoint arrays
    (length == ``len(JOINT_NAMES)`` when present). ``detections`` reports how
    many persons the model returned and ``chosen_person_index`` which one the
    runner selected.
    """

    detections: int = 0
    chosen_person_index: Optional[int] = None
    keypoints: Optional[np.ndarray] = None  # (N, 2) raw full-frame (u, v)
    confidence: Optional[np.ndarray] = None  # (N,)


def _resolved(path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(Path(path).resolve(strict=False)))))


def snapshot_dir(runtime_root) -> Path:
    """Return the managed snapshot root under ``runtime_root``."""
    return Path(runtime_root) / "diagnostics" / "snapshots"


def is_within_snapshot_root(path, runtime_root) -> bool:
    """True when ``path`` is equal to or contained inside the snapshot root."""
    root = _resolved(snapshot_dir(runtime_root))
    return _resolved(path) == root or _resolved(path).is_relative_to(root)


def _utc_now(now: Optional[datetime]) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _utcoffset_str(now: Optional[datetime]) -> str:
    if now is not None and now.tzinfo is not None:
        return now.strftime("%z")
    return "+0000"


def _new_snapshot_dir(runtime_root, now: Optional[datetime]) -> Path:
    """Create a uniquely named snapshot directory without overwriting."""
    root = _resolved(snapshot_dir(runtime_root))
    root.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now(now).strftime("%Y%m%d_%H%M%S")
    counter = 1
    while True:
        dest = root / stamp if counter == 1 else root / f"{stamp}_{counter}"
        if not is_within_snapshot_root(dest, runtime_root):
            raise SnapshotPathError(f"snapshot destination {dest} escapes {root}")
        try:
            dest.mkdir()
            return dest
        except FileExistsError:
            counter += 1


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _write_image(path: Path, frame: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        raise OSError(f"could not encode image: {path.name}")
    _atomic_write_bytes(path, buf.tobytes())


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    data = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
    _atomic_write_bytes(path, data)


def _sha256_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _is_missing(uv, conf) -> bool:
    if uv is None or conf is None:
        return True
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return True
    return bool(np.isnan(c)) or c <= 0.0


def _uv(uv) -> Optional[list]:
    if uv is None:
        return None
    arr = np.asarray(uv, dtype=float)
    if arr.size < 2 or not np.all(np.isfinite(arr)):
        return None
    return [float(arr[0]), float(arr[1])]


def compute_epipolar(calibration, uv_left, uv_right) -> Optional[Dict[str, Any]]:
    """Rectify one raw keypoint pair and return its epipolar diagnostics.

    ``calibration`` is a mapping carrying the same self-contained bundle written
    to ``calibration_snapshot.npz`` (keys K1, D1, K2, D2, R1, R2, P1, P2).
    Returns ``None`` when either input point is missing or non-finite.
    """
    pl = np.asarray(uv_left, np.float64)
    pr = np.asarray(uv_right, np.float64)
    if pl.shape != (2,) or pr.shape != (2,):
        return None
    if not (np.all(np.isfinite(pl)) and np.all(np.isfinite(pr))):
        return None
    ul = cv2.undistortPoints(
        pl.reshape(1, 1, 2), calibration["K1"], calibration["D1"],
        R=calibration["R1"], P=calibration["P1"],
    ).reshape(2)
    ur = cv2.undistortPoints(
        pr.reshape(1, 1, 2), calibration["K2"], calibration["D2"],
        R=calibration["R2"], P=calibration["P2"],
    ).reshape(2)
    signed_dy = float(ul[1] - ur[1])
    return {
        "rectified_uv_left": [float(x) for x in ul],
        "rectified_uv_right": [float(x) for x in ur],
        "signed_y_delta_px": signed_dy,
        "epipolar_error_px": abs(signed_dy),
    }


def calibrate_bundle(triangulator) -> Optional[Dict[str, np.ndarray]]:
    """Extract the self-contained geometry matrices from a triangulator.

    Returns ``None`` when no triangulator is supplied (no active calibration).
    The returned mapping is a fresh copy and never mutates the source NPZ.
    """
    if triangulator is None:
        return None
    bundle = {}
    for key in _CAL_KEYS:
        val = getattr(triangulator, key, None)
        if val is None:
            raise ValueError(f"triangulator missing {key}")
        bundle[key] = np.array(val, dtype=float, copy=True)
    return bundle


def annotate_frame(frame, keypoints, confidence) -> np.ndarray:
    """Return a copy of ``frame`` with upper-body keypoints labelled.

    Never mutates the caller's raw buffer. Missing / low-confidence keypoints
    are skipped.
    """
    img = np.array(frame, copy=True)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if keypoints is None:
        return img
    for name in ANNOTATED_JOINTS:
        i = JOINT_INDEX[name]
        if i >= len(keypoints):
            continue
        uv = keypoints[i]
        conf = None if confidence is None or i >= len(confidence) else confidence[i]
        if _is_missing(uv, conf):
            continue
        x, y = int(round(float(uv[0]))), int(round(float(uv[1])))
        cv2.circle(img, (x, y), 3, (0, 255, 0), -1)
        cv2.putText(
            img, f"{name} {float(conf):.2f}", (x + 4, y - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA,
        )
    return img


def _pose_to_dict(pose: SnapshotPose) -> Dict[str, Any]:
    keypoints = []
    n = len(JOINT_NAMES)
    for i, name in enumerate(JOINT_NAMES):
        uv = None
        conf = None
        if pose.keypoints is not None and i < len(pose.keypoints):
            uv = pose.keypoints[i]
        if pose.confidence is not None and i < len(pose.confidence):
            conf = pose.confidence[i]
        missing = _is_missing(uv, conf)
        keypoints.append({
            "label": name,
            "index": i,
            "uv": None if missing else _uv(uv),
            "confidence": None if (conf is None or missing) else float(conf),
            "missing": missing,
        })
    return {
        "detections": int(pose.detections),
        "chosen_person_index": pose.chosen_person_index,
        "keypoints": keypoints,
    }


def _joint_entry(
    name: str,
    pose_left: SnapshotPose,
    pose_right: SnapshotPose,
    calibration: Optional[Dict[str, np.ndarray]],
    verdict: Optional[Any],
) -> Dict[str, Any]:
    i = JOINT_INDEX[name]

    def side(pose: SnapshotPose) -> Dict[str, Any]:
        uv = None
        conf = None
        if pose.keypoints is not None and i < len(pose.keypoints):
            uv = pose.keypoints[i]
        if pose.confidence is not None and i < len(pose.confidence):
            conf = pose.confidence[i]
        missing = _is_missing(uv, conf)
        return {
            "label": name,
            "uv": None if missing else _uv(uv),
            "confidence": None if (conf is None or missing) else float(conf),
            "missing": missing,
        }

    left = side(pose_left)
    right = side(pose_right)

    rectified = {
        "available": False,
        "uv_left": None,
        "uv_right": None,
        "signed_y_delta_px": None,
        "epipolar_error_px": None,
        "missing_reason": None,
    }
    if calibration is not None and not left["missing"] and not right["missing"]:
        epi = compute_epipolar(calibration, left["uv"], right["uv"])
        if epi is not None:
            rectified.update({
                "available": True,
                "uv_left": epi["rectified_uv_left"],
                "uv_right": epi["rectified_uv_right"],
                "signed_y_delta_px": epi["signed_y_delta_px"],
                "epipolar_error_px": epi["epipolar_error_px"],
            })
        else:
            rectified["missing_reason"] = "non-finite keypoint"
    elif calibration is None:
        rectified["missing_reason"] = "no calibration loaded"
    elif left["missing"] or right["missing"]:
        rectified["missing_reason"] = "missing keypoint"

    if verdict is not None:
        rejection = {"state": getattr(verdict, "state", None), "accepted": bool(getattr(verdict, "accepted", False))}
    else:
        rejection = {"state": None, "accepted": False}

    return {
        "joint": name,
        "index": i,
        "left": left,
        "right": right,
        "rectified": rectified,
        "rejection": rejection,
    }


def save_snapshot(
    *,
    runtime_root,
    frame_index: int,
    wall_timestamp_ns: Optional[int],
    pair_timing: Optional[Dict[str, Any]],
    camera_left: int,
    camera_right: int,
    backend: str,
    requested_size,
    actual_size,
    frame_left: np.ndarray,
    frame_right: np.ndarray,
    pose_left: SnapshotPose,
    pose_right: SnapshotPose,
    selected_joints: Iterable[str],
    verdicts: Iterable[Any],
    triangulator=None,
    calib_path=None,
    now: Optional[datetime] = None,
) -> Path:
    """Write a diagnostic snapshot and return its directory path.

    All inputs are the exact objects from one tracking iteration. This function
    performs no camera reads and no inference. Any I/O failure raises and is
    handled by the caller so tracking keeps running.
    """
    dest = _new_snapshot_dir(runtime_root, now)
    _write_image(dest / "left_raw.png", frame_left)
    _write_image(dest / "right_raw.png", frame_right)
    _write_image(dest / "left_annotated.png", annotate_frame(frame_left, pose_left.keypoints, pose_left.confidence))
    _write_image(dest / "right_annotated.png", annotate_frame(frame_right, pose_right.keypoints, pose_right.confidence))

    calibration = calibrate_bundle(triangulator)
    cal_sha = _sha256_file(Path(calib_path)) if calib_path is not None else None

    if calibration is not None:
        np.savez(dest / "calibration_snapshot.npz", **calibration)

    verdict_map = {getattr(v, "joint_name", None): v for v in verdicts}

    utc_now = _utc_now(now)
    if wall_timestamp_ns is not None:
        wall_utc = datetime.fromtimestamp(float(wall_timestamp_ns) / 1e9, tz=timezone.utc).isoformat()
    else:
        wall_utc = utc_now.isoformat()

    manifest: Dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "snapshot_id": dest.name,
        "wall_timestamp_utc": wall_utc,
        "wall_timestamp_offset": _utcoffset_str(now),
        "frame_index": int(frame_index),
        "capture": {
            "camera": {"left": int(camera_left), "right": int(camera_right)},
            "backend": backend,
            "requested_resolution": {"width": int(requested_size[0]), "height": int(requested_size[1])},
            "actual_resolution": {"width": int(actual_size[0]), "height": int(actual_size[1])},
            "raw_frame": {
                "left": {
                    "width": int(frame_left.shape[1]),
                    "height": int(frame_left.shape[0]),
                    "channels": int(frame_left.shape[2]) if frame_left.ndim == 3 else 1,
                    "transforms": {"mirrored": False, "rotated": False, "cropped": False, "resized": False},
                },
                "right": {
                    "width": int(frame_right.shape[1]),
                    "height": int(frame_right.shape[0]),
                    "channels": int(frame_right.shape[2]) if frame_right.ndim == 3 else 1,
                    "transforms": {"mirrored": False, "rotated": False, "cropped": False, "resized": False},
                },
            },
        },
        "host_timing": {
            "wall_timestamp_ns": wall_timestamp_ns,
            "host_grab_skew_ms": pair_timing.get("host_grab_skew_ms") if pair_timing else None,
            "pair_cycle_ms": pair_timing.get("pair_cycle_ms") if pair_timing else None,
            "note": "host observation only; NOT sensor exposure synchronization",
        },
        "calibration": {
            "available": calibration is not None,
            "path": str(calib_path) if calib_path is not None else None,
            "sha256": cal_sha,
            "coordinate_system": "rectified_left_camera",
            "units": "mm",
            "stereo_rms": float(triangulator.stereo_rms) if (triangulator is not None and triangulator.stereo_rms is not None) else None,
            "missing_reason": None if calibration is not None else "no stereo calibration loaded",
        },
        "pose": {
            "left": _pose_to_dict(pose_left),
            "right": _pose_to_dict(pose_right),
        },
        "joints": [
            _joint_entry(name, pose_left, pose_right, calibration, verdict_map.get(name))
            for name in selected_joints
        ],
    }
    _write_json(dest / "manifest.json", manifest)

    _write_text = README_TEMPLATE.format(snapshot_id=dest.name)
    _atomic_write_bytes(dest / "README.txt", _write_text.encode("utf-8"))

    return dest


README_TEMPLATE = """Stereo diagnostic snapshot — {snapshot_id}

Generated only by an explicit S hotkey press during live tracking, from the
already captured left/right frame pair and the already completed pose inference.
No camera was re-read and YOLO was never re-run to produce these files.

  left_raw.png / right_raw.png         full-size, unannotated camera frames
                                       passed to inference (original orientation)
  left_annotated.png / right_annotated.png
                                       upper-body keypoints with name + confidence
  manifest.json                        versioned schema with coordinates,
                                       confidence, rectified points and
                                       quality states (plain-text readable)
  calibration_snapshot.npz             self-contained rectification geometry
                                       (absent when no calibration was active)

Replay the epipolar errors offline with:

  python tools/inspect_snapshot.py <this-directory>

Only NumPy and OpenCV are required; no camera, torch, CUDA, YOLO or model
weights. This folder contains human imagery — never commit or upload it to a
repository or external service.
"""
