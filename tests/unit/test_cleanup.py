"""Cleanup safety-boundary tests (managed auto/ vs saved/ + trusted root guard)."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import stereo_pose.persistence.cleanup as cleanup_mod
from stereo_pose.persistence import CleanupSafetyError, cleanup_project, ensure_managed_location


def _utime_days_ago(p, days):
    t = time.time() - days * 86400
    os.utime(p, (t, t))


def _auto(cal):
    a = cal / "auto"
    a.mkdir(parents=True, exist_ok=True)
    return a


def _saved(cal):
    s = cal / "saved"
    s.mkdir(parents=True, exist_ok=True)
    return s


class TestCleanupAutoRetention(unittest.TestCase):
    def test_keeps_latest_auto_calibrations(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            for i in range(10):
                p = auto / f"stereo_{i:04d}_000000.npz"
                p.write_bytes(b"x")
                os.utime(p, (1000 + i, 1000 + i))
            removed = cleanup_project(cal, Path(d) / "sess", runtime_root=Path(d), keep_latest=4, failed_days=7, verbose=False)
            remaining = sorted(auto.glob("stereo_*.npz"), key=lambda p: p.name)
            self.assertEqual(len(remaining), 4)
            self.assertEqual([p.name for p in remaining], [f"stereo_{i:04d}_000000.npz" for i in range(6, 10)])
            self.assertEqual(len(removed), 6)

    def test_auto_retention_touches_only_auto_area(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            saved = _saved(cal)
            for i in range(6):
                (auto / f"stereo_{i:04d}_000000.npz").write_bytes(b"x")
            (auto / "other.npz").write_bytes(b"keep")
            (auto / "readme.txt").write_text("keep")
            (saved / "pinned_old.npz").write_bytes(b"keep")
            cleanup_project(cal, Path(d) / "sess", runtime_root=Path(d), keep_latest=1, failed_days=7, verbose=False)
            self.assertTrue((auto / "other.npz").exists())
            self.assertTrue((auto / "readme.txt").exists())
            self.assertTrue((saved / "pinned_old.npz").exists())


class TestCleanupSavedProtection(unittest.TestCase):
    def test_saved_survives_regardless_of_age_and_count(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            saved = _saved(cal)
            for i in range(4):
                p = auto / f"stereo_{i:04d}_000000.npz"
                p.write_bytes(b"x")
            for i in range(8):
                p = saved / f"profile_{i:02d}.npz"
                p.write_bytes(b"keep")
                _utime_days_ago(p, 365)
            cleanup_project(cal, Path(d) / "sess", runtime_root=Path(d), keep_latest=1, failed_days=7, verbose=False)
            self.assertEqual(len(list(saved.glob("*.npz"))), 8)

    def test_imported_artifact_cannot_be_auto_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            saved = _saved(cal)
            imported = saved / "imported_2020.npz"
            imported.write_bytes(b"immutable")
            _utime_days_ago(imported, 1000)
            cleanup_project(cal, Path(d) / "sess", runtime_root=Path(d), keep_latest=1, failed_days=7, verbose=False)
            self.assertTrue(imported.exists())


class TestCleanupRootGuard(unittest.TestCase):
    def test_rejects_dirs_outside_trusted_root_without_deletion(self):
        with tempfile.TemporaryDirectory() as d:
            trusted = Path(d) / "runtime"
            trusted.mkdir()
            user_dir = Path(d) / "user"
            user_dir.mkdir()
            victim = user_dir / "stereo_9999_000000.npz"
            victim.write_bytes(b"important")

            with self.assertRaises(CleanupSafetyError):
                cleanup_project(
                    user_dir, user_dir / "sessions",
                    keep_latest=1, failed_days=7, verbose=False,
                    runtime_root=trusted,
                )
            # Nothing was deleted despite the refusal.
            self.assertTrue(victim.exists())

    def test_allows_dirs_within_trusted_root(self):
        with tempfile.TemporaryDirectory() as d:
            trusted = Path(d) / "runtime"
            cal = trusted / "calibrations"
            sess = trusted / "sessions"
            auto = _auto(cal)
            for i in range(5):
                (auto / f"stereo_{i:04d}_000000.npz").write_bytes(b"x")
            removed = cleanup_project(cal, sess, keep_latest=1, failed_days=7, verbose=False, runtime_root=trusted)
            self.assertEqual(len(removed), 4)

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            trusted = Path(d) / "runtime"
            cal = trusted / "calibrations"
            auto = _auto(cal)
            outside = Path(d) / "outside.npz"
            outside.write_bytes(b"keep")
            link = auto / "stereo_symlink_000000.npz"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks not supported on this platform")
            with self.assertRaises(CleanupSafetyError):
                cleanup_project(cal, trusted / "sessions", keep_latest=1, failed_days=7, verbose=False, runtime_root=trusted)
            self.assertTrue(outside.exists())

    def test_omitting_runtime_root_refuses_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            (auto / "stereo_0001_000000.npz").write_bytes(b"x")
            with self.assertRaises(TypeError):
                cleanup_project(cal, Path(d) / "sess", keep_latest=1, failed_days=7, verbose=False)

    def test_none_runtime_root_refuses_before_deletion(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            p = auto / "stereo_0001_000000.npz"
            p.write_bytes(b"x")
            with self.assertRaises(CleanupSafetyError):
                cleanup_project(cal, Path(d) / "sess", runtime_root=None, keep_latest=1, failed_days=7, verbose=False)
            self.assertTrue(p.exists())


class TestCleanupMassDeletionGuard(unittest.TestCase):
    def test_over_limit_cleanup_aborts_before_deleting_anything(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            for i in range(6):
                (auto / f"stereo_{i:04d}_000000.npz").write_bytes(b"x")
            with mock.patch.object(cleanup_mod, "_MAX_REMOVED_GUARD", 3):
                with self.assertRaises(CleanupSafetyError):
                    cleanup_project(cal, Path(d) / "sess", runtime_root=Path(d), keep_latest=1, failed_days=7, verbose=False)
            # Every candidate is still present: nothing was deleted before the guard fired.
            self.assertEqual(len(list(auto.glob("stereo_*.npz"))), 6)


class TestCleanupSessions(unittest.TestCase):
    def test_removes_only_old_session_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            sess = Path(d) / "sess"
            sess.mkdir()
            old = sess / "session_old"
            recent = sess / "session_recent"
            nope = sess / "not_a_session_folder"
            for folder in (old, recent, nope):
                folder.mkdir()
            _utime_days_ago(old, 30)

            cleanup_project(cal, sess, runtime_root=Path(d), keep_latest=10, failed_days=7, verbose=False)

            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(nope.exists())


if __name__ == "__main__":
    unittest.main()