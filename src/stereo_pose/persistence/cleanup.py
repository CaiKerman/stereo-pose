"""Persistence / artifact management: safe cleanup of runtime artifacts.

Cleanup only ever operates inside explicitly managed runtime roots:

* ``<calibration_dir>/auto/stereo_*.npz`` — rolling calibrations (keep latest N);
* ``<session_dir>/session_*`` — abandoned calibration capture sessions.

It never recurses into or deletes arbitrary user-provided locations, and it
never touches the user-preserved ``saved/`` calibration library.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from stereo_pose.persistence.paths import auto_dir

_MAX_REMOVED_GUARD = 10_000


class CleanupSafetyError(RuntimeError):
    """Raised when a cleanup target falls outside the trusted runtime root."""


def _resolved(path) -> Path:
    """Resolve to an absolute, normalised path (``resolve(strict=False)``)."""
    return Path(os.path.abspath(os.path.expanduser(str(Path(path).resolve(strict=False)))))


def _is_within(child: Path, root: Path) -> bool:
    """True if ``child`` is equal to or a strictly contained descendant of ``root``."""
    return child == root or child.is_relative_to(root)


def ensure_managed_location(path, trusted_root: Path, label: str) -> Path:
    """Return ``path`` resolved, raising :class:`CleanupSafetyError` if it is not
    inside ``trusted_root``. This is the managed-root containment guard: nothing
    outside the trusted runtime root may be a cleanup operand.
    """
    root = _resolved(trusted_root)
    resolved = _resolved(path)
    if not _is_within(resolved, root):
        raise CleanupSafetyError(
            f"{label} {resolved} is outside the trusted runtime root {root}; refusing to clean it"
        )
    return resolved


def cleanup_project(
    calibration_dir,
    session_dir,
    runtime_root,
    keep_latest=10,
    failed_days=7,
    verbose=True,
):
    """Clean only files created by this project in its managed folders.

    ``runtime_root`` is a mandatory trusted managed root: both
    ``calibration_dir`` and ``session_dir`` must resolve inside it, otherwise a
    :class:`CleanupSafetyError` is raised before any deletion. Rolling
    calibrations are kept newest-first under ``auto/``; the ``saved/`` library
    is never touched.

    Deletion candidates are computed and checked against the mass-deletion
    safety guard *before* anything is removed.
    """
    if not runtime_root:
        raise CleanupSafetyError(
            "cleanup requires a trusted runtime_root; refusing unguarded cleanup"
        )
    trust = _resolved(runtime_root)
    cal_root = _resolved(calibration_dir)
    sess_root = _resolved(session_dir)
    ensure_managed_location(cal_root, trust, "calibration_dir")
    ensure_managed_location(sess_root, trust, "session_dir")

    auto = auto_dir(cal_root)
    auto.mkdir(parents=True, exist_ok=True)

    # Phase 1: compute every deletion candidate before deleting anything.
    cal_candidates = []
    cal_files = sorted(
        auto.glob("stereo_*.npz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in cal_files[max(1, int(keep_latest)):]:
        if not _is_within(_resolved(p), auto):
            raise CleanupSafetyError(f"refusing to delete {p}: escapes managed auto root {auto}")
        cal_candidates.append(p)

    sess_dir = Path(session_dir)
    sess_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=float(failed_days))
    sess_candidates = []
    for p in sess_dir.glob("session_*"):
        if not p.is_dir():
            continue
        if not _is_within(_resolved(p), sess_root):
            raise CleanupSafetyError(f"refusing to delete {p}: escapes managed session root {sess_root}")
        try:
            stale = datetime.fromtimestamp(p.stat().st_mtime) < cutoff
        except OSError:
            stale = False
        if stale:
            sess_candidates.append(p)

    total = len(cal_candidates) + len(sess_candidates)
    if total > _MAX_REMOVED_GUARD:
        raise CleanupSafetyError(
            f"cleanup would remove {total} items, exceeding safety guard "
            f"{_MAX_REMOVED_GUARD}; aborting before any deletion"
        )

    # Phase 2: delete only after the guard has passed.
    removed = []
    for p in cal_candidates:
        try:
            p.unlink()
            removed.append(str(p))
        except OSError:
            pass
    for p in sess_candidates:
        try:
            shutil.rmtree(p)
            removed.append(str(p))
        except OSError:
            pass

    if verbose:
        print(f"[cleanup] removed {len(removed)} item(s)")
    return removed