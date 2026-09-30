"""Stereo calibration metadata loading with compatibility checks.

Loads the versioned ``stereo_YYYYMMDD_HHMMSS.npz`` artifacts produced by the
solver and surfaces resolution/config mismatches as warnings rather than
silently assuming validity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from stereo_pose.models import StereoCalibrationMetadata

_REQUIRED = ["K1", "D1", "K2", "D2", "R1", "R2", "P1", "P2"]

_VEC_FIELDS = [
    "K1", "D1", "K2", "D2", "R", "T", "E", "F",
    "R1", "R2", "P1", "P2", "Q",
]
_SCALAR_FIELDS = [
    "left_rms", "right_rms", "stereo_rms",
    "sample_count", "sample_count_initial", "pruned_count",
    "sample_epipolar_mean_px", "sample_epipolar_max_px",
    "board_cols", "board_rows", "square_mm", "readiness",
]


def _to_float_array(v) -> np.ndarray:
    return np.asarray(v, dtype=float)


def load_calibration_metadata(
    path,
    expected_image_size: Optional[Tuple[int, int]] = None,
    expected_board: Optional[Tuple[int, int]] = None,
    expected_fps: Optional[float] = None,
) -> StereoCalibrationMetadata:
    """Load a calibration NPZ into :class:`StereoCalibrationMetadata`.

    Checks required keys, then optionally warns about resolution/board-geometry/
    fps mismatches against caller expectations.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Calibration file not found: {p}")
    c = np.load(p, allow_pickle=False)

    missing = [k for k in _REQUIRED if k not in c]
    if missing:
        raise ValueError(f"Calibration file missing keys: {missing}")

    meta = StereoCalibrationMetadata(path=p)
    for field in _VEC_FIELDS:
        if field in c:
            setattr(meta, field, _to_float_array(c[field]))
    for field in _SCALAR_FIELDS:
        if field in c:
            setattr(meta, field, float(np.asarray(c[field]).reshape(-1)[0]))

    if "image_size" in c:
        size = np.asarray(c["image_size"]).reshape(-1).astype(int)
        meta.image_size = (int(size[0]), int(size[1]))
    if "created_at" in c:
        meta.created_at = str(np.asarray(c["created_at"]).reshape(-1)[0])
    if "_schema_version" in c:
        meta.schema_version = str(np.asarray(c["_schema_version"]).reshape(-1)[0])

    if "camera_left" in c:
        meta.camera_left = int(np.asarray(c["camera_left"]).reshape(-1)[0])
    if "camera_right" in c:
        meta.camera_right = int(np.asarray(c["camera_right"]).reshape(-1)[0])
    if "camera_backend" in c:
        meta.camera_backend = str(np.asarray(c["camera_backend"]).reshape(-1)[0])
    if "camera_requested_size" in c:
        cs = np.asarray(c["camera_requested_size"]).reshape(-1).astype(int)
        meta.camera_requested_size = (int(cs[0]), int(cs[1]))
    if "camera_requested_fps" in c:
        meta.camera_requested_fps = float(np.asarray(c["camera_requested_fps"]).reshape(-1)[0])
    if "camera_actual_fps" in c:
        meta.camera_actual_fps = float(np.asarray(c["camera_actual_fps"]).reshape(-1)[0])

    # Compatibility warnings (never silently assume validity).
    if expected_image_size is not None and meta.image_size is not None:
        if tuple(meta.image_size) != tuple(expected_image_size):
            meta.warnings.append(
                f"calibration image_size {meta.image_size} != expected {expected_image_size}"
            )
    if expected_board is not None and meta.board_cols is not None and meta.board_rows is not None:
        if (meta.board_cols, meta.board_rows) != tuple(expected_board):
            meta.warnings.append(
                f"calibration board {meta.board_cols}x{meta.board_rows} "
                f"!= expected {expected_board}"
            )
    if expected_fps is not None and meta.camera_requested_fps is not None:
        if float(meta.camera_requested_fps) != float(expected_fps):
            meta.warnings.append(
                f"calibration requested_fps {meta.camera_requested_fps} != expected {expected_fps}"
            )
    return meta


def validate_calibration_compatibility(
    path,
    image_size,
    board=None,
    fps=None,
) -> list:
    """Return compatibility warning strings for a calibration vs. an active capture.

    Pure and deterministic (no printing): loads the artifact metadata and
    compares its recorded image size / board geometry / FPS against the caller's
    expectations. Used by the live load path before a calibration is activated.
    """
    meta = load_calibration_metadata(
        path,
        expected_image_size=tuple(image_size) if image_size is not None else None,
        expected_board=tuple(board) if board is not None else None,
        expected_fps=None if fps is None else float(fps),
    )
    return meta.warnings