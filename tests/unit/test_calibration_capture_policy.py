"""Runtime calibration capture policy tests.

RC2 behavior:
- auto capture still requires the stability gate;
- SPACE/manual force capture bypasses only the stability gate;
- both cameras must still detect the full board and satisfy minimum area.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from stereo_pose.calibration.collection import RuntimeCalibration


def _calibrator(root: Path) -> RuntimeCalibration:
    stereo = {
        "board_cols": 9,
        "board_rows": 6,
        "square_mm": 25.0,
        "calibration_dir": str(root / "calibrations"),
    }
    runtime = {
        "session_dir": str(root / "sessions"),
        "auto_capture": True,
        "auto_capture_interval_s": 0.7,
        "min_pairs_to_solve": 12,
        "target_pairs": 24,
        "recommended_readiness": 75,
        "min_board_area_ratio": 0.012,
        "diversity_threshold": 0.12,
        "stable_dwell_s": 0.30,
        "stable_min_frames": 3,
        "stable_corner_motion_px": 5.0,
        "robust_prune": True,
        "prune_min_epipolar_px": 0.8,
        "prune_max_epipolar_px": 2.5,
        "max_prune_fraction": 0.25,
        "keep_images_after_success": False,
    }
    return RuntimeCalibration(stereo, runtime)


def _det(area=0.02):
    corners = np.zeros((54, 2), dtype=np.float32)
    return {
        "corners": corners,
        "center": (0.5, 0.5),
        "area_ratio": float(area),
        "angle_deg": 0.0,
        "sharpness": 100.0,
    }


class TestCalibrationCapturePolicy(unittest.TestCase):
    def test_manual_force_capture_bypasses_stability_gate(self):
        with tempfile.TemporaryDirectory() as d:
            cal = _calibrator(Path(d))
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            detections = [_det(), _det()]
            with (
                mock.patch.object(cal, "_detect", side_effect=detections),
                mock.patch.object(cal, "_update_stability", return_value=(False, 9.0, 0.1)),
                mock.patch.object(cal, "_save") as save,
            ):
                result = cal.process(frame, frame, force_capture=True)

            save.assert_called_once()
            self.assertTrue(result["captured"])
            self.assertFalse(result["stable"])
            self.assertTrue(result["good_area"])

    def test_auto_capture_still_requires_stability(self):
        with tempfile.TemporaryDirectory() as d:
            cal = _calibrator(Path(d))
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            detections = [_det(), _det()]
            with (
                mock.patch.object(cal, "_detect", side_effect=detections),
                mock.patch.object(cal, "_update_stability", return_value=(False, 9.0, 0.1)),
                mock.patch.object(cal, "_save") as save,
            ):
                result = cal.process(frame, frame, force_capture=False)

            save.assert_not_called()
            self.assertFalse(result["captured"])

    def test_manual_force_capture_still_rejects_too_small_board(self):
        with tempfile.TemporaryDirectory() as d:
            cal = _calibrator(Path(d))
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            detections = [_det(area=0.005), _det(area=0.005)]
            with (
                mock.patch.object(cal, "_detect", side_effect=detections),
                mock.patch.object(cal, "_update_stability", return_value=(False, 2.0, 0.1)),
                mock.patch.object(cal, "_save") as save,
            ):
                result = cal.process(frame, frame, force_capture=True)

            save.assert_not_called()
            self.assertFalse(result["captured"])
            self.assertFalse(result["good_area"])


if __name__ == "__main__":
    unittest.main()
