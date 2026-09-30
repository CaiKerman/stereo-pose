"""Synthetic stereo geometry regression test (mandatory).

Constructs known rectified stereo projection matrices and known 3D points,
projects them to left/right 2D, triangulates, and asserts recovery within a
small numerical tolerance. This proves geometry independently of webcams/YOLO.
"""

import unittest

import numpy as np

from stereo_pose.geometry import StereoTriangulator


def build_rectified_rig(B_mm=120.0, fx=800.0, fy=800.0, cx=640.0, cy=360.0):
    K = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=float)
    D = np.zeros(5, dtype=float)
    R = np.eye(3, dtype=float)
    P1 = np.hstack([K, np.zeros((3, 1))])
    Rt2 = np.array([[1.0, 0.0, 0.0, -B_mm],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0]], dtype=float)
    P2 = K @ Rt2
    return K, D, R, P1, P2


def project(P, X):
    h = P @ np.append(np.asarray(X, dtype=float), 1.0)
    return h[:2] / h[2]


class TestSyntheticTriangulation(unittest.TestCase):
    def setUp(self):
        self.K, self.D, self.R, self.P1, self.P2 = build_rectified_rig()
        self.tri = StereoTriangulator({
            "K1": self.K, "D1": self.D,
            "K2": self.K, "D2": self.D,
            "R1": self.R, "R2": self.R,
            "P1": self.P1, "P2": self.P2,
        })
        # Points in the left-camera coordinate frame (Z = depth in mm).
        self.points = [
            np.array([0.0, 0.0, 2000.0]),
            np.array([150.0, -100.0, 1800.0]),
            np.array([-60.0, 40.0, 3000.0]),
        ]

    def test_recovers_known_3d_points(self):
        for X in self.points:
            pl = project(self.P1, X)
            pr = project(self.P2, X)
            q = self.tri.triangulate_with_quality(pl, pr)
            self.assertIsNotNone(q)
            np.testing.assert_allclose(q["xyz_mm"], X, atol=0.1)

    def test_epipolar_error_is_near_zero_for_matched(self):
        X = self.points[0]
        pl = project(self.P1, X)
        pr = project(self.P2, X)
        q = self.tri.triangulate_with_quality(pl, pr)
        self.assertLess(q["epipolar_error_px"], 0.01)

    def test_reprojection_error_is_near_zero(self):
        X = self.points[1]
        pl = project(self.P1, X)
        pr = project(self.P2, X)
        q = self.tri.triangulate_with_quality(pl, pr)
        self.assertLess(q["reprojection_error_max_px"], 0.05)

    def test_epipolar_error_detects_mismatch(self):
        # Pair the left point of one 3D point with the right point of another.
        pl = project(self.P1, self.points[0])
        pr = project(self.P2, self.points[1])
        q = self.tri.triangulate_with_quality(pl, pr)
        self.assertGreater(q["epipolar_error_px"], 0.01)

    def test_triangulate_returns_xyz(self):
        X = self.points[2]
        pl = project(self.P1, X)
        pr = project(self.P2, X)
        xyz = self.tri.triangulate(pl, pr)
        np.testing.assert_allclose(xyz, X, atol=0.1)

    def test_rejects_invalid_calibration(self):
        with self.assertRaises(ValueError):
            StereoTriangulator({"K1": self.K})  # missing keys


if __name__ == "__main__":
    unittest.main()