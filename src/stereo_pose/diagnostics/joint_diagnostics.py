"""Per-joint diagnostic summary formatting (pure, deterministic).

Turns an internal :class:`stereo_pose.models.FrameDiagnostics` into the compact
text view shown under the ``D`` hotkey, without changing any acceptance behavior.
"""

from __future__ import annotations

from stereo_pose.quality import RejectionReason

_AGGREGATE_GROUPS = [
    ("conf", [RejectionReason.LEFT_KEYPOINT_CONFIDENCE,
              RejectionReason.RIGHT_KEYPOINT_CONFIDENCE,
              RejectionReason.BOTH_KEYPOINT_CONFIDENCE]),
    ("epi", [RejectionReason.EPIPOLAR_THRESHOLD]),
    ("reproj", [RejectionReason.REPROJECTION_THRESHOLD]),
    ("depth", [RejectionReason.DEPTH_BELOW_MIN, RejectionReason.DEPTH_ABOVE_MAX]),
    ("quality", [RejectionReason.QUALITY_SCORE]),
    ("speed", [RejectionReason.SPEED]),
    ("missing", [RejectionReason.MISSING_POSE]),
    ("nocalib", [RejectionReason.CALIBRATION_UNAVAILABLE]),
    ("geom", [RejectionReason.GEOMETRY_UNAVAILABLE]),
]


def format_aggregate(aggregate) -> str:
    """Render the grouped aggregate rejection counts (``conf=.. epi=.. ...``)."""
    tokens = []
    for name, states in _AGGREGATE_GROUPS:
        total = sum(int(aggregate.get(s, 0)) for s in states)
        tokens.append(f"{name}={total}")
    return " ".join(tokens)


def format_diagnostic_summary(frame_index, diagnostics) -> str:
    """Render a compact per-joint diagnostic block for one frame."""
    lines = [
        f"frame={frame_index} "
        f"accepted={diagnostics.accepted_count}/{diagnostics.selected_joint_count}"
    ]
    for v in diagnostics.joints:
        if v.accepted:
            xyz = v.metrics.get("xyz_mm")
            if xyz is not None and len(xyz) == 3:
                lines.append(
                    f"{v.joint_name:<15} ACCEPT xyz=({xyz[0]:.0f},{xyz[1]:.0f},{xyz[2]:.0f})"
                )
            else:
                lines.append(f"{v.joint_name:<15} ACCEPT")
        else:
            lines.append(f"{v.joint_name:<15} REJECT {v.detail}")
    lines.append("aggregate: " + format_aggregate(diagnostics.aggregate))
    return "\n".join(lines)