"""Promotion-to-saved-library tests."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from stereo_pose.persistence import (
    auto_dir,
    cleanup_project,
    library_meta_path,
    promote_calibration,
    saved_dir,
)


def _write_npz(path):
    np.savez(str(path), K1=np.eye(3), _schema_version=np.array("1"))


class TestPromoteCalibration(unittest.TestCase):
    def test_promote_copies_without_losing_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = auto_dir(cal)
            auto.mkdir(parents=True, exist_ok=True)
            src = auto / "stereo_20260101_000000.npz"
            _write_npz(src)

            dest = promote_calibration(src, cal, name="position A", notes="left rig", source="auto")

            self.assertEqual(dest.read_bytes(), src.read_bytes())
            meta = json.loads(library_meta_path(dest).read_text(encoding="utf-8"))
            self.assertEqual(meta["name"], "position A")
            self.assertEqual(meta["source"], "auto")
            self.assertEqual(meta["notes"], "left rig")
            self.assertEqual(meta["sha256"], hashlib.sha256(src.read_bytes()).hexdigest())

    def test_pinned_artifact_survives_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            auto = auto_dir(cal)
            auto.mkdir(parents=True, exist_ok=True)
            src = auto / "stereo_20260101_000000.npz"
            _write_npz(src)
            dest = promote_calibration(src, cal, name="pinned", source="auto")

            # Add several auto artifacts so retention would prune aggressively.
            for i in range(6):
                _write_npz(auto / f"stereo_{i:04d}_000000.npz")

            cleanup_project(cal, Path(d) / "sess", keep_latest=1, failed_days=7, verbose=False)

            self.assertTrue(dest.exists())
            self.assertTrue(library_meta_path(dest).exists())

    def test_promote_generated_artifact_persists_and_is_not_auto_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            src = Path(d) / "fresh.npz"
            _write_npz(src)
            dest = promote_calibration(src, cal, source="promoted")
            cleanup_project(cal, Path(d) / "sess", keep_latest=1, failed_days=7, verbose=False)
            self.assertTrue(dest.exists())

    def test_promote_never_overwrites_existing_pin(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal"
            src = Path(d) / "a.npz"
            _write_npz(src)
            first = promote_calibration(src, cal, name="mypin")
            second = promote_calibration(src, cal, name="mypin")
            self.assertNotEqual(first.resolve(), second.resolve())
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_promote_missing_source_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                promote_calibration(Path(d) / "nope.npz", Path(d) / "cal")


if __name__ == "__main__":
    unittest.main()