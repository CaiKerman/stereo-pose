"""Default metric rig frame derived from the owning rectified stereo geometry.

The origin is the midpoint of the optical centers, +Y points right -> left,
+X points forward and +Z points up assuming a level, upright camera rig.
Relative stereo geometry does not observe gravity or a common rig pitch/roll.
An owner-confirmed world registration remains necessary for physical world-up.
"""
from __future__ import annotations

import numpy as np

from stereo_pose.coordinates.rigid import RigidTransform


def _camera_center(projection):
    """P [c, 1] = 0; centers share the same frame as triangulated points."""
    P = np.asarray(projection, dtype=float)
    if P.shape != (3, 4) or not np.all(np.isfinite(P)):
        raise ValueError('finite 3x4 stereo projection matrices required')
    try:
        center = np.linalg.solve(P[:, :3], -P[:, 3])
    except np.linalg.LinAlgError as e:
        raise ValueError('singular stereo projection matrix') from e
    if not np.all(np.isfinite(center)):
        raise ValueError('nonfinite camera center')
    return center


def _unit(vector, description):
    length = float(np.linalg.norm(vector))
    if not np.isfinite(length) or length < 1e-6:
        raise ValueError(f'cannot define {description}; check stereo rig and use W alignment')
    return vector / length


def camera_midpoint_registration(bundle):
    """Return the existing registration interface without writing any NPZ.

    Use P1/P2, not raw T/2: T expresses translation in the second raw camera's
    axes, whereas measured points use the first rectified camera's axes.
    Camera-up vectors are brought into that common orientation by R1/R2.
    No scaling, reflection, gravity certification or fiducial fit is involved.
    Projection-only legacy stereo files need no extra R/T keys.
    """
    left = _camera_center(bundle['P1'])
    right = _camera_center(bundle['P2'])
    rotations = [RigidTransform(bundle[key], np.zeros(3)).R for key in ('R1', 'R2')]
    midpoint = (left + right) / 2.
    y_axis = _unit(left - right, 'right-to-left baseline')
    up_hint = _unit(sum(R @ np.array([0., -1., 0.]) for R in rotations), 'camera-up reference')
    z_axis = _unit(up_hint - np.dot(up_hint, y_axis) * y_axis, 'up perpendicular to baseline')
    x_axis = _unit(np.cross(y_axis, z_axis), 'forward axis')
    forward_hint = _unit(sum(R @ np.array([0., 0., 1.]) for R in rotations), 'camera-forward reference')
    if np.dot(x_axis, forward_hint) <= 1e-6:
        raise ValueError('left/right camera order or mounting conflicts with forward/+Y/up; verify physical LEFT/RIGHT or align W')
    R = np.stack([x_axis, y_axis, z_axis])
    transform = RigidTransform(R, -R @ midpoint)
    return {
        'name': 'camera_midpoint',
        'transform': transform,
        'metadata': {
            'mode': 'camera_midpoint', 'method': 'stereo_optical_centers_no_scale',
            'source_system': 'rectified_left_camera', 'unit': 'mm',
            'transform_direction': 'C_to_W',
            'origin_camera_mm': midpoint.tolist(),
            'left_center_camera_mm': left.tolist(), 'right_center_camera_mm': right.tolist(),
            'baseline_mm': float(np.linalg.norm(left - right)),
            'axes': {'X': 'forward, away from cameras', 'Y': 'right camera -> left camera',
                     'Z': 'up assuming level upright camera mounting'},
            'axis_vectors_camera': {'X': x_axis.tolist(), 'Y': y_axis.tolist(), 'Z': z_axis.tolist()},
            'up_confirmed': False, 'up_reference': 'camera_mount_assumption',
            'mount_assumption': 'optical centers at the same height; level upright cameras; gravity not measured',
        },
    }
