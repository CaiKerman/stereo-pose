"""Diagnostic snapshot + offline epipolar replay + compact menu tests (Task 002B).

Deterministic: no camera, torch, CUDA, YOLO or model weights. Calibration
geometry uses exact synthetic matrices so rectified ``uv`` round-trips to the
raw pixel coordinates and the signed epipolar delta is analytically known.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from stereo_pose.diagnostics.snapshot import (
    SnapshotPose,
    compute_epipolar,
    is_within_snapshot_root,
    save_snapshot,
    snapshot_dir,
)
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.joints import JOINT_INDEX
from stereo_pose.persistence import cleanup_project

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"


def _calibration():
    """Exact synthetic rectified geometry: undistortPoints round-trips pixels."""
    f, cx, cy = 1000.0, 320.0, 240.0
    K = np.array([[f, 0.0, cx], [0.0, f, cy], [0.0, 0.0, 1.0]], dtype=float)
    D = np.zeros(5, dtype=float)
    R = np.eye(3, dtype=float)
    P = np.hstack([K, np.zeros((3, 1))])
    return {
        "K1": K.copy(), "D1": D.copy(), "K2": K.copy(), "D2": D.copy(),
        "R1": R.copy(), "R2": R.copy(), "P1": P.copy(), "P2": P.copy(),
        "stereo_rms": 0.5,
    }


def _frames():
    left = np.full((120, 160, 3), 10, dtype=np.uint8)
    right = np.full((120, 160, 3), 20, dtype=np.uint8)
    return left, right


def _pose(points, confs):
    return SnapshotPose(
        detections=1,
        chosen_person_index=0,
        keypoints=np.asarray(points, dtype=float),
        confidence=np.asarray(confs, dtype=float),
    )


def _sample_poses():
    n = len(JOINT_INDEX)
    l_p = np.zeros((n, 2))
    r_p = np.zeros((n, 2))
    l_c = np.full(n, 0.9)
    r_c = np.full(n, 0.9)

    l_p[JOINT_INDEX["left_shoulder"]] = (110.0, 200.0)
    r_p[JOINT_INDEX["left_shoulder"]] = (110.0, 203.0)  # 3 px vertical mismatch
    l_p[JOINT_INDEX["right_shoulder"]] = (300.0, 200.0)
    r_p[JOINT_INDEX["right_shoulder"]] = (300.0, 200.0)

    l_c[JOINT_INDEX["nose"]] = 0.0  # missing (confidence <= 0)
    r_c[JOINT_INDEX["nose"]] = 0.0

    return _pose(l_p, l_c), _pose(r_p, r_c)


def _save(runtime_root, triangulator=None, now=None):
    return save_snapshot(
        runtime_root=runtime_root,
        frame_index=42,
        wall_timestamp_ns=1_700_000_000_000_000_000,
        pair_timing={"host_grab_skew_ms": 1.25, "pair_cycle_ms": 33.0},
        camera_left=2,
        camera_right=1,
        backend="MJPG",
        requested_size=(320, 240),
        actual_size=(320, 240),
        frame_left=_frames()[0],
        frame_right=_frames()[1],
        pose_left=_sample_poses()[0],
        pose_right=_sample_poses()[1],
        selected_joints=["left_shoulder", "right_shoulder"],
        verdicts=[],
        triangulator=triangulator,
        calib_path="/some/calib.npz" if triangulator is not None else None,
        now=now,
    )


class TestComputeEpipolar(unittest.TestCase):
    def test_known_delta(self):
        epi = compute_epipolar(_calibration(), (110.0, 200.0), (110.0, 203.0))
        self.assertIsNotNone(epi)
        self.assertAlmostEqual(epi["signed_y_delta_px"], -3.0, places=3)
        self.assertAlmostEqual(epi["epipolar_error_px"], 3.0, places=3)

    def test_non_finite_returns_none(self):
        self.assertIsNone(compute_epipolar(_calibration(), (np.nan, 0.0), (1.0, 1.0)))


class TestSaveSnapshot(unittest.TestCase):
    def test_writes_expected_files_and_raw_frames_unchanged(self):
        left, right = _frames()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = _save(root, triangulator=StereoTriangulator(_calibration()))

            self.assertTrue((dest / "left_raw.png").exists())
            self.assertTrue((dest / "right_raw.png").exists())
            self.assertTrue((dest / "left_annotated.png").exists())
            self.assertTrue((dest / "right_annotated.png").exists())
            self.assertTrue((dest / "manifest.json").exists())
            self.assertTrue((dest / "calibration_snapshot.npz").exists())
            self.assertTrue((dest / "README.txt").exists())

            # Raw frames passed by the caller are never mutated in memory.
            self.assertTrue(np.array_equal(left, np.full((120, 160, 3), 10, dtype=np.uint8)))
            self.assertTrue(np.array_equal(right, np.full((120, 160, 3), 20, dtype=np.uint8)))

            # Saved raw PNGs keep source attribution (left != right).
            raw_l = cv2.imread(str(dest / "left_raw.png"))
            raw_r = cv2.imread(str(dest / "right_raw.png"))
            self.assertEqual(raw_l.shape, (120, 160, 3))
            self.assertEqual(raw_r.shape, (120, 160, 3))
            self.assertAlmostEqual(float(raw_l[0, 0, 0]), 10.0, places=0)
            self.assertAlmostEqual(float(raw_r[0, 0, 0]), 20.0, places=0)

        # Containment, once more, against a plain path.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(is_within_snapshot_root(snapshot_dir(root) / "x", root))
            self.assertFalse(is_within_snapshot_root(Path(tmp) / "other", root))

    def test_manifest_maps_joints_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            mani = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(mani["schema"], "stereo_pose_3d/snapshot/v1")
            self.assertEqual(mani["frame_index"], 42)
            self.assertEqual(mani["calibration"]["coordinate_system"], "rectified_left_camera")
            self.assertEqual(mani["calibration"]["units"], "mm")
            self.assertTrue(mani["calibration"]["available"])

            joints = {j["joint"]: j for j in mani["joints"]}
            ls = joints["left_shoulder"]
            self.assertAlmostEqual(ls["rectified"]["signed_y_delta_px"], -3.0, places=3)
            self.assertAlmostEqual(ls["rectified"]["epipolar_error_px"], 3.0, places=3)
            self.assertTrue(ls["rectified"]["available"])

            # nose is missing (low confidence) in the pose table.
            pose_l = mani["pose"]["left"]["keypoints"]
            nose = next(k for k in pose_l if k["label"] == "nose")
            self.assertTrue(nose["missing"])
            self.assertIsNone(nose["uv"])

    def test_no_calibration_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=None)
            mani = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(mani["calibration"]["available"])
            self.assertEqual(mani["calibration"]["missing_reason"], "no stereo calibration loaded")
            self.assertFalse((dest / "calibration_snapshot.npz").exists())
            ls = next(j for j in mani["joints"] if j["joint"] == "left_shoulder")
            self.assertFalse(ls["rectified"]["available"])
            self.assertEqual(ls["rectified"]["missing_reason"], "no calibration loaded")

    def test_no_overwrite_and_containment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
            d1 = _save(root, triangulator=StereoTriangulator(_calibration()), now=now)
            d2 = _save(root, triangulator=StereoTriangulator(_calibration()), now=now)
            self.assertNotEqual(d1, d2)
            for d in (d1, d2):
                self.assertTrue(is_within_snapshot_root(d, root))

    def test_cleanup_does_not_delete_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = _save(root, triangulator=StereoTriangulator(_calibration()))
            cleanup_project(
                root / "calibrations", root / "sessions",
                runtime_root=root,
                keep_latest=10, failed_days=7, verbose=False,
            )
            self.assertTrue((dest / "manifest.json").exists())


class TestOfflineReplay(unittest.TestCase):
    def test_inspect_snapshot_cli_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            proc = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "inspect_snapshot.py"), str(dest)],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("replayed 2 joint(s); 0 mismatch(es)", proc.stdout)

    def test_inspect_snapshot_cli_no_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=None)
            proc = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "inspect_snapshot.py"), str(dest)],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            self.assertEqual(proc.returncode, 1)


class TestMenuLines(unittest.TestCase):
    def test_collapsed_keeps_warnings_and_hint(self):
        from stereo_pose.app.runner import build_menu_lines
        alarms = ["! no stereo calibration loaded (C -> R)"]
        lines = build_menu_lines(
            False, camera_left=2, camera_right=1, device="cpu", cal_state="calib=NONE",
            accepted_total=0, selected_total=14, rejected_total=14, fps_txt="30fps",
            rms_txt="n/a", epi_txt="n/a", reproj_txt="n/a", skew_txt="1.25ms",
            smooth_txt="F:smoothing ON", one_euro_min=1.2, one_euro_beta=0.015,
            one_euro_d=1.0, alarms=alarms,
        )
        joined = " | ".join(lines)
        self.assertIn("! no stereo calibration loaded", joined)
        self.assertIn("M: Developer tools", joined)
        self.assertNotIn("OneEuro", joined)
        self.assertNotIn("S=snapshot", joined)

    def test_expanded_has_hotkeys_and_internals(self):
        from stereo_pose.app.runner import build_menu_lines
        lines = build_menu_lines(
            True, camera_left=2, camera_right=1, device="cpu", cal_state="calib=OK",
            accepted_total=3, selected_total=14, rejected_total=11, fps_txt="30fps",
            rms_txt="0.56", epi_txt="2.1px", reproj_txt="0.3px", skew_txt="1.25ms",
            smooth_txt="F:smoothing ON", one_euro_min=1.2, one_euro_beta=0.015,
            one_euro_d=1.0, alarms=[],
        )
        joined = "\n".join(lines)
        self.assertIn("S=snapshot", joined)
        self.assertIn("M=collapse", joined)
        self.assertIn("OneEuro min_cutoff=1.2", joined)


if __name__ == "__main__":
    unittest.main()
