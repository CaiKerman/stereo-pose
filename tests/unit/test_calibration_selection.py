"""Calibration newest-file selection tests (auto/ vs saved/ layout)."""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from stereo_pose.calibration.selection import newest_calibration
from stereo_pose.persistence import auto_dir, saved_dir


def _write_npz(path, tag):
    np.savez(str(path), tag=np.array(tag))


def _auto(cal):
    a = auto_dir(cal)
    a.mkdir(parents=True, exist_ok=True)
    return a


def _saved(cal):
    s = saved_dir(cal)
    s.mkdir(parents=True, exist_ok=True)
    return s


class TestNewestCalibration(unittest.TestCase):
    def test_selects_newest_in_auto_by_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            paths = [auto / f"stereo_{i:04d}_000000.npz" for i in range(3)]
            for i, p in enumerate(paths):
                _write_npz(p, i)
                os.utime(p, (1000 + i, 1000 + i))
            newest = newest_calibration(cal)
            self.assertEqual(newest.resolve(), paths[-1].resolve())

    def test_default_ignores_saved_library(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            saved = _saved(cal)
            auto_p = auto / "stereo_0001_000000.npz"
            saved_p = saved / "pinned.npz"
            _write_npz(auto_p, 1)
            _write_npz(saved_p, 2)
            os.utime(saved_p, (999999, 999999))  # saved is newer
            self.assertEqual(newest_calibration(cal).resolve(), auto_p.resolve())

    def test_auto_beats_newer_legacy_flat_file(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            auto_p = auto / "stereo_0001_000000.npz"
            legacy_p = cal / "stereo_9999_000000.npz"
            _write_npz(auto_p, 1)
            _write_npz(legacy_p, 2)
            os.utime(auto_p, (1000, 1000))
            os.utime(legacy_p, (999999, 999999))  # legacy flat file is newer
            self.assertEqual(newest_calibration(cal).resolve(), auto_p.resolve())

    def test_explicit_file_selects_saved_profile(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            saved = _saved(cal)
            p = saved / "custom_profile.npz"
            _write_npz(p, 1)
            self.assertEqual(newest_calibration(cal, explicit_file=p).resolve(), p.resolve())

    def test_explicit_file_must_exist(self):
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "missing.npz"
            with self.assertRaises(FileNotFoundError):
                newest_calibration(Path(d), explicit_file=missing)

    def test_legacy_flat_files_still_found(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            cal.mkdir()
            p = cal / "stereo_20260101_000000.npz"
            _write_npz(p, 1)
            self.assertEqual(newest_calibration(cal).name, "stereo_20260101_000000.npz")

    def test_ignores_non_versioned_files(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = _auto(cal)
            _write_npz(auto / "stereo_20260101_000000.npz", 1)
            (auto / "other.npz").write_bytes(b"x")
            (auto / "notes.txt").write_text("hi")
            newest = newest_calibration(cal)
            self.assertEqual(newest.name, "stereo_20260101_000000.npz")


if __name__ == "__main__":
    unittest.main()