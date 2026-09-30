"""Camera open-parameter (FOURCC / buffer) tests."""

import unittest

from stereo_pose.capture.camera import _fourcc_code


class TestFourcc(unittest.TestCase):
    def test_valid_fourcc_returns_int(self):
        self.assertIsInstance(_fourcc_code("MJPG"), int)
        self.assertIsInstance(_fourcc_code("YUYV"), int)

    def test_none_returns_none(self):
        self.assertIsNone(_fourcc_code(None))

    def test_invalid_length_raises(self):
        with self.assertRaises(ValueError):
            _fourcc_code("MJ")
        with self.assertRaises(ValueError):
            _fourcc_code("TOOLONG")

    def test_non_ascii_raises(self):
        with self.assertRaises(ValueError):
            _fourcc_code("MJ\u00a7G")


if __name__ == "__main__":
    unittest.main()