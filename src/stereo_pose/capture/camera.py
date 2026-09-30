"""Camera acquisition: opening devices and reading matched stereo pairs."""

from __future__ import annotations

import os
import time

import cv2

from stereo_pose.models import FrameTiming, StereoFramePair

_BACKEND_CODES = {
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "v4l2": cv2.CAP_V4L2,
}


def _backend_code(name):
    name = (name or "auto").lower()
    return _BACKEND_CODES.get(name)


def open_camera(index, width=1280, height=720, fps=30, backend="auto"):
    """Open a camera by index, applying requested resolution/FPS/backend.

    On Windows, an explicit backend code is tried first (DSHOW) before falling
    back to the platform default when ``backend`` is ``auto``.
    """
    code = _backend_code(backend)
    if code is None and os.name == "nt":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
    elif code is None:
        cap = cv2.VideoCapture(index)
    else:
        cap = cv2.VideoCapture(index, code)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {index}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    cap.set(cv2.CAP_PROP_FPS, int(fps))
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def read_stereo_pair(left, right, alternate_order=False, frame_index=0):
    """Grab both devices before decoding either frame.

    This reduces software-induced left/right skew versus ``left.read()`` followed
    by ``right.read()``. ``host_grab_skew_ms`` is a host-side diagnostic only;
    commodity webcams usually do not expose true exposure timestamps, so it does
    NOT measure sensor exposure skew.
    """
    start_ns = time.perf_counter_ns()

    reverse = bool(alternate_order and (frame_index % 2))
    if not reverse:
        ok_l_grab = left.grab()
        t_l = time.perf_counter_ns()
        ok_r_grab = right.grab()
        t_r = time.perf_counter_ns()
    else:
        ok_r_grab = right.grab()
        t_r = time.perf_counter_ns()
        ok_l_grab = left.grab()
        t_l = time.perf_counter_ns()

    if not (ok_l_grab and ok_r_grab):
        return False, None, None, {
            "host_grab_skew_ms": None,
            "pair_cycle_ms": (time.perf_counter_ns() - start_ns) / 1e6,
        }

    ok_l, frame_l = left.retrieve()
    ok_r, frame_r = right.retrieve()
    end_ns = time.perf_counter_ns()

    return bool(ok_l and ok_r), frame_l, frame_r, {
        "host_grab_skew_ms": abs(t_l - t_r) / 1e6,
        "pair_cycle_ms": (end_ns - start_ns) / 1e6,
        "host_midpoint_perf_ns": int((t_l + t_r) // 2),
        "wall_timestamp_ns": time.time_ns(),
    }