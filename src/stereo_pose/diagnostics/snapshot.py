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
snapshot or any calibration artifact. All writes are staged in a ``.partial``
directory and atomically renamed on completion, so a failed save can never
leave a half-written folder that looks like valid evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import cv2
import numpy as np

from stereo_pose.geometry.triangulation import StereoTriangulator
from stereo_pose.joints import JOINT_INDEX, JOINT_NAMES

SNAPSHOT_SCHEMA = "stereo_pose_3d/snapshot/v2"

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


def _new_snapshot_dir(runtime_root, now: Optional[datetime]) -> Tuple[Path, Path]:
    """Reserve a unique staging directory for a new snapshot.

    Returns ``(staging, final)``: everything is written into ``staging`` (whose
    name ends in ``.partial``) and then atomically renamed to ``final``. A write
    failure or hard crash can therefore never leave a half-written folder that
    looks like valid diagnostic evidence — only an explicitly ``.partial``
    staging directory that is safely removed on ordinary failures.
    """
    root = _resolved(snapshot_dir(runtime_root))
    root.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now(now).strftime("%Y%m%d_%H%M%S")
    counter = 1
    while True:
        name = stamp if counter == 1 else f"{stamp}_{counter}"
        final = root / name
        staging = root / f"{name}.partial"
        if not is_within_snapshot_root(final, runtime_root) or not is_within_snapshot_root(staging, runtime_root):
            raise SnapshotPathError(f"snapshot destination {final} escapes {root}")
        if not final.exists() and not staging.exists():
            staging.mkdir()
            return staging, final
        counter += 1


def _promote_snapshot(staging: Path, final: Path) -> Path:
    """Atomically publish a fully written staging directory."""
    os.replace(staging, final)
    return final


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


def _finite_pair(uv) -> Optional[list]:
    """Return ``[u, v]`` when ``uv`` is a finite 2-vector, else ``None``."""
    if uv is None:
        return None
    try:
        arr = np.asarray(uv, dtype=float).ravel()
    except (TypeError, ValueError):
        return None
    if arr.size < 2 or not np.all(np.isfinite(arr[:2])):
        return None
    return [float(arr[0]), float(arr[1])]


def _finite_conf(conf) -> Optional[float]:
    """Return the confidence as a finite float, else ``None``."""
    if conf is None:
        return None
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return None
    return c if math.isfinite(c) else None


def _observation(pose: "SnapshotPose", i: int, name: str, confidence_threshold=None) -> Dict[str, Any]:
    """Per-keypoint observation record that preserves the raw evidence.

    Review B1: the raw finite ``uv`` and numeric ``confidence`` are ALWAYS
    preserved — including Ultralytics zero placeholders (``uv=(0, 0)`` with
    ``confidence=0.0``) and subthreshold detections — instead of being silently
    nulled. Usability is expressed by independent fields:

    - ``missing`` / ``missing_reason``: why the keypoint is not usable
      (absent pose, non-finite uv/confidence, or the ``confidence <= 0``
      not-detected placeholder);
    - ``low_confidence``: the keypoint WAS detected but its confidence is
      below the runner's acceptance ``confidence_threshold``.
    """
    uv_raw = None
    conf_raw = None
    if pose.keypoints is not None and i < len(pose.keypoints):
        uv_raw = pose.keypoints[i]
    if pose.confidence is not None and i < len(pose.confidence):
        conf_raw = pose.confidence[i]

    uv = _finite_pair(uv_raw)
    conf = _finite_conf(conf_raw)

    if pose.keypoints is None:
        reason = "absent pose"
    elif uv_raw is None:
        reason = "keypoint not present"
    elif uv is None:
        reason = "non-finite uv"
    elif conf_raw is None:
        reason = "confidence not present"
    elif conf is None:
        reason = "non-finite confidence"
    elif conf <= 0.0:
        reason = "confidence <= 0 (zero placeholder / not detected)"
    else:
        reason = None

    missing = reason is not None
    low_conf = bool(
        not missing
        and confidence_threshold is not None
        and conf < float(confidence_threshold)
    )
    return {
        "label": name,
        "index": i,
        "uv": uv,
        "confidence": conf,
        "missing": missing,
        "missing_reason": reason,
        "low_confidence": low_conf,
    }


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
    if 'projection_replay_version' in calibration or 'camera_model' in calibration:
        tri = StereoTriangulator(calibration)
        left, right = tri.rectify_pair(pl, pr)
        ul, ur = left[0], right[0]
        axis = tri.epipolar_axis
    else:
        # Preserve replay of historical snapshots with OpenCV's original
        # inverse and horizontal epipolar convention.
        ul, ur = (cv2.undistortPoints(uv.reshape(1, 1, 2), calibration[f"K{i}"],
                  calibration[f"D{i}"], R=calibration[f"R{i}"], P=calibration[f"P{i}"]).reshape(2)
                  for i, uv in enumerate((pl, pr), 1))
        axis = 1
    if not (np.isfinite(ul).all() and np.isfinite(ur).all()):
        return None
    return {
        "rectified_uv_left": ul.tolist(), "rectified_uv_right": ur.tolist(),
        "signed_y_delta_px": float(ul[1] - ur[1]),
        "epipolar_error_px": abs(float(ul[axis] - ur[axis])),
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
    if isinstance(triangulator, StereoTriangulator):
        bundle['projection_replay_version'] = np.array(1)
        if not triangulator.legacy_projection:
            bundle['camera_model'] = np.array(triangulator.camera_model)
        if triangulator.image_size:
            bundle['image_size'] = np.array(triangulator.image_size)
    return bundle


def annotate_frame(frame, keypoints, confidence) -> np.ndarray:
    """Return a copy of ``frame`` with upper-body keypoints labelled.

    Never mutates the caller's raw buffer. Review B1: keypoints whose uv is
    non-finite (NaN/Inf) or whose confidence is absent/non-positive are skipped
    safely — a NaN coordinate can never round its way into cv2 drawing calls
    (which would abort the whole snapshot).
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
        uv = _finite_pair(keypoints[i])
        conf = None if confidence is None or i >= len(confidence) else _finite_conf(confidence[i])
        if uv is None or conf is None or conf <= 0.0:
            continue
        x, y = int(round(uv[0])), int(round(uv[1]))
        cv2.circle(img, (x, y), 3, (0, 255, 0), -1)
        cv2.putText(
            img, f"{name} {conf:.2f}", (x + 4, y - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA,
        )
    return img


def _pose_to_dict(pose: SnapshotPose, confidence_threshold=None) -> Dict[str, Any]:
    keypoints = [
        _observation(pose, i, name, confidence_threshold)
        for i, name in enumerate(JOINT_NAMES)
    ]
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
    confidence_threshold=None,
) -> Dict[str, Any]:
    i = JOINT_INDEX[name]

    left = _observation(pose_left, i, name, confidence_threshold)
    right = _observation(pose_right, i, name, confidence_threshold)

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
            rectified["missing_reason"] = "invalid keypoint or inverse projection"
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
    confidence_threshold=None,
    now: Optional[datetime] = None,
) -> Path:
    """Write a diagnostic snapshot and return its directory path.

    All inputs are the exact objects from one tracking iteration. This function
    performs no camera reads and no inference. Any I/O failure raises and is
    handled by the caller so tracking keeps running.

    Review follow-up: all files are first written into a ``.partial`` staging
    directory and only atomically renamed to the final snapshot folder once
    complete, so a failed save can never leave a half-written folder that looks
    like valid evidence (the staging directory is removed on failure; only the
    freshly created staging directory is ever touched, never a historical
    snapshot).

    ``confidence_threshold`` is the runner's keypoint acceptance threshold
    (``pose.keypoint_confidence``); it only annotates the manifest with
    ``low_confidence`` flags and never gates what raw data is preserved.
    """
    staging, final = _new_snapshot_dir(runtime_root, now)
    try:
        _write_image(staging / "left_raw.png", frame_left)
        _write_image(staging / "right_raw.png", frame_right)
        _write_image(staging / "left_annotated.png", annotate_frame(frame_left, pose_left.keypoints, pose_left.confidence))
        _write_image(staging / "right_annotated.png", annotate_frame(frame_right, pose_right.keypoints, pose_right.confidence))

        calibration = calibrate_bundle(triangulator)
        cal_sha = _sha256_file(Path(calib_path)) if calib_path is not None else None

        if calibration is not None:
            np.savez(staging / "calibration_snapshot.npz", **calibration)

        verdict_map = {getattr(v, "joint_name", None): v for v in verdicts}

        utc_now = _utc_now(now)
        if wall_timestamp_ns is not None:
            wall_utc = datetime.fromtimestamp(float(wall_timestamp_ns) / 1e9, tz=timezone.utc).isoformat()
        else:
            wall_utc = utc_now.isoformat()

        manifest: Dict[str, Any] = {
            "schema": SNAPSHOT_SCHEMA,
            "snapshot_id": final.name,
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
                "note": (
                    "host observation only; NOT sensor exposure synchronization. "
                    "pair_cycle_ms measures the camera grab/retrieve pair only, "
                    "not the full processing-loop rate."
                ),
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
                "confidence_threshold": None if confidence_threshold is None else float(confidence_threshold),
                "left": _pose_to_dict(pose_left, confidence_threshold),
                "right": _pose_to_dict(pose_right, confidence_threshold),
            },
            "joints": [
                _joint_entry(name, pose_left, pose_right, calibration, verdict_map.get(name), confidence_threshold)
                for name in selected_joints
            ],
        }
        _write_json(staging / "manifest.json", manifest)

        _write_text = README_TEMPLATE.format(snapshot_id=final.name)
        _atomic_write_bytes(staging / "README.txt", _write_text.encode("utf-8"))

        return _promote_snapshot(staging, final)
    except BaseException:
        # Only the freshly created staging directory is removed; historical
        # snapshots and calibrations are never touched.
        shutil.rmtree(staging, ignore_errors=True)
        raise


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

manifest.json keeps the RAW observed keypoint uv/confidence for every joint —
including zero-valued "not detected" placeholders (confidence <= 0) — and marks
usability separately: `missing` + `missing_reason` say why a keypoint is not
usable, `low_confidence` flags detected-but-subthreshold evidence. A snapshot
folder only ever appears complete: writes are staged in a `.partial` directory
and atomically renamed, so any leftover `.partial` directory is a failed save.

Replay the epipolar errors offline with:

  python tools/inspect_snapshot.py <this-directory>

Only NumPy and OpenCV are required; no camera, torch, CUDA, YOLO or model
weights. This folder contains human imagery — never commit or upload it to a
repository or external service.
"""
