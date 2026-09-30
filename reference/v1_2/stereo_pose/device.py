def resolve_device(requested="auto"):
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

    # Allow advanced Ultralytics syntax such as "0,1".
    return requested
