"""Rigid coordinate-transform scaffold tests."""

import unittest

import numpy as np

from stereo_pose.coordinates import RigidTransform


class TestRigidTransform(unittest.TestCase):
    def test_translation_only(self):
        t = RigidTransform(np.eye(3), np.array([1.0, 2.0, 3.0]))
        pts = np.array([[0.0, 0.0, 0.0], [10.0, -5.0, 2.0]])
        out = t.apply(pts)
        np.testing.assert_allclose(out, pts + [1.0, 2.0, 3.0])

    def test_rotation(self):
        theta = np.pi / 2
        R = np.array([
            [np.cos(theta), -np.sin(theta), 0],
            [np.sin(theta), np.cos(theta), 0],
            [0, 0, 1],
        ])
        t = RigidTransform(R, np.zeros(3))
        out = t.apply(np.array([[1.0, 0.0, 0.0]]))
        np.testing.assert_allclose(out, [[0.0, 1.0, 0.0]], atol=1e-12)

    def test_inverse_round_trip(self):
        R = np.array([
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        t = RigidTransform(R, np.array([3.0, -2.0, 7.0]))
        pts = np.array([[1.0, 2.0, 3.0], [-4.0, 5.0, 6.0]])
        back = t.inverse().apply(t.apply(pts))
        np.testing.assert_allclose(back, pts, atol=1e-12)

    def test_compose(self):
        a = RigidTransform(np.eye(3), np.array([1.0, 0.0, 0.0]))
        b = RigidTransform(np.eye(3), np.array([0.0, 2.0, 0.0]))
        c = a.compose(b)  # a after b
        out = c.apply(np.array([[0.0, 0.0, 0.0]]))
        np.testing.assert_allclose(out, [[1.0, 2.0, 0.0]])

    def test_as_matrix(self):
        t = RigidTransform(np.eye(3), np.array([1.0, 2.0, 3.0]))
        M = t.as_matrix()
        self.assertEqual(M.shape, (4, 4))
        np.testing.assert_allclose(M[:3, 3], [1.0, 2.0, 3.0])

    def test_rejects_bad_shapes(self):
        with self.assertRaises(ValueError):
            RigidTransform(np.eye(4), np.zeros(3))
        with self.assertRaises(ValueError):
            RigidTransform(np.eye(3), np.zeros(4))


if __name__ == "__main__":
    unittest.main()