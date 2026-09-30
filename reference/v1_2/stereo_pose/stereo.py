from pathlib import Path
import cv2
import numpy as np


class StereoTriangulator:
    def __init__(self, calibration_file):
        self.load(calibration_file)

    def load(self, calibration_file):
        self.path = Path(calibration_file)
        c = np.load(self.path, allow_pickle=False)
        required = ["K1", "D1", "K2", "D2", "R1", "R2", "P1", "P2"]
        missing = [k for k in required if k not in c]
        if missing:
            raise ValueError(f"Calibration file missing keys: {missing}")
        for k in required:
            setattr(self, k, c[k])
        self.stereo_rms = float(c["stereo_rms"]) if "stereo_rms" in c else None
        self.sample_epipolar_mean_px = (
            float(c["sample_epipolar_mean_px"]) if "sample_epipolar_mean_px" in c else None
        )
        self.sample_epipolar_max_px = (
            float(c["sample_epipolar_max_px"]) if "sample_epipolar_max_px" in c else None
        )

    @staticmethod
    def _project(P, Xh):
        p = P @ Xh
        if abs(float(p[2])) < 1e-12:
            return None
        return np.array([float(p[0] / p[2]), float(p[1] / p[2])], dtype=float)

    def triangulate_with_quality(self, pt_l, pt_r):
        pl = np.asarray(pt_l, np.float64).reshape(1, 1, 2)
        pr = np.asarray(pt_r, np.float64).reshape(1, 1, 2)

        ul = cv2.undistortPoints(pl, self.K1, self.D1, R=self.R1, P=self.P1).reshape(2)
        ur = cv2.undistortPoints(pr, self.K2, self.D2, R=self.R2, P=self.P2).reshape(2)

        epipolar_error = abs(float(ul[1] - ur[1]))

        Xh = cv2.triangulatePoints(
            self.P1, self.P2,
            ul.reshape(2, 1), ur.reshape(2, 1)
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


def newest_calibration(calibration_dir, explicit_file=None):
    if explicit_file:
        p = Path(explicit_file)
        if not p.exists():
            raise FileNotFoundError(f"Explicit calibration file not found: {p}")
        return p

    d = Path(calibration_dir)
    d.mkdir(parents=True, exist_ok=True)
    files = list(d.glob("stereo_*.npz"))
    if files:
        return max(files, key=lambda p: p.stat().st_mtime)

    legacy = Path("stereo_calib.npz")
    if legacy.exists():
        return legacy

    raise FileNotFoundError(
        f"No calibration found in {d}; press C at runtime to create one."
    )
