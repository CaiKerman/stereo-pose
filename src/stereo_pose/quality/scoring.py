"""Measurement quality: heuristic score, accept/reject decisions, and diagnostics.

Ported from the v1.2 ``heuristic_quality_score`` in
``reference/v1_2/main.py`` plus an extracted, deterministic accept/reject helper.
The quality score is a heuristic combining pose confidence and geometric error;
it is not a statistical probability.

``classify_joint`` adds fine-grained, per-joint terminal-state classification
without changing acceptance/rejection behavior; the coarse ``evaluate_measurement``
result and the aggregate ``rejected`` counters are preserved.
"""

from __future__ import annotations

import math
from typing import Optional

from stereo_pose.models import JointRejection


def heuristic_quality_score(conf_l, conf_r, epi_px, reproj_px, qcfg) -> float:
    """Heuristic 0..1 quality score (matching the v1.2 reference)."""
    base = math.sqrt(max(0.0, float(conf_l)) * max(0.0, float(conf_r)))
    epi_scale = max(float(qcfg["max_epipolar_error_px"]), 1e-6)
    rep_scale = max(float(qcfg["max_reprojection_error_px"]), 1e-6)
    geom = math.exp(-float(epi_px) / epi_scale) * math.exp(-float(reproj_px) / rep_scale)
    return float(max(0.0, min(1.0, base * geom)))


class RejectionReason:
    # Coarse aggregate buckets (kept for ``stereo_pose_3d/v1.2`` ``rejected``).
    KEYPOINT_CONFIDENCE = "keypoint_confidence"
    GEOMETRY = "geometry"
    DEPTH = "depth"
    QUALITY_SCORE = "quality_score"
    SPEED = "speed"

    # Fine-grained terminal states (Task 002 per-joint diagnostics).
    ACCEPTED = "accepted"
    LEFT_KEYPOINT_CONFIDENCE = "left_keypoint_confidence"
    RIGHT_KEYPOINT_CONFIDENCE = "right_keypoint_confidence"
    BOTH_KEYPOINT_CONFIDENCE = "both_keypoint_confidence"
    GEOMETRY_UNAVAILABLE = "geometry_unavailable"
    EPIPOLAR_THRESHOLD = "epipolar_threshold"
    REPROJECTION_THRESHOLD = "reprojection_threshold"
    DEPTH_BELOW_MIN = "depth_below_min"
    DEPTH_ABOVE_MAX = "depth_above_max"
    CALIBRATION_UNAVAILABLE = "calibration_unavailable"
    MISSING_POSE = "missing_pose"


# Fine-grained state -> coarse v1.2 aggregate bucket. ``None`` means a state is
# not counted in the legacy ``rejected`` aggregate (accepted, missing pose,
# no-calibration-loaded). ``no-calibration`` and ``missing pose`` were handled
# in v1.2 by skipping the joint loop entirely, so they must not be counted.
_COARSE_BUCKET = {
    RejectionReason.LEFT_KEYPOINT_CONFIDENCE: RejectionReason.KEYPOINT_CONFIDENCE,
    RejectionReason.RIGHT_KEYPOINT_CONFIDENCE: RejectionReason.KEYPOINT_CONFIDENCE,
    RejectionReason.BOTH_KEYPOINT_CONFIDENCE: RejectionReason.KEYPOINT_CONFIDENCE,
    RejectionReason.GEOMETRY_UNAVAILABLE: RejectionReason.GEOMETRY,
    RejectionReason.EPIPOLAR_THRESHOLD: RejectionReason.GEOMETRY,
    RejectionReason.REPROJECTION_THRESHOLD: RejectionReason.GEOMETRY,
    RejectionReason.DEPTH_BELOW_MIN: RejectionReason.DEPTH,
    RejectionReason.DEPTH_ABOVE_MAX: RejectionReason.DEPTH,
    RejectionReason.QUALITY_SCORE: RejectionReason.QUALITY_SCORE,
    RejectionReason.SPEED: RejectionReason.SPEED,
}


def aggregate_bucket(state: str) -> Optional[str]:
    """Map a fine-grained terminal state to its coarse v1.2 aggregate bucket."""
    return _COARSE_BUCKET.get(state)


def classify_joint(
    joint_name,
    *,
    conf_l,
    conf_r,
    keypoint_confidence,
    geometry,
    qcfg,
    speed_result=None,
    missing_pose=False,
    calibration_available=True,
) -> JointRejection:
    """Classify one selected joint's frame result into exactly one terminal state.

    Parameters mirror the ordered gate chain of the live pipeline: pose presence,
    calibration availability, per-view keypoint confidence, triangulation
    availability, epipolar, reprojection, depth, quality score, and speed.

    ``geometry`` is the ``StereoTriangulator.triangulate_with_quality`` dict (or
    ``None`` when triangulation produced no result). ``speed_result`` is either
    ``None`` or an ``(accepted: bool, speed_mm_s: float)`` tuple from the
    temporal speed gate.
    """
    metrics = {}

    def fail(state, detail):
        return JointRejection(joint_name, state, False, detail, metrics)

    if missing_pose:
        metrics["missing_pose"] = True
        return fail(RejectionReason.MISSING_POSE, "missing person/pose on one or both cameras")

    if not calibration_available:
        metrics["calibration_available"] = False
        return fail(RejectionReason.CALIBRATION_UNAVAILABLE, "no stereo calibration loaded")

    left_low = float(conf_l) < float(keypoint_confidence)
    right_low = float(conf_r) < float(keypoint_confidence)
    metrics["conf_l"] = float(conf_l)
    metrics["conf_r"] = float(conf_r)
    metrics["keypoint_confidence"] = float(keypoint_confidence)
    if left_low and right_low:
        return fail(
            RejectionReason.BOTH_KEYPOINT_CONFIDENCE,
            f"both_conf {conf_l:.2f},{conf_r:.2f} < {keypoint_confidence}",
        )
    if left_low:
        return fail(
            RejectionReason.LEFT_KEYPOINT_CONFIDENCE,
            f"left_conf {conf_l:.2f} < {keypoint_confidence}",
        )
    if right_low:
        return fail(
            RejectionReason.RIGHT_KEYPOINT_CONFIDENCE,
            f"right_conf {conf_r:.2f} < {keypoint_confidence}",
        )

    if geometry is None:
        return fail(RejectionReason.GEOMETRY_UNAVAILABLE, "triangulation unavailable")

    epi = float(geometry["epipolar_error_px"])
    rep = float(geometry["reprojection_error_max_px"])
    xyz = geometry["xyz_mm"]
    z = float(xyz[2])
    metrics["epipolar_error_px"] = epi
    metrics["reprojection_error_max_px"] = rep
    metrics["depth_mm"] = z

    max_epi = float(qcfg["max_epipolar_error_px"])
    max_rep = float(qcfg["max_reprojection_error_px"])
    if epi > max_epi:
        return fail(RejectionReason.EPIPOLAR_THRESHOLD, f"epipolar {epi:.2f} > {max_epi} px")
    if rep > max_rep:
        return fail(RejectionReason.REPROJECTION_THRESHOLD, f"reprojection {rep:.2f} > {max_rep} px")

    min_d = float(qcfg["min_depth_mm"])
    max_d = float(qcfg["max_depth_mm"])
    if z < min_d:
        return fail(RejectionReason.DEPTH_BELOW_MIN, f"depth {z:.1f} < {min_d} mm")
    if z > max_d:
        return fail(RejectionReason.DEPTH_ABOVE_MAX, f"depth {z:.1f} > {max_d} mm")

    score = heuristic_quality_score(conf_l, conf_r, epi, rep, qcfg)
    metrics["score"] = score
    if score < float(qcfg.get("min_quality_score", 0.0)):
        return fail(
            RejectionReason.QUALITY_SCORE,
            f"quality {score:.3f} < {qcfg.get('min_quality_score', 0.0)}",
        )

    if speed_result is not None and not speed_result[0]:
        metrics["speed_mm_s"] = float(speed_result[1])
        return fail(RejectionReason.SPEED, f"speed {speed_result[1]:.1f} mm/s exceeds gate")

    metrics["speed_mm_s"] = float(speed_result[1]) if speed_result is not None else 0.0
    metrics["xyz_mm"] = [float(x) for x in xyz]
    return JointRejection(joint_name, RejectionReason.ACCEPTED, True, "", metrics)


def evaluate_measurement(
    *,
    conf_l: float,
    conf_r: float,
    epipolar_error_px: float,
    reprojection_error_max_px: float,
    depth_mm: float,
    keypoint_confidence: float,
    qcfg: dict,
) -> tuple:
    """Deterministic accept/reject for a single triangulated joint.

    Returns ``(accepted: bool, reason: Optional[str], score: float)``. ``reason``
    is ``None`` when accepted, otherwise one of :class:`RejectionReason`.
    """
    if conf_l < keypoint_confidence or conf_r < keypoint_confidence:
        return False, RejectionReason.KEYPOINT_CONFIDENCE, 0.0

    if (
        epipolar_error_px > float(qcfg["max_epipolar_error_px"])
        or reprojection_error_max_px > float(qcfg["max_reprojection_error_px"])
    ):
        return False, RejectionReason.GEOMETRY, 0.0

    if depth_mm < float(qcfg["min_depth_mm"]) or depth_mm > float(qcfg["max_depth_mm"]):
        return False, RejectionReason.DEPTH, 0.0

    score = heuristic_quality_score(conf_l, conf_r, epipolar_error_px, reprojection_error_max_px, qcfg)
    if score < float(qcfg.get("min_quality_score", 0.0)):
        return False, RejectionReason.QUALITY_SCORE, score

    return True, None, score