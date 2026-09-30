"""Measurement quality accept/reject + speed gate tests."""

import unittest

import numpy as np

from stereo_pose.quality import (
    RejectionReason,
    TemporalSpeedGate,
    evaluate_measurement,
    heuristic_quality_score,
)

QCFG = {
    "max_epipolar_error_px": 3.0,
    "max_reprojection_error_px": 2.5,
    "min_depth_mm": 250.0,
    "max_depth_mm": 7000.0,
    "min_quality_score": 0.12,
}


class TestHeuristicQualityScore(unittest.TestCase):
    def test_range(self):
        s = heuristic_quality_score(0.9, 0.9, 0.0, 0.0, QCFG)
        self.assertTrue(0.0 <= s <= 1.0)
        self.assertAlmostEqual(s, 0.9, places=6)

    def test_worse_epipolar_lowers_score(self):
        good = heuristic_quality_score(0.9, 0.9, 0.1, 0.1, QCFG)
        bad = heuristic_quality_score(0.9, 0.9, 2.9, 0.1, QCFG)
        self.assertLess(bad, good)


class TestEvaluateMeasurement(unittest.TestCase):
    def test_accept_good_measurement(self):
        ok, reason, score = evaluate_measurement(
            conf_l=0.9, conf_r=0.9, epipolar_error_px=0.5,
            reprojection_error_max_px=0.4, depth_mm=2000.0,
            keypoint_confidence=0.45, qcfg=QCFG,
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertGreater(score, 0.0)

    def test_reject_keypoint_confidence(self):
        ok, reason, _ = evaluate_measurement(
            conf_l=0.9, conf_r=0.2, epipolar_error_px=0.5,
            reprojection_error_max_px=0.4, depth_mm=2000.0,
            keypoint_confidence=0.45, qcfg=QCFG,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, RejectionReason.KEYPOINT_CONFIDENCE)

    def test_reject_geometry(self):
        ok, reason, _ = evaluate_measurement(
            conf_l=0.9, conf_r=0.9, epipolar_error_px=10.0,
            reprojection_error_max_px=0.4, depth_mm=2000.0,
            keypoint_confidence=0.45, qcfg=QCFG,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, RejectionReason.GEOMETRY)

    def test_reject_depth(self):
        ok, reason, _ = evaluate_measurement(
            conf_l=0.9, conf_r=0.9, epipolar_error_px=0.5,
            reprojection_error_max_px=0.4, depth_mm=100.0,
            keypoint_confidence=0.45, qcfg=QCFG,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, RejectionReason.DEPTH)

    def test_reject_quality_score(self):
        ok, reason, _ = evaluate_measurement(
            conf_l=0.5, conf_r=0.5, epipolar_error_px=0.5,
            reprojection_error_max_px=0.4, depth_mm=2000.0,
            keypoint_confidence=0.45, qcfg={**QCFG, "min_quality_score": 0.9},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, RejectionReason.QUALITY_SCORE)


class TestTemporalSpeedGate(unittest.TestCase):
    def test_first_check_accepts_zero_speed(self):
        g = TemporalSpeedGate(max_speed_mm_s=6000.0)
        ok, speed = g.check("j", np.array([0.0, 0.0, 0.0]), 0.0)
        self.assertTrue(ok)
        self.assertEqual(speed, 0.0)

    def test_fast_jump_rejected(self):
        g = TemporalSpeedGate(max_speed_mm_s=1000.0)
        g.check("j", np.array([0.0, 0.0, 0.0]), 0.0)
        ok, speed = g.check("j", np.array([5000.0, 0.0, 0.0]), 0.1)
        self.assertFalse(ok)
        self.assertGreater(speed, 1000.0)

    def test_slow_jump_accepted(self):
        g = TemporalSpeedGate(max_speed_mm_s=1000.0)
        g.check("j", np.array([0.0, 0.0, 0.0]), 0.0)
        ok, speed = g.check("j", np.array([10.0, 0.0, 0.0]), 0.1)
        self.assertTrue(ok)
        self.assertEqual(speed, 100.0)

    def test_reset_clears_history(self):
        g = TemporalSpeedGate(max_speed_mm_s=1000.0)
        g.check("j", np.array([0.0, 0.0, 0.0]), 0.0)
        g.reset()
        ok, speed = g.check("j", np.array([99999.0, 0.0, 0.0]), 0.1)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()