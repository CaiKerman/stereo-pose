"""``stereo_pose_3d/v1`` message serialization tests."""

import unittest

from stereo_pose import V1_SCHEMA
from stereo_pose.models import (
    FilteredJoint3D,
    FrameTiming,
    JointQuality,
    PoseFrame,
)
from stereo_pose.outputs.v1_message import to_v1_message


def _sample_frame() -> PoseFrame:
    timing = FrameTiming(
        host_grab_skew_ms=0.42,
        pair_cycle_ms=14.8,
        host_midpoint_perf_ns=1_790_701_200_000_000,
        wall_timestamp_ns=1_790_701_200_123_456_789,
    )
    joint = FilteredJoint3D(
        joint_name="left_wrist",
        xyz_mm=(-492.2, 31.6, 1759.4),
        xyz_raw_mm=(-500.1, 28.2, 1773.8),
        quality=JointQuality(
            score=0.67,
            epipolar_error_px=0.81,
            reprojection_error_mean_px=0.40,
            reprojection_error_max_px=0.41,
            speed_mm_s=640.0,
        ),
        confidence_left=0.96,
        confidence_right=0.93,
        uv_left=(542.1, 311.8),
        uv_right=(438.7, 312.5),
        rectified_uv_left=(535.2, 309.9),
        rectified_uv_right=(431.5, 310.7),
    )
    return PoseFrame(
        frame_index=152,
        wall_timestamp_ns=timing.wall_timestamp_ns,
        coordinate_system="rectified_left_camera",
        unit="mm",
        calibration_file="calibrations/stereo_20260929_183500.npz",
        timing=timing,
        filtering={"enabled": True, "type": "one_euro", "min_cutoff": 1.2, "beta": 0.015, "d_cutoff": 1.0},
        frame_quality={
            "accepted_joints": 1,
            "rejected": {"keypoint_confidence": 1, "geometry": 1, "depth": 0, "quality_score": 0, "speed": 0},
            "mean_epipolar_error_px": 0.71,
            "mean_reprojection_error_px": 0.36,
        },
        joints={"left_wrist": joint},
    )


class TestV1Message(unittest.TestCase):
    def test_top_level_fields(self):
        m = to_v1_message(_sample_frame())
        self.assertEqual(m["schema"], V1_SCHEMA)
        self.assertEqual(m["unit"], "mm")
        self.assertEqual(m["coordinate_system"], "rectified_left_camera")
        self.assertEqual(m["frame_index"], 152)
        self.assertIsInstance(m["timestamp_ns"], int)

    def test_timing_warning_present(self):
        m = to_v1_message(_sample_frame())
        self.assertIn("warning", m["timing"])
        self.assertIn("not sensor exposure", m["timing"]["warning"])

    def test_joint_payload_shape_and_units(self):
        m = to_v1_message(_sample_frame())
        j = m["joints"]["left_wrist"]
        self.assertEqual(len(j["xyz_mm"]), 3)
        self.assertEqual(len(j["xyz_raw_mm"]), 3)
        self.assertAlmostEqual(j["xyz_mm"][0], -492.2)
        q = j["quality"]
        self.assertAlmostEqual(q["epipolar_error_px"], 0.81)
        self.assertAlmostEqual(q["speed_mm_s"], 640.0)
        self.assertAlmostEqual(j["confidence"]["left"], 0.96)
        self.assertEqual(len(j["uv"]["left"]), 2)

    def test_round_trip_json(self):
        from stereo_pose.outputs.v1_message import serialize_v1_json

        s = serialize_v1_json(_sample_frame())
        import json

        m = json.loads(s)
        self.assertEqual(m["schema"], V1_SCHEMA)


if __name__ == "__main__":
    unittest.main()