#!/usr/bin/env python3
"""Offline epipolar replay for a stereo diagnostic snapshot (Task 002B).

Usage::

    python tools/inspect_snapshot.py <snapshot_dir>

Recomputes rectified keypoints and epipolar errors from the saved raw keypoints
and the saved ``calibration_snapshot.npz``, then prints a compact per-joint
table and cross-checks the stored signed deltas within floating tolerance.

Only NumPy and OpenCV are required. No camera, torch, CUDA, YOLO or model
weights are loaded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stereo_pose.diagnostics.snapshot import SNAPSHOT_SCHEMA, compute_epipolar  # noqa: E402

_CAL_KEYS = ("K1", "D1", "K2", "D2", "R1", "R2", "P1", "P2")
_TOLERANCE = 1e-3  # float32 rectified coordinates round-trip tolerance


def _load_calibration(snapshot_dir: Path):
    npz_path = snapshot_dir / "calibration_snapshot.npz"
    if not npz_path.exists():
        return None
    loaded = np.load(npz_path, allow_pickle=False)
    missing = [k for k in _CAL_KEYS if k not in loaded]
    if missing:
        raise ValueError(f"calibration_snapshot.npz missing keys: {missing}")
    return {k: np.array(loaded[k], dtype=float) for k in _CAL_KEYS}


def recompute(snapshot_dir: Path):
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError(
            f"unsupported manifest schema: {manifest.get('schema')!r} "
            f"(expected {SNAPSHOT_SCHEMA!r})"
        )

    calibration = _load_calibration(snapshot_dir)
    joints = manifest.get("joints", [])

    print(f"Snapshot      : {snapshot_dir}")
    print(f"schema        : {manifest.get('schema')}")
    print(f"snapshot_id   : {manifest.get('snapshot_id')}")
    print(f"frame_index   : {manifest.get('frame_index')}")
    print(
        f"calibration   : "
        f"{manifest.get('calibration', {}).get('path') or 'NONE'}"
    )
    print()

    if calibration is None:
        print("No calibration snapshot present; cannot recompute epipolar errors.")
        return 1

    header = (
        f"{'joint':<15} {'y_left':>10} {'y_right':>10} "
        f"{'dy(store)':>11} {'dy(replay)':>11} {'|dy|':>8} {'match':>5}"
    )
    print(header)
    print("-" * len(header))

    mismatches = 0
    for joint in joints:
        left = joint.get("left", {})
        right = joint.get("right", {})
        uv_l = left.get("uv")
        uv_r = right.get("uv")
        stored = joint.get("rectified", {}) or {}

        if uv_l is None or uv_r is None:
            print(f"{joint.get('joint', '?'):<15} missing observation(s)")
            continue

        epi = compute_epipolar(calibration, uv_l, uv_r)
        if epi is None:
            print(f"{joint.get('joint', '?'):<15} non-finite keypoint")
            continue

        y_l = epi["rectified_uv_left"][1]
        y_r = epi["rectified_uv_right"][1]
        dy = epi["signed_y_delta_px"]
        abs_epi = epi["epipolar_error_px"]

        stored_dy = stored.get("signed_y_delta_px")
        stored_abs = stored.get("epipolar_error_px")

        match = True
        if stored_dy is None or abs(stored_dy - dy) > _TOLERANCE:
            match = False
            mismatches += 1
        if stored_abs is None or abs(stored_abs - abs_epi) > _TOLERANCE:
            match = False
            mismatches += 1

        print(
            f"{joint.get('joint', '?'):<15} {y_l:>10.3f} {y_r:>10.3f} "
            f"{stored_dy if stored_dy is None else stored_dy:>11.4f} "
            f"{dy:>11.4f} {abs_epi:>8.3f} "
            f"{'ok' if match else 'DIFF':>5}"
        )

    print("-" * len(header))
    print(f"replayed {len(joints)} joint(s); {mismatches} mismatch(es) beyond "
          f"{_TOLERANCE:g} tolerance")
    return 0 if mismatches == 0 else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a stereo diagnostic snapshot offline.")
    parser.add_argument("snapshot_dir", help="path to the snapshot directory")
    args = parser.parse_args(argv)

    snapshot_dir = Path(args.snapshot_dir)
    if not snapshot_dir.is_dir():
        parser.error(f"not a directory: {snapshot_dir}")
    return recompute(snapshot_dir)


if __name__ == "__main__":
    raise SystemExit(main())
