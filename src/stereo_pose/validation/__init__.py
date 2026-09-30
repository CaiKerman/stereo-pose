"""Metric validation subsystem (checkerboard 3D scale/flatness reporting)."""

from stereo_pose.validation.metrics import (
    SCHEMA,
    MetricValidationResult,
    compute_metric_validation,
    compute_metrics_from_triangulations,
    detect_checkerboard,
    render_summary,
    timestamp_now,
    triangulate_corners,
)
from stereo_pose.validation.report import (
    ValidationPathError,
    is_within_validation_root,
    save_validation_report,
    validation_dir,
)

__all__ = [
    "SCHEMA",
    "MetricValidationResult",
    "ValidationPathError",
    "compute_metric_validation",
    "compute_metrics_from_triangulations",
    "detect_checkerboard",
    "is_within_validation_root",
    "render_summary",
    "save_validation_report",
    "timestamp_now",
    "triangulate_corners",
    "validation_dir",
]