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
) -> StereoCalibrationMetadata:
    """Load a calibration NPZ into :class:`StereoCalibrationMetadata`.

    Checks required keys, then optionally warns about resolution/board-geometry
    mismatches against caller expectations.
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
    return meta