"""Timestamped checkerboard stability evidence; independent of camera FPS/IO.

Missing detections pause evidence time. Long observation gaps reset it. Known
180-degree detector order reversals are normalized only for motion comparisons;
this module never modifies the corners supplied to the calibration solver.
"""
from __future__ import annotations
from collections import deque
import numpy as np


def align_corner_order(points, reference):
    """Choose direct/reverse-180 temporal correspondence without mutating input."""
    p = np.asarray(points, dtype=float)
    if reference is None:
        return p.copy(), 'DIRECT'
    ref = np.asarray(reference, dtype=float)
    direct = float(np.mean(np.linalg.norm(p - ref, axis=1)))
    reverse = float(np.mean(np.linalg.norm(p[::-1] - ref, axis=1)))
    if reverse + 1e-6 < direct:
        return p[::-1].copy(), 'REV180'
    return p.copy(), 'DIRECT'


class BoardStability:
    def __init__(self, dwell_s, min_frames, motion_px, loss_grace_s, pattern):
        self.dwell_s = float(dwell_s)
        self.min_frames = int(min_frames)
        self.motion_px = float(motion_px)
        self.loss_grace_s = float(loss_grace_s)
        self.cols,self.rows=map(int,pattern)
        self.corner_count=self.cols*self.rows
        self.history = deque(maxlen=max(128, self.min_frames + 1))
        self.reset()

    def reset(self):
        self.history.clear()
        self.cadence=deque(maxlen=20)
        self.gap_limit_s=self.loss_grace_s
        self.anchor = None
        self.order_reference = None
        self.last_valid_t = None
        self.last_observation_t = None
        self.missed = False
        self.duration = 0.
        self.observations = 0
        self.info = self._info('insufficient_observations')

    def _clear_run(self, keep_order=False):
        self.history.clear()
        self.anchor = None
        self.duration = 0.
        self.observations = 0
        if not keep_order:
            self.order_reference = None
            self.last_valid_t = None

    def _info(self, reason, motion_l=None, motion_r=None, drift_l=0., drift_r=0.,
              order_l='n/a', order_r='n/a', reset_reason='', motion_cause=''):
        return {'stable': reason == 'stable', 'reason': reason,
                'motion_left_px': motion_l, 'motion_right_px': motion_r,
                'motion_px': None if motion_l is None or motion_r is None else max(motion_l,motion_r),
                'drift_left_px': drift_l, 'drift_right_px': drift_r,
                'dwell_s': self.duration, 'observations': self.observations,
                'progress': min(1.,self.observations/max(1,self.min_frames),
                                self.duration/self.dwell_s if self.dwell_s > 0 else 1.),
                'order_left': order_l, 'order_right': order_r, 'reset_reason': reset_reason,
                'gap_limit_s':self.gap_limit_s,'motion_cause':motion_cause}

    def _finish(self, *args, **kwargs):
        self.info = self._info(*args, **kwargs)
        return self.info

    def _motion(self):
        """Anchor excursion plus coherent drift, evaluated in BOTH views.

        Drift only rejects a well-explained trend (>=80% energy), spanning at
        least max(0.5px, one quarter of the existing motion budget). Independent
        subpixel corner jitter is retained; no enlarged motion threshold.
        """
        times = np.array([x[0] for x in self.history])
        dt = times - times.mean()
        variance = float(dt @ dt)
        span = times[-1] - times[0]
        motions=[];drifts=[];moving=False
        for side in (1,2):
            pts=np.stack([x[side] for x in self.history])
            excursion=np.linalg.norm(pts-self.anchor[side-1],axis=2).mean(axis=1)
            motions.append(float(excursion.max()))
            drift=0.
            if len(times) >= 3 and variance > 1e-12:
                centered=pts-pts.mean(axis=0)
                velocity=np.tensordot(dt,centered,axes=(0,0))/variance
                prediction=dt[:,None,None]*velocity[None,:,:]
                energy=float(np.sum(centered**2))
                explained=float(np.sum(prediction**2))/energy if energy > 1e-12 else 0.
                drift=float(np.mean(np.linalg.norm(velocity,axis=1))*span)
                if explained >= .80 and drift >= max(.5,self.motion_px*.25):
                    moving=True
            drifts.append(drift)
        return motions,drifts,moving

    def update(self, now, left, right):
        now=float(now)
        if not np.isfinite(now) or (self.last_observation_t is not None and now < self.last_observation_t):
            self.reset()
            return self._finish('invalid_timestamp')
        if self.last_observation_t is not None and now == self.last_observation_t:
            return self._finish('duplicate_observation')
        # Use established ATTEMPT cadence, before adding the current interval.
        # A long stall cannot inflate its own timeout; consistently slow
        # detectors get three normal periods of grace, not a hidden FPS gate.
        self.gap_limit_s=max(self.loss_grace_s,3*float(np.median(self.cadence))) if self.cadence else self.loss_grace_s
        if self.last_observation_t is not None:
            self.cadence.append(now-self.last_observation_t)
        self.last_observation_t=now
        reset_reason=''
        if self.last_valid_t is not None and now-self.last_valid_t > self.gap_limit_s+1e-9:
            self._clear_run()
            reset_reason='detection_gap'
        if left is None or right is None:
            self.missed=True
            return self._finish('detection_failed',reset_reason=reset_reason)
        arrays=[np.asarray(det['corners'],dtype=float) for det in (left,right)]
        if any(p.shape != (self.corner_count,2) or not np.isfinite(p).all() for p in arrays):
            self._clear_run();self.missed=True
            return self._finish('invalid_corners')
        for p in arrays:
            grid=p.reshape(self.rows,self.cols,2)
            # A legal rectangular grid has coherent adjacent row/column
            # directions. Reverse-180 keeps this property; rolled/shuffled
            # indices do not. This is only a capture-evidence guard.
            for axis in (0,1):
                steps=np.diff(grid,axis=axis).reshape(-1,2)
                direction=steps.mean(axis=0)
                if not np.any(steps) or np.any(steps@direction <= 0):
                    self._clear_run(keep_order=True);self.missed=True
                    return self._finish('corner_order_jump')
        aligned=[];orders=[]
        for side,p in enumerate(arrays):
            ref=None if self.order_reference is None else self.order_reference[side]
            point,order=align_corner_order(p,ref)
            if ref is not None and np.mean(np.linalg.norm(point-ref,axis=1)) > self.motion_px:
                distances=np.linalg.norm(p[:,None,:]-ref[None,:,:],axis=2)
                nearest=np.argmin(distances,axis=1)
                # Same physical point cloud, but neither legal row order:
                # reset evidence instead of calling it true board motion.
                if len(np.unique(nearest)) == len(p) and np.max(distances[np.arange(len(p)),nearest]) <= max(.5,self.motion_px*.25):
                    self._clear_run(keep_order=True);self.missed=True
                    return self._finish('corner_order_jump')
            aligned.append(point);orders.append(order)
        if self.anchor is None:
            self.anchor=tuple(p.copy() for p in aligned)
        elif not self.missed and self.last_valid_t is not None:
            self.duration+=now-self.last_valid_t
        self.observations+=1
        self.history.append((now,*aligned))
        self.last_valid_t=now;self.missed=False
        self.order_reference=tuple(p.copy() for p in aligned)
        motions,drifts,trend=self._motion()
        if max(motions) > self.motion_px+1e-6 or trend:
            self._clear_run(keep_order=True)
            self.anchor=tuple(p.copy() for p in aligned)
            self.history.append((now,*aligned));self.observations=1
            return self._finish('moving',*motions,*drifts,*orders,reset_reason='motion',
                                motion_cause='coherent_drift' if trend else 'anchor_excursion')
        reason=('insufficient_observations' if self.observations < self.min_frames else
                'settling' if self.duration+1e-9 < self.dwell_s else 'stable')
        return self._finish(reason,*motions,*drifts,*orders,reset_reason=reset_reason)
