"""Persistence / artifact management: safe cleanup of runtime artifacts.

Cleanup operates ONLY inside project-managed runtime roots:
``<calibration_dir>/stereo_*.npz`` and ``<session_dir>/session_*``. It never
recurses into or deletes arbitrary user-provided locations.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path


def cleanup_project(calibration_dir, session_dir, keep_latest=10, failed_days=7, verbose=True):
    """Clean only files created by this project in its managed folders."""
    removed = []

    cal_dir = Path(calibration_dir)
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_files = sorted(
        cal_dir.glob("stereo_*.npz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in cal_files[max(1, int(keep_latest)):]:
        try:
            p.unlink()
            removed.append(str(p))
        except OSError:
            pass

    sess_dir = Path(session_dir)
    sess_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=float(failed_days))
    for p in sess_dir.glob("session_*"):
        if not p.is_dir():
            continue
        try:
            if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                shutil.rmtree(p)
                removed.append(str(p))
        except OSError:
            pass

    if verbose:
        print(f"[cleanup] removed {len(removed)} item(s)")
    return removed