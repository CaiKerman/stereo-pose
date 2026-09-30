"""Calibration artifact selection (which NPZ to load)."""

from __future__ import annotations

from pathlib import Path

from stereo_pose.persistence.paths import auto_dir


def newest_calibration(calibration_dir, explicit_file=None):
    """Return the newest ``stereo_*.npz`` under ``calibration_dir/auto/``.

    When ``explicit_file`` is provided it is used directly (must exist); this is
    how a saved/pinned profile under ``saved/`` is selected explicitly. Falls
    back to legacy flat ``stereo_*.npz`` files and a legacy ``stereo_calib.npz``
    in the current directory for backwards compatibility. Raises
    ``FileNotFoundError`` when nothing is found.
    """
    if explicit_file:
        p = Path(explicit_file)
        if not p.exists():
            raise FileNotFoundError(f"Explicit calibration file not found: {p}")
        return p

    d = Path(calibration_dir)
    d.mkdir(parents=True, exist_ok=True)
    candidates = list(auto_dir(d).glob("stereo_*.npz"))
    # Legacy rolling files written directly under the root (pre-auto/ layout).
    candidates.extend(d.glob("stereo_*.npz"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)

    legacy = Path("stereo_calib.npz")
    if legacy.exists():
        return legacy

    raise FileNotFoundError(
        f"No calibration found in {d}/auto; press C at runtime to create one."
    )