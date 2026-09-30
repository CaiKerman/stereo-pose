"""Checkerboard 3D metric validation.

Uses the active stereo calibration and the already-printed checkerboard to
quantify metric scale, flatness, and stereo geometry error without introducing
any world-coordinate convention. All coordinates remain in the
rectified-left-camera frame and all units are millimetres.

The metric math is deliberately separated from triangulation so it can be tested
deterministically with synthetic cameras and synthetic planar boards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

SCHEMA = "stereo_pose_3d/metric_validation/v1"
SAMPLE_MODE = "single_frame"

# A rectified-stereo correspondence is geometrically plausible only when every
# corner triangulates and the mean vertical-disparity (epipolar) error stays
# under this many pixels. A wrong 180-degree pairing matches corners from
# different board rows, so its vertical disparity is on the order of a board row
# (tens of pixels). This threshold gates correspondence only and is not a
# measurement threshold.
MAX_PLAUSIBLE_MEAN_EPIPOLAR_PX = 5.0


class MetricValidationError(RuntimeError):
    """Raised when a validation capture cannot produce trustworthy metrics."""


@dataclass
class MetricValidationResult:
    """A single checkerboard metric-validation measurement."""

    expected_spacing_mm: float
    board_cols: int
    board_rows: int
    sample_mode: str
    calibration_file: Optional[str]
    timestamp: str
    corners_total: int
    corners_valid: int
    horizontal: Dict[str, Any]
    vertical: Dict[str, Any]
    combined_mean_spacing_mm: Optional[float]
    scale_error_percent: Optional[float]
    plane: Dict[str, Optional[float]]
    epipolar: Dict[str, Optional[float]]
    reprojection: Dict[str, Optional[float]]
    depth_range_mm: Dict[str, Optional[float]]
    corner_order_mode: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA,
            "timestamp": self.timestamp,
            "sample_mode": self.sample_mode,
            "calibration_file": self.calibration_file,
            "expected_spacing_mm": self.expected_spacing_mm,
            "board": {"cols": self.board_cols, "rows": self.board_rows},
            "corners": {"total": self.corners_total, "valid": self.corners_valid},
            "horizontal": self.horizontal,
            "vertical": self.vertical,
            "combined_mean_spacing_mm": self.combined_mean_spacing_mm,
            "scale_error_percent": self.scale_error_percent,
            "plane": self.plane,
            "epipolar": self.epipolar,
            "reprojection": self.reprojection,
            "depth_range_mm": self.depth_range_mm,
            "corner_order_mode": self.corner_order_mode,
        }


def detect_checkerboard(frame, cols: int, rows: int):
    """Detect a full ``(cols, rows)`` internal-corner grid, or return ``None``.

    Reuses the same detector and flags as runtime calibration for consistency.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ok, corners = cv2.findChessboardCornersSB(
        gray, (int(cols), int(rows)), flags=cv2.CALIB_CB_NORMALIZE_IMAGE
    )
    if not ok:
        return None
    return corners.reshape(-1, 2).astype(np.float32)


def triangulate_corners(triangulator, corners_left, corners_right) -> List[Optional[Dict]]:
    """Triangulate every matched corner; a ``None`` marks an invalid corner."""
    out = []
    for pl, pr in zip(corners_left, corners_right):
        out.append(triangulator.triangulate_with_quality(pl, pr))
    return out


def _candidate_fit(triangulator, corners_left, corners_right):
    """Return ``(valid, total, mean_epipolar_px)`` for one right-camera ordering."""
    total = min(len(corners_left), len(corners_right))
    epi: List[float] = []
    valid = 0
    for pl, pr in zip(corners_left, corners_right):
        q = triangulator.triangulate_with_quality(pl, pr)
        if q is None:
            continue
        valid += 1
        epi.append(float(q["epipolar_error_px"]))
    mean = float(np.mean(epi)) if epi else float("inf")
    return valid, total, mean


def normalize_correspondence(triangulator, corners_left, corners_right):
    """Choose a right-camera corner ordering consistent with the left camera.

    ``cv2.findChessboardCornersSB`` can report a rectangular board's corners in
    either of two 180-degree-related orderings. Pairing them positionally would
    then create wrong correspondences and spuriously inflate the metric error.

    Two orderings are scored with stereo-geometry evidence only (mean rectified
    epipolar error; the expected ``square_mm`` is never consulted):

    * ``direct``       — pair ``left[k]`` with ``right[k]``;
    * ``reversed_180`` — pair ``left[k]`` with ``right[-1-k]`` (180 degree).

    Returns ``(ordered_right_corners, mode)`` for the plausible ordering with the
    lowest aggregate epipolar error, or ``None`` when neither ordering is
    geometrically plausible.
    """
    if len(corners_left) == 0 or len(corners_right) == 0:
        return None

    reversed_right = corners_right[::-1]
    v_direct, t_direct, e_direct = _candidate_fit(
        triangulator, corners_left, corners_right
    )
    v_rev, t_rev, e_rev = _candidate_fit(triangulator, corners_left, reversed_right)

    best_mode = None
    best_error = float("inf")
    for mode, valid, total, err in (
        ("direct", v_direct, t_direct, e_direct),
        ("reversed_180", v_rev, t_rev, e_rev),
    ):
        # Full triangulation is required: a correct correspondence triangulates
        # every detected corner; a failed corner signals a broken board/rig.
        if valid != total or err > MAX_PLAUSIBLE_MEAN_EPIPOLAR_PX:
            continue
        if err < best_error:  # ties keep the earlier candidate (direct)
            best_error = err
            best_mode = mode

    if best_mode is None:
        return None
    ordered = corners_right if best_mode == "direct" else reversed_right
    return ordered, best_mode


def _edge_stats(edges: List[float], expected: float) -> Dict[str, Any]:
    n = len(edges)
    if n == 0:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "rmse": None,
            "max_abs_error": None,
        }
    arr = np.asarray(edges, dtype=float)
    err = arr - float(expected)
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    return {
        "count": int(n),
        "mean": float(arr.mean()),
        "std": float(std),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "max_abs_error": float(np.max(np.abs(err))),
    }


def _mean_max(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"mean_px": None, "max_px": None}
    arr = np.asarray(values, dtype=float)
    return {"mean_px": float(arr.mean()), "max_px": float(arr.max())}


def _fit_plane(points: np.ndarray) -> Dict[str, Optional[float]]:
    """Best-fit plane via SVD; returns point-to-plane residual stats in mm."""
    pts = np.asarray(points, dtype=float)
    if pts.shape[0] < 3 or not np.all(np.isfinite(pts)):
        return {"rms_residual_mm": None, "max_abs_residual_mm": None}
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    normal /= np.linalg.norm(normal)
    signed = centered @ normal
    return {
        "rms_residual_mm": float(np.sqrt(np.mean(signed ** 2))),
        "max_abs_residual_mm": float(np.max(np.abs(signed))),
    }


def compute_metrics_from_triangulations(
    triangulations: List[Optional[Dict]],
    *,
    board_cols: int,
    board_rows: int,
    square_mm: float,
    calibration_file: Optional[str] = None,
    timestamp: Optional[str] = None,
    sample_mode: str = SAMPLE_MODE,
    corner_order_mode: Optional[str] = None,
) -> MetricValidationResult:
    """Compute metric-validation metrics from a per-corner triangulation list.

    ``triangulations`` must be ordered consistently with the calibration object
    grid: index ``k`` -> ``row = k // board_cols``, ``col = k % board_cols``.
    A ``None`` entry marks an invalid corner (skipped from all metrics).
    """
    cols = int(board_cols)
    rows = int(board_rows)
    total = cols * rows
    expected = float(square_mm)

    n = min(len(triangulations), total)
    pts = [None] * total
    epi_errors: List[float] = []
    reproj_errors: List[float] = []
    for k in range(n):
        q = triangulations[k]
        if q is None:
            continue
        pts[k] = q["xyz_mm"]
        epi_errors.append(float(q["epipolar_error_px"]))
        reproj_errors.append(float(q["reprojection_error_max_px"]))
    valid = sum(1 for p in pts if p is not None)

    horizontal: List[float] = []
    vertical: List[float] = []
    for r in range(rows):
        for c in range(cols - 1):
            a, b = pts[r * cols + c], pts[r * cols + c + 1]
            if a is not None and b is not None:
                horizontal.append(float(np.linalg.norm(np.asarray(a) - np.asarray(b))))
    for r in range(rows - 1):
        for c in range(cols):
            a, b = pts[r * cols + c], pts[(r + 1) * cols + c]
            if a is not None and b is not None:
                vertical.append(float(np.linalg.norm(np.asarray(a) - np.asarray(b))))

    combined = horizontal + vertical
    combined_mean = float(np.mean(combined)) if combined else None
    scale_error = (
        (combined_mean - expected) / expected * 100.0 if combined_mean is not None else None
    )

    valid_points = [np.asarray(p, dtype=float) for p in pts if p is not None]
    if valid_points:
        zs = [float(p[2]) for p in valid_points]
        depth_range = {"min": min(zs), "max": max(zs), "span": max(zs) - min(zs)}
    else:
        depth_range = {"min": None, "max": None, "span": None}

    return MetricValidationResult(
        expected_spacing_mm=expected,
        board_cols=cols,
        board_rows=rows,
        sample_mode=sample_mode,
        calibration_file=calibration_file,
        timestamp=timestamp or "",
        corners_total=total,
        corners_valid=valid,
        horizontal=_edge_stats(horizontal, expected),
        vertical=_edge_stats(vertical, expected),
        combined_mean_spacing_mm=combined_mean,
        scale_error_percent=scale_error,
        plane=_fit_plane(np.asarray(valid_points, dtype=float)),
        epipolar=_mean_max(epi_errors),
        reprojection=_mean_max(reproj_errors),
        depth_range_mm=depth_range,
        corner_order_mode=corner_order_mode,
    )


def compute_metric_validation(
    triangulator,
    corner_det_l,
    corner_det_r,
    *,
    board_cols: int,
    board_rows: int,
    square_mm: float,
    calibration_file: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> MetricValidationResult:
    """Triangulate matched checkerboard corners and compute validation metrics.

    Correspondence between the two detected grids is normalized first (the two
    cameras may report 180-degree-related orderings). Raises
    :class:`MetricValidationError` when neither ordering is geometrically
    plausible.
    """
    decision = normalize_correspondence(triangulator, corner_det_l, corner_det_r)
    if decision is None:
        raise MetricValidationError(
            "checkerboard corner correspondence is not geometrically plausible "
            "under either the direct or 180-degree ordering"
        )
    ordered_right, mode = decision
    triangulations = triangulate_corners(triangulator, corner_det_l, ordered_right)
    return compute_metrics_from_triangulations(
        triangulations,
        board_cols=board_cols,
        board_rows=board_rows,
        square_mm=square_mm,
        calibration_file=calibration_file,
        timestamp=timestamp,
        corner_order_mode=mode,
    )


def render_summary(result: MetricValidationResult) -> str:
    """Render a compact, human-readable single-frame validation summary."""
    h = result.horizontal
    v = result.vertical
    lines = [
        "Metric validation (single frame)",
        f"expected spacing : {result.expected_spacing_mm:.3f} mm",
        f"corners          : {result.corners_valid}/{result.corners_total}",
    ]
    if h["count"]:
        lines.append(
            f"horizontal       : mean {h['mean']:.2f}, std {h['std']:.2f}, "
            f"RMSE {h['rmse']:.2f}, max abs err {h['max_abs_error']:.2f} mm "
            f"(n={h['count']})"
        )
    else:
        lines.append("horizontal       : no valid edges")
    if v["count"]:
        lines.append(
            f"vertical         : mean {v['mean']:.2f}, std {v['std']:.2f}, "
            f"RMSE {v['rmse']:.2f}, max abs err {v['max_abs_error']:.2f} mm "
            f"(n={v['count']})"
        )
    else:
        lines.append("vertical         : no valid edges")
    combined = result.combined_mean_spacing_mm
    if combined is not None:
        lines.append(f"combined mean    : {combined:.2f} mm")
        lines.append(f"scale error      : {result.scale_error_percent:+.2f} %")
    p = result.plane
    if p["rms_residual_mm"] is not None:
        lines.append(f"plane RMS        : {p['rms_residual_mm']:.2f} mm")
        lines.append(f"plane max        : {p['max_abs_residual_mm']:.2f} mm")
    e = result.epipolar
    if e["mean_px"] is not None:
        lines.append(f"epi mean/max     : {e['mean_px']:.2f} / {e['max_px']:.2f} px")
    rp = result.reprojection
    if rp["mean_px"] is not None:
        lines.append(f"reproj mean/max  : {rp['mean_px']:.2f} / {rp['max_px']:.2f} px")
    dr = result.depth_range_mm
    if dr["min"] is not None:
        lines.append(f"depth range      : {dr['min']:.0f} .. {dr['max']:.0f} mm")
    lines.append(f"calibration     : {result.calibration_file or 'NONE'}")
    return "\n".join(lines)


def timestamp_now() -> str:
    return datetime.now().isoformat(timespec="seconds")