"""Calibration artifact selection (which NPZ to load)."""

from __future__ import annotations

from pathlib import Path

from stereo_pose.persistence.paths import auto_dir


def newest_calibration(calibration_dir, explicit_file=None):
    """Return the newest calibration NPZ, in strict selection order:

    1. ``explicit_file`` when provided (must exist);
    2. newest ``auto/stereo_*.npz``;
    3. only if ``auto/`` is empty, newest legacy root-level ``stereo_*.npz``;
    4. only then legacy ``./stereo_calib.npz``.

    Raises ``FileNotFoundError`` when nothing is found.
    """
    if explicit_file:
        p = Path(explicit_file)
        if not p.exists():
            raise FileNotFoundError(f"Explicit calibration file not found: {p}")
        return p

    d = Path(calibration_dir)
    d.mkdir(parents=True, exist_ok=True)

    auto_candidates = list(auto_dir(d).glob("stereo_*.npz"))
    if auto_candidates:
        return max(auto_candidates, key=lambda p: p.stat().st_mtime)

    # Legacy rolling files written directly under the root (pre-auto/ layout).
    legacy_candidates = list(d.glob("stereo_*.npz"))
    if legacy_candidates:
        return max(legacy_candidates, key=lambda p: p.stat().st_mtime)

    legacy = Path("stereo_calib.npz")
    if legacy.exists():
        return legacy

    raise FileNotFoundError(
        f"No calibration found in {d}/auto; press C at runtime to create one."
    )