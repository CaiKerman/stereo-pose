"""Pose inference hardware device resolution (cpu / auto / CUDA index)."""

from __future__ import annotations


def resolve_device(requested="auto"):
    """Resolve a requested device selector to a value Ultralytics accepts.

    Raises a clear error when a numeric CUDA index is requested but CUDA is not
    available. Allows advanced Ultralytics syntax (e.g. ``"0,1"``) through.
    """
    requested = str(requested).strip().lower()

    if requested == "cpu":
        return "cpu"

    try:
        import torch
    except Exception:
        if requested == "auto":
            return "cpu"
        raise

    if requested == "auto":
        return "0" if torch.cuda.is_available() and torch.cuda.device_count() > 0 else "cpu"

    if requested.isdigit():
        idx = int(requested)
        if not torch.cuda.is_available():
            raise RuntimeError(
                f"CUDA device {idx} requested, but torch.cuda.is_available() is False. "
                "Use device='auto' or 'cpu'."
            )
        if idx >= torch.cuda.device_count():
            raise RuntimeError(
                f"CUDA device {idx} requested, but only {torch.cuda.device_count()} device(s) found."
            )
        return requested

    return requested