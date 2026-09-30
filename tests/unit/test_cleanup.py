"""Cleanup safety-boundary tests."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from stereo_pose.persistence.cleanup import cleanup_project


def _utime_days_ago(p, days):
    t = time.time() - days * 86400
    os.utime(p, (t, t))


class TestCleanupSafety(unittest.TestCase):
    def test_keeps_latest_calibrations(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            cal.mkdir()
            for i in range(10):
                p = cal / f"stereo_{i:04d}_000000.npz"
                p.write_bytes(b"x")
                _utime_days_ago(p, 0)
                os.utime(p, (1000 + i, 1000 + i))
            sess = Path(d) / "sess"
            removed = cleanup_project(cal, sess, keep_latest=4, failed_days=7, verbose=False)
            remaining = sorted(cal.glob("stereo_*.npz"), key=lambda p: p.name)
            self.assertEqual(len(remaining), 4)
            # The 4 newest (i=6..9) survive.
            self.assertEqual([p.name for p in remaining], [f"stereo_{i:04d}_000000.npz" for i in range(6, 10)])
            self.assertEqual(len(removed), 6)

    def test_does_not_touch_other_files_in_managed_dir(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            cal.mkdir()
            for i in range(6):
                (cal / f"stereo_{i:04d}_000000.npz").write_bytes(b"x")
            (cal / "other.npz").write_bytes(b"keep")
            (cal / "readme.txt").write_text("keep")
            sess = Path(d) / "sess"
            cleanup_project(cal, sess, keep_latest=1, failed_days=7, verbose=False)
            self.assertTrue((cal / "other.npz").exists())
            self.assertTrue((cal / "readme.txt").exists())

    def test_does_not_touch_outside_roots(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cal = root / "cal"
            cal.mkdir()
            sess = root / "sess"
            sess.mkdir()
            outside_cal = root / "outside" / "stereo_9999_000000.npz"
            outside_cal.parent.mkdir()
            outside_cal.write_bytes(b"keep")
            outside_sess = root / "outside" / "session_old"
            outside_sess.mkdir()
            (cal / "stereo_9999_000000.npz").write_bytes(b"x")
            (sess / "session_old").mkdir()
            _utime_days_ago(sess / "session_old", 30)

            cleanup_project(cal, sess, keep_latest=1, failed_days=7, verbose=False)

            self.assertTrue(outside_cal.exists())
            self.assertTrue(outside_sess.exists())

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

            cleanup_project(cal, sess, keep_latest=10, failed_days=7, verbose=False)

            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(nope.exists())


if __name__ == "__main__":
    unittest.main()