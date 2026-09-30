"""Validation report persistence.

Reports are human-readable JSON saved under a managed runtime validation root
(``<runtime_root>/validation/``). This area is intentionally separate from the
calibration auto/saved areas so it is never removed by ordinary
calibration-history cleanup.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

_VALIDATION_SUBDIR = "validation"


class ValidationPathError(RuntimeError):
    """Raised when a validation output path escapes the managed root."""


def _resolved(path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(Path(path).resolve(strict=False)))))


def validation_dir(runtime_root) -> Path:
    """Return the managed validation root under ``runtime_root``."""
    return Path(runtime_root) / _VALIDATION_SUBDIR


def is_within_validation_root(path, runtime_root) -> bool:
    """True when ``path`` is inside the managed validation root."""
    root = _resolved(validation_dir(runtime_root))
    return _resolved(path) == root or _resolved(path).is_relative_to(root)


def save_validation_report(result: dict, runtime_root, *, now: datetime = None) -> Path:
    """Write a validation ``result`` dict as JSON and return its path.

    The destination filename is generated internally (timestamp + counter) so the
    output can never escape the managed validation root. Collisions are resolved
    with exclusive creation, never overwriting an existing report.
    """
    root = _resolved(validation_dir(runtime_root))
    root.mkdir(parents=True, exist_ok=True)

    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    dest = root / f"metric_{stamp}.json"
    counter = 1
    while True:
        if not is_within_validation_root(dest, runtime_root):
            raise ValidationPathError(f"validation output {dest} escapes managed root {root}")
        try:
            with open(dest, "x", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            return dest
        except FileExistsError:
            dest = root / f"metric_{stamp}_{counter}.json"
            counter += 1