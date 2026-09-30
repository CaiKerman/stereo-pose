"""Calibration metadata loading + compatibility warning tests."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from stereo_pose.calibration.metadata import (
    load_calibration_metadata,
    validate_calibration_compatibility,
)


def _write_calib(
    path,
    image_size=(1280, 720),
    board=(9, 6),
    fps=None,
    camera_context=True,
):
    K = np.eye(3, dtype=float)
    D = np.zeros(5, dtype=float)
    P = np.hstack([K, np.zeros((3, 1), dtype=float)])
    fields = {
        "K1": K, "D1": D, "K2": K, "D2": D,
        "R1": np.eye(3), "R2": np.eye(3), "P1": P, "P2": P,
        "image_size": np.array(image_size),
        "board_cols": np.array(board[0]),
        "board_rows": np.array(board[1]),
        "square_mm": np.array(25.0),
        "_schema_version": np.array("1"),
    }
    if camera_context:
        fields.update({
            "camera_left": np.array(0),
            "camera_right": np.array(1),
            "camera_backend": np.array("dshow"),
            "camera_requested_size": np.array(image_size),
            "camera_requested_fps": np.array(30.0 if fps is None else fps),
            "camera_actual_fps": np.array(29.9),
        })
    np.savez(str(path), **fields)


class TestCalibrationMetadata(unittest.TestCase):
    def test_no_warnings_when_matching(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cal.npz"
            _write_calib(p)
            meta = load_calibration_metadata(p, expected_image_size=(1280, 720), expected_board=(9, 6))
            self.assertEqual(meta.warnings, [])
            self.assertEqual(meta.image_size, (1280, 720))
            self.assertEqual((meta.board_cols, meta.board_rows), (9, 6))

    def test_warns_on_image_size_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cal.npz"
            _write_calib(p, image_size=(1280, 720))
            warnings = validate_calibration_compatibility(p, image_size=(640, 480), board=(9, 6))
            self.assertTrue(any("image_size" in w for w in warnings))

    def test_warns_on_board_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cal.npz"
            _write_calib(p, board=(9, 6))
            warnings = validate_calibration_compatibility(p, image_size=(1280, 720), board=(7, 5))
            self.assertTrue(any("board" in w for w in warnings))

    def test_warns_on_fps_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cal.npz"
            _write_calib(p, fps=30.0)
            warnings = validate_calibration_compatibility(p, image_size=(1280, 720), board=(9, 6), fps=60.0)
            self.assertTrue(any("fps" in w for w in warnings))

    def test_camera_context_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cal.npz"
            _write_calib(p)
            meta = load_calibration_metadata(p)
            self.assertEqual(meta.camera_left, 0)
            self.assertEqual(meta.camera_right, 1)
            self.assertEqual(meta.camera_backend, "dshow")
            self.assertEqual(meta.camera_requested_size, (1280, 720))
            self.assertEqual(meta.camera_requested_fps, 30.0)
            self.assertEqual(meta.camera_actual_fps, 29.9)

    def test_legacy_artifact_without_camera_fields_loads(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cal.npz"
            _write_calib(p, camera_context=False)
            meta = load_calibration_metadata(p)
            self.assertIsNone(meta.camera_left)
            self.assertEqual(meta.image_size, (1280, 720))


if __name__ == "__main__":
    unittest.main()