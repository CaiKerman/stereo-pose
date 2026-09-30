"""Temporal speed plausibility gate (measurement quality).

Rejects a joint when its implied velocity between consecutive accepted
positions exceeds a configured maximum. Part of the measurement-quality
boundary rather than signal smoothing.
"""

from __future__ import annotations

import numpy as np


class TemporalSpeedGate:
    def __init__(self, max_speed_mm_s=6000.0, reset_after_s=0.6):
        self.max_speed = float(max_speed_mm_s)
        self.reset_after_s = float(reset_after_s)
        self.last = {}

    def reset(self, joint=None):
        if joint is None:
            self.last.clear()
        else:
            self.last.pop(joint, None)

    def check(self, joint, xyz, t_s):
        xyz = np.asarray(xyz, dtype=float)
        t_s = float(t_s)
        prev = self.last.get(joint)

        if prev is None or self.max_speed <= 0:
            self.last[joint] = (xyz.copy(), t_s)
            return True, 0.0

        prev_xyz, prev_t = prev
        dt = t_s - prev_t
        if dt <= 1e-6 or dt > self.reset_after_s:
            self.last[joint] = (xyz.copy(), t_s)
            return True, 0.0

        speed = float(np.linalg.norm(xyz - prev_xyz) / dt)
        if speed > self.max_speed:
            return False, speed

        self.last[joint] = (xyz.copy(), t_s)
        return True, speed