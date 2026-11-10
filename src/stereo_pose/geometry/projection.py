"""Raw sensor pixels, camera rays and rectified pixels for each NPZ model."""
from __future__ import annotations

import cv2
import numpy as np
from numpy.polynomial import Polynomial

CAMERA_MODELS = ('pinhole', 'rational', 'fisheye')
MODEL_LABELS = dict(zip(CAMERA_MODELS, ('普通针孔', '扩展针孔', '鱼眼')))
INVERSE_TOLERANCE_PX = 0.1


def camera_model(bundle):
    model = str(np.asarray(bundle.get('camera_model', 'pinhole')).item())
    if model not in CAMERA_MODELS:
        raise ValueError(f'unsupported camera_model: {model}')
    return model


def validate_distortion(model, distortion):
    d = np.asarray(distortion, dtype=float)
    sizes = {'pinhole': (4, 5, 8, 12, 14), 'rational': (8, 12, 14), 'fisheye': (4,)}
    if (d.size not in sizes[model] or d.ndim not in (1, 2) or
            (d.ndim == 2 and 1 not in d.shape) or not np.isfinite(d).all()):
        raise ValueError(f'invalid distortion vector for camera_model={model}')
    return d


def project_points(model, xyz, K, D, rvec=None, tvec=None):
    project = cv2.fisheye.projectPoints if model == 'fisheye' else cv2.projectPoints
    rvec = np.zeros(3) if rvec is None else rvec
    tvec = np.zeros(3) if tvec is None else tvec
    uv, _ = project(np.asarray(xyz, dtype=np.float64).reshape(-1, 1, 3),
                    np.asarray(rvec, dtype=float).reshape(3, 1),
                    np.asarray(tvec, dtype=float).reshape(3, 1), K, D)
    return uv.reshape(-1, 2)


def radial_domain(model, distortion):
    """Central monotonic branch, ending at the first fold or rational pole."""
    d = np.pad(np.asarray(distortion).ravel(), (0, max(0, 8 - np.size(distortion))))
    if model == 'fisheye':
        derivative = Polynomial([1, 3*d[0], 5*d[1], 7*d[2], 9*d[3]])
        polynomials = (derivative,)
        limit = np.pi / 2
    else:
        n = Polynomial([1, d[0], d[1], d[4]])
        den = Polynomial([1, *d[5:8]])
        s = Polynomial([0, 1])
        derivative = (n + 2*s*n.deriv())*den - 2*s*n*den.deriv()
        polynomials = (derivative, den)
        limit = np.inf
    roots = [r.real for p in polynomials for r in p.roots()
             if abs(r.imag) < 1e-8 and r.real > 0]
    if roots:
        limit = min(limit, np.sqrt(min(roots)))
    return float(limit)


class RawCamera:
    def __init__(self, model, K, D, image_size=None, *, legacy=False):
        self.model = model
        self.K = np.asarray(K, dtype=float)
        self.D = validate_distortion(model, D)
        self.limit = radial_domain(model, self.D)
        self.size = image_size
        self.legacy = legacy

    def inverse(self, uv):
        """Return normalized rays and forward round-trip residuals in raw px.

        Invalid inverse results are NaN. OpenCV can return finite sentinels
        or a plausible-looking pixel when the inverse did not converge.
        """
        uv = np.asarray(uv, dtype=float).reshape(-1, 2)
        rays = np.full_like(uv, np.nan)
        residual = np.full(len(uv), np.nan)
        valid = np.isfinite(uv).all(axis=1)
        if self.size is not None:
            valid &= np.all((uv >= 0) & (uv <= np.asarray(self.size) - 1), axis=1)
        if not np.any(valid):
            return rays, residual
        points = uv[valid].reshape(-1, 1, 2)
        if self.model == 'fisheye':
            xy = cv2.fisheye.undistortPoints(points, self.K, self.D).reshape(-1, 2)
        elif self.legacy:
            xy = cv2.undistortPoints(points, self.K, self.D).reshape(-1, 2)
        else:
            xy = self._iterate(points)
        errors = self._inverse_errors(xy, uv[valid])
        if self.legacy and np.any(errors > INVERSE_TOLERANCE_PX):
            retry = errors > INVERSE_TOLERANCE_PX
            xy[retry] = self._iterate(points[retry])
            errors[retry] = self._inverse_errors(xy[retry], uv[valid][retry])
        radius = np.linalg.norm(xy, axis=1)
        if self.model == 'fisheye':
            radius = np.arctan(radius)
        good = (np.isfinite(xy).all(axis=1) & np.isfinite(errors) &
                (errors <= INVERSE_TOLERANCE_PX) & (radius < self.limit))
        # Forward round-trip alone cannot identify locally folded mappings
        # from tangential/thin-prism/tilt terms, or near-singular inverse rays.
        if np.any(good):
            good[good] = self._positive_jacobian(xy[good])
        indices = np.flatnonzero(valid)
        rays[indices[good]] = xy[good]
        residual[indices] = errors
        return rays, residual

    def _positive_jacobian(self, xy):
        step = 1e-5
        offsets = step * np.array([[1., 0.], [-1., 0.], [0., 1.], [0., -1.]])
        samples = (xy[None, :, :] + offsets[:, None, :]).reshape(-1, 2)
        uv = project_points(self.model, np.c_[samples, np.ones(len(samples))], self.K, self.D)
        xp, xm, yp, ym = uv.reshape(4, len(xy), 2)
        dx, dy = (xp - xm) / (2 * step), (yp - ym) / (2 * step)
        determinant = (dx[:, 0] * dy[:, 1] - dx[:, 1] * dy[:, 0]) / (self.K[0, 0] * self.K[1, 1])
        return np.isfinite(determinant) & (determinant > 1e-6)

    def _iterate(self, points):
        criteria = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-9)
        return cv2.undistortPointsIter(points, self.K, self.D, None, None, criteria).reshape(-1, 2)

    def _inverse_errors(self, xy, uv):
        forward = project_points(self.model, np.c_[xy, np.ones(len(xy))], self.K, self.D)
        return np.linalg.norm(forward - uv, axis=1)

    def rectify(self, uv, R, P):
        rays, _ = self.inverse(uv)
        rotated = np.c_[rays, np.ones(len(rays))] @ np.asarray(R).T
        # A virtual perspective camera only represents its forward hemisphere.
        good = rotated[:, 2] > 1e-12
        pixels = np.full_like(rays, np.nan)
        projected = rotated[good] @ np.asarray(P)[:, :3].T
        pixels[good] = projected[:, :2] / projected[:, 2:3]
        return pixels


def epipolar_axis(P1, P2):
    """Return the constrained coordinate index (y for a horizontal baseline)."""
    t = np.linalg.solve(P2[:, :3], P2[:, 3]) - np.linalg.solve(P1[:, :3], P1[:, 3])
    return 1 - int(np.argmax(np.abs(t[:2])))


def rectify_stereo(bundle, image_size, framing):
    if framing not in (0, 1):
        raise ValueError('rectification framing must be 0 (crop) or 1 (wide)')
    args = [bundle[k] for k in ('K1', 'D1', 'K2', 'D2')]
    args.extend((tuple(image_size), bundle['R'], bundle['T']))
    if camera_model(bundle) == 'fisheye':
        values = cv2.fisheye.stereoRectify(*args, flags=cv2.CALIB_ZERO_DISPARITY,
                                          balance=float(framing), fov_scale=1.0)
        rois = (None, None)
    else:
        *values, roi1, roi2 = cv2.stereoRectify(*args, alpha=float(framing))
        rois = (list(roi1), list(roi2))
    return dict(zip(('R1', 'R2', 'P1', 'P2', 'Q'), values)), rois


def rectification_maps(model, K, D, R, P, image_size):
    init = (cv2.fisheye.initUndistortRectifyMap if model == 'fisheye'
            else cv2.initUndistortRectifyMap)
    return init(K, D, R, P, tuple(image_size), cv2.CV_32FC1)
