"""Camera discovery / preview / LEFT-RIGHT selection tests (Task 002A).

Deterministic: no camera hardware, no display. Device and GUI access are
injected fakes (``FakeCameras``, scripted key streams, recording show_fn);
every requirement of ``docs/instructions/002A_CAMERA_SELECTION_PRETEST.md``
section E is covered without touching a real device.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

import stereo_pose.capture.selection as selection_module
from stereo_pose.capture.selection import (
    CameraSelectionSession,
    discover_cameras,
    release_all,
    render_canvas,
    run_camera_selection,
    save_camera_choice,
    selection_requested,
)
from stereo_pose.config import ConfigError, load_config, validate_config

SRC = Path(__file__).resolve().parents[2] / "src"

KEY_ENTER = 13
KEY_ESC = 27


def _k(ch):
    """ord() helper for scripted key presses."""
    return ord(ch)


class FakeCam:
    def __init__(self, fake, index):
        self.fake = fake
        self.index = index
        self.release_count = 0

    @property
    def released(self):
        return self.release_count > 0


class FakeCameras:
    """Injectable open/read/release triple with per-index behavior modes.

    Modes: ``"ok"`` (delivers frames), ``"no_frames"`` (opens, never delivers),
    ``"read_error"`` (opens, read raises), ``"open_fail"``/missing (open raises).
    Frames encode their camera index so previews are distinguishable.
    """

    def __init__(self, specs=None):
        self.specs = dict(specs or {})
        self.open_log = []      # every open attempt (including failures)
        self.release_log = []  # every release call
        self.read_counts = {}
        self.cams = []          # every successfully created handle

    def open(self, index):
        self.open_log.append(index)
        if self.specs.get(index) in (None, "open_fail"):
            raise RuntimeError(f"Cannot open camera index {index}")
        cam = FakeCam(self, index)
        self.cams.append(cam)
        return cam

    def read(self, cam):
        self.read_counts[cam.index] = self.read_counts.get(cam.index, 0) + 1
        mode = self.specs.get(cam.index)
        if mode == "no_frames":
            return False, None
        if mode == "read_error":
            raise OSError("device read error")
        return True, np.full((36, 64, 3), (cam.index + 1) * 8, dtype=np.uint8)

    def release(self, cam):
        cam.release_count += 1
        self.release_log.append(cam.index)

    def all_handles_released_exactly_once(self):
        """Every handle ever created was released exactly once."""
        return all(cam.release_count == 1 for cam in self.cams)


def key_script(keys):
    """waitKey fake that replays ``keys``; exhausting the script fails loudly
    instead of looping forever (the real loop blocks on a human)."""
    it = iter(keys)

    def wait_key():
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("key script exhausted — picker would loop forever")

    return wait_key


class RecordingUI:
    """show_fn / destroy_fn fakes: capture canvases, never touch the cv2 GUI."""

    def __init__(self):
        self.canvases = []
        self.destroy_count = 0

    def show(self, canvas):
        self.canvases.append(canvas)

    def destroy(self):
        self.destroy_count += 1


def _write_config(path, extra=None, camera=None):
    data = json.loads(
        (Path(__file__).parents[2] / "configs" / "default.json").read_text(encoding="utf-8")
    )
    if camera:
        data["camera"].update(camera)
    if extra:
        data.update(extra)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class TestDiscovery(unittest.TestCase):
    def test_three_cameras_all_usable(self):
        fake = FakeCameras({0: "ok", 1: "ok", 2: "ok"})
        result = discover_cameras(7, fake.open, fake.read, fake.release)
        self.assertEqual(result.usable_indexes, [0, 1, 2])
        self.assertEqual(sorted(result.handles), [0, 1, 2])
        for cand in result.candidates[:3]:
            self.assertTrue(cand.usable)
            self.assertIsNotNone(cand.frame)
        # Probed-but-missing indexes are reported as unusable, not hidden.
        self.assertEqual([c.usable for c in result.candidates[3:]], [False] * 5)

    def test_sparse_indexes_supported(self):
        fake = FakeCameras({0: "ok", 2: "ok", 5: "ok"})
        result = discover_cameras(7, fake.open, fake.read, fake.release)
        self.assertEqual(result.usable_indexes, [0, 2, 5])
        # Missing indexes were probed too (1, 3, 4, 6, 7) — sparse is fine.
        self.assertEqual(fake.open_log, [0, 1, 2, 3, 4, 5, 6, 7])

    def test_opens_but_no_frames_is_not_usable_and_released(self):
        fake = FakeCameras({0: "ok", 1: "no_frames", 2: "ok"})
        result = discover_cameras(7, fake.open, fake.read, fake.release, first_frame_attempts=5)
        self.assertEqual(result.usable_indexes, [0, 2])
        self.assertNotIn(1, result.handles)
        self.assertIn(1, fake.release_log)  # dead handle released immediately
        self.assertEqual(fake.read_counts[1], 5)  # bounded read attempts
        # The kept preview handles are released too once the caller is done.
        release_all(result.handles, fake.release)
        self.assertTrue(fake.all_handles_released_exactly_once())

    def test_read_error_is_not_usable_and_released(self):
        fake = FakeCameras({0: "read_error", 1: "ok"})
        result = discover_cameras(7, fake.open, fake.read, fake.release)
        self.assertEqual(result.usable_indexes, [1])
        self.assertIn(0, fake.release_log)

    def test_probe_respects_max_index(self):
        fake = FakeCameras({5: "ok"})
        result = discover_cameras(2, fake.open, fake.read, fake.release)
        self.assertEqual(fake.open_log, [0, 1, 2])
        self.assertEqual(result.usable_indexes, [])
        # The one usable handle (5 is outside the probe range here) never opened.
        self.assertEqual(fake.cams, [])


class TestSessionState(unittest.TestCase):
    def make(self, usable=(0, 1, 2)):
        return CameraSelectionSession(list(usable))

    def test_left_then_right_assignment(self):
        s = self.make()
        s.handle_key(_k("1"))
        s.handle_key(_k("2"))
        self.assertEqual((s.left, s.right), (1, 2))
        self.assertTrue(s.complete)

    def test_duplicate_camera_rejected(self):
        s = self.make()
        s.handle_key(_k("1"))
        action = s.handle_key(_k("1"))  # same camera for RIGHT
        self.assertIsNone(action)
        self.assertIsNone(s.right)
        self.assertIn("already LEFT", s.message)
        self.assertFalse(s.complete)

    def test_right_can_be_reassigned_before_confirm(self):
        s = self.make()
        s.handle_key(_k("1"))
        s.handle_key(_k("2"))
        s.handle_key(_k("0"))  # change of mind: RIGHT becomes CAM 0
        self.assertEqual((s.left, s.right), (1, 0))

    def test_undo_clears_right_then_left(self):
        s = self.make()
        s.handle_key(_k("1"))
        s.handle_key(_k("2"))
        s.handle_key(_k("u"))
        self.assertEqual((s.left, s.right), (1, None))
        s.handle_key(_k("u"))
        self.assertEqual((s.left, s.right), (None, None))

    def test_unavailable_index_rejected(self):
        s = self.make((0, 1, 2))
        s.handle_key(_k("9"))
        self.assertIn("not available", s.message)
        self.assertIsNone(s.left)

    def test_enter_requires_complete_assignment(self):
        s = self.make()
        s.handle_key(_k("1"))
        self.assertIsNone(s.handle_key(KEY_ENTER))
        self.assertFalse(s.complete)
        self.assertIn("assign two different", s.message)

    def test_enter_confirms_when_complete(self):
        s = self.make()
        s.handle_key(_k("1"))
        s.handle_key(_k("2"))
        self.assertEqual(s.handle_key(KEY_ENTER), "confirm")

    def test_rescan_and_cancel_keys(self):
        s = self.make()
        self.assertEqual(s.handle_key(_k("r")), "rescan")
        self.assertEqual(s.handle_key(_k("q")), "cancel")
        s2 = self.make()
        self.assertEqual(s2.handle_key(KEY_ESC), "cancel")

    def test_no_key_and_unknown_keys_ignored(self):
        s = self.make()
        self.assertIsNone(s.handle_key(255))
        self.assertIsNone(s.handle_key(_k("z")))
        self.assertEqual((s.left, s.right), (None, None))


class TestRunCameraSelection(unittest.TestCase):
    def run_picker(self, fake, keys, cfg_path, **kwargs):
        ui = RecordingUI()
        logs = []

        choice = run_camera_selection(
            cfg_path,
            open_fn=fake.open,
            read_fn=fake.read,
            release_fn=fake.release,
            wait_key=key_script(keys),
            show_fn=ui.show,
            destroy_fn=ui.destroy,
            log=logs.append,
            **kwargs,
        )
        return choice, ui, logs

    def test_confirm_persists_choice_and_feeds_startup_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(
                Path(d) / "config.json",
                extra={"note": "keep me", "my_section": {"deep": [1, 2, 3]}},
                camera={"left": 0, "right": 1},
            )
            fake = FakeCameras({0: "ok", 1: "ok", 2: "ok"})
            choice, ui, logs = self.run_picker(fake, [_k("1"), _k("2"), KEY_ENTER], cfg_path)
            self.assertEqual((choice.left, choice.right), (1, 2))
            # The confirmed order reaches the real startup pipeline (config).
            cfg = load_config(cfg_path)
            self.assertEqual(cfg["camera"]["left"], 1)
            self.assertEqual(cfg["camera"]["right"], 2)
            # Unrelated fields survive.
            self.assertEqual(cfg["note"], "keep me")
            self.assertEqual(cfg["my_section"]["deep"], [1, 2, 3])
            # All probe handles released before tracking would open cameras.
            self.assertTrue(fake.all_handles_released_exactly_once())
            self.assertEqual(ui.destroy_count, 1)
            self.assertTrue(any("saved" in m for m in logs))
            # Previews were rendered with live frames (visual identification).
            self.assertGreaterEqual(len(ui.canvases), 3)

    def test_cancel_never_writes_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json", camera={"left": 0, "right": 1})
            before = cfg_path.read_bytes()
            fake = FakeCameras({0: "ok", 1: "ok", 2: "ok"})
            choice, ui, logs = self.run_picker(fake, [KEY_ESC], cfg_path)
            self.assertIsNone(choice)
            self.assertEqual(cfg_path.read_bytes(), before)
            self.assertTrue(fake.all_handles_released_exactly_once())
            self.assertTrue(any("cancelled" in m for m in logs))

    def test_rescan_releases_then_reprobes(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json")
            fake = FakeCameras({0: "ok", 1: "ok"})
            script = [_k("r"), _k("1"), _k("2"), KEY_ENTER]

            def wait_key():
                assert script, "picker looped past the scripted keys"
                key = script.pop(0)
                if key == _k("r"):
                    # Owner plugs the third USB camera, then hits R to rescan.
                    fake.specs[2] = "ok"
                return key

            logs = []
            choice = run_camera_selection(
                cfg_path,
                open_fn=fake.open,
                read_fn=fake.read,
                release_fn=fake.release,
                wait_key=wait_key,
                show_fn=lambda canvas: None,
                destroy_fn=lambda: None,
                log=logs.append,
            )
            self.assertEqual((choice.left, choice.right), (1, 2))
            cfg = load_config(cfg_path)
            self.assertEqual((cfg["camera"]["left"], cfg["camera"]["right"]), (1, 2))
            # First scan's two handles were released before the re-probe...
            self.assertEqual(fake.release_log[:2], [0, 1])
            # ...and the second scan saw all three cameras.
            self.assertEqual(fake.open_log[8:], [0, 1, 2, 3, 4, 5, 6, 7])
            self.assertTrue(fake.all_handles_released_exactly_once())
            self.assertTrue(any("usable cameras: CAM [0, 1, 2]" in m for m in logs))

    def test_fewer_than_two_cameras_warns_and_cancel_keeps_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json", camera={"left": 0, "right": 1})
            before = cfg_path.read_bytes()
            fake = FakeCameras({0: "ok"})
            choice, ui, logs = self.run_picker(fake, [KEY_ESC], cfg_path)
            self.assertIsNone(choice)
            self.assertTrue(any("only 1 usable" in m for m in logs))
            self.assertEqual(cfg_path.read_bytes(), before)
            self.assertTrue(fake.all_handles_released_exactly_once())

    def test_zero_cameras_error_path(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json")
            fake = FakeCameras({})
            choice, ui, logs = self.run_picker(fake, [_k("q")], cfg_path)
            self.assertIsNone(choice)
            self.assertTrue(any("only 0 usable" in m for m in logs))
            self.assertEqual(fake.release_log, [])
            self.assertEqual(ui.destroy_count, 1)

    def test_failed_save_returns_none_and_keeps_previous_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(
                Path(d) / "config.json",
                extra={"note": "keep"},
                camera={"left": 0, "right": 1},
            )
            before = cfg_path.read_bytes()
            fake = FakeCameras({0: "ok", 1: "ok"})
            logs = []

            with mock.patch.object(
                selection_module.os, "replace", side_effect=OSError("disk full")
            ):
                choice = run_camera_selection(
                    cfg_path,
                    open_fn=fake.open,
                    read_fn=fake.read,
                    release_fn=fake.release,
                    wait_key=key_script([_k("1"), _k("0"), KEY_ENTER]),
                    show_fn=lambda canvas: None,
                    destroy_fn=lambda: None,
                    log=logs.append,
                )
            self.assertIsNone(choice)
            self.assertEqual(cfg_path.read_bytes(), before)
            self.assertTrue(any("could not save" in m for m in logs))
            self.assertTrue(fake.all_handles_released_exactly_once())
            # No temp files left behind after a failed atomic replace.
            leftovers = [p for p in Path(d).iterdir() if p.name != "config.json"]
            self.assertEqual(leftovers, [])

    def test_show_error_still_releases_all_handles(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json")
            fake = FakeCameras({0: "ok", 1: "ok", 2: "ok"})

            def exploding_show(canvas):
                raise RuntimeError("display backend died")

            with self.assertRaises(RuntimeError):
                run_camera_selection(
                    cfg_path,
                    open_fn=fake.open,
                    read_fn=fake.read,
                    release_fn=fake.release,
                    wait_key=key_script([]),
                    show_fn=exploding_show,
                    destroy_fn=lambda: None,
                )
            self.assertTrue(fake.all_handles_released_exactly_once())

    def test_loop_limit_guard(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json")
            fake = FakeCameras({0: "ok", 1: "ok"})
            with self.assertRaises(RuntimeError):
                run_camera_selection(
                    cfg_path,
                    open_fn=fake.open,
                    read_fn=fake.read,
                    release_fn=fake.release,
                    wait_key=lambda: 255,  # human never presses anything
                    show_fn=lambda canvas: None,
                    destroy_fn=lambda: None,
                    max_loop_frames=3,
                )
            self.assertTrue(fake.all_handles_released_exactly_once())

    def test_canvas_layout_and_fallbacks(self):
        session = CameraSelectionSession([0, 1, 2])
        session.handle_key(_k("1"))
        session.handle_key(_k("2"))
        frames = {i: np.full((36, 64, 3), 128, np.uint8) for i in (0, 1, 2)}
        canvas = render_canvas(frames, session)
        self.assertEqual(canvas.shape[0], 225 + 3 * 26 + 10)
        self.assertEqual(canvas.shape[1], 3 * 400)
        # Grayscale frames also render.
        gray = render_canvas({0: np.zeros((36, 64), np.uint8)}, CameraSelectionSession([0]))
        self.assertEqual(gray.ndim, 3)
        # A camera that stopped delivering falls back to a NO SIGNAL tile.
        dead = render_canvas({}, CameraSelectionSession([3]))
        self.assertEqual(dead.shape[1], 400)
        # Zero usable cameras still renders an actionable canvas.
        empty = render_canvas({}, CameraSelectionSession([]))
        self.assertEqual(empty.shape[1], 400)


class TestSaveCameraChoice(unittest.TestCase):
    def test_preserves_unrelated_fields_and_updates_cameras(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_config(
                Path(d) / "config.json",
                extra={"note": "keep", "custom": {"a": 1}},
                camera={"left": 0, "right": 1, "width": 960},
            )
            save_camera_choice(p, 1, 2)
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["camera"]["left"], 1)
            self.assertEqual(data["camera"]["right"], 2)
            self.assertEqual(data["camera"]["width"], 960)
            self.assertEqual(data["note"], "keep")
            self.assertEqual(data["custom"], {"a": 1})
            # The saved file is still a fully valid config.
            validate_config(load_config(p))

    def test_missing_config_file_creates_camera_section(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            save_camera_choice(p, 0, 2)
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["camera"], {"left": 0, "right": 2})

    def test_malformed_config_raises_and_leaves_file_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_camera_choice(p, 1, 2)
            self.assertEqual(p.read_text(encoding="utf-8"), "{not json")

    def test_failed_write_does_not_corrupt_previous_config(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            _write_config(p, camera={"left": 0, "right": 1})
            before = p.read_bytes()
            with mock.patch.object(
                selection_module.os, "replace", side_effect=OSError("cannot replace")
            ):
                with self.assertRaises(OSError):
                    save_camera_choice(p, 1, 2)
            self.assertEqual(p.read_bytes(), before)
            leftovers = [x for x in Path(d).iterdir() if x.name != "config.json"]
            self.assertEqual(leftovers, [])

    def test_rejects_invalid_choices(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            _write_config(p)
            with self.assertRaises(ValueError):
                save_camera_choice(p, 1, 1)  # duplicate index
            with self.assertRaises(ValueError):
                save_camera_choice(p, -1, 2)  # negative index
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["camera"]["left"], 0)


class TestSelectionConfig(unittest.TestCase):
    def test_old_config_without_selection_merges_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text(json.dumps({"camera": {"left": 3, "right": 4}}), encoding="utf-8")
            cfg = load_config(p)
            self.assertEqual(cfg["camera"]["selection"]["startup_pick"], True)
            self.assertEqual(cfg["camera"]["selection"]["probe_max_index"], 7)
            self.assertEqual(cfg["camera"]["selection"]["first_frame_attempts"], 5)
            validate_config(cfg)

    def test_bad_probe_max_index_raises(self):
        cfg = load_config(None)
        cfg["camera"]["selection"]["probe_max_index"] = 10
        with self.assertRaises(ConfigError):
            validate_config(cfg)
        cfg["camera"]["selection"]["probe_max_index"] = -1
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_probe_max_index_boundary_accepted(self):
        # B3: the picker assigns cameras with single-digit keys, so the scan
        # range is 0..9; 9 is the maximum valid value.
        for idx in (0, 9):
            cfg = load_config(None)
            cfg["camera"]["selection"]["probe_max_index"] = idx
            validate_config(cfg)  # must not raise

    def test_bad_first_frame_attempts_raises(self):
        cfg = load_config(None)
        cfg["camera"]["selection"]["first_frame_attempts"] = 0
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_non_bool_startup_pick_raises(self):
        cfg = load_config(None)
        cfg["camera"]["selection"]["startup_pick"] = "yes"
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_probe_covers_configured_index_range(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_config(Path(d) / "config.json")
            fake = FakeCameras({0: "ok", 1: "ok"})
            logs = []
            run_camera_selection(
                p,
                open_fn=fake.open,
                read_fn=fake.read,
                release_fn=fake.release,
                wait_key=key_script([KEY_ESC]),
                show_fn=lambda canvas: None,
                destroy_fn=lambda: None,
                log=logs.append,
            )
            self.assertEqual(fake.open_log, [0, 1, 2, 3, 4, 5, 6, 7])
            self.assertTrue(fake.all_handles_released_exactly_once())


class TestNoninteractiveSafety(unittest.TestCase):
    def _args(self, camera_pick=False, left=None, right=None):
        return SimpleNamespace(camera_pick=camera_pick, left_cam=left, right_cam=right)

    def test_cli_without_pick_never_offers_selection(self):
        from stereo_pose.app.runner import should_pick_cameras

        self.assertFalse(should_pick_cameras(self._args()))
        self.assertFalse(should_pick_cameras(self._args(camera_pick=False, left=1, right=2)))

    def test_camera_pick_flag_enables_selection(self):
        from stereo_pose.app.runner import should_pick_cameras

        self.assertTrue(should_pick_cameras(self._args(camera_pick=True)))

    def test_explicit_cli_indexes_override_picker(self):
        from stereo_pose.app.runner import should_pick_cameras

        self.assertFalse(should_pick_cameras(self._args(camera_pick=True, left=1, right=2)))
        self.assertFalse(should_pick_cameras(self._args(camera_pick=True, left=1)))
        self.assertFalse(should_pick_cameras(self._args(camera_pick=True, right=2)))

    def test_startup_pick_config_and_env(self):
        cfg = load_config(None)
        self.assertTrue(selection_requested(cfg))
        self.assertFalse(selection_requested(cfg, env={"STEREO_POSE_NO_CAMERA_PICK": "1"}))
        cfg["camera"]["selection"]["startup_pick"] = False
        self.assertFalse(selection_requested(cfg))
        self.assertFalse(selection_requested(cfg, env={}))

    def test_runner_cli_help_lists_camera_pick(self):
        """The CLI parses offline and never blocks on GUI for --help."""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        proc = subprocess.run(
            [sys.executable, "-m", "stereo_pose", "run", "--help"],
            capture_output=True, text=True, env=env, timeout=60,
            cwd=str(SRC.parent),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--camera-pick", proc.stdout)
        self.assertIn("--left-cam", proc.stdout)


class TestFailClosed(unittest.TestCase):
    """B1: cancelling or failing camera selection must never start tracking."""

    def _load_run_me(self):
        import importlib.util

        run_me_path = Path(__file__).resolve().parents[2] / "RUN_ME.py"
        spec = importlib.util.spec_from_file_location("run_me_under_test", run_me_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _exercise_launcher(self, picker_kwargs):
        """Run the RUN_ME launcher main() with camera selection forced to
        cancel (return None) or fail (raise); return the run_main call log."""
        mod = self._load_run_me()
        from stereo_pose.app import runner as runner_mod
        from stereo_pose.capture import selection as sel

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "yolo11n-pose.pt").write_bytes(b"dummy model")
            cfg_path = _write_config(root / "config.json")  # startup_pick: true
            run_main_calls = []

            with mock.patch.object(mod, "ROOT", root), \
                 mock.patch.object(mod, "check_dependencies"), \
                 mock.patch.object(mod, "ensure_config", return_value=cfg_path), \
                 mock.patch.object(sel, "run_camera_selection", **picker_kwargs), \
                 mock.patch.object(runner_mod, "main", side_effect=lambda: run_main_calls.append(1)):
                with self.assertRaises(SystemExit):
                    mod.main()
            return run_main_calls

    def test_cli_camera_pick_cancel_never_runs_tracking(self):
        from stereo_pose.app import runner as runner_mod
        from stereo_pose.capture import selection as sel

        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json")
            with mock.patch.object(
                sys, "argv", ["stereo_pose", "run", "--config", str(cfg_path), "--camera-pick"]
            ), mock.patch.object(sel, "run_camera_selection", return_value=None), \
               mock.patch.object(runner_mod, "run") as run_fn:
                with self.assertRaises(SystemExit):
                    runner_mod.main()
                run_fn.assert_not_called()

    def test_cli_camera_pick_failure_never_runs_tracking(self):
        from stereo_pose.app import runner as runner_mod
        from stereo_pose.capture import selection as sel

        with tempfile.TemporaryDirectory() as d:
            cfg_path = _write_config(Path(d) / "config.json")
            with mock.patch.object(
                sys, "argv", ["stereo_pose", "run", "--config", str(cfg_path), "--camera-pick"]
            ), mock.patch.object(sel, "run_camera_selection", side_effect=RuntimeError("boom")), \
               mock.patch.object(runner_mod, "run") as run_fn:
                with self.assertRaises(SystemExit):
                    runner_mod.main()
                run_fn.assert_not_called()

    def test_launcher_cancel_never_runs_tracking(self):
        self.assertEqual(self._exercise_launcher({"return_value": None}), [])

    def test_launcher_failure_never_runs_tracking(self):
        self.assertEqual(self._exercise_launcher({"side_effect": RuntimeError("boom")}), [])


class TestCalibrationIdentityWarning(unittest.TestCase):
    """NPZ camera-index mismatch warns prominently without discarding the NPZ."""

    def _calib(self, path, camera_left=0, camera_right=1, with_camera_fields=True):
        K = np.eye(3, dtype=float)
        D = np.zeros(5, dtype=float)
        P = np.hstack([K, np.zeros((3, 1), dtype=float)])
        fields = {
            "K1": K, "D1": D, "K2": K, "D2": D,
            "R1": np.eye(3), "R2": np.eye(3), "P1": P, "P2": P,
            "image_size": np.array((1280, 720)),
        }
        if with_camera_fields:
            fields["camera_left"] = np.array(camera_left)
            fields["camera_right"] = np.array(camera_right)
        np.savez(str(path), **fields)
        return path

    def test_identity_warnings_on_mismatch(self):
        from stereo_pose.calibration.metadata import camera_identity_warnings

        with tempfile.TemporaryDirectory() as d:
            p = self._calib(Path(d) / "cal.npz", camera_left=0, camera_right=1)
            warnings = camera_identity_warnings(p, 1, 2)
            self.assertEqual(len(warnings), 1)
            self.assertIn("LEFT=camera 0", warnings[0])
            self.assertIn("LEFT=camera 1", warnings[0])

    def test_identity_silent_when_indexes_match(self):
        from stereo_pose.calibration.metadata import camera_identity_warnings

        with tempfile.TemporaryDirectory() as d:
            p = self._calib(Path(d) / "cal.npz", camera_left=1, camera_right=2)
            self.assertEqual(camera_identity_warnings(p, 1, 2), [])

    def test_identity_warning_when_npz_lacks_camera_fields(self):
        from stereo_pose.calibration.metadata import camera_identity_warnings

        with tempfile.TemporaryDirectory() as d:
            p = self._calib(Path(d) / "cal.npz", with_camera_fields=False)
            warnings = camera_identity_warnings(p, 1, 2)
            self.assertEqual(len(warnings), 1)
            self.assertIn("cannot be verified", warnings[0])

    def test_runner_banner_on_mismatch_without_discarding(self):
        from stereo_pose.app.runner import _report_calibration_compatibility

        with tempfile.TemporaryDirectory() as d:
            p = self._calib(Path(d) / "cal.npz", camera_left=0, camera_right=1)
            buf = io.StringIO()
            with redirect_stdout(buf):
                _report_calibration_compatibility(
                    p, (1280, 720), (9, 6),
                    fps=30.0, camera_indexes=(1, 2),
                )
            out = buf.getvalue()
            self.assertIn("CALIBRATION / CAMERA PAIRING WARNING", out)
            self.assertIn("was NOT modified", out)
            self.assertIn("recalibrate", out)
            self.assertTrue(p.exists())  # calibration never discarded

    def test_runner_no_banner_when_indexes_match(self):
        from stereo_pose.app.runner import _report_calibration_compatibility

        with tempfile.TemporaryDirectory() as d:
            p = self._calib(Path(d) / "cal.npz", camera_left=1, camera_right=2)
            buf = io.StringIO()
            with redirect_stdout(buf):
                _report_calibration_compatibility(
                    p, (1280, 720), (9, 6),
                    fps=30.0, camera_indexes=(1, 2),
                )
            self.assertNotIn("CAMERA PAIRING WARNING", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
