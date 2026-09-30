"""Offline doctor command tests."""

import io
import json
import unittest
from contextlib import redirect_stdout

from stereo_pose.config import load_config
from stereo_pose.diagnostics.doctor import main as doctor_main, run_doctor


class TestDoctor(unittest.TestCase):
    def test_run_doctor_report_structure(self):
        info = run_doctor(load_config(None))
        for key in ("python_version", "opencv_version", "numpy_version", "torch",
                    "pose_model", "calibration_dir", "config_status", "runtime_writable"):
            self.assertIn(key, info)
        self.assertEqual(info["config_status"], "valid")

    def test_doctor_main_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = doctor_main(["--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("python_version", data)

    def test_doctor_main_plain(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = doctor_main([])
        self.assertEqual(rc, 0)
        self.assertIn("Stereo Pose doctor", buf.getvalue())


if __name__ == "__main__":
    unittest.main()