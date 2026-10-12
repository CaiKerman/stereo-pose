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
from stereo_pose.app.measurements import measure_frame, make_readout, append_readout
from stereo_pose.app.world_setup import run_world_setup
from stereo_pose.calibration.package import load_readout_registration, activate_calibration, file_sha256, read_bundle, validate_stereo_bundle
from stereo_pose.filtering import JointSmoother
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.joints import JOINT_INDEX, resolve_joints
from stereo_pose.diagnostics.joint_diagnostics import format_diagnostic_summary
from stereo_pose.diagnostics.snapshot import SnapshotPose, save_snapshot
from stereo_pose.models import FilteredJoint3D, FrameDiagnostics, FrameTiming, JointQuality, PoseFrame
from stereo_pose.outputs import build_publisher
from stereo_pose.outputs.csv_recorder import CsvRecorder
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


def build_menu_lines(
    menu_expanded,
    *,
    camera_left,
    camera_right,
    device,
    cal_state,
    accepted_total,
    selected_total,
    rejected_total,
    fps_txt,
    grab_txt,
    rms_txt,
    epi_txt,
    reproj_txt,
    skew_txt,
    smooth_txt,
    one_euro_min,
    one_euro_beta,
    one_euro_d,
    alarms,
):
    """Return the status lines to draw for the tracking overlay.

    Collapsed (default) keeps only camera indexes, calibration state, accepted
    joint count, FPS, live alarms and a compact ``M: Developer tools`` hint.
    Expanded adds the full hotkey row and smoothing internals.

    Review B4: ``fps_txt`` is the measured FULL-loop frame rate (capture +
    inference + triangulation + publish + render), never the camera grab
    cycle; the grab-only period is shown separately as ``grab_txt`` so the two
    can no longer be confused. Warnings are ALWAYS prepended in both the
    collapsed and the expanded view so opening the developer menu can never
    hide a live alarm.
    """
    lines = (
        [
            f"LEFT={camera_left}  RIGHT={camera_right} | {cal_state} | "
            f"joints={accepted_total}/{selected_total} | {fps_txt} | M: Developer tools",
        ]
        if not menu_expanded
        else [
            f"TRACKING | device={device} | {cal_state} | "
            f"accepted={accepted_total}/{selected_total} rejected={rejected_total} | {fps_txt} | {grab_txt}",
            f"Stereo RMS={rms_txt} | epi={epi_txt} | reproj={reproj_txt}",
            f"host grab skew={skew_txt} (not exposure skew) | {smooth_txt}",
            f"OneEuro min_cutoff={one_euro_min:g} beta={one_euro_beta:g} d_cutoff={one_euro_d:g}",
            "S=snapshot  D=joint reasons  V=validate  C=calibrate  P=pin  G=cleanup  F=smoothing  M=collapse  Q/ESC=quit",
        ]
    )
    return list(alarms) + lines


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
            protected_files=[s.get("explicit_file")] if s.get("load") == "explicit" else [],
        )

    device = resolve_device(p["device"])
    selected_joints = resolve_joints(o["joint_group"], o.get("joints") or None)
    readout_joints = list(dict.fromkeys(["left_eye", "right_eye", "eye_midpoint"] +
        resolve_joints(cfg["readout"]["joint_group"], cfg["readout"].get("joints") or None)))
    registration = None
    world_warnings = []
    active_artifact_sha = None

    calib_path = None
    triangulator = None
    try:
        explicit = s.get("explicit_file") if s.get("load") == "explicit" else None
        calib_path = newest_calibration(s["calibration_dir"], explicit)
        if s.get("load") == "explicit" and s.get("active_sha256") and file_sha256(calib_path) != s["active_sha256"]:
            raise ValueError("selected calibration SHA-256 mismatch; reselect known artifact, no fallback")
        validate_stereo_bundle(read_bundle(calib_path))
        triangulator = StereoTriangulator(calib_path)
        active_artifact_sha = file_sha256(calib_path)
    except (FileNotFoundError, ValueError, OSError) as e:
        calib_path = None
        triangulator = None
        active_artifact_sha = None
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

    if calib_path is not None:
        registration, world_warnings = load_readout_registration(calib_path, active_size)
        for warning in world_warnings: print("[world]", warning)
        if registration is not None:
            if registration['metadata'].get('mode') == 'camera_midpoint':
                print("[coordinates] DEFAULT camera_midpoint: optical-center midpoint=0; +X forward, +Y right->left, +Z assumed up (level/upright cameras; W=physical alignment)")
            else:
                print("[world] RESTORED", registration["name"], "| confirm physical cameras/mounting unchanged; file/index cannot prove this")

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
        "D=diagnostics | V=validate board | S=snapshot | M=dev menu | W=world/zero | T=CSV | Q/ESC=quit"
    )
    print("Calibration: AUTO waits for STABLE | SPACE=manual force capture | R=solve | X=discard | C=return\n")

    recorder = CsvRecorder(cfg["recording"]["output_dir"], runtime_root,
        sample_rate_hz=cfg["recording"]["sample_rate_hz"],
        include_candidates=cfg["recording"]["include_rejected_candidates"])

    frame_index = 0
    kp_conf = float(p["keypoint_confidence"])
    alternate_grab = bool(c.get("alternate_grab_order", True))
    diagnostics_enabled = bool(d.get("enabled", False))
    diag_every = max(1, int(d.get("every_n_frames", 10)))
    menu_expanded = False
    # Review B4: full-loop FPS. ``pair_cycle_ms`` only times the camera
    # grab/retrieve pair; presenting 1000/pair_cycle_ms as "fps" overstated
    # the real rate because it excluded inference, triangulation, publishing,
    # rendering and the waitKey delay. We measure the whole loop iteration
    # instead (capture -> inference -> publish -> render -> waitKey) and show
    # a small EMA so the overlay does not flicker frame to frame.
    prev_loop_ns = None
    loop_ema_ms = None

    try:
        while True:
            loop_ns = time.perf_counter_ns()
            if prev_loop_ns is not None:
                cycle_ms = (loop_ns - prev_loop_ns) / 1e6
                loop_ema_ms = cycle_ms if loop_ema_ms is None else (
                    0.85 * loop_ema_ms + 0.15 * cycle_ms
                )
            prev_loop_ns = loop_ns

            ok, fl, fr, pair_timing = read_stereo_pair(
                left, right,
                alternate_order=alternate_grab,
                frame_index=frame_index,
            )
            if not ok:
                raise RuntimeError("Camera pair read failed")

            if registration is not None and ((fl.shape[1], fl.shape[0]) != tuple(active_size) or
                                              (fr.shape[1], fr.shape[0]) != tuple(active_size)):
                recorder.stop("capture_resolution_changed")
                registration = None
                world_warnings = ["WORLD INVALID: capture resolution changed; recalibrate C -> R, then W"]

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
                            registration, world_warnings = load_readout_registration(calib_path, active_size)
                            active_artifact_sha = file_sha256(calib_path)
                            print("[coordinates] prior world cleared after stereo solve; default camera midpoint active when available; W=re-register world")
                            try:
                                s.update(activate_calibration(args.config, calib_path))
                            except Exception as selection_error:
                                print("[calibration] active for this run only; preference save failed:", selection_error)
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
                                    protected_files=[calib_path],
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
            pts_l, cf_l, chosen_l, count_l = estimator.best_person(res_l)
            pts_r, cf_r, chosen_r, count_r = estimator.best_person(res_r)

            frame, all_accepted, all_verdicts, geometries = measure_frame(
                selected_joints=selected_joints, readout_joints=readout_joints,
                triangulator=triangulator, points_left=pts_l, points_right=pts_r,
                conf_left=cf_l, conf_right=cf_r, kp_conf=kp_conf, qcfg=qcfg,
                speed_gate=speed_gate, smoother=smoother, t_s=t_filter_s,
                frame_index=frame_index, wall_timestamp_ns=wall_timestamp_ns,
                pair_timing=pair_timing, calib_path=calib_path)
            joints = frame.joints
            diagnostics = frame.diagnostics
            verdicts = diagnostics.joints
            rejected = frame.frame_quality["rejected"]
            mean_epi = frame.frame_quality["mean_epipolar_error_px"]
            mean_reproj = frame.frame_quality["mean_reprojection_error_px"]
            readout_rows = make_readout(readout_joints, all_accepted, all_verdicts, geometries, registration)
            publisher.publish(to_v1_message(frame))
            recorder.sample(frame, readout_rows)

            if diagnostics_enabled and frame_index % diag_every == 0:
                print(format_diagnostic_summary(frame_index, diagnostics))

            vl, vr = resize_pair(res_l.plot(), res_r.plot(), target_h=360)
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

            cal_state = "calib=OK" if triangulator is not None else "calib=NONE"
            cycle = pair_timing.get("pair_cycle_ms")
            # Review B4: fps shows the measured FULL processing-loop rate;
            # the camera grab pair period is reported separately below.
            fps_txt = f"{1000.0 / loop_ema_ms:.0f}fps" if loop_ema_ms else "fps n/a"
            grab_txt = "grab n/a" if not cycle else f"grab={float(cycle):.0f}ms"
            smooth_txt = "F:smoothing ON" if smoother.enabled else "F:smoothing OFF"

            alarms = []
            if triangulator is None:
                alarms.append("! no stereo calibration loaded (C -> R)")
            if mean_epi is not None and mean_epi > 3.0:
                alarms.append(f"! mean epipolar {mean_epi:.1f}px > 3px gate")

            overlay_status(canvas, build_menu_lines(
                menu_expanded,
                camera_left=c["left"],
                camera_right=c["right"],
                device=device,
                cal_state=cal_state,
                accepted_total=len(joints),
                selected_total=len(verdicts),
                rejected_total=rej_total,
                fps_txt=fps_txt,
                grab_txt=grab_txt,
                rms_txt=rms,
                epi_txt=epi_txt,
                reproj_txt=rep_txt,
                skew_txt=skew_txt,
                smooth_txt=smooth_txt,
                one_euro_min=smoother.min_cutoff,
                one_euro_beta=smoother.beta,
                one_euro_d=smoother.d_cutoff,
                alarms=alarms,
            ))
            canvas = append_readout(canvas, readout_rows, registration, recorder.status(), world_warnings=world_warnings)
            cv2.imshow("Stereo Pose 3D", canvas)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("c"), ord("C")):
                recorder.stop("enter_calibration")
                calibrator.start()
            elif key in (ord("f"), ord("F")):
                recorder.stop("filter_changed")
                enabled = smoother.toggle()
                smoother.reset()
                speed_gate.reset()
                print(f"[filter] One Euro smoothing {'ON' if enabled else 'OFF'}")
            elif key in (ord("g"), ord("G")):
                try:
                    cleanup_project(
                        s["calibration_dir"], cr["session_dir"],
                        runtime_root=runtime_root,
                        keep_latest=cl.get("keep_latest_calibrations", 10),
                        failed_days=cl.get("delete_failed_sessions_older_days", 7),
                        verbose=True,
                        protected_files=[calib_path],
                    )
                except Exception as e:
                    print("[cleanup] refused/failed; tracking continues:", e)
            elif key in (ord("p"), ord("P")):
                if calib_path is not None:
                    try:
                        saved = promote_calibration(calib_path, s["calibration_dir"], source="promoted")
                        print(f"[calibration] pinned current calibration -> {saved}")
                    except Exception as e:
                        print(f"[calibration] pin failed: {e}")
                else:
                    print("[calibration] no active calibration to pin")
            elif key in (ord("w"), ord("W")):
                recorder.stop("world_setup")
                if triangulator is None:
                    print("[world] create/load stereo calibration first (C -> R)")
                else:
                    try:
                        new_path = run_world_setup(frame_left=fl, frame_right=fr, triangulator=triangulator,
                            calib_path=calib_path, config_path=args.config, cfg=cfg, registration=registration)
                        if new_path is not None:
                            # Setup saves+activates atomically before exposing the new frame.
                            calib_path = new_path
                            active_artifact_sha = file_sha256(new_path)
                            triangulator = StereoTriangulator(new_path)
                            s.update(load_config(args.config)["stereo"])
                            registration, world_warnings = load_readout_registration(new_path, active_size)
                    except Exception as e:
                        print("[world] setup failed; previous active retained:", e)
            elif key in (ord("t"), ord("T")):
                if recorder.active:
                    path = recorder.stop("manual")
                    print(f"[recording] STOPPED samples={recorder.samples} -> {path}")
                elif not cfg["recording"]["enabled"] or not cfg["recording"]["save_csv"]:
                    print("[recording] CSV disabled by config")
                elif calib_path is None:
                    print("[recording] load/create a stereo calibration first")
                else:
                    try:
                        if file_sha256(calib_path) != active_artifact_sha:
                            raise ValueError("active NPZ changed on disk; reselect/re-register before recording")
                        world_metadata = None if registration is None else {
                            "name": registration["name"], "R_wc": registration["transform"].R.tolist(),
                            "t_wc_mm": registration["transform"].t.tolist(), "definition": registration["metadata"]}
                        path = recorder.start({
                            "calibration_file": str(calib_path), "calibration_sha256": active_artifact_sha,
                            "coordinate_frame": "rectified_left_camera" if registration is None else registration["name"],
                            "source_frame": "rectified_left_camera", "world": world_metadata,
                            "model": str(p["model"]), "device": str(device), "camera": dict(c), "actual_image_size": list(active_size),
                            "actual_image_size_left": [fl.shape[1], fl.shape[0]],
                            "actual_image_size_right": [fr.shape[1], fr.shape[0]],
                            "timing_note": "host timing only; not sensor exposure timestamps",
                            "quality": dict(qcfg), "filtering": {**dict(scfg), "enabled": bool(smoother.enabled)},
                            "selected_joints": list(readout_joints), "pose": dict(p)})
                        print(f"[recording] STARTED at {cfg['recording']['sample_rate_hz']:g}Hz (export sampling) -> {path}")
                    except Exception as e:
                        print("[recording] start failed; tracking continues:", e)
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
            elif key in (ord("m"), ord("M")):
                menu_expanded = not menu_expanded
                print(f"[menu] developer overlay {'expanded' if menu_expanded else 'collapsed'}")
            elif key in (ord("s"), ord("S")):
                try:
                    snap_left = SnapshotPose(
                        detections=int(count_l),
                        chosen_person_index=chosen_l,
                        keypoints=pts_l,
                        confidence=cf_l,
                    )
                    snap_right = SnapshotPose(
                        detections=int(count_r),
                        chosen_person_index=chosen_r,
                        keypoints=pts_r,
                        confidence=cf_r,
                    )
                    snap_dir = save_snapshot(
                        runtime_root=runtime_root,
                        frame_index=frame_index,
                        wall_timestamp_ns=wall_timestamp_ns,
                        pair_timing=pair_timing,
                        camera_left=c["left"],
                        camera_right=c["right"],
                        backend=c["backend"],
                        requested_size=(int(c["width"]), int(c["height"])),
                        actual_size=active_size,
                        frame_left=fl,
                        frame_right=fr,
                        pose_left=snap_left,
                        pose_right=snap_right,
                        selected_joints=selected_joints,
                        verdicts=verdicts,
                        triangulator=triangulator,
                        calib_path=calib_path,
                        confidence_threshold=kp_conf,
                    )
                    print(f"[snapshot] saved -> {snap_dir}")
                    print(f"[snapshot] offline replay: python tools/inspect_snapshot.py {snap_dir}")
                except Exception as e:  # noqa: BLE001 — snapshot must never crash tracking
                    print(f"[snapshot] FAILED: {e}")
            elif key in (ord("q"), 27):
                break

            frame_index += 1

    finally:
        recorder.stop("app_exit")
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
             "are given; the confirmed choice is saved to the config; "
             "cancelling or failure aborts startup without opening cameras)",
    )
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = load_config(cfg_path if cfg_path.exists() else None)

    if getattr(args, "camera_pick", False) and not should_pick_cameras(args):
        print("[camera-pick] explicit --left-cam/--right-cam given; skipping interactive selection")
    elif should_pick_cameras(args):
        from stereo_pose.capture.selection import run_camera_selection

        try:
            choice = run_camera_selection(cfg_path)
        except Exception as e:  # noqa: BLE001 — surface, then fail closed
            print(f"[camera-pick] camera selection failed: {e}")
            print("[camera-pick] aborting startup — no stereo tracking started.")
            raise SystemExit(1)
        if choice is None:
            print("[camera-pick] camera selection cancelled or could not be saved.")
            print("[camera-pick] aborting startup — no stereo tracking started.")
            raise SystemExit(1)
        cfg = load_config(cfg_path)  # reload: the confirmed choice was persisted
        print(f"[camera-pick] cameras confirmed: LEFT={choice.left} RIGHT={choice.right}")

    run(args, cfg)


if __name__ == "__main__":
    main()
