"""One Euro filter behavior and reset tests."""

import unittest

import numpy as np

from stereo_pose.filtering import JointSmoother, OneEuroVectorFilter


class TestOneEuroVectorFilter(unittest.TestCase):
    def test_first_update_passthrough(self):
        f = OneEuroVectorFilter(min_cutoff=1.2, beta=0.015, d_cutoff=1.0)
        out = f.update(np.array([10.0, 20.0, 30.0]), 0.0)
        np.testing.assert_allclose(out, [10.0, 20.0, 30.0])

    def test_smoothing_pulls_toward_input(self):
        f = OneEuroVectorFilter(min_cutoff=1.2, beta=0.015, d_cutoff=1.0)
        f.update(np.array([0.0, 0.0, 0.0]), 0.0)
        out = f.update(np.array([100.0, 0.0, 0.0]), 0.1)
        # Output is strictly between previous and current (low-pass behavior).
        self.assertTrue(0.0 < out[0] < 100.0)
        np.testing.assert_allclose(out[1:], [0.0, 0.0])

    def test_reset_restores_passthrough(self):
        f = OneEuroVectorFilter(min_cutoff=1.2, beta=0.015, d_cutoff=1.0)
        f.update(np.array([0.0, 0.0, 0.0]), 0.0)
        f.update(np.array([100.0, 0.0, 0.0]), 0.1)
        f.reset()
        out = f.update(np.array([50.0, 60.0, 70.0]), 0.2)
        np.testing.assert_allclose(out, [50.0, 60.0, 70.0])

    def test_disabled_returns_raw(self):
        s = JointSmoother(enabled=False)
        out = s.update("left_wrist", np.array([1.0, 2.0, 3.0]), 0.0)
        np.testing.assert_allclose(out, [1.0, 2.0, 3.0])


class TestJointSmoother(unittest.TestCase):
    def test_gap_reset_reinitializes_filter(self):
        s = JointSmoother(enabled=True, reset_after_s=0.6)
        s.update("j", np.array([0.0, 0.0, 0.0]), 0.0)
        s.update("j", np.array([100.0, 0.0, 0.0]), 0.1)
        # After a long gap, the filter resets and next update passes through.
        out = s.update("j", np.array([30.0, 40.0, 50.0]), 5.0)
        np.testing.assert_allclose(out, [30.0, 40.0, 50.0])

    def test_per_joint_independence(self):
        s = JointSmoother(enabled=True)
        a = s.update("a", np.array([0.0, 0.0, 0.0]), 0.0)
        b = s.update("b", np.array([10.0, 10.0, 10.0]), 0.0)
        np.testing.assert_allclose(a, [0.0, 0.0, 0.0])
        np.testing.assert_allclose(b, [10.0, 10.0, 10.0])


if __name__ == "__main__":
    unittest.main()