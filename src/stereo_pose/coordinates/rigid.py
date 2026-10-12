"""Generic proper rigid transforms and user-control registration.

Axis conventions belong to the owner-defined W or the separate camera_midpoint
default, not this generic math. Points are ``(N, 3)``; callers carry units.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from stereo_pose.models import CoordinateTransformMetadata


class RigidTransform:
    """A rigid transform ``y = R @ x + t`` with rotation ``R`` and translation ``t``."""

    def __init__(self, rotation: np.ndarray, translation: np.ndarray):
        R = np.asarray(rotation, dtype=float)
        t = np.asarray(translation, dtype=float).reshape(-1)
        if R.shape != (3, 3):
            raise ValueError("rotation must be a 3x3 matrix")
        if t.shape != (3,):
            raise ValueError("translation must be a 3-vector")
        if not np.all(np.isfinite(R)) or not np.all(np.isfinite(t)):
            raise ValueError("transform must be finite")
        if not np.allclose(R.T @ R, np.eye(3), atol=1e-8, rtol=0) or not np.isclose(np.linalg.det(R), 1, atol=1e-8):
            raise ValueError("rotation must be orthogonal with det=+1; no scale/reflection")
        self.R = R.copy()
        self.t = t.copy()

    def apply(self, points) -> np.ndarray:
        """Apply the transform to an ``(..., 3)`` array of points."""
        p = np.asarray(points, dtype=float)
        return p @ self.R.T + self.t

    def compose(self, other: "RigidTransform") -> "RigidTransform":
        """``self`` after ``other``: ``y = self(other(x))``."""
        return RigidTransform(self.R @ other.R, self.R @ other.t + self.t)

    def inverse(self) -> "RigidTransform":
        R_inv = self.R.T
        return RigidTransform(R_inv, -R_inv @ self.t)

    def as_matrix(self) -> np.ndarray:
        """Return a 4x4 homogeneous transform matrix."""
        M = np.eye(4, dtype=float)
        M[:3, :3] = self.R
        M[:3, 3] = self.t
        return M

    @classmethod
    def identity(cls) -> "RigidTransform":
        return cls(np.eye(3), np.zeros(3))

    def to_metadata(self, source: str, target: str, units: str = "mm") -> CoordinateTransformMetadata:
        return CoordinateTransformMetadata(
            source_system=source,
            target_system=target,
            rotation=self.R.copy(),
            translation=self.t.copy(),
            units=units,
        )


@dataclass
class RigidFit:
    transform: RigidTransform
    residuals_mm: np.ndarray
    spread_camera_mm: np.ndarray
    spread_world_mm: np.ndarray

    def report(self):
        return {
            "method": "kabsch_no_scale", "count": len(self.residuals_mm),
            "inlier_count": len(self.residuals_mm), "residuals_mm": self.residuals_mm.tolist(),
            "rms_mm": float(np.sqrt(np.mean(self.residuals_mm ** 2))),
            "max_mm": float(np.max(self.residuals_mm)), "det_R": float(np.linalg.det(self.transform.R)),
            "spread_camera_mm": self.spread_camera_mm.tolist(), "spread_world_mm": self.spread_world_mm.tolist(),
            "warning": "three controls: no independent redundancy" if len(self.residuals_mm) == 3 else "",
        }


def fit_rigid(camera, world, max_residual_mm=10.0):
    """Kabsch SE(3), no scaling. Coplanar rank-2 controls are valid.

    Explicitly reject inconsistent/outlier controls instead of silently dropping
    IDs or changing scale. The configured residual limit is registration-only.
    """
    C, W = np.asarray(camera, dtype=float), np.asarray(world, dtype=float)
    if C.ndim != 2 or C.shape[1:] != (3,) or C.shape != W.shape or len(C) < 3:
        raise ValueError("need matching arrays of >=3 non-collinear XYZ controls")
    if not np.isfinite(max_residual_mm) or max_residual_mm <= 0 or not np.all(np.isfinite(C)) or not np.all(np.isfinite(W)):
        raise ValueError("controls and positive residual limit must be finite (mm)")
    cc, ww = C - C.mean(axis=0), W - W.mean(axis=0)
    spreads = [np.linalg.svd(x, compute_uv=False) for x in (cc, ww)]
    for s in spreads:
        if s[0] < 1e-6 or s[1] / s[0] < 1e-3:
            raise ValueError("collinear/near-collinear controls; spread points in two directions")
    U, _, Vt = np.linalg.svd(cc.T @ ww)
    correction = np.diag([1., 1., np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ correction @ U.T
    transform = RigidTransform(R, W.mean(axis=0) - R @ C.mean(axis=0))
    residuals = np.linalg.norm(transform.apply(C) - W, axis=1)
    if np.max(residuals) > max_residual_mm:
        raise ValueError(f"registration residual {np.max(residuals):.3f}mm > {max_residual_mm:g}mm; check IDs, XYZ, units and rig; no scale correction")
    return RigidFit(transform, residuals, *spreads)


def relative_origin(base, camera_point, target=(0., 0., 0.)):
    """Change origin only, preserving the existing world or camera axes."""
    R = np.eye(3) if base is None else base.R
    point, target = np.asarray(camera_point, dtype=float), np.asarray(target, dtype=float)
    if point.shape != (3,) or target.shape != (3,):
        raise ValueError("reference and target must be XYZ vectors")
    return RigidTransform(R, target - R @ point)
