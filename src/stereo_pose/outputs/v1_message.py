"""``stereo_pose_3d/v1`` message serialization (compatibility adapter).

External consumers receive exactly the v1.2 field names and units. Internal
typed models (:class:`stereo_pose.models.PoseFrame`) are adapted here so the
wire format stays stable even if internal structures change.
"""

from __future__ import annotations

from stereo_pose import V1_SCHEMA
from stereo_pose.models import PoseFrame

_TIMING_WARNING = "host timing only; not sensor exposure timestamps"


def _joint_to_v1(j) -> dict:
    return {
        "xyz_mm": [float(x) for x in j.xyz_mm],
        "xyz_raw_mm": [float(x) for x in j.xyz_raw_mm],
        "confidence": {
            "left": float(j.confidence_left),
            "right": float(j.confidence_right),
        },
        "quality": {
            "score": float(j.quality.score),
            "epipolar_error_px": float(j.quality.epipolar_error_px),
            "reprojection_error_mean_px": float(j.quality.reprojection_error_mean_px),
            "reprojection_error_max_px": float(j.quality.reprojection_error_max_px),
            "speed_mm_s": float(j.quality.speed_mm_s),
        },
        "uv": {
            "left": [float(j.uv_left[0]), float(j.uv_left[1])],
            "right": [float(j.uv_right[0]), float(j.uv_right[1])],
            "rectified_left": [float(j.rectified_uv_left[0]), float(j.rectified_uv_left[1])],
            "rectified_right": [float(j.rectified_uv_right[0]), float(j.rectified_uv_right[1])],
        },
    }


def to_v1_message(frame: PoseFrame) -> dict:
    """Serialize a :class:`PoseFrame` into the ``stereo_pose_3d/v1.2`` message."""
    timing = {
        "host_grab_skew_ms": frame.timing.host_grab_skew_ms,
        "pair_cycle_ms": frame.timing.pair_cycle_ms,
        "warning": _TIMING_WARNING,
    }
    return {
        "schema": V1_SCHEMA,
        "timestamp_ns": frame.wall_timestamp_ns,
        "frame_index": frame.frame_index,
        "unit": frame.unit,
        "coordinate_system": frame.coordinate_system,
        "calibration_file": frame.calibration_file,
        "timing": timing,
        "filtering": frame.filtering,
        "frame_quality": frame.frame_quality,
        "joints": {name: _joint_to_v1(j) for name, j in frame.joints.items()},
    }


def serialize_v1_json(frame: PoseFrame) -> str:
    """Serialize a :class:`PoseFrame` to a JSON string (compat with JSONL/UDP)."""
    import json

    return json.dumps(to_v1_message(frame), ensure_ascii=False, separators=(",", ":"))