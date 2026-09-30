"""Calibration artifact selection (which NPZ to load)."""

from __future__ import annotations

from pathlib import Path


def newest_calibration(calibration_dir, explicit_file=None):
    """Return the newest ``stereo_*.npz`` under ``calibration_dir``.

    When ``explicit_file`` is provided it is used directly (must exist).
    Falls back to a legacy ``stereo_calib.npz`` in the current directory when no
    versioned file exists. Raises ``FileNotFoundError`` when nothing is found.
    """
    if explicit_file:
        p = Path(explicit_file)
        if not p.exists():
            raise FileNotFoundError(f"Explicit calibration file not found: {p}")
        return p

    d = Path(calibration_dir)
    d.mkdir(parents=True, exist_ok=True)
    files = list(d.glob("stereo_*.npz"))
    if files:
        return max(files, key=lambda p: p.stat().st_mtime)

    legacy = Path("stereo_calib.npz")
    if legacy.exists():
        return legacy

    raise FileNotFoundError(
        f"No calibration found in {d}; press C at runtime to create one."
    )