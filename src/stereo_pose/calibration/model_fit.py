"""Fit the selected OpenCV model to already matched stereo observations."""
from __future__ import annotations

import cv2
import numpy as np

from stereo_pose.geometry.projection import rectify_stereo


_FISH_FLAGS = (cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC | cv2.fisheye.CALIB_CHECK_COND |
               cv2.fisheye.CALIB_FIX_SKEW)
_CRITERIA = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 80, 1e-6)


def fit_fisheye_intrinsics(objects, image_points, image_size):
    objects = [np.asarray(obj, dtype=float).reshape(-1, 1, 3) for obj in objects]
    image_points = [np.asarray(uv, dtype=float).reshape(-1, 1, 2) for uv in image_points]
    rms, K, D, _, _ = cv2.fisheye.calibrate(objects, image_points, image_size, None, None,
                                            flags=_FISH_FLAGS, criteria=_CRITERIA)
    return rms, K, D


def _measurement_matrices(bundle, image_size, framing):
    matrices, _ = rectify_stereo(bundle, image_size, framing)
    if str(bundle['camera_model'].item()) == 'pinhole':
        return matrices
    # Wide-angle stereoRectify can produce a very small virtual focal or an
    # off-screen principal point. Keep alternate-model quality pixels at
    # least as fine as native sensor pixels near the optical axis.
    P1, P2 = matrices['P1'], matrices['P2']
    focal = P1[0, 0]
    if not np.isfinite(focal) or focal <= 0:
        raise ValueError('rectification returned a non-positive virtual focal length')
    native_focal = max(max(K[0, 0], K[1, 1]) for K in (bundle['K1'], bundle['K2']))
    scale = max(1., native_focal / focal)
    translation = (np.asarray(image_size) - 1) / 2 - scale * P1[:2, 2]
    change = np.array([[scale, 0., translation[0]], [0., scale, translation[1]], [0., 0., 1.]])
    matrices['P1'], matrices['P2'] = change @ P1, change @ P2
    # Q consumes [u, v, disparity, 1]. Undo the shared image transform
    # before the original reprojection; disparity has scale but no offset.
    undo = np.diag([1/scale, 1/scale, 1/scale, 1.])
    undo[:2, 3] = -translation / scale
    matrices['Q'] = matrices['Q'] @ undo
    return matrices


def fit_model(model, objpoints, left, right, image_size, framing=0):
    if model == 'fisheye':
        objpoints = [np.asarray(obj, dtype=float).reshape(-1, 1, 3) for obj in objpoints]
        left, right = ([np.asarray(uv, dtype=float).reshape(-1, 1, 2) for uv in side]
                       for side in (left, right))
        rms_l, K1, D1 = fit_fisheye_intrinsics(objpoints, left, image_size)
        rms_r, K2, D2 = fit_fisheye_intrinsics(objpoints, right, image_size)
        rms, K1, D1, K2, D2, R, T, *_ = cv2.fisheye.stereoCalibrate(
            objpoints, left, right, K1, D1, K2, D2, image_size,
            flags=cv2.fisheye.CALIB_FIX_INTRINSIC, criteria=_CRITERIA)
        x, y, z = T.ravel()
        E = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]]) @ R
        F = np.linalg.solve(K2.T, E) @ np.linalg.inv(K1)
    else:
        mono_flags = cv2.CALIB_RATIONAL_MODEL if model == 'rational' else 0
        rms_l, K1, D1, _, _ = cv2.calibrateCamera(
            objpoints, left, image_size, None, None, flags=mono_flags)
        rms_r, K2, D2, _, _ = cv2.calibrateCamera(
            objpoints, right, image_size, None, None, flags=mono_flags)
        rms, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
            objpoints, left, right, K1, D1, K2, D2, image_size, criteria=_CRITERIA,
            flags=cv2.CALIB_FIX_INTRINSIC | mono_flags)
    bundle = dict(camera_model=np.array(model), K1=K1, D1=D1, K2=K2, D2=D2,
                  R=R, T=T, E=E, F=F, left_rms=rms_l, right_rms=rms_r, stereo_rms=rms)
    if (not all(np.isfinite(value).all() for key, value in bundle.items() if key != 'camera_model')
            or np.linalg.norm(T) < 1e-6):
        raise ValueError(f'{model}: non-finite fit or degenerate stereo baseline')
    bundle.update(_measurement_matrices(bundle, image_size, framing))
    return bundle
