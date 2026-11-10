"""Stereo geometry: rectified triangulation and error metrics.

Numerical behavior is preserved from the validated v1.2 reference
(``reference/v1_2/stereo_pose/stereo.py``). The triangulated coordinate frame is
the rectified-left-camera frame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import cv2
import numpy as np

from stereo_pose.geometry.projection import RawCamera, camera_model, epipolar_axis

_REQUIRED_KEYS = ["K1", "D1", "K2", "D2", "R1", "R2", "P1", "P2"]


class StereoTriangulator:
    """Triangulate matched, rectified 2D points into metric 3D coordinates."""

    def __init__(self, calibration):
        self.path = None
        self.stereo_rms = None
        self.sample_epipolar_mean_px = None
        self.sample_epipolar_max_px = None
        self.load(calibration)

    def load(self, calibration):
        """Load calibration from an NPZ path or a mapping of matrices/metadata."""
        self.path = None if isinstance(calibration, Mapping) else Path(calibration)
        if self.path is None:
            c = calibration
        else:
            with np.load(self.path, allow_pickle=False) as archive:
                c = {key: archive[key] for key in (*_REQUIRED_KEYS, 'camera_model',
                     'image_size', 'stereo_rms', 'sample_epipolar_mean_px',
                     'sample_epipolar_max_px') if key in archive}
        missing = [k for k in _REQUIRED_KEYS if k not in c]
        if missing:
            raise ValueError(f"Calibration missing keys: {missing}")
        for k in _REQUIRED_KEYS:
            setattr(self, k, np.asarray(c[k], dtype=float))
        self.camera_model = camera_model(c)
        self.legacy_projection = 'camera_model' not in c
        self.image_size = tuple(map(int, c['image_size'])) if 'image_size' in c else None
        self.raw_left = RawCamera(self.camera_model, self.K1, self.D1, self.image_size,
                                  legacy=self.legacy_projection)
        self.raw_right = RawCamera(self.camera_model, self.K2, self.D2, self.image_size,
                                   legacy=self.legacy_projection)
        self.epipolar_axis = epipolar_axis(self.P1, self.P2)
        self.stereo_rms = float(c["stereo_rms"]) if "stereo_rms" in c else None
        self.sample_epipolar_mean_px = (
            float(c["sample_epipolar_mean_px"]) if "sample_epipolar_mean_px" in c else None
        )
        self.sample_epipolar_max_px = (
            float(c["sample_epipolar_max_px"]) if "sample_epipolar_max_px" in c else None
        )
        return self

    @staticmethod
    def _project(P, Xh):
        p = P @ Xh
        if abs(float(p[2])) < 1e-12:
            return None
        return np.array([float(p[0] / p[2]), float(p[1] / p[2])], dtype=float)

    def rectify_pair(self, left, right):
        return (self.raw_left.rectify(left, self.R1, self.P1),
                self.raw_right.rectify(right, self.R2, self.P2))

    def triangulate_with_quality(self, pt_l, pt_r):
        left, right = self.rectify_pair(pt_l, pt_r)
        ul, ur = left[0], right[0]
        if not (np.isfinite(ul).all() and np.isfinite(ur).all()):
            return None
        axis = self.epipolar_axis
        epipolar_error = abs(float(ul[axis] - ur[axis]))

        Xh = cv2.triangulatePoints(
            self.P1, self.P2,
            ul.reshape(2, 1), ur.reshape(2, 1),
        ).reshape(4)

        w = float(Xh[3])
        if abs(w) < 1e-12:
            return None

        Xh_norm = Xh / w
        xyz = Xh_norm[:3].astype(float)
        if not np.all(np.isfinite(xyz)):
            return None

        rl = self._project(self.P1, Xh_norm)
        rr = self._project(self.P2, Xh_norm)
        if rl is None or rr is None:
            return None

        err_l = float(np.linalg.norm(rl - ul))
        err_r = float(np.linalg.norm(rr - ur))
        reproj_mean = 0.5 * (err_l + err_r)
        reproj_max = max(err_l, err_r)

        return {
            "xyz_mm": xyz,
            "rectified_uv_left": ul,
            "rectified_uv_right": ur,
            "epipolar_error_px": epipolar_error,
            "reprojection_error_left_px": err_l,
            "reprojection_error_right_px": err_r,
            "reprojection_error_mean_px": reproj_mean,
            "reprojection_error_max_px": reproj_max,
        }

    def triangulate(self, pt_l, pt_r):
        q = self.triangulate_with_quality(pt_l, pt_r)
        return None if q is None else q["xyz_mm"]