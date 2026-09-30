"""Coordinate transforms: a minimal rigid-transform scaffold.

This is a math scaffold only. It does NOT define a final world X/Y convention;
that remains a future project decision (ground ``Z=0``, ``+Z`` upward). Points
are ``(N, 3)`` with units carried by the caller.
"""

from __future__ import annotations

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
        self.R = R
        self.t = t

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