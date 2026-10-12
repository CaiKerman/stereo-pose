"""Diagnostic snapshot + offline epipolar replay + compact menu tests (Task 002B).

Deterministic: no camera, torch, CUDA, YOLO or model weights. Calibration
geometry uses exact synthetic matrices so rectified ``uv`` round-trips to the
raw pixel coordinates and the signed epipolar delta is analytically known.

Round-1 review coverage:

- B1: the RAW finite uv/confidence are always preserved (including the
  Ultralytics zero placeholder) and usability is expressed by independent
  ``missing``/``missing_reason``/``low_confidence`` fields.
- B2: the offline replay tool reports interpretable errors and exit codes for
  missing / corrupt / tampered data instead of raising, and cross-checks the
  stored rectified uv coordinates.
- B4: the overlay FPS is the measured full-loop rate and live alarms stay
  visible in the expanded developer menu.
- follow-ups: the caller's raw frame buffers are never mutated (the buffers
  asserted are the exact objects passed in), snapshot writes are staged and
  atomically published so a failed save leaves no half-written folder, and S
  reuses the already-captured pair / already-chosen pose without a second
  camera read or a second YOLO inference.
"""

import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from stereo_pose.diagnostics import snapshot as snapshot_module
from stereo_pose.diagnostics.snapshot import (
    SnapshotPose,
    compute_epipolar,
    is_within_snapshot_root,
    save_snapshot,
    snapshot_dir,
)
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.joints import JOINT_INDEX, JOINT_NAMES
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

    l_c[JOINT_INDEX["nose"]] = 0.0  # Ultralytics zero placeholder: uv=(0, 0), conf=0.0
    r_c[JOINT_INDEX["nose"]] = 0.0

    return _pose(l_p, l_c), _pose(r_p, r_c)


def _save(
    runtime_root,
    triangulator=None,
    now=None,
    *,
    frames=None,
    poses=None,
    confidence_threshold=None,
):
    """Save a snapshot, optionally injecting the exact buffers/poses to assert on."""
    frame_left, frame_right = frames if frames is not None else _frames()
    pose_left, pose_right = poses if poses is not None else _sample_poses()
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
        frame_left=frame_left,
        frame_right=frame_right,
        pose_left=pose_left,
        pose_right=pose_right,
        selected_joints=["left_shoulder", "right_shoulder"],
        verdicts=[],
        triangulator=triangulator,
        calib_path="/some/calib.npz" if triangulator is not None else None,
        confidence_threshold=confidence_threshold,
        now=now,
    )


def _manifest(dest):
    return json.loads((dest / "manifest.json").read_text(encoding="utf-8"))


def _run_cli(dest):
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "inspect_snapshot.py"), str(dest)],
        capture_output=True, text=True, cwd=str(ROOT),
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
        # Review follow-up: these must be the EXACT buffers handed to
        # save_snapshot, not fresh copies, for the mutation check to mean
        # anything.
        left, right = _frames()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = _save(
                root, frames=(left, right),
                triangulator=StereoTriangulator(_calibration()),
            )

            self.assertTrue((dest / "left_raw.png").exists())
            self.assertTrue((dest / "right_raw.png").exists())
            self.assertTrue((dest / "left_annotated.png").exists())
            self.assertTrue((dest / "right_annotated.png").exists())
            self.assertTrue((dest / "manifest.json").exists())
            self.assertTrue((dest / "calibration_snapshot.npz").exists())
            self.assertTrue((dest / "README.txt").exists())

            # The caller's buffers were not mutated in place.
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

    def test_manifest_maps_joints_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            mani = _manifest(dest)
            self.assertEqual(mani["schema"], "stereo_pose_3d/snapshot/v2")
            self.assertEqual(mani["frame_index"], 42)
            self.assertEqual(mani["calibration"]["coordinate_system"], "rectified_left_camera")
            self.assertEqual(mani["calibration"]["units"], "mm")
            self.assertTrue(mani["calibration"]["available"])

            joints = {j["joint"]: j for j in mani["joints"]}
            ls = joints["left_shoulder"]
            self.assertAlmostEqual(ls["rectified"]["signed_y_delta_px"], -3.0, places=3)
            self.assertAlmostEqual(ls["rectified"]["epipolar_error_px"], 3.0, places=3)
            self.assertTrue(ls["rectified"]["available"])

            # Review B1: the zero-placeholder nose keeps its RAW observation
            # (uv=(0,0), confidence=0.0) instead of being silently nulled.
            pose_l = mani["pose"]["left"]["keypoints"]
            nose = next(k for k in pose_l if k["label"] == "nose")
            self.assertEqual(nose["uv"], [0.0, 0.0])
            self.assertEqual(nose["confidence"], 0.0)
            self.assertTrue(nose["missing"])
            self.assertIn("zero placeholder", nose["missing_reason"])
            self.assertFalse(nose["low_confidence"])

    def test_no_calibration_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=None)
            mani = _manifest(dest)
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


class TestRawEvidencePreserved(unittest.TestCase):
    """Review B1: raw finite observations are ALWAYS kept; usability is a
    separate flag, never a reason to drop the evidence."""

    def test_nan_uv_is_missing_but_valid_keypoints_survive(self):
        lp, rp = _sample_poses()
        lp.keypoints[JOINT_INDEX["left_elbow"]] = (np.nan, 3.0)
        rp.keypoints[JOINT_INDEX["left_elbow"]] = (np.inf, 3.0)
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), poses=(lp, rp), triangulator=None)
            mani = _manifest(dest)
            elbow = next(
                k for k in mani["pose"]["left"]["keypoints"] if k["label"] == "left_elbow"
            )
            self.assertTrue(elbow["missing"])
            self.assertEqual(elbow["missing_reason"], "non-finite uv")
            self.assertIsNone(elbow["uv"])
            # The finite confidence value is still preserved.
            self.assertEqual(elbow["confidence"], 0.9)
            # A sibling detection with a bad coordinate never destroys the rest.
            nose = next(k for k in mani["pose"]["left"]["keypoints"] if k["label"] == "nose")
            self.assertTrue(nose["missing"])
            self.assertEqual(nose["uv"], [0.0, 0.0])

    def test_subthreshold_confidence_flagged_but_preserved(self):
        lp, rp = _sample_poses()
        lp.confidence[JOINT_INDEX["left_wrist"]] = 0.3
        rp.confidence[JOINT_INDEX["left_wrist"]] = 0.35
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(
                Path(tmp), poses=(lp, rp), confidence_threshold=0.5,
                triangulator=StereoTriangulator(_calibration()),
            )
            mani = _manifest(dest)
            self.assertEqual(mani["pose"]["confidence_threshold"], 0.5)
            lw = next(k for k in mani["pose"]["left"]["keypoints"] if k["label"] == "left_wrist")
            self.assertFalse(lw["missing"])
            self.assertTrue(lw["low_confidence"])
            self.assertEqual(lw["confidence"], 0.3)
            # Above-threshold evidence is not flagged.
            ls = next(k for k in mani["pose"]["left"]["keypoints"] if k["label"] == "left_shoulder")
            self.assertFalse(ls["low_confidence"])
            # Without a threshold nothing is flagged low-confidence.
            mani2 = _manifest(_save(Path(tmp), poses=_sample_poses()))
            self.assertIsNone(mani2["pose"]["confidence_threshold"])

    def test_absent_pose_marked_missing(self):
        empty = SnapshotPose(detections=0, chosen_person_index=None)
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), poses=(empty, empty), triangulator=None)
            mani = _manifest(dest)
            k0 = mani["pose"]["left"]["keypoints"][0]
            self.assertTrue(k0["missing"])
            self.assertEqual(k0["missing_reason"], "absent pose")
            self.assertEqual(mani["pose"]["left"]["detections"], 0)
            self.assertIsNone(mani["pose"]["left"]["chosen_person_index"])

    def test_annotate_frame_skips_non_finite_without_crashing(self):
        left, _ = _frames()
        n = len(JOINT_NAMES)
        pts = np.zeros((n, 2))
        confs = np.zeros(n)
        pts[JOINT_INDEX["nose"]] = (np.nan, np.inf)
        # A NaN/Inf coordinate used to round into cv2 drawing and abort the
        # whole snapshot; it must simply be skipped.
        out = snapshot_module.annotate_frame(left, pts, confs)
        self.assertEqual(out.shape, left.shape)
        self.assertTrue(np.array_equal(out, left))

        # Valid detections are still drawn.
        out2 = snapshot_module.annotate_frame(left, np.zeros((n, 2)), np.full(n, 0.9))
        self.assertFalse(np.array_equal(out2, left))


class TestAtomicSnapshotWrite(unittest.TestCase):
    """Review follow-up: a failed save must never leave a half-written folder
    that looks like valid evidence, and must never touch prior snapshots."""

    def test_failed_save_leaves_no_partial_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(
                snapshot_module, "_write_json", side_effect=OSError("disk full")
            ):
                with self.assertRaises(OSError):
                    _save(root, triangulator=StereoTriangulator(_calibration()))
            entries = sorted(snapshot_dir(root).iterdir())
            self.assertEqual(entries, [])  # nothing published, no .partial leftovers

    def test_failed_save_never_touches_previous_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = _save(root, triangulator=StereoTriangulator(_calibration()))
            with mock.patch.object(
                snapshot_module, "_write_json", side_effect=OSError("boom")
            ):
                with self.assertRaises(OSError):
                    _save(root, triangulator=StereoTriangulator(_calibration()))
            mani = _manifest(good)
            self.assertEqual(mani["frame_index"], 42)
            leftovers = [p for p in snapshot_dir(root).iterdir() if ".partial" in p.name]
            self.assertEqual(leftovers, [])
            published = [
                p for p in snapshot_dir(root).iterdir()
                if p.is_dir() and ".partial" not in p.name
            ]
            self.assertEqual(published, [good])

    def test_failed_save_can_retry_with_fresh_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(
                snapshot_module, "_write_json", side_effect=OSError("boom")
            ):
                with self.assertRaises(OSError):
                    _save(root, triangulator=StereoTriangulator(_calibration()))
            # The retry succeeds and publishes exactly one complete folder.
            dest = _save(root, triangulator=StereoTriangulator(_calibration()))
            self.assertTrue((dest / "manifest.json").exists())
            self.assertEqual(len(list(snapshot_dir(root).iterdir())), 1)


class TestOfflineReplay(unittest.TestCase):
    def test_inspect_snapshot_cli_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("replayed 2 joint(s); 0 mismatch(es)", proc.stdout)
            # Review B2: rectified uv coordinates are cross-checked too.
            self.assertIn("uv_ok", proc.stdout)
            self.assertNotIn("DIFF", proc.stdout)
            self.assertRegex(proc.stdout, r"ok\s+ok")

    def test_inspect_snapshot_cli_no_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=None)
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("cannot recompute", proc.stdout)


class TestOfflineReplayRobustness(unittest.TestCase):
    """Review B2: missing / corrupt / tampered inputs produce interpretable
    errors and stable exit codes; the tool must never raise a raw traceback.

    Exit codes: 0 = replayed and matched; 1 = replay impossible;
    2 = replayed but mismatching stored values.
    """

    def test_missing_manifest_directory_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run_cli(Path(tmp))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("manifest not found", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_corrupt_manifest_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            (dest / "manifest.json").write_text("{not json", encoding="utf-8")
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("corrupt", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_unsupported_schema_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            mani = _manifest(dest)
            mani["schema"] = "stereo_pose_3d/snapshot/v0"
            (dest / "manifest.json").write_text(
                json.dumps(mani), encoding="utf-8"
            )
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("unsupported manifest schema", proc.stderr)

    def test_corrupt_calibration_npz_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            (dest / "calibration_snapshot.npz").write_bytes(b"not an npz file")
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("corrupt", proc.stderr)

    def test_missing_stored_residual_reported_not_crash(self):
        # The original tool formatted the stored residual directly and raised
        # TypeError when it was null; now it is reported as a mismatch.
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            mani = _manifest(dest)
            mani["joints"][0]["rectified"]["signed_y_delta_px"] = None
            (dest / "manifest.json").write_text(
                json.dumps(mani), encoding="utf-8"
            )
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("missing/invalid stored signed_y_delta_px", proc.stdout)
            self.assertNotIn("Traceback", proc.stdout)

    def test_tampered_stored_delta_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            mani = _manifest(dest)
            mani["joints"][0]["rectified"]["signed_y_delta_px"] = 999.0
            (dest / "manifest.json").write_text(
                json.dumps(mani), encoding="utf-8"
            )
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("signed delta differs", proc.stdout)
            self.assertIn("1 mismatch(es)", proc.stdout)

    def test_tampered_rectified_uv_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            mani = _manifest(dest)
            mani["joints"][0]["rectified"]["uv_left"] = [123.0, 456.0]
            (dest / "manifest.json").write_text(
                json.dumps(mani), encoding="utf-8"
            )
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("rectified uv_left differs", proc.stdout)
            self.assertIn("DIFF", proc.stdout)

    def test_nonexistent_path_exit_1(self):
        proc = _run_cli(ROOT / "definitely_not_a_snapshot_dir")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not a directory", proc.stderr)


class TestRealOpenCVDistortionShape(unittest.TestCase):
    """Review round 2 B5: real cv2.calibrateCamera / cv2.stereoCalibrate return
    distortion coefficients as a (1, 5) row vector; column vectors (5, 1) are
    equally valid OpenCV output. The snapshot-write -> offline-replay round
    trip must accept both, exactly like the live pipeline does."""

    def _roundtrip(self, d_shape):
        cal = _calibration()
        cal["D1"] = np.zeros(d_shape, dtype=float)
        cal["D2"] = np.zeros(d_shape, dtype=float)
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(cal))
            # The saved NPZ preserves the real OpenCV distortion shape.
            saved = np.load(dest / "calibration_snapshot.npz")
            self.assertEqual(saved["D1"].shape, d_shape)
            self.assertEqual(saved["D2"].shape, d_shape)
            return _run_cli(dest)

    def test_row_vector_d_1x5_replays(self):
        proc = self._roundtrip((1, 5))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("replayed 2 joint(s); 0 mismatch(es)", proc.stdout)

    def test_column_vector_d_5x1_replays(self):
        proc = self._roundtrip((5, 1))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("replayed 2 joint(s); 0 mismatch(es)", proc.stdout)

    def test_flat_d_vector_still_replays(self):
        # A flat (5,) vector (the synthetic test geometry) remains accepted.
        proc = self._roundtrip((5,))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("replayed 2 joint(s); 0 mismatch(es)", proc.stdout)

    def test_true_2d_distortion_matrix_rejected(self):
        # A (2, 5) matrix is NOT a valid OpenCV distortion vector and must
        # still be rejected with exit 1 (never silently accepted). Rewrite the
        # saved NPZ in place so _load_calibration is exercised directly,
        # independent of how the live write path handles a bogus distortion
        # shape.
        with tempfile.TemporaryDirectory() as tmp:
            dest = _save(Path(tmp), triangulator=StereoTriangulator(_calibration()))
            with np.load(dest / "calibration_snapshot.npz") as loaded:
                fields = {k: loaded[k] for k in loaded.files}
            fields["D1"] = np.zeros((2, 5), dtype=float)
            fields["D2"] = np.zeros((2, 5), dtype=float)
            np.savez(dest / "calibration_snapshot.npz", **fields)
            proc = _run_cli(dest)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("distortion (row/column) vector", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)


class TestSnapshotPurity(unittest.TestCase):
    """Review follow-up: pressing S must reuse the already-captured frame pair
    and the already-completed pose inference — never a second camera read and
    never a second YOLO pass. Verified statically so no camera/GPU is needed.
    """

    def test_snapshot_module_has_no_camera_or_inference_dependencies(self):
        src = inspect.getsource(snapshot_module)
        self.assertNotIn("VideoCapture", src)
        self.assertNotIn("PoseEstimator", src)
        self.assertNotIn("infer_pair", src)
        # save_snapshot takes raw frames/keypoints only — no camera handles.
        params = " ".join(inspect.signature(save_snapshot).parameters)
        self.assertNotIn("cap", params)

    def test_runner_s_handler_reuses_captured_data_only(self):
        from stereo_pose.app import runner as runner_module

        src = inspect.getsource(runner_module.run)
        handler = src.split('key in (ord("s"), ord("S"))', 1)[1]
        handler = handler.split("elif key in", 1)[0]
        self.assertNotIn("read_stereo_pair", handler)
        self.assertNotIn("infer_pair", handler)
        self.assertNotIn("estimator.", handler)
        # The exact objects from the current iteration, not fresh reads.
        self.assertIn("frame_left=fl", handler)
        self.assertIn("frame_right=fr", handler)
        self.assertIn("keypoints=pts_l", handler)
        self.assertIn("keypoints=pts_r", handler)


class TestMenuLines(unittest.TestCase):
    def _lines(self, expanded, alarms):
        from stereo_pose.app.runner import build_menu_lines

        return build_menu_lines(
            expanded,
            camera_left=2, camera_right=1, device="cpu",
            cal_state="calib=NONE" if not expanded else "calib=OK",
            accepted_total=0 if not expanded else 3,
            selected_total=14, rejected_total=14 if not expanded else 11,
            fps_txt="31fps", grab_txt="grab=33ms",
            rms_txt="0.56", epi_txt="2.1px", reproj_txt="0.3px",
            skew_txt="1.25ms", smooth_txt="F:smoothing ON",
            one_euro_min=1.2, one_euro_beta=0.015, one_euro_d=1.0,
            alarms=alarms,
        )

    def test_collapsed_keeps_warnings_and_hint(self):
        lines = self._lines(False, ["! no stereo calibration loaded (C -> R)"])
        joined = " | ".join(lines)
        self.assertIn("! no stereo calibration loaded", joined)
        self.assertIn("M: Developer tools", joined)
        self.assertNotIn("OneEuro", joined)
        self.assertNotIn("S=snapshot", joined)

    def test_expanded_has_hotkeys_and_internals(self):
        lines = self._lines(True, [])
        joined = "\n".join(lines)
        self.assertIn("S=snapshot", joined)
        self.assertIn("M=collapse", joined)
        self.assertIn("OneEuro min_cutoff=1.2", joined)
        # Review B4: the grab-only cycle is shown separately from the
        # full-loop fps so it cannot be misread as the frame rate.
        self.assertIn("31fps", joined)
        self.assertIn("grab=33ms", joined)

    def test_expanded_also_prepends_alarms(self):
        # Review B4: expanding the developer menu must not hide live warnings.
        lines = self._lines(True, ["! mean epipolar 4.2px > 3px gate"])
        self.assertEqual(lines[0], "! mean epipolar 4.2px > 3px gate")
        self.assertIn("S=snapshot", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
