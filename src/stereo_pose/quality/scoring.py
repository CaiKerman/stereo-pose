"""Measurement quality: heuristic score and accept/reject decisions.

Ported from the v1.2 ``heuristic_quality_score`` in
``reference/v1_2/main.py`` plus an extracted, deterministic accept/reject helper.
The quality score is a heuristic combining pose confidence and geometric error;
it is not a statistical probability.
"""

from __future__ import annotations

import math
from typing import Optional


def heuristic_quality_score(conf_l, conf_r, epi_px, reproj_px, qcfg) -> float:
    """Heuristic 0..1 quality score (matching the v1.2 reference)."""
    base = math.sqrt(max(0.0, float(conf_l)) * max(0.0, float(conf_r)))
    epi_scale = max(float(qcfg["max_epipolar_error_px"]), 1e-6)
    rep_scale = max(float(qcfg["max_reprojection_error_px"]), 1e-6)
    geom = math.exp(-float(epi_px) / epi_scale) * math.exp(-float(reproj_px) / rep_scale)
    return float(max(0.0, min(1.0, base * geom)))


class RejectionReason:
    KEYPOINT_CONFIDENCE = "keypoint_confidence"
    GEOMETRY = "geometry"
    DEPTH = "depth"
    QUALITY_SCORE = "quality_score"
    SPEED = "speed"


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