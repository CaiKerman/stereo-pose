"""Configuration merge and validation tests."""

import json
import tempfile
import unittest
from pathlib import Path

from stereo_pose.config import ConfigError, deep_merge, load_config, validate_config


class TestDeepMerge(unittest.TestCase):
    def test_override_scalar(self):
        base = {"a": 1, "nested": {"x": 1, "y": 2}}
        out = deep_merge(base, {"a": 2})
        self.assertEqual(out["a"], 2)
        self.assertEqual(out["nested"]["y"], 2)
        self.assertEqual(base["a"], 1)  # base untouched

    def test_override_nested_dict(self):
        base = {"nested": {"x": 1, "y": 2}}
        out = deep_merge(base, {"nested": {"y": 9}})
        self.assertEqual(out["nested"]["x"], 1)
        self.assertEqual(out["nested"]["y"], 9)


class TestValidateConfig(unittest.TestCase):
    def test_defaults_valid(self):
        validate_config(load_config(None))

    def test_missing_section_raises(self):
        cfg = load_config(None)
        del cfg["quality"]
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_bad_backend_raises(self):
        cfg = load_config(None)
        cfg["camera"]["backend"] = "not-a-backend"
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_negative_width_raises(self):
        cfg = load_config(None)
        cfg["camera"]["width"] = -1
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_depth_ordering_raises(self):
        cfg = load_config(None)
        cfg["quality"]["min_depth_mm"] = 9000.0
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_invalid_load_mode_raises(self):
        cfg = load_config(None)
        cfg["stereo"]["load"] = "newest"
        with self.assertRaises(ConfigError):
            validate_config(cfg)

    def test_aggregated_messages(self):
        cfg = load_config(None)
        cfg["camera"]["backend"] = "bad"
        cfg["pose"]["detection_confidence"] = 2.0
        with self.assertRaises(ConfigError) as ctx:
            validate_config(cfg)
        self.assertIn("camera.backend", str(ctx.exception))
        self.assertIn("pose.detection_confidence", str(ctx.exception))


class TestLoadConfig(unittest.TestCase):
    def test_load_partial_file_merges(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cfg.json"
            p.write_text(json.dumps({"camera": {"width": 640, "height": 480}}))
            cfg = load_config(p)
            self.assertEqual(cfg["camera"]["width"], 640)
            self.assertEqual(cfg["camera"]["height"], 480)
            self.assertEqual(cfg["camera"]["left"], 0)  # from defaults

    def test_load_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                load_config(Path(d) / "nope.json")


if __name__ == "__main__":
    unittest.main()