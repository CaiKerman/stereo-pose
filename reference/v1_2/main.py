import argparse
import math
from pathlib import Path
import time

import cv2
import numpy as np

from stereo_pose.camera import open_camera, read_stereo_pair
from stereo_pose.calibration import RuntimeCalibration
from stereo_pose.cleanup import cleanup_project
from stereo_pose.config import load_config
from stereo_pose.device import resolve_device
from stereo_pose.filtering import JointSmoother, TemporalSpeedGate
from stereo_pose.joints import JOINT_INDEX, resolve_joints
from stereo_pose.pose import PoseEstimator
from stereo_pose.publishers import build_publisher
from stereo_pose.stereo import StereoTriangulator, newest_calibration


def resize_pair(a, b, target_h=480):
    a2 = cv2.resize(a, (int(a.shape[1] * target_h / a.shape[0]), target_h))
    b2 = cv2.resize(b, (int(b.shape[1] * target_h / b.shape[0]), target_h))
    return a2, b2


def overlay_status(img, lines):
    y = img.shape[0] - 18 - (len(lines) - 1) * 25
    for line in lines:
        cv2.putText(
            img, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX,
            0.58, (255, 255, 255), 2, cv2.LINE_AA
        )
        y += 25
    return img


def heuristic_quality_score(conf_l, conf_r, epi_px, reproj_px, qcfg):
    base = math.sqrt(max(0.0, float(conf_l)) * max(0.0, float(conf_r)))
    epi_scale = max(float(qcfg["max_epipolar_error_px"]), 1e-6)
    rep_scale = max(float(qcfg["max_reprojection_error_px"]), 1e-6)
    geom = math.exp(-float(epi_px) / epi_scale) * math.exp(-float(reproj_px) / rep_scale)
    return float(max(0.0, min(1.0, base * geom)))


def run(args, cfg):
    c = cfg["camera"]
    p = cfg["pose"]
    s = cfg["stereo"]
    cr = cfg["calibration_runtime"]
    cl = cfg["cleanup"]
    qcfg = cfg["quality"]
    scfg = cfg["smoothing"]
    o = cfg["output"]

    if args.left_cam is not None:
        c["left"] = args.left_cam
    if args.right_cam is not None:
        c["right"] = args.right_cam
    if args.device is not None:
        p["device"] = args.device
    if args.model is not None:
        p["model"] = args.model

    if cl.get("enabled", True):
        cleanup_project(
            s["calibration_dir"], cr["session_dir"],
            cl.get("keep_latest_calibrations", 10),
            cl.get("delete_failed_sessions_older_days", 7),
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

    left = open_camera(c["left"], c["width"], c["height"], c["fps"], c["backend"])
    right = open_camera(c["right"], c["width"], c["height"], c["fps"], c["backend"])
    estimator = PoseEstimator(p["model"], device, p["detection_confidence"])
    publisher = build_publisher(o)
    calibrator = RuntimeCalibration(s, cr)

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
    print("Hotkeys: C=calibration | F=smoothing on/off | G=cleanup | Q/ESC=quit")
    print("Calibration: wait for STABLE | SPACE=manual(still required) | R=solve | X=discard | C=return\n")

    frame_index = 0
    kp_conf = float(p["keypoint_confidence"])
    alternate_grab = bool(c.get("alternate_grab_order", True))

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
                                f"sample epipolar mean/max="
                                f"{result['sample_epipolar_mean_px']:.3f}/"
                                f"{result['sample_epipolar_max_px']:.3f}px"
                            )
                            if cl.get("enabled", True):
                                cleanup_project(
                                    s["calibration_dir"], cr["session_dir"],
                                    cl.get("keep_latest_calibrations", 10),
                                    cl.get("delete_failed_sessions_older_days", 7),
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

            joints_payload = {}
            rejected = {
                "keypoint_confidence": 0,
                "geometry": 0,
                "depth": 0,
                "quality_score": 0,
                "speed": 0,
            }
            current_epi = []
            current_reproj = []

            if triangulator is not None and pts_l is not None and pts_r is not None:
                for name in selected_joints:
                    i = JOINT_INDEX[name]
                    if cf_l[i] < kp_conf or cf_r[i] < kp_conf:
                        rejected["keypoint_confidence"] += 1
                        continue

                    geom = triangulator.triangulate_with_quality(pts_l[i], pts_r[i])
                    if geom is None:
                        rejected["geometry"] += 1
                        continue

                    epi = float(geom["epipolar_error_px"])
                    rep = float(geom["reprojection_error_max_px"])
                    current_epi.append(epi)
                    current_reproj.append(rep)

                    if (
                        epi > float(qcfg["max_epipolar_error_px"])
                        or rep > float(qcfg["max_reprojection_error_px"])
                    ):
                        rejected["geometry"] += 1
                        continue

                    raw_xyz = np.asarray(geom["xyz_mm"], dtype=float)
                    z = float(raw_xyz[2])
                    if z < float(qcfg["min_depth_mm"]) or z > float(qcfg["max_depth_mm"]):
                        rejected["depth"] += 1
                        continue

                    score = heuristic_quality_score(cf_l[i], cf_r[i], epi, rep, qcfg)
                    if score < float(qcfg.get("min_quality_score", 0.0)):
                        rejected["quality_score"] += 1
                        continue

                    speed_ok, speed = speed_gate.check(name, raw_xyz, t_filter_s)
                    if not speed_ok:
                        rejected["speed"] += 1
                        continue

                    filtered_xyz = smoother.update(name, raw_xyz, t_filter_s)

                    joints_payload[name] = {
                        "xyz_mm": [float(x) for x in filtered_xyz],
                        "xyz_raw_mm": [float(x) for x in raw_xyz],
                        "confidence": {
                            "left": float(cf_l[i]),
                            "right": float(cf_r[i]),
                        },
                        "quality": {
                            "score": score,
                            "epipolar_error_px": epi,
                            "reprojection_error_mean_px": float(geom["reprojection_error_mean_px"]),
                            "reprojection_error_max_px": rep,
                            "speed_mm_s": float(speed),
                        },
                        "uv": {
                            "left": [float(pts_l[i][0]), float(pts_l[i][1])],
                            "right": [float(pts_r[i][0]), float(pts_r[i][1])],
                            "rectified_left": [float(x) for x in geom["rectified_uv_left"]],
                            "rectified_right": [float(x) for x in geom["rectified_uv_right"]],
                        },
                    }

            mean_epi = float(np.mean(current_epi)) if current_epi else None
            mean_reproj = float(np.mean(current_reproj)) if current_reproj else None

            publisher.publish({
                "schema": "stereo_pose_3d/v1.2",
                "timestamp_ns": wall_timestamp_ns,
                "frame_index": frame_index,
                "unit": "mm",
                "coordinate_system": "rectified_left_camera",
                "calibration_file": str(calib_path) if calib_path else None,
                "timing": {
                    "host_grab_skew_ms": pair_timing.get("host_grab_skew_ms"),
                    "pair_cycle_ms": pair_timing.get("pair_cycle_ms"),
                    "warning": "host timing only; not sensor exposure timestamps",
                },
                "filtering": {
                    "enabled": bool(smoother.enabled),
                    "type": "one_euro",
                    "min_cutoff": smoother.min_cutoff,
                    "beta": smoother.beta,
                    "d_cutoff": smoother.d_cutoff,
                },
                "frame_quality": {
                    "accepted_joints": len(joints_payload),
                    "rejected": rejected,
                    "mean_epipolar_error_px": mean_epi,
                    "mean_reprojection_error_px": mean_reproj,
                },
                "joints": joints_payload,
            })

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
                f"TRACKING | device={device} | accepted={len(joints_payload)} rejected={rej_total}",
                f"Stereo RMS={rms} | epi={epi_txt} | reproj={rep_txt}",
                f"host grab skew={skew_txt} (not exposure skew) | smoothing={'ON' if smoother.enabled else 'OFF'}",
                f"OneEuro min_cutoff={smoother.min_cutoff:g} beta={smoother.beta:g} d_cutoff={smoother.d_cutoff:g}",
                "C=calibrate   F=filter on/off   G=cleanup   Q/ESC=quit",
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
                    cl.get("keep_latest_calibrations", 10),
                    cl.get("delete_failed_sessions_older_days", 7),
                    verbose=True,
                )
            elif key in (ord("q"), 27):
                break

            frame_index += 1

    finally:
        publisher.close()
        left.release()
        right.release()
        cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description="Stereo camera real-time 3D pose tracker")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--left-cam", type=int)
    ap.add_argument("--right-cam", type=int)
    ap.add_argument("--device", help="auto / cpu / 0 / 1 ...")
    ap.add_argument("--model")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = load_config(cfg_path if cfg_path.exists() else None)
    run(args, cfg)


if __name__ == "__main__":
    main()
