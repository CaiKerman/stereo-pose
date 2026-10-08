"""Application orchestration: the live-camera pipeline (v1.2-equivalent).

This is the formal port of ``reference/v1_2/main.py``. It wires the typed
modules together while preserving the v1.2 runtime behavior and the
``stereo_pose_3d/v1.2`` output message.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from stereo_pose.calibration import (
    RuntimeCalibration,
    camera_identity_warnings,
    newest_calibration,
    validate_calibration_compatibility,
)
from stereo_pose.capture.camera import open_camera, read_stereo_pair
from stereo_pose.config import load_config
from stereo_pose.filtering import JointSmoother
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.joints import JOINT_INDEX, resolve_joints
from stereo_pose.diagnostics.joint_diagnostics import format_diagnostic_summary
from stereo_pose.models import FilteredJoint3D, FrameDiagnostics, FrameTiming, JointQuality, PoseFrame
from stereo_pose.outputs import build_publisher
from stereo_pose.outputs.v1_message import to_v1_message
from stereo_pose.persistence import cleanup_project, promote_calibration
from stereo_pose.pose import PoseEstimator, resolve_device
from stereo_pose.quality import TemporalSpeedGate, aggregate_bucket, classify_joint
from stereo_pose.validation import (
    MetricValidationError,
    compute_metric_validation,
    detect_checkerboard,
    render_summary,
    save_validation_report,
    timestamp_now,
)


def resize_pair(a, b, target_h=480):
    a2 = cv2.resize(a, (int(a.shape[1] * target_h / a.shape[0]), target_h))
    b2 = cv2.resize(b, (int(b.shape[1] * target_h / b.shape[0]), target_h))
    return a2, b2


def overlay_status(img, lines):
    y = img.shape[0] - 18 - (len(lines) - 1) * 25
    for line in lines:
        cv2.putText(
            img, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX,
            0.58, (255, 255, 255), 2, cv2.LINE_AA,
        )
        y += 25
    return img


def _capture_image_size(left, right, requested):
    """Return the actual capture resolution, falling back to the requested size."""
    def _size(cap):
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h) if w > 0 and h > 0 else None
    return _size(left) or _size(right) or (int(requested[0]), int(requested[1]))


def _actual_fps(cap):
    try:
        v = cap.get(cv2.CAP_PROP_FPS)
        return float(v) if v and v > 0 else None
    except Exception:
        return None


def _report_calibration_compatibility(calib_path, active_size, board, fps=None, camera_indexes=None):
    """Warn (never silently accept) when a calibration's recorded image size,
    board geometry, or FPS do not match the active capture / configuration.

    When ``camera_indexes`` (left, right) is given, camera-index identity is
    also checked and any mismatch is reported as a prominent banner: numeric
    index equality never proves physical camera identity, and an index change
    never deletes or rewrites the calibration — the operator decides whether
    the physical pairing is unchanged or a recalibration is needed.
    """
    try:
        warnings = validate_calibration_compatibility(calib_path, active_size, board, fps)
        for w in warnings:
            print(f"[warning] {w}")
    except Exception as e:  # noqa: BLE001
        print(f"[warning] could not load calibration metadata for {calib_path}: {e}")
    if camera_indexes is None:
        return
    try:
        identity = camera_identity_warnings(calib_path, camera_indexes[0], camera_indexes[1])
    except Exception as e:  # noqa: BLE001
        print(f"[warning] could not check calibration camera identity for {calib_path}: {e}")
        return
    if not identity:
        return
    print("=" * 72)
    print("CALIBRATION / CAMERA PAIRING WARNING")
    for w in identity:
        print(f"  - {w}")
    print("Camera indexes do NOT prove which physical cameras these are.")
    print("If the same two physical USB cameras and their mounting are unchanged,")
    print("the calibration may still be valid after re-selecting the new indexes.")
    print("If the devices, their LEFT/RIGHT order, or the rig geometry changed,")
    print("recalibrate (C -> R). The saved calibration file was NOT modified.")
    print("=" * 72)


def _run_metric_validation(triangulator, frame_l, frame_r, stereo_cfg, runtime_root, calib_path):
    """Detect the checkerboard in both cameras, triangulate, compute a metric
    report, and persist it under the managed ``runtime/validation`` root.

    Returns the saved report path, or ``None`` when detection failed.
    """
    cols = int(stereo_cfg["board_cols"])
    rows = int(stereo_cfg["board_rows"])
    square = float(stereo_cfg["square_mm"])

    corner_l = detect_checkerboard(frame_l, cols, rows)
    corner_r = detect_checkerboard(frame_r, cols, rows)
    if corner_l is None or corner_r is None:
        print(
            f"[validation] checkerboard not fully detected: "
            f"L={'ok' if corner_l is not None else 'missing'} "
            f"R={'ok' if corner_r is not None else 'missing'}"
        )
        return None

    try:
        result = compute_metric_validation(
            triangulator,
            corner_l,
            corner_r,
            board_cols=cols,
            board_rows=rows,
            square_mm=square,
            calibration_file=str(calib_path) if calib_path else None,
            timestamp=timestamp_now(),
        )
    except MetricValidationError as e:
        print(f"[validation] failed: {e}")
        return None
    saved = save_validation_report(result.to_dict(), runtime_root)
    print(render_summary(result))
    print(f"[validation] saved report -> {saved}")
    return saved


def run(args, cfg):
    c = cfg["camera"]
    p = cfg["pose"]
    s = cfg["stereo"]
    cr = cfg["calibration_runtime"]
    cl = cfg["cleanup"]
    qcfg = cfg["quality"]
    scfg = cfg["smoothing"]
    o = cfg["output"]
    r = cfg["runtime"]
    d = cfg.get("diagnostics", {})

    if args.left_cam is not None:
        c["left"] = args.left_cam
    if args.right_cam is not None:
        c["right"] = args.right_cam
    if args.device is not None:
        p["device"] = args.device
    if args.model is not None:
        p["model"] = args.model

    runtime_root = r.get("root")

    if cl.get("enabled", True):
        cleanup_project(
            s["calibration_dir"], cr["session_dir"],
            runtime_root=runtime_root,
            keep_latest=cl.get("keep_latest_calibrations", 10),
            failed_days=cl.get("delete_failed_sessions_older_days", 7),
            verbose=True,
        )

    device = resolve_device(p["device"])
    selected_joints = resolve_joints(o["joint_group"], o.get("joints") or None)

    calib_path = None
    triangulator = None
    try:
        explicit = s.get("explicit_file") if s.get("load") == "explicit" else None
        calib_path = newest_calibration(s["calibration_dir"], explicit)
        triangulator = StereoTriangulator(calib_path)
    except FileNotFoundError as e:
        print(f"[warning] {e}")
        print("[warning] 3D output disabled until you create a calibration with C -> R.")

    fourcc = c.get("fourcc", "MJPG")
    buffer_size = c.get("buffer_size", 1)
    left = open_camera(c["left"], c["width"], c["height"], c["fps"], c["backend"], fourcc=fourcc, buffer_size=buffer_size)
    right = open_camera(c["right"], c["width"], c["height"], c["fps"], c["backend"], fourcc=fourcc, buffer_size=buffer_size)
    estimator = PoseEstimator(p["model"], device, p["detection_confidence"])
    publisher = build_publisher(o)
    calibrator = RuntimeCalibration(s, cr)

    active_size = _capture_image_size(left, right, (c["width"], c["height"]))
    calibrator.set_camera_context(
        left_index=c["left"],
        right_index=c["right"],
        backend=c["backend"],
        requested_size=(int(c["width"]), int(c["height"])),
        requested_fps=float(c["fps"]),
        actual_fps=_actual_fps(left),
    )
    if calib_path is not None:
        _report_calibration_compatibility(
            calib_path, active_size, (s["board_cols"], s["board_rows"]),
            fps=float(c.get("fps")) if c.get("fps") else None,
            camera_indexes=(c["left"], c["right"]),
        )

    smoother = JointSmoother(
        enabled=scfg.get("enabled", True),
        min_cutoff=scfg.get("min_cutoff", 1.2),
        beta=scfg.get("beta", 0.015),
        d_cutoff=scfg.get("d_cutoff", 1.0),
        reset_after_s=scfg.get("reset_after_s", 0.6),
    )
    speed_gate = TemporalSpeedGate(
        max_speed_mm_s=qcfg.get("max_joint_speed_mm_s", 6000.0),
        reset_after_s=qcfg.get("speed_gate_reset_after_s", 0.6),
    )

    print("\nStereo Pose 3D v1.2")
    print(f"LEFT={c['left']} RIGHT={c['right']} DEVICE={device}")
    print(f"Calibration={calib_path if calib_path else 'NONE'}")
    print(
        "Pairing=grab both -> retrieve both. Host skew is diagnostic only; "
        "commodity webcam exposure timing is not hardware-synchronised."
    )
    print(
        "Hotkeys: C=calibration | F=smoothing on/off | G=cleanup | P=pin calib | "
        "D=diagnostics | V=validate board | Q/ESC=quit"
    )
    print("Calibration: AUTO waits for STABLE | SPACE=manual force capture | R=solve | X=discard | C=return\n")

    frame_index = 0
    kp_conf = float(p["keypoint_confidence"])
    alternate_grab = bool(c.get("alternate_grab_order", True))
    diagnostics_enabled = bool(d.get("enabled", False))
    diag_every = max(1, int(d.get("every_n_frames", 10)))

    try:
        while True:
            ok, fl, fr, pair_timing = read_stereo_pair(
                left, right,
                alternate_order=alternate_grab,
                frame_index=frame_index,
            )
            if not ok:
                raise RuntimeError("Camera pair read failed")

            t_filter_s = pair_timing.get("host_midpoint_perf_ns", time.perf_counter_ns()) / 1e9
            wall_timestamp_ns = pair_timing.get("wall_timestamp_ns", time.time_ns())

            if calibrator.active:
                calibrator.process(fl, fr, force_capture=False)
                pl, pr = resize_pair(fl, fr)
                canvas = cv2.hconcat([pl, pr])
                calibrator.draw_overlay(canvas, pair_timing)
                cv2.imshow("Stereo Pose 3D", canvas)
                key = cv2.waitKey(1) & 0xFF

                if key == ord(" "):
                    calibrator.process(fl, fr, force_capture=True)
                elif key in (ord("r"), ord("R")):
                    if not calibrator.can_solve():
                        print(
                            f"[calibration] not enough samples: "
                            f"{len(calibrator.samples)}/{calibrator.min_pairs}"
                        )
                    else:
                        if calibrator.readiness() < calibrator.recommended_readiness:
                            print(
                                f"[calibration] warning: readiness={calibrator.readiness():.0f}/100 "
                                f"(< recommended {calibrator.recommended_readiness:.0f}); solving anyway"
                            )
                        try:
                            result = calibrator.solve()
                            triangulator = StereoTriangulator(result["path"])
                            calib_path = result["path"]
                            smoother.reset()
                            speed_gate.reset()
                            print(f"[calibration] ACTIVE switched to {calib_path}")
                            print(f"[calibration] T(mm)={result['T']}")
                            print(
                                f"[calibration] Stereo RMS={result['stereo_rms']:.4f}; "
                                f"sample epipolar mean/max={result['sample_epipolar_mean_px']:.3f}/"
                                f"{result['sample_epipolar_max_px']:.3f}px"
                            )
                            _report_calibration_compatibility(
                                calib_path, active_size, (s["board_cols"], s["board_rows"]),
                                fps=float(c.get("fps")) if c.get("fps") else None,
                                camera_indexes=(c["left"], c["right"]),
                            )
                            if cl.get("enabled", True):
                                cleanup_project(
                                    s["calibration_dir"], cr["session_dir"],
                                    runtime_root=runtime_root,
                                    keep_latest=cl.get("keep_latest_calibrations", 10),
                                    failed_days=cl.get("delete_failed_sessions_older_days", 7),
                                    verbose=True,
                                )
                        except Exception as e:
                            print(f"[calibration] solve failed: {e}")
                elif key in (ord("x"), ord("X")):
                    calibrator.discard()
                elif key in (ord("c"), ord("C")):
                    calibrator.stop_without_delete()
                elif key in (ord("q"), 27):
                    break

                frame_index += 1
                continue

            res_l, res_r = estimator.infer_pair(fl, fr)
            pts_l, cf_l = estimator.best_person_keypoints(res_l)
            pts_r, cf_r = estimator.best_person_keypoints(res_r)

            joints = {}
            rejected = {
                "keypoint_confidence": 0,
                "geometry": 0,
                "depth": 0,
                "quality_score": 0,
                "speed": 0,
            }
            current_epi = []
            current_reproj = []

            missing_pose = pts_l is None or pts_r is None
            verdicts = []

            for name in selected_joints:
                if triangulator is None or missing_pose:
                    verdicts.append(
                        classify_joint(
                            name,
                            conf_l=0.0,
                            conf_r=0.0,
                            keypoint_confidence=kp_conf,
                            geometry=None,
                            qcfg=qcfg,
                            missing_pose=missing_pose,
                            calibration_available=triangulator is not None,
                        )
                    )
                    continue

                i = JOINT_INDEX[name]
                geom = None
                if cf_l[i] >= kp_conf and cf_r[i] >= kp_conf:
                    geom = triangulator.triangulate_with_quality(pts_l[i], pts_r[i])
                    if geom is not None:
                        current_epi.append(float(geom["epipolar_error_px"]))
                        current_reproj.append(float(geom["reprojection_error_max_px"]))

                verdict = classify_joint(
                    name,
                    conf_l=float(cf_l[i]),
                    conf_r=float(cf_r[i]),
                    keypoint_confidence=kp_conf,
                    geometry=geom,
                    qcfg=qcfg,
                )

                if verdict.accepted:
                    raw_xyz = np.asarray(geom["xyz_mm"], dtype=float)
                    speed_ok, speed = speed_gate.check(name, raw_xyz, t_filter_s)
                    if not speed_ok:
                        verdict = classify_joint(
                            name,
                            conf_l=float(cf_l[i]),
                            conf_r=float(cf_r[i]),
                            keypoint_confidence=kp_conf,
                            geometry=geom,
                            qcfg=qcfg,
                            speed_result=(False, speed),
                        )
                    else:
                        verdict.metrics["speed_mm_s"] = float(speed)
                        filtered_xyz = smoother.update(name, raw_xyz, t_filter_s)
                        epi = float(geom["epipolar_error_px"])
                        rep = float(geom["reprojection_error_max_px"])
                        quality = JointQuality(
                            score=float(verdict.metrics["score"]),
                            epipolar_error_px=epi,
                            reprojection_error_mean_px=float(geom["reprojection_error_mean_px"]),
                            reprojection_error_max_px=rep,
                            speed_mm_s=float(speed),
                        )
                        joint = FilteredJoint3D(
                            joint_name=name,
                            xyz_mm=[float(x) for x in filtered_xyz],
                            xyz_raw_mm=[float(x) for x in raw_xyz],
                            quality=quality,
                            confidence_left=float(cf_l[i]),
                            confidence_right=float(cf_r[i]),
                            uv_left=(float(pts_l[i][0]), float(pts_l[i][1])),
                            uv_right=(float(pts_r[i][0]), float(pts_r[i][1])),
                            rectified_uv_left=(float(geom["rectified_uv_left"][0]), float(geom["rectified_uv_left"][1])),
                            rectified_uv_right=(float(geom["rectified_uv_right"][0]), float(geom["rectified_uv_right"][1])),
                        )
                        joints[name] = joint

                coarse = aggregate_bucket(verdict.state)
                if coarse:
                    rejected[coarse] += 1
                verdicts.append(verdict)

            mean_epi = float(np.mean(current_epi)) if current_epi else None
            mean_reproj = float(np.mean(current_reproj)) if current_reproj else None

            accepted_count = sum(1 for v in verdicts if v.accepted)
            fine_aggregate = {}
            for v in verdicts:
                if not v.accepted:
                    fine_aggregate[v.state] = fine_aggregate.get(v.state, 0) + 1

            diagnostics = FrameDiagnostics(
                selected_joint_count=len(verdicts),
                accepted_count=accepted_count,
                rejected_count=len(verdicts) - accepted_count,
                joints=verdicts,
                aggregate=fine_aggregate,
            )

            timing = FrameTiming.from_dict(pair_timing)
            frame = PoseFrame(
                frame_index=frame_index,
                wall_timestamp_ns=wall_timestamp_ns,
                coordinate_system="rectified_left_camera",
                unit="mm",
                calibration_file=str(calib_path) if calib_path else None,
                timing=timing,
                filtering={
                    "enabled": bool(smoother.enabled),
                    "type": "one_euro",
                    "min_cutoff": smoother.min_cutoff,
                    "beta": smoother.beta,
                    "d_cutoff": smoother.d_cutoff,
                },
                frame_quality={
                    "accepted_joints": len(joints),
                    "rejected": rejected,
                    "mean_epipolar_error_px": mean_epi,
                    "mean_reprojection_error_px": mean_reproj,
                },
                joints=joints,
                diagnostics=diagnostics,
            )
            publisher.publish(to_v1_message(frame))

            if diagnostics_enabled and frame_index % diag_every == 0:
                print(format_diagnostic_summary(frame_index, diagnostics))

            vl, vr = resize_pair(res_l.plot(), res_r.plot())
            canvas = cv2.hconcat([vl, vr])
            rms = (
                f"{triangulator.stereo_rms:.4f}"
                if triangulator is not None and triangulator.stereo_rms is not None
                else "n/a"
            )
            epi_txt = "n/a" if mean_epi is None else f"{mean_epi:.2f}px"
            rep_txt = "n/a" if mean_reproj is None else f"{mean_reproj:.2f}px"
            skew = pair_timing.get("host_grab_skew_ms")
            skew_txt = "n/a" if skew is None else f"{skew:.2f}ms"
            rej_total = sum(rejected.values())

            overlay_status(canvas, [
                f"TRACKING | device={device} | accepted={len(joints)} rejected={rej_total}",
                f"Stereo RMS={rms} | epi={epi_txt} | reproj={rep_txt}",
                f"host grab skew={skew_txt} (not exposure skew) | smoothing={'ON' if smoother.enabled else 'OFF'}",
                f"OneEuro min_cutoff={smoother.min_cutoff:g} beta={smoother.beta:g} d_cutoff={smoother.d_cutoff:g}",
                f"C=calibrate  F=filter  G=cleanup  P=pin  D=diag{' ON' if diagnostics_enabled else ''}  V=validate  Q/ESC=quit",
            ])
            cv2.imshow("Stereo Pose 3D", canvas)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("c"), ord("C")):
                calibrator.start()
            elif key in (ord("f"), ord("F")):
                enabled = smoother.toggle()
                smoother.reset()
                speed_gate.reset()
                print(f"[filter] One Euro smoothing {'ON' if enabled else 'OFF'}")
            elif key in (ord("g"), ord("G")):
                cleanup_project(
                    s["calibration_dir"], cr["session_dir"],
                    runtime_root=runtime_root,
                    keep_latest=cl.get("keep_latest_calibrations", 10),
                    failed_days=cl.get("delete_failed_sessions_older_days", 7),
                    verbose=True,
                )
            elif key in (ord("p"), ord("P")):
                if calib_path is not None:
                    try:
                        saved = promote_calibration(calib_path, s["calibration_dir"], source="promoted")
                        print(f"[calibration] pinned current calibration -> {saved}")
                    except Exception as e:
                        print(f"[calibration] pin failed: {e}")
                else:
                    print("[calibration] no active calibration to pin")
            elif key in (ord("d"), ord("D")):
                diagnostics_enabled = not diagnostics_enabled
                print(f"[diagnostics] per-joint view {'ON' if diagnostics_enabled else 'OFF'}")
            elif key in (ord("v"), ord("V")):
                if triangulator is None:
                    print("[validation] no active calibration; run calibration first (C -> R)")
                else:
                    _run_metric_validation(
                        triangulator, fl, fr, s, runtime_root, calib_path
                    )
            elif key in (ord("q"), 27):
                break

            frame_index += 1

    finally:
        publisher.close()
        left.release()
        right.release()
        cv2.destroyAllWindows()


def should_pick_cameras(args) -> bool:
    """Whether ``main()`` should run the interactive camera picker.

    Precedence: explicit ``--left-cam``/``--right-cam`` CLI arguments win and
    suppress the picker entirely; ``--camera-pick`` opts into the interactive
    selection; without it (the default, noninteractive/automated path) nothing
    GUI-blocking ever opens.
    """
    if not getattr(args, "camera_pick", False):
        return False
    if args.left_cam is not None or args.right_cam is not None:
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Stereo camera real-time 3D pose tracker")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--left-cam", type=int)
    ap.add_argument("--right-cam", type=int)
    ap.add_argument("--device", help="auto / cpu / 0 / 1 ...")
    ap.add_argument("--model")
    ap.add_argument(
        "--camera-pick", action="store_true",
        help="run the visual camera discovery/LEFT-RIGHT selection before "
             "opening the stereo cameras (skipped when --left-cam/--right-cam "
             "are given; the confirmed choice is saved to the config)",
    )
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = load_config(cfg_path if cfg_path.exists() else None)

    if getattr(args, "camera_pick", False) and not should_pick_cameras(args):
        print("[camera-pick] explicit --left-cam/--right-cam given; skipping interactive selection")
    elif should_pick_cameras(args):
        from stereo_pose.capture.selection import run_camera_selection

        run_camera_selection(cfg_path)
        cfg = load_config(cfg_path)  # reload: the confirmed choice was persisted

    run(args, cfg)


if __name__ == "__main__":
    main()