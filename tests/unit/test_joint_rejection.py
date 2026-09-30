"""Per-joint rejection classification tests (Task 002).

Deterministic, no cameras/models/network. Verifies that ``classify_joint``
assigns exactly one terminal state per rejection stage, maps each fine state to
the expected coarse v1.2 aggregate bucket, and does not change the existing
``evaluate_measurement`` accept/reject decisions.
"""

import unittest

import numpy as np

from stereo_pose.quality import (
    RejectionReason,
    aggregate_bucket,
    classify_joint,
    evaluate_measurement,
)

KP = 0.45

QCFG = {
    "max_epipolar_error_px": 3.0,
    "max_reprojection_error_px": 2.5,
    "min_depth_mm": 250.0,
    "max_depth_mm": 7000.0,
    "min_quality_score": 0.12,
}


def geom(xyz=(0.0, 0.0, 2000.0), epi=0.5, rep=0.4):
    return {
        "xyz_mm": np.asarray(xyz, dtype=float),
        "epipolar_error_px": float(epi),
        "reprojection_error_max_px": float(rep),
    }


class TestClassifyJoint(unittest.TestCase):
    def test_accepted(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(), qcfg=QCFG)
        self.assertTrue(v.accepted)
        self.assertEqual(v.state, RejectionReason.ACCEPTED)

    def test_left_confidence_low(self):
        v = classify_joint("j", conf_l=0.3, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.LEFT_KEYPOINT_CONFIDENCE)

    def test_right_confidence_low(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.3, keypoint_confidence=KP,
                           geometry=geom(), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.RIGHT_KEYPOINT_CONFIDENCE)

    def test_both_confidence_low(self):
        v = classify_joint("j", conf_l=0.3, conf_r=0.4, keypoint_confidence=KP,
                           geometry=geom(), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.BOTH_KEYPOINT_CONFIDENCE)

    def test_missing_pose(self):
        v = classify_joint("j", conf_l=0.0, conf_r=0.0, keypoint_confidence=KP,
                           geometry=None, qcfg=QCFG, missing_pose=True)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.MISSING_POSE)

    def test_calibration_unavailable(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=None, qcfg=QCFG, calibration_available=False)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.CALIBRATION_UNAVAILABLE)

    def test_geometry_unavailable(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=None, qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.GEOMETRY_UNAVAILABLE)

    def test_epipolar_threshold(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(epi=4.0), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.EPIPOLAR_THRESHOLD)

    def test_reprojection_threshold(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(rep=3.0), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.REPROJECTION_THRESHOLD)

    def test_depth_below_min(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(xyz=(0.0, 0.0, 100.0)), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.DEPTH_BELOW_MIN)

    def test_depth_above_max(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(xyz=(0.0, 0.0, 8000.0)), qcfg=QCFG)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.DEPTH_ABOVE_MAX)

    def test_quality_score(self):
        qcfg = {**QCFG, "min_quality_score": 0.9}
        # base = sqrt(0.5*0.5) = 0.5, geom = 1 -> score 0.5 < 0.9
        v = classify_joint("j", conf_l=0.5, conf_r=0.5, keypoint_confidence=KP,
                           geometry=geom(epi=0.0, rep=0.0), qcfg=qcfg)
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.QUALITY_SCORE)

    def test_speed_rejected(self):
        v = classify_joint("j", conf_l=0.9, conf_r=0.9, keypoint_confidence=KP,
                           geometry=geom(), qcfg=QCFG, speed_result=(False, 7000.0))
        self.assertFalse(v.accepted)
        self.assertEqual(v.state, RejectionReason.SPEED)


class TestAggregateBucket(unittest.TestCase):
    def test_fine_to_coarse_mapping(self):
        expected = {
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
        for state, bucket in expected.items():
            self.assertEqual(aggregate_bucket(state), bucket, state)

    def test_not_counted_states(self):
        for state in (RejectionReason.ACCEPTED,
                      RejectionReason.MISSING_POSE,
                      RejectionReason.CALIBRATION_UNAVAILABLE):
            self.assertIsNone(aggregate_bucket(state), state)


class TestNoBehaviourChange(unittest.TestCase):
    """classify_joint must not change acceptance decisions vs evaluate_measurement."""

    def test_acceptance_matches(self):
        cases = [
            (0.9, 0.9, 0.5, 0.4, 2000.0),
            (0.3, 0.9, 0.5, 0.4, 2000.0),
            (0.9, 0.3, 0.5, 0.4, 2000.0),
            (0.4, 0.4, 0.5, 0.4, 2000.0),
            (0.9, 0.9, 10.0, 0.4, 2000.0),
            (0.9, 0.9, 0.5, 9.0, 2000.0),
            (0.9, 0.9, 0.5, 0.4, 100.0),
            (0.9, 0.9, 0.5, 0.4, 8000.0),
            (0.5, 0.5, 0.0, 0.0, 2000.0),
        ]
        for conf_l, conf_r, epi, rep, z in cases:
            geom_d = geom(xyz=(0.0, 0.0, z), epi=epi, rep=rep)
            v = classify_joint("j", conf_l=conf_l, conf_r=conf_r,
                               keypoint_confidence=KP, geometry=geom_d, qcfg=QCFG)
            ok, _, _ = evaluate_measurement(
                conf_l=conf_l, conf_r=conf_r,
                epipolar_error_px=epi, reprojection_error_max_px=rep,
                depth_mm=z, keypoint_confidence=KP, qcfg=QCFG,
            )
            self.assertEqual(v.accepted, ok, (conf_l, conf_r, epi, rep, z))

    def test_rejected_coarse_bucket_matches_reason(self):
        for conf_l, conf_r, epi, rep, z in [
            (0.3, 0.9, 0.5, 0.4, 2000.0),
            (0.9, 0.9, 10.0, 0.4, 2000.0),
            (0.9, 0.9, 0.5, 9.0, 2000.0),
            (0.9, 0.9, 0.5, 0.4, 100.0),
            (0.9, 0.9, 0.5, 0.4, 8000.0),
        ]:
            geom_d = geom(xyz=(0.0, 0.0, z), epi=epi, rep=rep)
            v = classify_joint("j", conf_l=conf_l, conf_r=conf_r,
                               keypoint_confidence=KP, geometry=geom_d, qcfg=QCFG)
            ok, reason, _ = evaluate_measurement(
                conf_l=conf_l, conf_r=conf_r,
                epipolar_error_px=epi, reprojection_error_max_px=rep,
                depth_mm=z, keypoint_confidence=KP, qcfg=QCFG,
            )
            self.assertFalse(ok)
            self.assertEqual(aggregate_bucket(v.state), reason, v.state)


if __name__ == "__main__":
    unittest.main()