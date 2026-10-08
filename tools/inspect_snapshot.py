#!/usr/bin/env python3
"""Offline epipolar replay for a stereo diagnostic snapshot (Task 002B).

Usage::

    python tools/inspect_snapshot.py <snapshot_dir>

Recomputes rectified keypoints and epipolar errors from the saved raw keypoints
and the saved ``calibration_snapshot.npz``, then prints a compact per-joint
table and cross-checks the stored signed deltas and rectified uv coordinates
within floating tolerance.

Exit codes:
    0  replay finished; every stored value matched the recomputation
    1  replay impossible (missing/corrupt manifest, unsupported schema,
       missing/corrupt calibration geometry, bad arguments)
    2  replay finished but found mismatching or incomplete stored values

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
_CAL_SHAPES = {
    "K1": ((3, 3),), "K2": ((3, 3),),
    "R1": ((3, 3),), "R2": ((3, 3),),
    "P1": ((3, 3), (3, 4)), "P2": ((3, 3), (3, 4)),
}
_TOLERANCE = 1e-3  # float32 rectified coordinates round-trip tolerance
_UV_TOLERANCE = 1e-3


class ReplayError(RuntimeError):
    """Replay cannot proceed at all (reported with exit code 1)."""


def _load_manifest(snapshot_dir: Path):
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise ReplayError(f"manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ReplayError(f"manifest.json is unreadable or corrupt: {e}") from e
    if not isinstance(manifest, dict):
        raise ReplayError("manifest.json is corrupt: top level is not a JSON object")
    if manifest.get("schema") != SNAPSHOT_SCHEMA:
        raise ReplayError(
            f"unsupported manifest schema: {manifest.get('schema')!r} "
            f"(expected {SNAPSHOT_SCHEMA!r})"
        )
    return manifest


def _load_calibration(snapshot_dir: Path):
    """Return the calibration bundle, ``None`` when no NPZ is present."""
    npz_path = snapshot_dir / "calibration_snapshot.npz"
    if not npz_path.exists():
        return None
    try:
        loaded = np.load(npz_path, allow_pickle=False)
    except Exception as e:  # noqa: BLE001 — corrupt zip / not an NPZ at all
        raise ReplayError(f"calibration_snapshot.npz is corrupt: {e}") from e
    missing = [k for k in _CAL_KEYS if k not in loaded]
    if missing:
        raise ReplayError(f"calibration_snapshot.npz missing keys: {missing}")
    bundle = {k: np.array(loaded[k], dtype=float) for k in _CAL_KEYS}
    for key, shapes in _CAL_SHAPES.items():
        if bundle[key].shape not in shapes:
            raise ReplayError(
                f"invalid calibration geometry: {key} has shape "
                f"{bundle[key].shape}, expected one of {shapes}"
            )
    for key in ("D1", "D2"):
        d = bundle[key]
        if d.ndim != 1 or not 4 <= d.size <= 8:
            raise ReplayError(
                f"invalid calibration geometry: {key} has shape {d.shape}, "
                f"expected a 4..8 coefficient distortion vector"
            )
    if not all(np.all(np.isfinite(bundle[k])) for k in _CAL_KEYS):
        raise ReplayError("invalid calibration geometry: non-finite matrix entries")
    return bundle


def _as_float(value):
    """Return ``value`` as a finite float, or ``None`` for null/non-numeric."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _fmt(value, spec):
    """Format a possibly-missing numeric without ever raising (review B2)."""
    v = _as_float(value)
    return "n/a" if v is None else format(v, spec)


def _uv_close(stored, recomputed, tol=_UV_TOLERANCE):
    if not isinstance(stored, (list, tuple)) or len(stored) != 2:
        return False
    a, b = _as_float(stored[0]), _as_float(stored[1])
    if a is None or b is None:
        return False
    return abs(a - recomputed[0]) <= tol and abs(b - recomputed[1]) <= tol


def recompute(snapshot_dir: Path) -> int:
    manifest = _load_manifest(snapshot_dir)
    calibration = _load_calibration(snapshot_dir)

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

    joints = manifest.get("joints")
    if not isinstance(joints, list):
        raise ReplayError("manifest.json is corrupt: 'joints' is not a list")

    header = (
        f"{'joint':<15} {'y_left':>10} {'y_right':>10} "
        f"{'dy(store)':>11} {'dy(replay)':>11} {'|dy|':>8} {'uv_ok':>5} {'match':>5}"
    )
    print(header)
    print("-" * len(header))

    checked = 0
    mismatches = 0
    for entry in joints:
        if not isinstance(entry, dict):
            print(f"{'?':<15} malformed joint entry (not an object)")
            mismatches += 1
            continue
        name = str(entry.get("joint", "?"))
        left = entry.get("left") if isinstance(entry.get("left"), dict) else {}
        right = entry.get("right") if isinstance(entry.get("right"), dict) else {}
        stored = entry.get("rectified") if isinstance(entry.get("rectified"), dict) else {}
        uv_l = left.get("uv")
        uv_r = right.get("uv")

        if uv_l is None or uv_r is None:
            print(f"{name:<15} missing observation(s) — no raw uv to replay")
            continue

        try:
            epi = compute_epipolar(calibration, uv_l, uv_r)
        except Exception as e:  # noqa: BLE001 — cv2 errors on invalid geometry
            raise ReplayError(f"invalid calibration geometry: {e}") from e
        if epi is None:
            print(f"{name:<15} non-finite keypoint — cannot rectify")
            continue

        if stored.get("available") is not True:
            reason = stored.get("missing_reason") or "unavailable"
            print(f"{name:<15} no stored geometry ({reason}) — nothing to cross-check")
            continue

        checked += 1
        y_l = epi["rectified_uv_left"][1]
        y_r = epi["rectified_uv_right"][1]
        dy = epi["signed_y_delta_px"]
        abs_epi = epi["epipolar_error_px"]

        stored_dy = _as_float(stored.get("signed_y_delta_px"))
        stored_abs = _as_float(stored.get("epipolar_error_px"))

        problems = []
        if stored_dy is None:
            problems.append("missing/invalid stored signed_y_delta_px")
        elif abs(stored_dy - dy) > _TOLERANCE:
            problems.append("signed delta differs")

        if stored_abs is None:
            problems.append("missing/invalid stored epipolar_error_px")
        elif abs(stored_abs - abs_epi) > _TOLERANCE:
            problems.append("absolute error differs")

        # Review B2: cross-check the stored rectified uv coordinates too, when
        # present — catches coordinate-transform errors a dy-only check misses.
        uv_problems = []
        stored_uv_l = stored.get("uv_left")
        stored_uv_r = stored.get("uv_right")
        if stored_uv_l is not None:
            if not _uv_close(stored_uv_l, epi["rectified_uv_left"]):
                uv_problems.append("rectified uv_left differs")
        if stored_uv_r is not None:
            if not _uv_close(stored_uv_r, epi["rectified_uv_right"]):
                uv_problems.append("rectified uv_right differs")
        uv_ok = "n/a" if (stored_uv_l is None and stored_uv_r is None) else ("ok" if not uv_problems else "DIFF")
        problems.extend(uv_problems)

        ok = not problems
        if not ok:
            mismatches += 1
        print(
            f"{name:<15} {y_l:>10.3f} {y_r:>10.3f} "
            f"{_fmt(stored.get('signed_y_delta_px'), '>11.4f')} "
            f"{dy:>11.4f} {abs_epi:>8.3f} {uv_ok:>5} "
            f"{'ok' if ok else 'DIFF':>5}"
        )
        if problems:
            print(f"{'':<15}   -> {'; '.join(problems)}")

    print("-" * len(header))
    print(
        f"replayed {checked} joint(s); {mismatches} mismatch(es) beyond "
        f"{_TOLERANCE:g} tolerance"
    )
    return 0 if mismatches == 0 else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a stereo diagnostic snapshot offline.")
    parser.add_argument("snapshot_dir", help="path to the snapshot directory")
    args = parser.parse_args(argv)

    snapshot_dir = Path(args.snapshot_dir)
    if not snapshot_dir.is_dir():
        print(f"error: not a directory: {snapshot_dir}", file=sys.stderr)
        return 1
    try:
        return recompute(snapshot_dir)
    except ReplayError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
