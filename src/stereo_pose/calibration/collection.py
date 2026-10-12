"""Runtime stereo calibration collection and solver.

Ported faithfully from the validated v1.2 reference
(``reference/v1_2/stereo_pose/calibration.py``). ``readiness`` is a heuristic
sample-preparation score, not a statistical confidence.
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
        self.robust_prune = bool(runtime_cfg.get("robust_prune", True))
        self.prune_min_epipolar_px = float(runtime_cfg.get("prune_min_epipolar_px", 0.8))
        self.prune_max_epipolar_px = float(runtime_cfg.get("prune_max_epipolar_px", 2.5))
        self.max_prune_fraction = float(runtime_cfg.get("max_prune_fraction", 0.25))

        self.active = False
        self.session_dir = None
        self.left_dir = None
        self.right_dir = None
        self.samples = []
        self.last_capture_t = 0.0
        self.current = None
        self.stability_history = deque()
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
        self.session_dir = self.session_root / f"session_{stamp}"
        self.left_dir = self.session_dir / "left"
        self.right_dir = self.session_dir / "right"
        self.left_dir.mkdir(parents=True, exist_ok=True)
        self.right_dir.mkdir(parents=True, exist_ok=True)
        self.samples = []
        self.last_capture_t = 0.0
        self.current = None
        self.stability_history.clear()
        self.active = True
        print(f"[calibration] session started: {self.session_dir}")

    def discard(self):
        if self.session_dir and self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)
        self.active = False
        self.samples = []
        self.current = None
        self.stability_history.clear()
        print("[calibration] current session discarded")

    def stop_without_delete(self):
        self.active = False
        self.stability_history.clear()
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
        return np.array([
            det["center"][0],
            det["center"][1],
            min(1.0, math.sqrt(max(det["area_ratio"], 0.0)) * 2.5),
            det["angle_deg"] / 60.0,
        ], dtype=np.float32)

    def _is_diverse(self, dl, dr):
        desc = np.concatenate([self._descriptor(dl), self._descriptor(dr)])
        if not self.samples:
            return True
        prev = np.stack([s["descriptor"] for s in self.samples])
        d = np.linalg.norm(prev - desc[None, :], axis=1)
        return float(d.min()) >= self.diversity_threshold

    def _update_stability(self, now, dl, dr):
        if dl is None or dr is None:
            self.stability_history.clear()
            return False, None, 0.0

        self.stability_history.append((now, dl["corners"].copy(), dr["corners"].copy()))

        horizon = max(self.stable_dwell_s * 1.4, self.stable_dwell_s + 0.2)
        while self.stability_history and (now - self.stability_history[0][0]) > horizon:
            self.stability_history.popleft()

        if len(self.stability_history) < self.stable_min_frames:
            return False, None, 0.0

        recent = [x for x in self.stability_history if (now - x[0]) <= self.stable_dwell_s]
        if len(recent) < self.stable_min_frames:
            return False, None, 0.0
        dwell = recent[-1][0] - recent[0][0]
        if dwell < self.stable_dwell_s * 0.80:
            return False, None, dwell

        ref_l = recent[0][1]
        ref_r = recent[0][2]
        motion_l = max(float(np.mean(np.linalg.norm(x[1] - ref_l, axis=1))) for x in recent)
        motion_r = max(float(np.mean(np.linalg.norm(x[2] - ref_r, axis=1))) for x in recent)
        worst = max(motion_l, motion_r)
        stable = worst <= self.stable_corner_motion_px
        return stable, worst, dwell

    def _save(self, frame_l, frame_r, dl, dr, stability_motion_px):
        i = len(self.samples)
        lp = self.left_dir / f"{i:03d}.png"
        rp = self.right_dir / f"{i:03d}.png"
        cv2.imwrite(str(lp), frame_l)
        cv2.imwrite(str(rp), frame_r)
        self.samples.append({
            "left": dl,
            "right": dr,
            "descriptor": np.concatenate([self._descriptor(dl), self._descriptor(dr)]),
            "left_path": lp,
            "right_path": rp,
            "stability_motion_px": float(stability_motion_px or 0.0),
        })
        self.last_capture_t = time.monotonic()
        print(
            f"[calibration] captured pair {len(self.samples)} | "
            f"motion={float(stability_motion_px or 0.0):.2f}px | "
            f"readiness={self.readiness():.0f}/100"
        )

    def process(self, frame_l, frame_r, force_capture=False):
        now = time.monotonic()
        dl = self._detect(frame_l)
        dr = self._detect(frame_r)
        valid = dl is not None and dr is not None
        good_area = bool(
            valid
            and dl["area_ratio"] >= self.min_area_ratio
            and dr["area_ratio"] >= self.min_area_ratio
        )

        stable, motion_px, stable_dwell = self._update_stability(now, dl, dr)
        captured = False

        # SPACE is a true manual override: the operator decides whether the
        # checkerboard is physically still enough. We still require complete
        # detection in both cameras and a minimum useful board size.
        if force_capture and valid and good_area:
            self._save(frame_l, frame_r, dl, dr, motion_px)
            captured = True
        elif valid and good_area and stable:
            time_ok = (now - self.last_capture_t) >= self.interval
            diverse = self._is_diverse(dl, dr)
            if self.auto_capture and time_ok and diverse:
                self._save(frame_l, frame_r, dl, dr, motion_px)
                captured = True
        elif force_capture:
            print(
                "[calibration] manual capture rejected: board must be fully visible "
                "and large enough in BOTH cameras; automatic stillness is NOT required"
            )

        self.current = {
            "valid": valid,
            "good_area": good_area,
            "stable": bool(stable),
            "stability_motion_px": motion_px,
            "stable_dwell_s": float(stable_dwell),
            "area_ratio_left": None if dl is None else float(dl["area_ratio"]),
            "area_ratio_right": None if dr is None else float(dr["area_ratio"]),
            "captured": captured,
        }
        return self.current

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

        angles = [s[side]["angle_deg"] for s in self.samples for side in ("left", "right")]
        angle_span = max(angles) - min(angles) if len(angles) > 1 else 0.0
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
                initial_count - self.min_pairs,
            )
            bad = set(bad_order[:max(0, max_prune)])

            if bad:
                keep = [i for i in range(initial_count) if i not in bad]
                objpoints = [objpoints[i] for i in keep]
                img_l = [img_l[i] for i in keep]
                img_r = [img_r[i] for i in keep]
                paths = [paths[i] for i in keep]
                pruned_count = len(bad)
                solution = self._solve_core(objpoints, img_l, img_r, image_size)
                epi = self._sample_epipolar_errors(solution, img_l, img_r)
                print(
                    f"[calibration] robust prune removed {pruned_count} sample(s); "
                    f"remaining={len(objpoints)}"
                )

        epi_mean = float(np.mean(epi)) if len(epi) else float("nan")
        epi_max = float(np.max(epi)) if len(epi) else float("nan")

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
            "readiness": self.readiness(),
            "T": solution["T"].reshape(-1).astype(float),
        }

        if not self.keep_images and self.session_dir and self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)

        self.active = False
        self.stability_history.clear()
        print(
            f"[calibration] saved {out} | Stereo RMS={solution['stereo_rms']:.4f} | "
            f"sample epipolar mean/max={epi_mean:.3f}/{epi_max:.3f}px | "
            f"samples={len(objpoints)}"
        )
        return result

    def draw_overlay(self, canvas, pair_timing=None):
        cur = self.current or {}
        ready = self.readiness()
        motion = cur.get("stability_motion_px")
        motion_text = "n/a" if motion is None else f"{motion:.2f}px"
        area_l = cur.get("area_ratio_left")
        area_r = cur.get("area_ratio_right")
        area_text = (
            "n/a"
            if area_l is None or area_r is None
            else f"L={area_l * 100:.1f}% R={area_r * 100:.1f}%"
        )
        manual_ready = bool(cur.get("valid") and cur.get("good_area"))
        host_skew = None if pair_timing is None else pair_timing.get("host_grab_skew_ms")
        skew_text = "n/a" if host_skew is None else f"{host_skew:.2f}ms"

        if not cur.get("valid"):
            board_state = "NOT FOUND"
        elif not cur.get("good_area"):
            board_state = "TOO SMALL"
        elif cur.get("stable"):
            board_state = "STABLE / READY"
        else:
            board_state = "WAITING FOR STILLNESS"

        lines = [
            "CALIBRATION MODE - STATIC BOARD CAPTURE",
            f"pairs: {len(self.samples)}/{self.target_pairs}   readiness*: {ready:.0f}/100",
            f"board: {board_state}   area: {area_text}",
            f"corner motion: {motion_text}   SPACE manual={'READY' if manual_ready else 'WAIT'}",
            f"host grab skew: {skew_text}  (NOT sensor exposure skew)",
            "AUTO capture ON" if self.auto_capture else "AUTO capture OFF",
            "SPACE=FORCE CAPTURE(size+visibility only)   R=solve   X=discard   C=return",
            "* readiness is heuristic; final metrics: Stereo RMS + epipolar error",
        ]

        y = 34
        for i, line in enumerate(lines):
            cv2.putText(
                canvas, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX,
                0.72 if i < 6 else 0.48,
                (255, 255, 255), 2 if i < 6 else 1, cv2.LINE_AA,
            )
            y += 29 if i < 6 else 21
        return canvas
