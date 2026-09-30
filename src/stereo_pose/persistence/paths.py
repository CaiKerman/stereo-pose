"""Managed runtime path layout for calibration artifacts.

The persistence subsystem splits calibration artifacts into two classes (see
``docs/calibration/STEREO_CALIBRATION.md``):

* ``auto/``  — rolling calibrations generated during normal recalibration;
  eligible for automatic retention cleanup (keep latest N).
* ``saved/`` — the user-preserved calibration library; never auto-cleaned.

Both live under ``stereo.calibration_dir``. Only ``auto/`` (and the separate
session area) may be touched by automatic cleanup.
"""

from __future__ import annotations

from pathlib import Path

AUTO_SUBDIR = "auto"
SAVED_SUBDIR = "saved"


def auto_dir(calibration_dir) -> Path:
    """Return the rolling/cleanup-managed subdirectory under ``calibration_dir``."""
    return Path(calibration_dir) / AUTO_SUBDIR


def saved_dir(calibration_dir) -> Path:
    """Return the user-preserved calibration library directory."""
    return Path(calibration_dir) / SAVED_SUBDIR