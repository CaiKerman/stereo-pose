"""Validation report persistence tests (Task 002, Part C).

Verifies JSON round-trip serialization and that output paths never escape the
managed runtime validation root.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from stereo_pose.validation import (
    SCHEMA,
    MetricValidationResult,
    compute_metrics_from_triangulations,
    is_within_validation_root,
    save_validation_report,
    validation_dir,
)


def _sample_result_dict():
    tris = []
    for r in range(6):
        for c in range(9):
            tris.append({
                "xyz_mm": np.array([(c - 4) * 25.0, (r - 2.5) * 25.0, 1500.0]),
                "epipolar_error_px": 0.1,
                "reprojection_error_max_px": 0.2,
            })
    res = compute_metrics_from_triangulations(
        tris, board_cols=9, board_rows=6, square_mm=25.0,
        calibration_file="runtime/calibrations/auto/stereo_x.npz",
        timestamp="2026-09-30T12:00:00",
        corner_order_mode="direct",
    )
    return res.to_dict()


class TestSerialization(unittest.TestCase):
    def test_round_trip_preserves_metrics(self):
        d = _sample_result_dict()
        s = json.dumps(d)
        d2 = json.loads(s)
        self.assertEqual(d2["schema"], SCHEMA)
        self.assertEqual(d2["corners"]["valid"], d["corners"]["valid"])
        self.assertEqual(d2["horizontal"]["count"], d["horizontal"]["count"])
        self.assertAlmostEqual(d2["horizontal"]["mean"], d["horizontal"]["mean"])
        self.assertAlmostEqual(d2["scale_error_percent"], d["scale_error_percent"])
        self.assertEqual(d2["calibration_file"], d["calibration_file"])
        self.assertEqual(d2["timestamp"], d["timestamp"])
        self.assertEqual(d2["corner_order_mode"], "direct")

    def test_has_required_metric_keys(self):
        d = _sample_result_dict()
        for key in ("expected_spacing_mm", "corners", "horizontal", "vertical",
                    "combined_mean_spacing_mm", "scale_error_percent", "plane",
                    "epipolar", "reprojection", "depth_range_mm",
                    "corner_order_mode"):
            self.assertIn(key, d)


class TestReportPersistence(unittest.TestCase):
    def test_saved_path_within_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = save_validation_report(_sample_result_dict(), root)
            self.assertTrue(dest.exists())
            self.assertTrue(is_within_validation_root(dest, root))
            # resolve() normalizes Windows 8.3 short vs long path names for a
            # stable comparison.
            self.assertEqual(dest.parent.resolve(), validation_dir(root).resolve())

    def test_no_overwrite_with_same_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 9, 30, 12, 0, 0)
            d1 = save_validation_report({"n": 1, "schema": SCHEMA}, root, now=now)
            d2 = save_validation_report({"n": 2, "schema": SCHEMA}, root, now=now)
            self.assertNotEqual(d1, d2)
            self.assertEqual(json.loads(d1.read_text(encoding="utf-8"))["n"], 1)
            self.assertEqual(json.loads(d2.read_text(encoding="utf-8"))["n"], 2)

    def test_containment_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(is_within_validation_root(
                root / "validation" / "metric_x.json", root))
            self.assertTrue(is_within_validation_root(
                root / "validation" / "sub" / "metric_x.json", root))
            self.assertFalse(is_within_validation_root(
                root / "calibrations" / "auto" / "stereo_x.npz", root))
            self.assertFalse(is_within_validation_root(
                root.parent / "validation" / "metric_x.json", root))


if __name__ == "__main__":
    unittest.main()