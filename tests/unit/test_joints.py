"""Joint-group selection tests."""

import unittest

from stereo_pose.joints import JOINT_GROUPS, JOINT_INDEX, JOINT_NAMES, resolve_joints


class TestResolveJoints(unittest.TestCase):
    def test_default_group(self):
        self.assertEqual(resolve_joints("ergonomics"), JOINT_GROUPS["ergonomics"])

    def test_all_group_has_all_joints(self):
        self.assertEqual(resolve_joints("all"), JOINT_NAMES)

    def test_explicit_overrides_group(self):
        out = resolve_joints("ergonomics", ["left_wrist", "right_wrist"])
        self.assertEqual(out, ["left_wrist", "right_wrist"])

    def test_unknown_group_raises(self):
        with self.assertRaises(ValueError):
            resolve_joints("not-a-group")

    def test_unknown_joint_raises(self):
        with self.assertRaises(ValueError):
            resolve_joints("ergonomics", ["left_wrist", "not_a_joint"])

    def test_vocabulary_size(self):
        # COCO pose 17-keypoint vocabulary.
        self.assertEqual(len(JOINT_NAMES), 17)
        self.assertEqual(len(JOINT_INDEX), 17)


if __name__ == "__main__":
    unittest.main()