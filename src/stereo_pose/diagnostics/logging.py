"""Diagnostics logging: structured, non-flooding log setup."""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(log_dir=None, level=logging.INFO, console=True):
    """Configure root/package logging. Returns the configured logger name prefix.

    Logs go to a rotating-style single file (size-capped via RotatingFileHandler)
    under ``log_dir`` and optionally to the console.
    """
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger("stereo_pose")
    root.setLevel(level)
    root.propagate = False
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    fmt = logging.Formatter(_FORMAT)

    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)

    if log_dir:
        d = Path(log_dir)
        d.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(d / "stereo_pose.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``stereo_pose`` namespace."""
    return logging.getLogger(f"stereo_pose.{name}")