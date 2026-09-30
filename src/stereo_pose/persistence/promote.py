"""Promote a generated calibration into the user-preserved ``saved/`` library.

Promotion copies the artifact (preserving its embedded metadata byte-for-byte)
and writes a sidecar ``*.meta.json`` carrying library-level information (name,
source, notes, checksum). The ``saved/`` library is never touched by automatic
cleanup.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from stereo_pose.persistence.paths import saved_dir

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(name: str) -> str:
    return _SAFE_NAME.sub("_", name).strip("._") or "calibration"


def library_meta_path(npz_path: Path) -> Path:
    """Return the sidecar ``.meta.json`` path next to a saved ``.npz``."""
    return npz_path.with_suffix(".meta.json")


def promote_calibration(src_path, calibration_dir, name=None, notes=None, source="promoted"):
    """Copy ``src_path`` into the ``saved/`` library and record its metadata.

    Parameters
    ----------
    src_path:
        An existing versioned calibration NPZ (e.g. under ``auto/``).
    calibration_dir:
        The calibration root; the destination is ``calibration_dir/saved/``.
    name:
        Optional user-visible name / position label. When omitted, the source
        stem is used.
    notes:
        Optional free-form notes.
    source:
        Provenance tag: ``"auto"``, ``"imported"``, or ``"promoted"``.

    Returns
    -------
    Path
        The copied NPZ inside the ``saved/`` library.
    """
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"Calibration to promote not found: {src}")

    saved = saved_dir(calibration_dir)
    saved.mkdir(parents=True, exist_ok=True)

    base_name = _sanitize(name) if name else src.stem
    dest = saved / f"{base_name}.npz"

    # Never overwrite an existing pinned artifact; disambiguate with a stamp.
    if dest.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = saved / f"{base_name}_{stamp}.npz"

    data = src.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    dest.write_bytes(data)

    meta = {
        "name": name or src.stem,
        "source": source,
        "notes": notes,
        "promoted_at": datetime.now().isoformat(timespec="seconds"),
        "original_path": str(src.resolve()),
        "sha256": sha256,
    }
    library_meta_path(dest).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return dest