"""Metric default frame: synthetic camera rigs, no owner data or hardware."""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from stereo_pose.calibration.package import (
    load_readout_registration, read_bundle, save_registered,
)
from stereo_pose.coordinates.camera_midpoint import camera_midpoint_registration
from stereo_pose.coordinates.rigid import RigidTransform
from tests.unit.test_world_alignment import synthetic_calibration


class TestCameraMidpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = synthetic_calibration(self.root / 'stereo.npz')
        self.bundle = read_bundle(self.path)

    def test_midpoint_camera_centers_and_axis_signs_in_mm(self):
        reg = camera_midpoint_registration(self.bundle)
        transform = reg['transform']
        points = [[150, 0, 0], [0, 0, 0], [300, 0, 0],
                  [150, 0, 1000], [50, 0, 0], [150, -100, 0]]
        expected = [[0, 0, 0], [0, 150, 0], [0, -150, 0],
                    [1000, 0, 0], [0, 100, 0], [0, 0, 100]]
        np.testing.assert_allclose(transform.apply(points), expected, atol=1e-10)
        np.testing.assert_allclose(transform.inverse().apply(expected), points, atol=1e-10)
        self.assertAlmostEqual(np.linalg.det(transform.R), 1)
        np.testing.assert_allclose(transform.R.T @ transform.R, np.eye(3), atol=1e-12)
        self.assertEqual(reg['metadata']['mode'], 'camera_midpoint')
        self.assertFalse(reg['metadata']['up_confirmed'])
        self.assertEqual(reg['metadata']['up_reference'], 'camera_mount_assumption')

    def test_toed_in_cameras_use_rectified_centers_not_half_raw_T(self):
        # Both optical centers are level in the rig frame; cameras toe inward.
        theta = np.deg2rad(12)
        left_to_rig = cv2.Rodrigues(np.array([0., theta, 0.]))[0]
        right_to_rig = cv2.Rodrigues(np.array([0., -theta, 0.]))[0]
        right_center = np.array([420., 0., 0.])
        R = right_to_rig.T @ left_to_rig
        T = right_to_rig.T @ -right_center
        K = self.bundle['K1']
        R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
            K, np.zeros(5), K, np.zeros(5), (1280, 720), R, T.reshape(3, 1))
        self.bundle.update(R=R, T=T, R1=R1, R2=R2, P1=P1, P2=P2, Q=Q)
        reg = camera_midpoint_registration(self.bundle)
        rig_points = np.array([[210, 0, 0], [210, 0, 1500],
                               [110, 0, 1500], [210, -100, 1500]])
        camera_points = rig_points @ left_to_rig @ R1.T
        np.testing.assert_allclose(reg['transform'].apply(camera_points),
            [[0, 0, 0], [1500, 0, 0], [1500, 100, 0], [1500, 0, 100]], atol=1e-8)
        self.assertAlmostEqual(reg['metadata']['baseline_mm'], 420.)

    def test_legacy_projection_only_bundle_retains_mount_assumption(self):
        self.bundle.pop('R')
        self.bundle.pop('T')
        reg = camera_midpoint_registration(self.bundle)
        self.assertAlmostEqual(reg['metadata']['baseline_mm'], 300)
        # A common physical tilt cannot be discovered from relative geometry.
        self.assertIn('level', reg['metadata']['mount_assumption'])
        self.assertIn('upright', reg['metadata']['mount_assumption'])

    def test_invalid_or_ambiguous_geometry_rejected(self):
        cases = []
        b = dict(self.bundle); b['P2'] = b['P1'].copy(); cases.append(b)
        b = dict(self.bundle); b['P1'] = np.zeros((3, 4)); cases.append(b)
        b = dict(self.bundle); b['R1'] = np.eye(3) * 2; cases.append(b)
        b = dict(self.bundle); b['P2'] = np.full((3, 4), np.nan); cases.append(b)
        b = dict(self.bundle); b['P2'] = b['P2'].copy(); b['P2'][0, 3] *= -1; cases.append(b)
        b = dict(self.bundle); b['P2'] = b['P1'].copy(); b['P2'][1, 3] = -900 * 300; cases.append(b)
        for b in cases:
            with self.subTest(P2=b['P2']), self.assertRaises(ValueError):
                camera_midpoint_registration(b)

    def test_saved_world_precedes_default_and_source_npz_unchanged(self):
        before = self.path.read_bytes()
        reg, warnings = load_readout_registration(self.path, (1280, 720))
        self.assertFalse(warnings)
        self.assertEqual(reg['metadata']['mode'], 'camera_midpoint')
        self.assertEqual(self.path.read_bytes(), before)
        saved = save_registered(self.path, {
            'name': 'OWNER WORLD', 'transform': RigidTransform(np.eye(3), [1, 2, 3]),
            'metadata': {'mode': 'world', 'up_confirmed': True},
        }, self.root / 'cal', self.root)
        reg, warnings = load_readout_registration(saved, (1280, 720))
        self.assertEqual(reg['name'], 'OWNER WORLD')
        self.assertFalse(warnings)
        np.testing.assert_allclose(reg['transform'].t, [1, 2, 3])

    def test_stale_world_warns_and_uses_explicitly_named_default(self):
        self.bundle['world_R'] = np.eye(3)  # Incomplete W is never accepted.
        np.savez(self.path, **self.bundle)
        reg, warnings = load_readout_registration(self.path, (1280, 720))
        self.assertEqual(reg['metadata']['mode'], 'camera_midpoint')
        self.assertTrue(any('WORLD INVALID' in x for x in warnings))

    def test_wrong_resolution_disables_default(self):
        reg, warnings = load_readout_registration(self.path, (640, 480))
        self.assertIsNone(reg)
        self.assertTrue(warnings)
