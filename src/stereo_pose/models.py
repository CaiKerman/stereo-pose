"""Typed internal data models.

These dataclasses keep the distinctions required by the project contract:

* raw measurement vs. accepted/rejected measurement vs. filtered value;
* coordinate system;
* units;
* timestamps;
* quality metrics.

They are intentionally plain data holders; numerical behavior lives in the
corresponding modules (``geometry``, ``filtering``, ``quality``, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

Vec2 = Tuple[float, float]
Vec3 = Tuple[float, float, float]


@dataclass
class FrameTiming:
    """Host-side timing diagnostics for a stereo frame pair.

    ``host_grab_skew_ms`` is a host grab diagnostic only; it is NOT the sensor
    exposure time difference between the two webcams.
    """

    host_grab_skew_ms: Optional[float] = None
    pair_cycle_ms: Optional[float] = None
    host_midpoint_perf_ns: Optional[int] = None
    wall_timestamp_ns: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FrameTiming":
        return cls(
            host_grab_skew_ms=d.get("host_grab_skew_ms"),
            pair_cycle_ms=d.get("pair_cycle_ms"),
            host_midpoint_perf_ns=d.get("host_midpoint_perf_ns"),
            wall_timestamp_ns=d.get("wall_timestamp_ns"),
        )


@dataclass
class StereoFramePair:
    """A matched left/right image pair plus its timing metadata."""

    left: np.ndarray
    right: np.ndarray
    timing: FrameTiming
    frame_index: int = 0


@dataclass
class Joint2DObservation:
    """A single joint observed in both rectified views (raw 2D detection)."""

    joint_name: str
    uv_left: np.ndarray  # (2,)
    uv_right: np.ndarray  # (2,)
    confidence_left: float
    confidence_right: float


@dataclass
class RawJoint3D:
    """A raw triangulated 3D joint before geometric acceptance/filtering."""

    joint_name: str
    xyz_mm: np.ndarray  # (3,) in rectified-left-camera coordinates
    epipolar_error_px: float
    reprojection_error_left_px: float
    reprojection_error_right_px: float
    reprojection_error_mean_px: float
    reprojection_error_max_px: float
    rectified_uv_left: np.ndarray  # (2,)
    rectified_uv_right: np.ndarray  # (2,)


@dataclass
class JointQuality:
    """Per-joint measurement quality metrics."""

    score: float
    epipolar_error_px: float
    reprojection_error_mean_px: float
    reprojection_error_max_px: float
    speed_mm_s: float = 0.0


@dataclass
class FilteredJoint3D:
    """A joint that passed quality gates, including filtered + raw 3D values."""

    joint_name: str
    xyz_mm: Vec3  # filtered
    xyz_raw_mm: Vec3  # raw (post-quality, pre-smoothing)
    quality: JointQuality
    confidence_left: float
    confidence_right: float
    uv_left: Vec2  # left detection pixel (x, y)
    uv_right: Vec2
    rectified_uv_left: Vec2
    rectified_uv_right: Vec2


@dataclass
class StereoCalibrationMetadata:
    """Metadata attached to a versioned stereo calibration NPZ artifact.

    Array fields default to ``None`` and are populated by
    :class:`stereo_pose.calibration.metadata.load_calibration_metadata`.
    """

    path: Optional[Path] = None
    schema_version: str = "1"

    K1: Optional[np.ndarray] = None
    D1: Optional[np.ndarray] = None
    K2: Optional[np.ndarray] = None
    D2: Optional[np.ndarray] = None
    R: Optional[np.ndarray] = None
    T: Optional[np.ndarray] = None
    E: Optional[np.ndarray] = None
    F: Optional[np.ndarray] = None
    R1: Optional[np.ndarray] = None
    R2: Optional[np.ndarray] = None
    P1: Optional[np.ndarray] = None
    P2: Optional[np.ndarray] = None
    Q: Optional[np.ndarray] = None

    image_size: Optional[Tuple[int, int]] = None  # (width, height)
    board_cols: Optional[int] = None
    board_rows: Optional[int] = None
    square_mm: Optional[float] = None
    left_rms: Optional[float] = None
    right_rms: Optional[float] = None
    stereo_rms: Optional[float] = None
    sample_count: Optional[int] = None
    sample_count_initial: Optional[int] = None
    pruned_count: Optional[int] = None
    sample_epipolar_mean_px: Optional[float] = None
    sample_epipolar_max_px: Optional[float] = None
    readiness: Optional[float] = None
    created_at: Optional[str] = None

    camera_left: Optional[int] = None
    camera_right: Optional[int] = None
    camera_backend: Optional[str] = None
    camera_requested_size: Optional[Tuple[int, int]] = None  # (width, height)
    camera_requested_fps: Optional[float] = None
    camera_actual_fps: Optional[float] = None

    warnings: list = field(default_factory=list)


@dataclass
class CoordinateTransformMetadata:
    """Description of a coordinate transform (source/target, params, units).

    The world-axis convention is intentionally NOT defined by this scaffold:
    ground ``Z=0`` and ``+Z`` upward are the only fixed future requirements.
    """

    source_system: str
    target_system: str
    rotation: np.ndarray  # (3,3)
    translation: np.ndarray  # (3,) in target units
    units: str = "mm"
    note: str = ""


@dataclass
class PoseFrame:
    """A single assembled output frame (one per stereo pair)."""

    frame_index: int
    wall_timestamp_ns: Optional[int]
    coordinate_system: str
    unit: str
    calibration_file: Optional[str]
    timing: FrameTiming
    filtering: Dict[str, Any]
    frame_quality: Dict[str, Any]
    joints: Dict[str, FilteredJoint3D] = field(default_factory=dict)