"""Application orchestration: the live-camera pipeline (v1.2-equivalent).

This is the formal port of ``reference/v1_2/main.py``. It wires the typed
modules together while preserving the v1.2 runtime behavior and the
``stereo_pose_3d/v1.2`` output message.
"""

from __future__ import annotations

import argparse
import json
from contextlib import ExitStack
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
from stereo_pose.calibration.camera_settings import (camera_modes, compare_camera_modes,
                                                     load_camera_notes, save_camera_notes)
from stereo_pose.calibration.experiment import preview_pair
from stereo_pose.geometry.projection import rectify_stereo
from stereo_pose.capture.camera import open_camera, read_stereo_pair
from stereo_pose.config import load_config
from stereo_pose.app.measurements import measure_frame, make_readout, append_readout
from stereo_pose.app.world_setup import run_world_setup
from stereo_pose.app.desktop import create_display
from stereo_pose.app.presentation import tracking_view, calibration_view
from stereo_pose.calibration.package import load_readout_registration, activate_calibration, file_sha256, read_bundle, validate_stereo_bundle, export_calibration_npz
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


def inspect_npz_for_live_load(path, active_size, *, board, fps, camera_indexes):
    """Validate an operator-selected NPZ without altering running state/config.

    A saved NPZ is tied to capture resolution and physical LEFT/RIGHT rig.
    Resolution mismatch is a hard failure; index/FPS/board caveats are surfaced
    to the operator for explicit confirmation. The file is never rewritten.
    """
    candidate = Path(path).expanduser().resolve()
    if candidate.suffix.lower() != '.npz' or not candidate.is_file():
        raise ValueError('请选择已经存在的 .npz 双目标定文件')
    bundle = read_bundle(candidate)
    validate_stereo_bundle(bundle)
    if 'image_size' not in bundle:
        raise ValueError('NPZ 缺少 image_size，无法核对双摄分辨率；请重新标定或选择包含尺寸信息的文件')
    size = np.asarray(bundle['image_size']).reshape(-1)
    if size.size != 2 or not np.all(np.isfinite(size)) or np.any(size <= 0) or np.any(size != np.round(size)):
        raise ValueError('NPZ 中 image_size 无效，不能安全加载')
    image_size = tuple(int(v) for v in size)
    if image_size != tuple(active_size):
        raise ValueError(
            f'NPZ 标定分辨率 {image_size} 与当前双摄分辨率 {tuple(active_size)} 不一致；'
            '拒绝加载。请使用匹配的原始摄像头分辨率或重新标定。'
        )
    tri = StereoTriangulator(candidate)
    registration, world_warnings = load_readout_registration(candidate, active_size)
    warnings = validate_calibration_compatibility(candidate, active_size, board, fps)
    warnings.extend(camera_identity_warnings(candidate, camera_indexes[0], camera_indexes[1]))
    warnings.extend(world_warnings)
    return candidate, tri, registration, warnings, file_sha256(candidate)


def _camera_mode_issues(path, modes):
    if path is None:
        return [], []
    try:
        with np.load(path, allow_pickle=False) as archive:
            if 'capture_context_json' not in archive:
                return [], []
            return compare_camera_modes(json.loads(str(archive['capture_context_json'].item())), modes)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return [], [f'无法核对 NPZ 相机设置：{error}']


def _dataset_dialog(display, calibrator):
    chosen = display.choose_observation_file(calibrator.session_root)
    if chosen:
        calibrator.open_dataset(chosen)
        display.notify(f'已加载棋盘观测：{calibrator.dataset.path}')


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


def _close_windows():
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass


def run(args, cfg):
    # Own resources before setup can fail, not only after the live loop starts.
    # ExitStack runs every remaining callback even if one close operation fails.
    with ExitStack() as resources:
        return _run(args, cfg, resources)


def _run(args, cfg, resources):
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
        # File fingerprints are diagnostic metadata, never execution gates.
        if s.get("load") == "explicit" and s.get("active_sha256") and file_sha256(calib_path) != s["active_sha256"]:
            print("[warning] The active calibration was edited since selection; using its current contents.")
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
    resources.callback(_close_windows)
    left = open_camera(c["left"], c["width"], c["height"], c["fps"], c["backend"], fourcc=fourcc, buffer_size=buffer_size)
    resources.callback(left.release)
    right = open_camera(c["right"], c["width"], c["height"], c["fps"], c["backend"], fourcc=fourcc, buffer_size=buffer_size)
    resources.callback(right.release)
    estimator = PoseEstimator(p["model"], device, p["detection_confidence"])
    publisher = build_publisher(o)
    resources.callback(publisher.close)
    calibrator = RuntimeCalibration(s, cr)

    active_size = _capture_image_size(left, right, (c["width"], c["height"]))
    camera_indexes = (c['left'], c['right'])
    try:
        camera_notes = load_camera_notes(runtime_root)
    except (OSError, ValueError) as error:
        print(f'[calibration] cannot read webcam settings: {error}')
        camera_notes = {}

    def update_camera_context():
        modes = camera_modes(left, right, camera_indexes, camera_notes)
        calibrator.set_camera_context(
            left_index=c["left"], right_index=c["right"], backend=c["backend"],
            requested_size=(int(c["width"]), int(c["height"])), requested_fps=float(c["fps"]),
            actual_fps=_actual_fps(left), modes=modes)
        return modes

    current_modes = update_camera_context()
    settings_warnings, settings_mismatch = _camera_mode_issues(calib_path, current_modes)
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
    display = create_display(getattr(args, 'ui', 'auto'))
    resources.callback(display.close)

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
    use_projection_controls = getattr(display, 'calibration_controls', False) is True
    preview_rectified = False
    calibration_preview_rectified = False
    preview_cache = {}
    candidate_preview_cache = {}
    previous_incompatible = False

    def show_rectified(frames, tri, key):
        if tri is None or tri.image_size is None or any(
                (frame.shape[1], frame.shape[0]) != tri.image_size for frame in frames):
            return frames
        try:
            images, maps = preview_pair(frames, tri, preview_cache.get(key))
            if key not in preview_cache:
                preview_cache.clear()
                preview_cache[key] = maps
            return images
        except (cv2.error, ValueError) as error:
            display.notify(f'矫正预览不可用，显示原始画面：{error}')
            return frames

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

            active_size = (fl.shape[1], fl.shape[0])
            sizes = (active_size, (fr.shape[1], fr.shape[0]))
            mismatch = list(settings_mismatch)
            if sizes[0] != sizes[1] or (triangulator is not None and triangulator.image_size is not None
                    and any(size != triangulator.image_size for size in sizes)):
                mismatch.append(f'当前左右画面 {sizes} 与双目标定分辨率不符')
            incompatible = bool(mismatch)
            if incompatible and not previous_incompatible:
                recorder.stop("capture_settings_changed")
                print("[calibration] metric output disabled:", "; ".join(mismatch))
                smoother.reset()
                speed_gate.reset()
            previous_incompatible = incompatible
            measurement_tri = None if incompatible else triangulator
            measurement_registration = None if incompatible else registration

            t_filter_s = pair_timing.get("host_midpoint_perf_ns", time.perf_counter_ns()) / 1e9
            wall_timestamp_ns = pair_timing.get("wall_timestamp_ns", time.time_ns())

            if calibrator.active:
                calibrator.process(fl, fr, force_capture=False)
                options = display.projection_options() if use_projection_controls else None
                frames = (fl, fr)
                if options is not None and options[2]:
                    model, framing, _ = options
                    candidate = calibrator.results.get((model, 0))
                    if candidate is not None:
                        try:
                            preview_key = (candidate['path'], framing)
                            if preview_key not in candidate_preview_cache:
                                bundle = read_bundle(candidate['path'])
                                matrices, _ = rectify_stereo(bundle, tuple(bundle['image_size']), framing)
                                bundle.update(matrices)
                                candidate_preview_cache.clear()
                                candidate_preview_cache[preview_key] = StereoTriangulator(bundle)
                            frames = show_rectified(frames, candidate_preview_cache[preview_key], preview_key)
                        except (OSError, ValueError, cv2.error, np.linalg.LinAlgError) as error:
                            display.notify(f'矫正预览不可用，显示原始画面：{error}')
                if display.native:
                    key = display.show(pair=frames, view=calibration_view(
                        calibrator, options=options, active_file=calib_path,
                        active_model=getattr(triangulator, 'camera_model', None)))
                else:
                    if calibration_preview_rectified:
                        frames = show_rectified(frames, measurement_tri, (calib_path, 'live'))
                    pl, pr = resize_pair(*frames)
                    canvas = calibrator.draw_overlay(cv2.hconcat([pl, pr]), pair_timing)
                    overlay_status(canvas, [('RECTIFIED PREVIEW' if frames[0] is not fl else 'RAW FULL PREVIEW') + ' | H=toggle'])
                    key = display.show(canvas)

                if key == ord(" "):
                    calibrator.capture_current()
                elif key in (ord("r"), ord("R"), ord("a"), ord("A")):
                    try:
                        solving = key in (ord('r'), ord('R'))
                        if solving and not calibrator.can_solve():
                            raise ValueError(f'至少需要 {calibrator.min_pairs} 对可信棋盘观测')
                        if options is not None and solving:
                            result = calibrator.solve(options[0], stage=True, quality=qcfg)
                            display.notify(f'已计算 {result["camera_model"]}。可继续比较，或点击「启用所选标定」。')
                            frame_index += 1
                            continue
                        if options is None:
                            if not solving:
                                frame_index += 1
                                continue
                            result = calibrator.solve(stage=True, quality=qcfg)
                        else:
                            result = calibrator.results.get((options[0], 0))
                            if result is None:
                                raise ValueError('请先成功计算所选投影模型。')
                        candidate_path, candidate_tri, candidate_reg, warnings, candidate_sha = (
                            inspect_npz_for_live_load(result['path'], active_size,
                                board=(s['board_cols'], s['board_rows']), fps=float(c['fps']),
                                camera_indexes=camera_indexes))
                        if candidate_tri.image_size != sizes[1]:
                            raise ValueError('右相机当前分辨率与候选 NPZ 不符')
                        if 'npz_sha256' in result and candidate_sha != result['npz_sha256']:
                            print('[warning] 候选 NPZ 文件已修改；按当前文件内容继续启用')
                        device_warnings, device_mismatches = _camera_mode_issues(candidate_path, current_modes)
                        if device_mismatches:
                            raise ValueError('；'.join(device_mismatches))
                        warnings = [*warnings, *device_warnings, '启用此标定会清除旧 W 对齐，需要重新设置 W。']
                        if 'mapping' in result:
                            for side in ('left', 'right'):
                                invalid = result['mapping'][side]['invalid_grid_count']
                                if invalid:
                                    warnings.append(f'{side}: {invalid} 个抽样像素逆畸变失效，异常点将被拒绝。')
                        if options is None or display.confirm_calibration_file(candidate_path, warnings):
                            s.update(activate_calibration(args.config, candidate_path))
                            triangulator, calib_path = candidate_tri, candidate_path
                            registration, active_artifact_sha = candidate_reg, candidate_sha
                            world_warnings = warnings
                            settings_warnings, settings_mismatch = device_warnings, device_mismatches
                            smoother.reset()
                            speed_gate.reset()
                            calibrator.stop_without_delete()
                            display.notify(f'已启用 {candidate_tri.camera_model}｜{candidate_path.name}')
                            print(f'[calibration] ACTIVE {candidate_path} T(mm)={result["T"]}')
                    except Exception as error:
                        display.notify(f'标定操作失败：{error}')
                        print(f'[calibration] failed: {error}')
                elif options is None and key in (ord('h'), ord('H')):
                    calibration_preview_rectified = not calibration_preview_rectified
                elif options is not None and key in (ord('j'), ord('J'), ord('o'), ord('O')):
                    try:
                        if key in (ord('j'), ord('J')):
                            display.notify(calibrator.check_fixed_target())
                        else:
                            _dataset_dialog(display, calibrator)
                    except Exception as error:
                        display.notify(str(error))
                elif key in (ord("x"), ord("X")):
                    calibrator.discard()
                elif key in (ord("c"), ord("C")):
                    if options is not None and calibrator.dataset is None and calibrator.can_solve():
                        try:
                            dataset = calibrator.freeze_observations()
                            display.notify(f'已封存棋盘观测：{dataset.path}')
                        except Exception as error:
                            display.notify(f'无法封存棋盘观测：{error}')
                    calibrator.stop_without_delete()
                elif key in (ord("q"), 27):
                    if options is not None and calibrator.dataset is None and calibrator.can_solve():
                        try:
                            calibrator.freeze_observations()
                        except Exception as error:
                            print(f'[calibration] could not freeze observations before exit: {error}')
                    break

                frame_index += 1
                continue

            res_l, res_r = estimator.infer_pair(fl, fr)
            pts_l, cf_l, chosen_l, count_l = estimator.best_person(res_l)
            pts_r, cf_r, chosen_r, count_r = estimator.best_person(res_r)

            frame, all_accepted, all_verdicts, geometries = measure_frame(
                selected_joints=selected_joints, readout_joints=readout_joints,
                triangulator=measurement_tri, points_left=pts_l, points_right=pts_r,
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
            readout_rows = make_readout(readout_joints, all_accepted, all_verdicts, geometries, measurement_registration)
            publisher.publish(to_v1_message(frame))
            recorder.sample(frame, readout_rows)

            if diagnostics_enabled and frame_index % diag_every == 0:
                print(format_diagnostic_summary(frame_index, diagnostics))

            display_images = (res_l.plot(), res_r.plot())
            if preview_rectified:
                display_images = show_rectified(display_images, measurement_tri, (calib_path, 'live'))
            if not display.native:
                vl, vr = resize_pair(*display_images, target_h=360)
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

            cal_state = "calib=OK" if measurement_tri is not None else "calib=NONE"
            if preview_rectified and measurement_tri is not None and measurement_tri.image_size is not None:
                cal_state += " | RECTIFIED PREVIEW"
            cycle = pair_timing.get("pair_cycle_ms")
            # Review B4: fps shows the measured FULL processing-loop rate;
            # the camera grab pair period is reported separately below.
            fps_txt = f"{1000.0 / loop_ema_ms:.0f}fps" if loop_ema_ms else "fps n/a"
            grab_txt = "grab n/a" if not cycle else f"grab={float(cycle):.0f}ms"
            smooth_txt = "F:smoothing ON" if smoother.enabled else "F:smoothing OFF"

            alarms = [*settings_warnings, *[f'标定失配，暂停可信 XYZ：{reason}' for reason in mismatch]]
            if incompatible and not display.native:
                alarms = ['! CALIBRATION MISMATCH: metric output disabled (see console)']
            if triangulator is None:
                alarms.append("! no stereo calibration loaded (C -> R)")
            if mean_epi is not None and mean_epi > 3.0:
                alarms.append(f"! mean epipolar {mean_epi:.1f}px > 3px gate")

            menu_lines = build_menu_lines(
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
            )
            if display.native:
                key = display.show(pair=display_images, view=tracking_view(
                    readout_rows, measurement_registration, calibrated=measurement_tri is not None,
                    recording=recorder.active, record_status=recorder.status(), smoothing=smoother.enabled,
                    cameras=(c['left'],c['right']), fps=fps_txt, details=menu_lines,
                    warnings=alarms+world_warnings, calibration_file=calib_path,
                    model=getattr(triangulator, 'camera_model', None)))
            else:
                overlay_status(canvas, menu_lines)
                canvas = append_readout(canvas, readout_rows, measurement_registration, recorder.status(), world_warnings=world_warnings)
                key = display.show(canvas)

            if key in (ord("c"), ord("C")):
                recorder.stop("enter_calibration")
                current_modes = update_camera_context()
                settings_warnings, settings_mismatch = _camera_mode_issues(calib_path, current_modes)
                calibration_preview_rectified = False
                calibrator.start()
            elif use_projection_controls and key in (ord('o'), ord('O'), ord('b'), ord('B')):
                try:
                    if key in (ord('o'), ord('O')):
                        _dataset_dialog(display, calibrator)
                        if calibrator.active:
                            recorder.stop('open_calibration_dataset')
                    else:
                        notes = display.edit_camera_settings(current_modes)
                        if notes is not None:
                            new_notes = {**camera_notes, **notes}
                            save_camera_notes(runtime_root, new_notes)
                            camera_notes = new_notes
                            current_modes = update_camera_context()
                            settings_warnings, settings_mismatch = _camera_mode_issues(calib_path, current_modes)
                            display.notify('已保存相机输出设置记录。')
                except Exception as error:
                    display.notify(f'操作失败：{error}')
            elif key in (ord('h'), ord('H')) and measurement_tri is not None:
                preview_rectified = not preview_rectified
                display.notify('矫正显示（计算仍使用原始点）' if preview_rectified else '原始完整画面')
            elif key in (ord("k"), ord("K")):
                if calib_path is None or active_artifact_sha is None:
                    display.notify('尚未加载有效双目标定；请先加载或通过 C → R 创建 NPZ。')
                elif not display.native:
                    display.notify('OpenCV 兼容界面不支持文件选择窗口；请使用新版桌面界面另存 NPZ。')
                else:
                    try:
                        destination = display.save_calibration_file(calib_path)
                        if destination:
                            target=Path(destination).expanduser()
                            replace_existing=target.exists()
                            if replace_existing and not display.confirm_npz_overwrite(target):
                                display.notify('取消覆盖；原 NPZ 和目标文件均保持不变。')
                            else:
                                saved=export_calibration_npz(
                                    calib_path, target, expected_sha256=active_artifact_sha,
                                    overwrite=replace_existing)
                                display.notify(f'已另存完整 NPZ：{saved}；当前使用的标定未改变。')
                                print(f'[calibration] EXPORTED NPZ: {saved}; active remains {calib_path}')
                    except Exception as error:
                        display.notify(f'另存 NPZ 失败，原标定保持不变：{error}')
                        print('[calibration] NPZ export rejected; active calibration retained:',error)
            elif key in (ord("l"), ord("L")):
                if not display.native:
                    print('[calibration] 兼容模式请在 config.json 中设置 stereo.load=explicit 与 stereo.explicit_file，再重启')
                else:
                    try:
                        chosen = display.choose_calibration_file(
                            initialdir=Path(calib_path).parent if calib_path else Path(s['calibration_dir']))
                        if chosen:
                            candidate_path, candidate_tri, candidate_reg, warnings, candidate_sha = (
                                inspect_npz_for_live_load(
                                    chosen, active_size,
                                    board=(s['board_cols'], s['board_rows']),
                                    fps=float(c['fps']) if c.get('fps') else None,
                                    camera_indexes=(c['left'], c['right']),
                                )
                            )
                            if sizes[1] != candidate_tri.image_size:
                                raise ValueError('右相机当前分辨率与候选 NPZ 不符')
                            device_warnings, device_mismatches = _camera_mode_issues(candidate_path, current_modes)
                            warnings = [*warnings, *device_warnings, *device_mismatches]
                            if registration is not None and registration['metadata'].get('mode') != 'camera_midpoint' and (
                                    candidate_reg is None or candidate_reg['metadata'].get('mode') == 'camera_midpoint'):
                                warnings.append('切换后旧 W 对齐失配，需重新设置 W。')
                            if display.confirm_calibration_file(candidate_path, warnings):
                                # Durable selection first; a validation or config write
                                # failure leaves the running calibration untouched.
                                selection = activate_calibration(args.config, candidate_path)
                                recorder.stop('calibration_switched')
                                s.update(selection)
                                calib_path = candidate_path
                                triangulator = candidate_tri
                                registration = candidate_reg
                                world_warnings = list(warnings)
                                settings_warnings, settings_mismatch = device_warnings, device_mismatches
                                active_artifact_sha = candidate_sha
                                smoother.reset()
                                speed_gate.reset()
                                display.notify(f'已加载并启用 NPZ：{candidate_path.name}')
                                print(f'[calibration] SELECTED NPZ: {candidate_path}; SHA-256={candidate_sha}')
                            else:
                                display.notify('已取消切换 NPZ；当前标定未改变。')
                    except Exception as error:
                        display.notify(f'加载 NPZ 失败，原标定保持不变：{error}')
                        print('[calibration] NPZ load rejected; previous calibration retained:', error)
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
                        display.notify(f'已保留当前标定副本：{saved}')
                        print(f"[calibration] pinned current calibration -> {saved}")
                    except Exception as e:
                        display.notify(f'保留标定失败：{e}')
                        print(f"[calibration] pin failed: {e}")
                else:
                    print("[calibration] no active calibration to pin")
            elif key in (ord("w"), ord("W")):
                recorder.stop("world_setup")
                if measurement_tri is None:
                    print("[world] create/load stereo calibration first (C -> R)")
                else:
                    try:
                        new_path = run_world_setup(frame_left=fl, frame_right=fr, triangulator=triangulator,
                            calib_path=calib_path, config_path=args.config, cfg=cfg, registration=registration,
                            desktop=display if display.native else None)
                        if new_path is not None:
                            # Setup saves+activates atomically before exposing the new frame.
                            calib_path = new_path
                            active_artifact_sha = file_sha256(new_path)
                            triangulator = StereoTriangulator(new_path)
                            s.update(load_config(args.config)["stereo"])
                            registration, world_warnings = load_readout_registration(new_path, active_size)
                            display.notify(f'已保存并启用坐标系：{registration["name"] if registration else new_path}')
                    except Exception as e:
                        display.notify(f'坐标设置失败，原标定保持不变：{e}')
                        print("[world] setup failed; previous active retained:", e)
            elif key in (ord("t"), ord("T")):
                if recorder.active:
                    path = recorder.stop("manual")
                    print(f"[recording] STOPPED samples={recorder.samples} -> {path}")
                elif not cfg["recording"]["enabled"] or not cfg["recording"]["save_csv"]:
                    display.notify('配置已关闭 CSV 录制。')
                    print("[recording] CSV disabled by config")
                elif measurement_tri is None:
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
                        display.notify(f'录制启动失败：{e}')
                        print("[recording] start failed; tracking continues:", e)
            elif key in (ord("d"), ord("D")):
                diagnostics_enabled = not diagnostics_enabled
                print(f"[diagnostics] per-joint view {'ON' if diagnostics_enabled else 'OFF'}")
            elif key in (ord("v"), ord("V")):
                if measurement_tri is None:
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
                        triangulator=measurement_tri,
                        calib_path=calib_path,
                        confidence_threshold=kp_conf,
                    )
                    print(f"[snapshot] saved -> {snap_dir}")
                    display.notify(f'诊断快照已保存：{snap_dir}')
                    print(f"[snapshot] offline replay: python tools/inspect_snapshot.py {snap_dir}")
                except Exception as e:  # noqa: BLE001 — snapshot must never crash tracking
                    display.notify(f'快照保存失败：{e}')
                    print(f"[snapshot] FAILED: {e}")
            elif key in (ord("q"), 27):
                break

            frame_index += 1

    finally:
        recorder.stop("app_exit")


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
    ap.add_argument('--ui', choices=('auto','tk','opencv'), default='auto',
                    help='desktop UI (auto default); opencv keeps the compatible keyboard view')
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
