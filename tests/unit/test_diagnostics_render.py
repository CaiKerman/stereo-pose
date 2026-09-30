"""Per-joint diagnostic summary rendering tests (Task 002).

Pure, deterministic text formatting; no hardware, model weights, or network.
"""

import unittest

from stereo_pose.diagnostics.joint_diagnostics import (
    format_aggregate,
    format_diagnostic_summary,
)
from stereo_pose.models import FrameDiagnostics, JointRejection
from stereo_pose.quality import RejectionReason


class TestFormatAggregate(unittest.TestCase):
    def test_groups_fine_states(self):
        agg = {
            RejectionReason.LEFT_KEYPOINT_CONFIDENCE: 1,
            RejectionReason.RIGHT_KEYPOINT_CONFIDENCE: 1,
            RejectionReason.EPIPOLAR_THRESHOLD: 2,
            RejectionReason.DEPTH_BELOW_MIN: 3,
            RejectionReason.QUALITY_SCORE: 4,
            RejectionReason.SPEED: 5,
        }
        s = format_aggregate(agg)
        self.assertIn("conf=2", s)
        self.assertIn("epi=2", s)
        self.assertIn("reproj=0", s)
        self.assertIn("depth=3", s)
        self.assertIn("quality=4", s)
        self.assertIn("speed=5", s)

    def test_empty_aggregate(self):
        s = format_aggregate({})
        self.assertIn("conf=0", s)
        self.assertIn("missing=0", s)
        self.assertIn("nocalib=0", s)


class TestFormatSummary(unittest.TestCase):
    def test_renders_accepted_and_rejected(self):
        joints = [
            JointRejection("left_shoulder", RejectionReason.ACCEPTED, True, "",
                           {"xyz_mm": [1.0, 2.0, 3.0]}),
            JointRejection("right_shoulder", RejectionReason.EPIPOLAR_THRESHOLD,
                           False, "epipolar 4.20 > 3.00 px", {}),
        ]
        diag = FrameDiagnostics(
            selected_joint_count=2,
            accepted_count=1,
            rejected_count=1,
            joints=joints,
            aggregate={RejectionReason.EPIPOLAR_THRESHOLD: 1},
        )
        s = format_diagnostic_summary(1234, diag)
        self.assertIn("frame=1234 accepted=1/2", s)
        self.assertIn("left_shoulder", s)
        self.assertIn("ACCEPT xyz=(1,2,3)", s)
        self.assertIn("right_shoulder", s)
        self.assertIn("REJECT epipolar 4.20 > 3.00 px", s)
        self.assertIn("aggregate:", s)


if __name__ == "__main__":
    unittest.main()