"""Package import smoke tests (offline — no cameras, no CUDA, no weights)."""

import unittest


class TestPackageImports(unittest.TestCase):
    def test_import_package(self):
        import stereo_pose

        self.assertTrue(hasattr(stereo_pose, "__version__"))
        self.assertEqual(stereo_pose.V1_SCHEMA, "stereo_pose_3d/v1.2")

    def test_import_submodules(self):
        from stereo_pose import (
            calibration,
            capture,
            config,
            coordinates,
            filtering,
            geometry,
            models,
            outputs,
            persistence,
            quality,
        )

        self.assertTrue(all([calibration, capture, config, coordinates,
                             filtering, geometry, models, outputs, persistence, quality]))

    def test_import_does_not_pull_torch_or_ultralytics(self):
        import sys

        import stereo_pose  # noqa: F401
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("ultralytics", sys.modules)


if __name__ == "__main__":
    unittest.main()