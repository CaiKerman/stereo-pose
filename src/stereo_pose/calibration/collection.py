"""Runtime stereo calibration collection and solver.

Solver math and archive format preserve the v1.2 reference. Task004 capture
evidence adapts to detector cadence. ``readiness`` is a heuristic sample-
preparation score, not a statistical confidence.
"""

from __future__ import annotations

import math
import shutil
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from stereo_pose.persistence.paths import auto_dir
from stereo_pose.calibration.package import atomic_npz
from stereo_pose.calibration.stability import BoardStability, align_corner_order
from stereo_pose.calibration.correspondence import normalize_stereo_pairs

_SCHEMA_VERSION = "1"


class RuntimeCalibration:
    """Collects spatially-stable checkerboard pairs and solves stereo calibration."""

    def __init__(self, stereo_cfg, runtime_cfg):
        self.cols = int(stereo_cfg["board_cols"])
        self.rows = int(stereo_cfg["board_rows"])
        self.square_mm = float(stereo_cfg["square_mm"])
        self.pattern = (self.cols, self.rows)
        self.calibration_dir = Path(stereo_cfg["calibration_dir"])

        self.session_root = Path(runtime_cfg["session_dir"])
        self.auto_capture = bool(runtime_cfg.get("auto_capture", True))
        self.interval = float(runtime_cfg.get("auto_capture_interval_s", 0.7))
        self.min_pairs = int(runtime_cfg.get("min_pairs_to_solve", 12))
        self.target_pairs = int(runtime_cfg.get("target_pairs", 24))
        self.min_area_ratio = float(runtime_cfg.get("min_board_area_ratio", 0.012))
        self.diversity_threshold = float(runtime_cfg.get("diversity_threshold", 0.12))
        self.keep_images = bool(runtime_cfg.get("keep_images_after_success", False))
        self.recommended_readiness = float(runtime_cfg.get("recommended_readiness", 75))

        self.stable_dwell_s = float(runtime_cfg.get("stable_dwell_s", 0.30))
        self.stable_min_frames = int(runtime_cfg.get("stable_min_frames", 3))
        self.stable_corner_motion_px = float(runtime_cfg.get("stable_corner_motion_px", 5.0))
        self.stable_loss_grace_s = float(runtime_cfg.get("stable_loss_grace_s", 1.25))
        self.robust_prune = bool(runtime_cfg.get("robust_prune", True))
        self.prune_min_epipolar_px = float(runtime_cfg.get("prune_min_epipolar_px", 0.8))
        self.prune_max_epipolar_px = float(runtime_cfg.get("prune_max_epipolar_px", 2.5))
        self.max_prune_fraction = float(runtime_cfg.get("max_prune_fraction", 0.25))

        self.active = False
        self.session_dir = None
        self.left_dir = None
        self.right_dir = None
        self.samples = []
        self.last_capture_t = None
        self.current = None
        self.stability = BoardStability(self.stable_dwell_s,self.stable_min_frames,
            self.stable_corner_motion_px,self.stable_loss_grace_s,self.pattern)
        self.stability_history = self.stability.history
        self._stability_info = self.stability.info
        self.detection_history = deque(maxlen=120)
        self._current_pair = None
        self._current_timestamp = None
        self._last_capture_corners = None
        self.last_capture_notice = ''
        self._notice_until = 0.
        self.camera_context = None

    def set_camera_context(self, left_index, right_index, backend, requested_size, requested_fps, actual_fps=None):
        """Record the camera identity/config used to capture this calibration.

        This payload is embedded in the solved NPZ so later compatibility
        diagnostics have evidence to compare against the active capture.
        """
        self.camera_context = {
            "left_index": int(left_index),
            "right_index": int(right_index),
            "backend": str(backend or "auto"),
            "requested_size": (int(requested_size[0]), int(requested_size[1])),
            "requested_fps": float(requested_fps),
            "actual_fps": None if actual_fps is None else float(actual_fps),
        }

    def _camera_context_fields(self):
        if not self.camera_context:
            return {}
        cc = self.camera_context
        fields = {
            "camera_left": np.array(cc["left_index"]),
            "camera_right": np.array(cc["right_index"]),
            "camera_backend": np.array(cc["backend"]),
            "camera_requested_size": np.array(cc["requested_size"]),
            "camera_requested_fps": np.array(cc["requested_fps"]),
        }
        if cc["actual_fps"] is not None:
            fields["camera_actual_fps"] = np.array(cc["actual_fps"])
        return fields

    def start(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.session_root / f"session_{stamp}_{uuid.uuid4().hex}"
        self.left_dir = self.session_dir / "left"
        self.right_dir = self.session_dir / "right"
        self.left_dir.mkdir(parents=True, exist_ok=True)
        self.right_dir.mkdir(parents=True, exist_ok=True)
        self.samples = []
        self.last_capture_t = None
        self.current = None
        self._reset_capture_evidence()
        self._last_capture_corners = None
        self.last_capture_notice = ''
        self.active = True
        print(f"[calibration] session started: {self.session_dir}")

    def discard(self):
        if self.session_dir and self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)
        self.active = False
        self.samples = []
        self.current = None
        self._reset_capture_evidence()
        print("[calibration] current session discarded")

    def stop_without_delete(self):
        self.active = False
        self._reset_capture_evidence()
        print("[calibration] left calibration mode; temporary session kept")

    def _detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flags = cv2.CALIB_CB_NORMALIZE_IMAGE
        ok, corners = cv2.findChessboardCornersSB(gray, self.pattern, flags=flags)
        if not ok:
            return None

        corners = corners.reshape(-1, 2).astype(np.float32)
        h, w = gray.shape[:2]
        xmin, ymin = corners.min(axis=0)
        xmax, ymax = corners.max(axis=0)
        area_ratio = max(0.0, float((xmax - xmin) * (ymax - ymin) / (w * h)))
        cx = float(corners[:, 0].mean() / w)
        cy = float(corners[:, 1].mean() / h)

        a = corners[0]
        b = corners[self.cols - 1]
        angle = math.degrees(math.atan2(float(b[1] - a[1]), float(b[0] - a[0])))

        x0 = max(0, int(xmin))
        y0 = max(0, int(ymin))
        x1 = min(w, int(xmax) + 1)
        y1 = min(h, int(ymax) + 1)
        roi = gray[y0:y1, x0:x1]
        sharpness = float(cv2.Laplacian(roi, cv2.CV_64F).var()) if roi.size else 0.0

        return {
            "corners": corners,
            "center": (cx, cy),
            "area_ratio": area_ratio,
            "angle_deg": angle,
            "sharpness": sharpness,
        }

    @staticmethod
    def _descriptor(det):
        # Row orientation is periodic in 180 degrees: an SB order reversal
        # must not create a fictitious new pose or a discontinuity at +/-90.
        angle=math.radians(det['angle_deg'])*2
        weight=90/(math.pi*60)
        return np.array([
            det["center"][0],
            det["center"][1],
            min(1.0, math.sqrt(max(det["area_ratio"], 0.0)) * 2.5),
            weight*math.sin(angle),weight*math.cos(angle),
        ], dtype=np.float32)

    def _is_diverse(self, dl, dr):
        desc = np.concatenate([self._descriptor(dl), self._descriptor(dr)])
        if not self.samples:
            return True
        prev = np.stack([s["descriptor"] for s in self.samples])
        d = np.linalg.norm(prev - desc[None, :], axis=1)
        return float(d.min()) >= self.diversity_threshold

    def _update_stability(self, now, dl, dr):
        self._stability_info=self.stability.update(now,dl,dr)
        return self._stability_info['stable'],self._stability_info['motion_px'],self._stability_info['dwell_s']

    def _reset_capture_evidence(self):
        self.stability.reset();self._stability_info=self.stability.info
        self.detection_history.clear();self._current_pair=None;self._current_timestamp=None

    def _pose_distance(self, dl, dr):
        if not self.samples:return None
        desc=np.concatenate([self._descriptor(dl),self._descriptor(dr)])
        return float(np.min(np.linalg.norm(np.stack([s['descriptor'] for s in self.samples])-desc,axis=1)))

    def _new_pose(self, dl, dr):
        if self._last_capture_corners is None:return True
        for det,ref in zip((dl,dr),self._last_capture_corners):
            corners,_=align_corner_order(det['corners'],ref)
            if float(np.mean(np.linalg.norm(corners-ref,axis=1))) > self.stable_corner_motion_px+1e-6:
                return True
        return False

    def _save(self, frame_l, frame_r, dl, dr, stability_motion_px):
        i = len(self.samples)
        lp = self.left_dir / f"{i:03d}.png"
        rp = self.right_dir / f"{i:03d}.png"
        try:
            if not cv2.imwrite(str(lp), frame_l) or not cv2.imwrite(str(rp), frame_r):
                raise OSError('failed to write both calibration images')
        except (OSError,cv2.error):
            lp.unlink(missing_ok=True);rp.unlink(missing_ok=True)
            raise
        self.samples.append({
            "left": dl,
            "right": dr,
            "descriptor": np.concatenate([self._descriptor(dl), self._descriptor(dr)]),
            "left_path": lp,
            "right_path": rp,
            "stability_motion_px": float(stability_motion_px or 0.0),
        })
        self.last_capture_t = self._current_timestamp if self._current_timestamp is not None else time.monotonic()
        self._last_capture_corners = (dl['corners'].copy(),dr['corners'].copy())
        print(
            f"[calibration] captured pair {len(self.samples)} | "
            f"motion={float(stability_motion_px or 0.0):.2f}px | "
            f"readiness={self.readiness():.0f}/100"
        )

    def process(self, frame_l, frame_r, force_capture=False, timestamp_s=None):
        now = time.monotonic() if timestamp_s is None else float(timestamp_s)
        begin=time.perf_counter()
        dl = self._detect(frame_l)
        left_done=time.perf_counter()
        dr = self._detect(frame_r)
        right_done=time.perf_counter()
        valid = dl is not None and dr is not None
        good_area = bool(
            valid
            and dl["area_ratio"] >= self.min_area_ratio
            and dr["area_ratio"] >= self.min_area_ratio
        )

        stable, motion_px, stable_dwell = self._update_stability(now, dl, dr)
        if not self.detection_history or now > self.detection_history[-1][0]:
            self.detection_history.append((now,valid))
        while len(self.detection_history)>2 and now-self.detection_history[0][0]>5.:
            self.detection_history.popleft()
        span=0. if len(self.detection_history)<2 else now-self.detection_history[0][0]
        frequency=None if span <= 0 else sum(v for _,v in list(self.detection_history)[1:])/span
        loop_hz=None if span <= 0 else (len(self.detection_history)-1)/span
        info=self._stability_info
        interval_remaining=0. if self.last_capture_t is None else max(0.,self.interval-(now-self.last_capture_t))
        diverse=valid and self._is_diverse(dl,dr)
        new_pose=valid and self._new_pose(dl,dr)
        stability_reason=info['reason'] if not stable else 'stable'
        reason=('detection_failed' if not valid else 'board_too_small' if not good_area else
                'auto_disabled' if not self.auto_capture else stability_reason if not stable else
                'duplicate_pose' if not diverse or not new_pose else
                'waiting_interval' if interval_remaining>1e-9 else 'ready')
        self.current = {
            "valid": valid,
            "good_area": good_area,
            "stable": bool(stable),
            "stability_motion_px": motion_px,
            "stable_dwell_s": float(stable_dwell),
            "area_ratio_left": None if dl is None else float(dl["area_ratio"]),
            "area_ratio_right": None if dr is None else float(dr["area_ratio"]),
            "captured": False,
            "detected_left": dl is not None,"detected_right": dr is not None,
            "auto_capture": self.auto_capture,"capture_reason":reason,
            "stability_reason":stability_reason,"stability_observations":info['observations'],
            "stability_progress":info['progress'],"stability_reset_reason":info['reset_reason'],
            "stability_gap_limit_s":info['gap_limit_s'],
            "motion_left_px":info['motion_left_px'],"motion_right_px":info['motion_right_px'],
            "motion_cause":info['motion_cause'],
            "drift_left_px":info['drift_left_px'],"drift_right_px":info['drift_right_px'],
            "order_left":info['order_left'],"order_right":info['order_right'],
            "effective_detection_hz":frequency,"calibration_loop_hz":loop_hz,
            "detector_left_ms":(left_done-begin)*1000,"detector_right_ms":(right_done-left_done)*1000,
            "interval_remaining_s":interval_remaining,"diverse":bool(diverse),"new_pose":bool(new_pose),
            "pose_distance":self._pose_distance(dl,dr) if valid else None,"manual_duplicate":False,
        }
        self._current_pair=(frame_l,frame_r,dl,dr);self._current_timestamp=now
        if force_capture or reason=='ready':self._attempt_capture(force_capture)
        return self.current

    def _attempt_capture(self, manual):
        cur=self.current
        if not cur['valid'] or not cur['good_area']:
            if manual:print('[calibration] manual capture rejected: both boards must be fully visible and large enough')
            return cur
        frame_l,frame_r,dl,dr=self._current_pair
        if manual:
            # AUTO may already have saved this exact pair before SPACE arrived.
            # Recheck against CURRENT saved samples, not pre-save cached flags.
            cur['diverse']=self._is_diverse(dl,dr)
            cur['new_pose']=self._new_pose(dl,dr)
            cur['pose_distance']=self._pose_distance(dl,dr)
        duplicate=not cur['diverse'] or not cur['new_pose']
        cur['manual_duplicate']=bool(manual and duplicate)
        if cur['manual_duplicate']:
            print('[calibration] WARNING: manual duplicate pose; force capture retained (does not add pose diversity)')
        try:
            self._save(frame_l,frame_r,dl,dr,cur['stability_motion_px'])
        except (OSError,cv2.error) as e:
            cur.update(captured=False,capture_reason='capture_failed',capture_error=str(e))
            self.last_capture_notice=f'CAPTURE FAILED: {e}'
            print('[calibration]',self.last_capture_notice)
        else:
            cur.update(captured=True,capture_reason='manual_captured' if manual else 'auto_captured')
            self.last_capture_notice=f'{"MANUAL" if manual else "AUTO"} captured pair {len(self.samples)}'
            if cur['manual_duplicate']:self.last_capture_notice+=' | DUPLICATE WARNING (force retained)'
        self._notice_until=self._current_timestamp+2.
        return cur

    def capture_current(self):
        """SPACE uses the already detected current pair: no reread/re-detection."""
        if self.current is None or self._current_pair is None:
            return {'captured':False,'capture_reason':'no_current_pair'}
        return self._attempt_capture(True)

    def readiness(self):
        if not self.samples:
            return 0.0

        n = len(self.samples)
        count_score = min(1.0, n / max(1, self.target_pairs)) * 45.0

        bins = set()
        for s in self.samples:
            for side in ("left", "right"):
                cx, cy = s[side]["center"]
                bins.add((side, min(2, max(0, int(cx * 3))), min(2, max(0, int(cy * 3)))))
        coverage_score = min(1.0, len(bins) / 18.0) * 25.0

        areas = [s[side]["area_ratio"] for s in self.samples for side in ("left", "right")]
        scale_span = max(areas) - min(areas) if len(areas) > 1 else 0.0
        scale_score = min(1.0, scale_span / 0.12) * 15.0

        angles = sorted(s[side]["angle_deg"]%180 for s in self.samples for side in ("left", "right"))
        angle_span = 180-max(np.diff(angles+[angles[0]+180])) if len(angles)>1 else 0.
        angle_score = min(1.0, abs(angle_span) / 35.0) * 15.0

        return float(min(100.0, count_score + coverage_score + scale_score + angle_score))

    def can_solve(self):
        return len(self.samples) >= self.min_pairs

    def _load_points(self):
        objp = np.zeros((self.rows * self.cols, 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.cols, 0:self.rows].T.reshape(-1, 2)
        objp *= self.square_mm

        objpoints, img_l, img_r, paths = [], [], [], []
        image_size = None

        for sample in self.samples:
            l = cv2.imread(str(sample["left_path"]))
            r = cv2.imread(str(sample["right_path"]))
            if l is None or r is None:
                continue
            gl = cv2.cvtColor(l, cv2.COLOR_BGR2GRAY)
            gr = cv2.cvtColor(r, cv2.COLOR_BGR2GRAY)
            image_size = gl.shape[::-1]

            ok_l, cl = cv2.findChessboardCornersSB(gl, self.pattern, flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
            ok_r, cr = cv2.findChessboardCornersSB(gr, self.pattern, flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
            if not (ok_l and ok_r):
                continue

            objpoints.append(objp.copy())
            img_l.append(cl.astype(np.float32))
            img_r.append(cr.astype(np.float32))
            paths.append((sample["left_path"], sample["right_path"]))

        return objpoints, img_l, img_r, paths, image_size

    @staticmethod
    def _solve_core(objpoints, img_l, img_r, image_size):
        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            80,
            1e-6,
        )
        ret_l, K1, D1, _, _ = cv2.calibrateCamera(objpoints, img_l, image_size, None, None)
        ret_r, K2, D2, _, _ = cv2.calibrateCamera(objpoints, img_r, image_size, None, None)
        stereo_rms, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
            objpoints, img_l, img_r,
            K1, D1, K2, D2,
            image_size,
            criteria=criteria,
            flags=cv2.CALIB_FIX_INTRINSIC,
        )
        R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
            K1, D1, K2, D2, image_size, R, T, alpha=0
        )
        return {
            "left_rms": float(ret_l),
            "right_rms": float(ret_r),
            "stereo_rms": float(stereo_rms),
            "K1": K1, "D1": D1, "K2": K2, "D2": D2,
            "R": R, "T": T, "E": E, "F": F,
            "R1": R1, "R2": R2, "P1": P1, "P2": P2, "Q": Q,
        }

    @staticmethod
    def _sample_epipolar_errors(solution, img_l, img_r):
        errors = []
        for cl, cr in zip(img_l, img_r):
            ul = cv2.undistortPoints(
                cl, solution["K1"], solution["D1"],
                R=solution["R1"], P=solution["P1"]
            ).reshape(-1, 2)
            ur = cv2.undistortPoints(
                cr, solution["K2"], solution["D2"],
                R=solution["R2"], P=solution["P2"]
            ).reshape(-1, 2)
            errors.append(float(np.mean(np.abs(ul[:, 1] - ur[:, 1]))))
        return np.asarray(errors, dtype=float)

    def solve(self):
        if not self.can_solve():
            raise RuntimeError(f"Need at least {self.min_pairs} pairs; have {len(self.samples)}")

        objpoints, img_l, img_r, paths, image_size = self._load_points()
        if len(objpoints) < self.min_pairs:
            raise RuntimeError(f"Only {len(objpoints)} saved pairs usable; need {self.min_pairs}")

        initial_count = len(objpoints)
        # OpenCV's independent left/right checkerboard detections can use
        # opposite (180-degree) physical corner orders. Never send unmatched
        # index pairs to stereoCalibrate: reconcile on raw stereo geometry first.
        # This does not use matching intrinsics, parallel cameras, or square_mm.
        img_r, corner_alignment = normalize_stereo_pairs(
            img_l, img_r, min_good_pairs=self.min_pairs
        )
        accepted_indices = corner_alignment["accepted_indices"]
        rejected_indices = corner_alignment["rejected_indices"]
        if rejected_indices:
            objpoints = [objpoints[i] for i in accepted_indices]
            img_l = [img_l[i] for i in accepted_indices]
            paths = [paths[i] for i in accepted_indices]
            print(
                f'[calibration] rejected {len(rejected_indices)} ambiguous '
                f'correspondence pair(s), 1-based indices: '
                f'{[i+1 for i in rejected_indices]}'
            )
        corner_modes = list(corner_alignment["modes"])
        print(
            f'[calibration] corner correspondence: '
            f'direct={len(corner_modes)-corner_alignment["reversed_count"]}, '
            f'reversed_180={corner_alignment["reversed_count"]}, '
            f'median Sampson={corner_alignment["median_sampson_px"]:.3f}px'
        )
        solution = self._solve_core(objpoints, img_l, img_r, image_size)
        epi = self._sample_epipolar_errors(solution, img_l, img_r)
        pruned_count = 0

        if self.robust_prune and len(epi) > self.min_pairs:
            median = float(np.median(epi))
            mad = float(np.median(np.abs(epi - median)))
            robust_sigma = 1.4826 * mad
            cutoff = max(self.prune_min_epipolar_px, median + 3.0 * robust_sigma)
            cutoff = min(self.prune_max_epipolar_px, cutoff)

            bad_order = [int(i) for i in np.argsort(epi)[::-1] if epi[i] > cutoff]
            max_prune = min(
                int(math.floor(initial_count * self.max_prune_fraction)),
                len(epi) - self.min_pairs,
            )
            bad = set(bad_order[:max(0, max_prune)])

            if bad:
                keep = [i for i in range(initial_count) if i not in bad]
                objpoints = [objpoints[i] for i in keep]
                img_l = [img_l[i] for i in keep]
                img_r = [img_r[i] for i in keep]
                paths = [paths[i] for i in keep]
                corner_modes = [corner_modes[i] for i in keep]
                pruned_count = len(bad)
                solution = self._solve_core(objpoints, img_l, img_r, image_size)
                epi = self._sample_epipolar_errors(solution, img_l, img_r)
                print(
                    f"[calibration] robust prune removed {pruned_count} sample(s); "
                    f"remaining={len(objpoints)}"
                )

        epi_mean = float(np.mean(epi)) if len(epi) else float("nan")
        epi_max = float(np.max(epi)) if len(epi) else float("nan")
        # The previous implementation published unusable NPZs even when the
        # computed rectification sent all pixels out of view. Reject only
        # catastrophic failures here; do NOT replace runtime 3px gating or
        # impose a fixed 24-sample minimum.
        if not np.isfinite(epi_mean) or not np.isfinite(epi_max) or epi_mean > 25.0:
            raise ValueError(
                f'双目求解结果未通过几何检查：样本平均极线误差 '
                f'{epi_mean:.2f}px，最大 {epi_max:.2f}px。'
                '角点对应已检查，但内参与姿态求解仍不一致；'
                '本次不生成/启用 NPZ，原标定保持不变。'
            )

        out_dir = auto_dir(self.calibration_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = out_dir / f"stereo_{stamp}_{uuid.uuid4().hex}.npz"

        save_fields = {
            "K1": solution["K1"], "D1": solution["D1"],
            "K2": solution["K2"], "D2": solution["D2"],
            "R": solution["R"], "T": solution["T"], "E": solution["E"], "F": solution["F"],
            "R1": solution["R1"], "R2": solution["R2"],
            "P1": solution["P1"], "P2": solution["P2"], "Q": solution["Q"],
            "image_size": np.array(image_size),
            "board_cols": np.array(self.cols), "board_rows": np.array(self.rows),
            "square_mm": np.array(self.square_mm),
            "left_rms": np.array(solution["left_rms"]),
            "right_rms": np.array(solution["right_rms"]),
            "stereo_rms": np.array(solution["stereo_rms"]),
            "sample_count": np.array(len(objpoints)),
            "sample_count_initial": np.array(initial_count),
            "pruned_count": np.array(pruned_count),
            "sample_epipolar_mean_px": np.array(epi_mean),
            "sample_epipolar_max_px": np.array(epi_max),
            "corner_order_modes": np.asarray(corner_modes, dtype=str),
            "corner_order_rejected_indices": np.asarray(rejected_indices, dtype=np.int32),
            "corner_order_reversed_count": np.array(corner_modes.count("reversed_180")),
            "corner_order_sampson_median_px": np.array(corner_alignment["median_sampson_px"]),
            "readiness": np.array(self.readiness()),
            "created_at": np.array(stamp),
            "_schema_version": np.array(_SCHEMA_VERSION),
        }
        save_fields.update(self._camera_context_fields())
        atomic_npz(out, save_fields)

        result = {
            "path": out,
            "left_rms": solution["left_rms"],
            "right_rms": solution["right_rms"],
            "stereo_rms": solution["stereo_rms"],
            "sample_count": len(objpoints),
            "pruned_count": pruned_count,
            "sample_epipolar_mean_px": epi_mean,
            "sample_epipolar_max_px": epi_max,
            "corner_order_modes": corner_modes,
            "corner_order_rejected_indices": rejected_indices,
            "corner_order_reversed_count": corner_modes.count("reversed_180"),
            "corner_order_sampson_median_px": corner_alignment["median_sampson_px"],
            "readiness": self.readiness(),
            "T": solution["T"].reshape(-1).astype(float),
        }

        if not self.keep_images and self.session_dir and self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)

        self.active = False
        self._reset_capture_evidence()
        print(
            f"[calibration] saved {out} | Stereo RMS={solution['stereo_rms']:.4f} | "
            f"sample epipolar mean/max={epi_mean:.3f}/{epi_max:.3f}px | "
            f"corner_order reversed={corner_modes.count('reversed_180')} | "
            f"samples={len(objpoints)}"
        )
        return result

    def draw_overlay(self, canvas, pair_timing=None):
        cur = self.current or {}
        def number(value,suffix=''):
            return 'n/a'+suffix if value is None else f'{value:.2f}{suffix}'
        manual_ready = bool(cur.get("valid") and cur.get("good_area"))
        host_skew = None if pair_timing is None else pair_timing.get("host_grab_skew_ms")
        skew_text = "n/a" if host_skew is None else f"{host_skew:.2f}ms"

        states={'detection_failed':'WAIT DETECTION','board_too_small':'BOARD TOO SMALL',
                'insufficient_observations':'WAIT OBSERVATIONS','settling':'WAIT STABLE TIME',
                'moving':'CORNER MOTION DETECTED','corner_order_jump':'CORNER ORDER JUMP: RECHECKING',
                'invalid_corners':'INVALID CORNER DATA','invalid_timestamp':'INVALID OBSERVATION TIME',
                'duplicate_observation':'WAIT NEW FRAME','duplicate_pose':'POSE REPEATED: MOVE BOARD',
                'waiting_interval':'WAIT CAPTURE INTERVAL','auto_disabled':'AUTO DISABLED',
                'auto_captured':'AUTO CAPTURED','manual_captured':'MANUAL CAPTURED',
                'capture_failed':'IMAGE WRITE FAILED','ready':'READY'}
        area=lambda side:number(None if cur.get('area_ratio_'+side) is None else cur['area_ratio_'+side]*100,'%')
        lines = [
            f'CALIBRATION | AUTO capture {"ON" if self.auto_capture else "OFF"} | {states.get(cur.get("capture_reason"),"WAIT DETECTION")}',
            f'Board detected L={"YES" if cur.get("detected_left") else "NO"} R={"YES" if cur.get("detected_right") else "NO"} | effective BOTH detections={number(cur.get("effective_detection_hz"),"Hz")} | cal loop={number(cur.get("calibration_loop_hz"),"Hz")}',
            f'SB detector cost L={number(cur.get("detector_left_ms"),"ms")} R={number(cur.get("detector_right_ms"),"ms")} | board area L={area("left")} R={area("right")} (min {self.min_area_ratio*100:.2f}%)',
            f'Corner motion L={number(cur.get("motion_left_px"),"px")} R={number(cur.get("motion_right_px"),"px")} | limit={self.stable_corner_motion_px:g}px | order L={cur.get("order_left","n/a")} R={cur.get("order_right","n/a")}',
            f'Coherent drift L={number(cur.get("drift_left_px"),"px")} R={number(cur.get("drift_right_px"),"px")} | guard={max(.5,self.stable_corner_motion_px*.25):.2f}px + trend fit >=80% | motion check={cur.get("motion_cause") or "none"}',
            f'Stable observed time={cur.get("stable_dwell_s",0):.2f}/{self.stable_dwell_s:g}s | observations={cur.get("stability_observations",0)}/{self.stable_min_frames} | progress={cur.get("stability_progress",0)*100:.0f}% | loss timeout={cur.get("stability_gap_limit_s",self.stable_loss_grace_s):.2f}s | reset={cur.get("stability_reset_reason") or "none"}',
            f'Capture interval remaining={cur.get("interval_remaining_s",0):.2f}s | pose distance={number(cur.get("pose_distance"))} (min {self.diversity_threshold:g}) | SPACE manual={"READY" if manual_ready else "WAIT"}',
            f'pairs={len(self.samples)}/{self.target_pairs} | R solve={"READY" if self.can_solve() else f"WAIT SAMPLES ({len(self.samples)}/{self.min_pairs})"} | readiness*={self.readiness():.0f}/100',
            f"host grab skew: {skew_text}  (NOT sensor exposure skew)",
            "SPACE=FORCE CAPTURE(size+visibility only)   R=solve   X=discard   C=return",
            "* readiness is heuristic; final metrics: Stereo RMS + epipolar error",
        ]
        if self.last_capture_notice and (self._current_timestamp or 0)<=self._notice_until:
            lines.insert(8,self.last_capture_notice)
        panel=np.zeros((len(lines)*24+18,canvas.shape[1],3),np.uint8)
        for i,line in enumerate(lines):
            cv2.putText(
                panel,line,(14,25+i*24),cv2.FONT_HERSHEY_SIMPLEX,
                .52 if i<8 else .43,(255,255,255),1,cv2.LINE_AA,
            )
        return cv2.vconcat([canvas,panel])
