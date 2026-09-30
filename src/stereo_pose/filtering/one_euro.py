"""Temporal filtering: One Euro filtering for per-joint 3D smoothing.

Ported faithfully from ``reference/v1_2/stereo_pose/filtering.py``.
"""

from __future__ import annotations

import math

import numpy as np


class OneEuroVectorFilter:
    """One Euro filter applied independently per vector component."""

    def __init__(self, min_cutoff=1.2, beta=0.015, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        cutoff = np.maximum(np.asarray(cutoff, dtype=float), 1e-6)
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / max(dt, 1e-6))

    def reset(self):
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def update(self, x, t_s):
        x = np.asarray(x, dtype=float)
        t_s = float(t_s)

        if self.x_prev is None or self.t_prev is None:
            self.x_prev = x.copy()
            self.dx_prev = np.zeros_like(x)
            self.t_prev = t_s
            return x.copy()

        dt = max(1e-6, t_s - self.t_prev)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1.0 - a_d) * self.dx_prev

        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1.0 - a) * self.x_prev

        self.x_prev = x_hat.copy()
        self.dx_prev = dx_hat.copy()
        self.t_prev = t_s
        return x_hat


class JointSmoother:
    """Per-joint One Euro smoothing with gap-based reset."""

    def __init__(self, enabled=True, min_cutoff=1.2, beta=0.015, d_cutoff=1.0, reset_after_s=0.6):
        self.enabled = bool(enabled)
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.reset_after_s = float(reset_after_s)
        self.filters = {}
        self.last_seen = {}

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

    def reset(self, joint=None):
        if joint is None:
            self.filters.clear()
            self.last_seen.clear()
            return
        self.filters.pop(joint, None)
        self.last_seen.pop(joint, None)

    def update(self, joint, xyz, t_s):
        xyz = np.asarray(xyz, dtype=float)
        if not self.enabled:
            self.last_seen[joint] = float(t_s)
            return xyz.copy()

        last = self.last_seen.get(joint)
        if last is not None and (t_s - last) > self.reset_after_s:
            self.reset(joint)

        f = self.filters.get(joint)
        if f is None:
            f = OneEuroVectorFilter(self.min_cutoff, self.beta, self.d_cutoff)
            self.filters[joint] = f

        self.last_seen[joint] = float(t_s)
        return f.update(xyz, t_s)