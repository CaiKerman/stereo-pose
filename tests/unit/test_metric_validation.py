"""Checkerboard 3D metric validation tests (Task 002, Part C).

Deterministic synthetic cameras + a synthetic planar checkerboard. No cameras,
model weights, CUDA, or network are required.
"""

import unittest

import numpy as np

from stereo_pose.geometry import StereoTriangulator
from stereo_pose.validation import (
    MetricValidationError,
    compute_metric_validation,
    compute_metrics_from_triangulations,
    normalize_correspondence,
)

COLS = 9
ROWS = 6
SQUARE = 25.0


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


def grid_3d(cols, rows, square):
    pts = []
    for r in range(rows):
        for c in range(cols):
            pts.append([(c - (cols - 1) / 2.0) * square,
                        (r - (rows - 1) / 2.0) * square,
                        0.0])
    return np.asarray(pts, dtype=float)


def rotate_y(pts, angle_deg):
    a = np.radians(angle_deg)
    R = np.array([[np.cos(a), 0.0, np.sin(a)],
                  [0.0, 1.0, 0.0],
                  [-np.sin(a), 0.0, np.cos(a)]], dtype=float)
    return (R @ pts.T).T


class _Rig(unittest.TestCase):
    def setUp(self):
        self.K, self.D, self.R, self.P1, self.P2 = build_rectified_rig()
        self.tri = StereoTriangulator({
            "K1": self.K, "D1": self.D,
            "K2": self.K, "D2": self.D,
            "R1": self.R, "R2": self.R,
            "P1": self.P1, "P2": self.P2,
        })

    def project_board(self, pts):
        left = np.asarray([project(self.P1, p) for p in pts], dtype=float)
        right = np.asarray([project(self.P2, p) for p in pts], dtype=float)
        return left, right


class TestExactCheckerboard(_Rig):
    def test_reconstructs_expected_spacing(self):
        pts = grid_3d(COLS, ROWS, SQUARE) + np.array([0.0, 0.0, 1500.0])
        pl, pr = self.project_board(pts)
        res = compute_metric_validation(
            self.tri, pl, pr, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertEqual(res.corners_total, COLS * ROWS)
        self.assertEqual(res.corners_valid, COLS * ROWS)
        self.assertEqual(res.horizontal["count"], ROWS * (COLS - 1))
        self.assertEqual(res.vertical["count"], (ROWS - 1) * COLS)
        self.assertAlmostEqual(res.horizontal["mean"], SQUARE, delta=0.5)
        self.assertAlmostEqual(res.vertical["mean"], SQUARE, delta=0.5)
        self.assertAlmostEqual(res.combined_mean_spacing_mm, SQUARE, delta=0.5)
        self.assertAlmostEqual(res.scale_error_percent, 0.0, delta=0.5)

    def test_plane_residual_near_zero_for_exact_grid(self):
        pts = grid_3d(COLS, ROWS, SQUARE) + np.array([0.0, 0.0, 1500.0])
        pl, pr = self.project_board(pts)
        res = compute_metric_validation(
            self.tri, pl, pr, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertLess(res.plane["rms_residual_mm"], 0.05)
        self.assertLess(res.plane["max_abs_residual_mm"], 0.1)

    def test_tilted_plane_has_depth_range_and_still_flat(self):
        pts = rotate_y(grid_3d(COLS, ROWS, SQUARE), 15.0) + np.array([0.0, 0.0, 1500.0])
        pl, pr = self.project_board(pts)
        res = compute_metric_validation(
            self.tri, pl, pr, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertGreater(res.depth_range_mm["span"], 1.0)
        self.assertLess(res.plane["rms_residual_mm"], 0.05)

    def test_epipolar_and_reprojection_near_zero(self):
        pts = grid_3d(COLS, ROWS, SQUARE) + np.array([0.0, 0.0, 1500.0])
        pl, pr = self.project_board(pts)
        res = compute_metric_validation(
            self.tri, pl, pr, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertLess(res.epipolar["max_px"], 0.05)
        self.assertLess(res.reprojection["max_px"], 0.05)


class TestNoisyObservations(_Rig):
    def test_noisy_2d_produces_finite_sensible_errors(self):
        # Subpixel displacement noise on the horizontal (disparity) coordinate of
        # a rectified rig. This is the dominant noise for subpixel corner
        # detection; the small 120mm baseline / large depth makes disparity only
        # ~64px, so we keep sigma realistic (~0.05px) to stay in a sensible regime.
        rng = np.random.default_rng(1)
        pts = grid_3d(COLS, ROWS, SQUARE) + np.array([0.0, 0.0, 1500.0])
        pl, pr = self.project_board(pts)
        pl = pl + np.column_stack([rng.normal(0.0, 0.05, pl.shape[0]), np.zeros(pl.shape[0])])
        pr = pr + np.column_stack([rng.normal(0.0, 0.05, pr.shape[0]), np.zeros(pr.shape[0])])
        res = compute_metric_validation(
            self.tri, pl, pr, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertEqual(res.corners_valid, COLS * ROWS)
        self.assertTrue(np.isfinite(res.horizontal["rmse"]))
        self.assertGreater(res.horizontal["rmse"], 0.0)
        self.assertGreater(res.horizontal["max_abs_error"], 0.0)
        self.assertTrue(np.isfinite(res.plane["rms_residual_mm"]))
        self.assertTrue(np.isfinite(res.scale_error_percent))
        self.assertAlmostEqual(res.horizontal["mean"], SQUARE, delta=1.0)


class TestCorrespondenceNormalization(_Rig):
    def _board(self, z=1500.0):
        pts = grid_3d(COLS, ROWS, SQUARE) + np.array([0.0, 0.0, z])
        return self.project_board(pts)

    def test_direct_ordering_selects_direct(self):
        pl, pr = self._board()
        ordered, mode = normalize_correspondence(self.tri, pl, pr)
        self.assertEqual(mode, "direct")
        np.testing.assert_allclose(ordered, pr)

    def test_reversed_right_ordering_is_corrected(self):
        pl, pr = self._board()
        ordered, mode = normalize_correspondence(self.tri, pl, pr[::-1])
        self.assertEqual(mode, "reversed_180")
        np.testing.assert_allclose(ordered, pr)

    def test_implausible_correspondence_fails_cleanly(self):
        pl, pr = self._board()
        # A row scramble breaks BOTH the direct and 180-degree pairings.
        pr_scrambled = np.roll(pr.reshape(ROWS, COLS, 2), 1, axis=0).reshape(-1, 2)
        self.assertIsNone(normalize_correspondence(self.tri, pl, pr_scrambled))
        with self.assertRaises(MetricValidationError):
            compute_metric_validation(
                self.tri, pl, pr_scrambled,
                board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
            )

    def test_reversed_right_recovers_expected_grid_metric(self):
        pl, pr = self._board()
        res = compute_metric_validation(
            self.tri, pl, pr[::-1],
            board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertEqual(res.corner_order_mode, "reversed_180")
        self.assertAlmostEqual(res.combined_mean_spacing_mm, SQUARE, delta=0.5)
        self.assertAlmostEqual(res.scale_error_percent, 0.0, delta=0.5)


class TestMetricsMath(unittest.TestCase):
    def _triangulations(self, square, z=0.0):
        pts = grid_3d(COLS, ROWS, square) + np.array([0.0, 0.0, z])
        return [{"xyz_mm": np.asarray(p, dtype=float),
                 "epipolar_error_px": 0.0,
                 "reprojection_error_max_px": 0.0} for p in pts]

    def test_scale_error_calculation(self):
        # Reconstruct at 20 mm spacing but report against 25 mm expected.
        tris = self._triangulations(20.0)
        res = compute_metrics_from_triangulations(
            tris, board_cols=COLS, board_rows=ROWS, square_mm=25.0,
        )
        self.assertAlmostEqual(res.combined_mean_spacing_mm, 20.0, delta=0.01)
        self.assertAlmostEqual(res.scale_error_percent, -20.0, delta=0.1)

    def test_missing_corners_reported_cleanly(self):
        tris = self._triangulations(SQUARE)
        total = COLS * ROWS
        tris[0] = None
        tris[total - 1] = None
        res = compute_metrics_from_triangulations(
            tris, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertEqual(res.corners_total, total)
        self.assertEqual(res.corners_valid, total - 2)
        self.assertLess(res.horizontal["count"], ROWS * (COLS - 1))
        self.assertAlmostEqual(res.horizontal["mean"], SQUARE, delta=0.01)
        self.assertAlmostEqual(res.combined_mean_spacing_mm, SQUARE, delta=0.01)

    def test_all_invalid_corners(self):
        total = COLS * ROWS
        tris = [None] * total
        res = compute_metrics_from_triangulations(
            tris, board_cols=COLS, board_rows=ROWS, square_mm=SQUARE,
        )
        self.assertEqual(res.corners_valid, 0)
        self.assertEqual(res.horizontal["count"], 0)
        self.assertIsNone(res.combined_mean_spacing_mm)
        self.assertIsNone(res.scale_error_percent)


if __name__ == "__main__":
    unittest.main()