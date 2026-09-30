"""Calibration newest-file selection tests."""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from stereo_pose.calibration.selection import newest_calibration


def _write_npz(path, tag):
    np.savez(str(path), tag=np.array(tag))


class TestNewestCalibration(unittest.TestCase):
    def test_selects_newest_by_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            cal_dir = Path(d) / "cal"
            cal_dir.mkdir()
            paths = [cal_dir / f"stereo_{i:04d}_000000.npz" for i in range(3)]
            for i, p in enumerate(paths):
                _write_npz(p, i)
                # set distinct mtimes, last created = newest
                os.utime(p, (1000 + i, 1000 + i))
            newest = newest_calibration(cal_dir)
            self.assertEqual(newest.resolve(), paths[-1].resolve())

    def test_explicit_file_returned_and_must_exist(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "custom.npz"
            _write_npz(p, 1)
            self.assertEqual(newest_calibration(Path(d), explicit_file=p).resolve(), p.resolve())

            missing = Path(d) / "missing.npz"
            with self.assertRaises(FileNotFoundError):
                newest_calibration(Path(d), explicit_file=missing)

    def test_ignores_non_versioned_files(self):
        with tempfile.TemporaryDirectory() as d:
            cal_dir = Path(d) / "cal"
            cal_dir.mkdir()
            _write_npz(cal_dir / "stereo_20260101_000000.npz", 1)
            (cal_dir / "other.npz").write_bytes(b"x")
            (cal_dir / "notes.txt").write_text("hi")
            newest = newest_calibration(cal_dir)
            self.assertEqual(newest.name, "stereo_20260101_000000.npz")


if __name__ == "__main__":
    unittest.main()