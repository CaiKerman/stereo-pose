"""Camera discovery, preview, and interactive LEFT/RIGHT selection (Task 002A).

Before the stereo tracking loop opens its two cameras, the operator must be
able to visually identify every usable camera feed and assign two distinct
physical cameras to the LEFT and RIGHT roles — without editing config.json,
knowing OpenCV indexes, or using Git/CLI.

Design constraints (see ``docs/instructions/002A_CAMERA_SELECTION_PRETEST.md``):

* discovery probes a bounded, configurable index range and marks only cameras
  that actually open **and deliver at least one frame** as usable;
* every temporary ``cv2.VideoCapture`` handle is released on every path
  (confirm / cancel / rescan / error) before the normal stereo ``open_camera``
  calls run;
* a confirmed choice is persisted to the local config.json with an atomic
  replace that keeps unrelated settings intact; cancelling never writes;
* all device and GUI access is funneled through small injectable callables so
  the deterministic test suite can exercise every path without camera
  hardware or a display.

Noninteractive runs never open this UI: it is only reached via the RUN_ME
launcher (``camera.selection.startup_pick``) or the explicit ``--camera-pick``
CLI flag, and is skipped entirely when ``--left-cam``/``--right-cam`` are given.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from stereo_pose.capture.camera import open_camera
from stereo_pose.config import load_config

WINDOW_NAME = "Stereo Pose - camera selection (press number keys: LEFT first, then RIGHT)"

# Preview tile geometry (fixed UI constants, not user-facing measurement config).
TILE_W = 400
TILE_H = 225
TILES_PER_ROW = 3
MESSAGE_BAR_LINES = 3
MESSAGE_BAR_LINE_H = 26

KEY_ENTER = 13
KEY_ESC = 27
KEY_NONE = 255  # (waitKey() == -1) & 0xFF

INSTRUCTION_LINE = (
    "Keys: 0-9 assign LEFT then RIGHT | U=undo | R=rescan | ENTER=confirm | Q/ESC=cancel (keep config)"
)


@dataclass
class CameraCandidate:
    """One probed camera index and whether it can deliver frames."""

    index: int
    usable: bool
    frame: Optional[np.ndarray] = None
    error: Optional[str] = None


@dataclass
class CameraChoice:
    """A confirmed, distinct LEFT/RIGHT camera index assignment."""

    left: int
    right: int


@dataclass
class CameraProbeResult:
    """Outcome of one discovery scan over the probed index range."""

    candidates: List[CameraCandidate] = field(default_factory=list)
    handles: Dict[int, object] = field(default_factory=dict)  # usable index -> open handle

    @property
    def usable_indexes(self) -> List[int]:
        return [c.index for c in self.candidates if c.usable]


class CameraSelectionSession:
    """Pure LEFT/RIGHT assignment state machine (no device or cv2 calls).

    Keys: ``0``-``9`` assign the corresponding usable camera — the first valid
    press fixes LEFT, later presses fix/replace RIGHT (never equal to LEFT);
    ``u`` undoes the most recent assignment. ``handle_key`` returns a terminal
    action string (``"confirm"`` / ``"cancel"`` / ``"rescan"``) or ``None``.
    """

    def __init__(self, usable_indexes: List[int]):
        self.usable: List[int] = list(usable_indexes)
        self.left: Optional[int] = None
        self.right: Optional[int] = None
        self.message: str = ""

    @property
    def complete(self) -> bool:
        return self.left is not None and self.right is not None and self.left != self.right

    def assign(self, index: int) -> None:
        if index not in self.usable:
            self.message = f"CAM {index} is not available"
            return
        if self.left is None:
            self.left = index
            self.message = f"LEFT = CAM {index} -- now press the number of the RIGHT camera"
            return
        if index == self.left:
            self.message = f"CAM {index} is already LEFT; RIGHT must be a different camera"
            return
        self.right = index
        self.message = f"LEFT = CAM {self.left}   RIGHT = CAM {index} -- press ENTER to confirm"

    def undo(self) -> None:
        if self.right is not None:
            self.right = None
            self.message = f"RIGHT cleared (LEFT still CAM {self.left})"
        elif self.left is not None:
            self.left = None
            self.message = "LEFT cleared"
        else:
            self.message = "nothing to undo"

    def handle_key(self, key: int) -> Optional[str]:
        """Apply one key; return a terminal action or ``None`` to continue."""
        if key < 0 or key == KEY_NONE or key > 255:
            return None
        ch = chr(key)
        if ch.isdigit():
            self.assign(int(ch))
            return None
        if key in (KEY_ENTER, ord(" ")):
            if self.complete:
                return "confirm"
            self.message = "assign two different cameras first (number keys), then press ENTER"
            return None
        if ch in ("u", "U"):
            self.undo()
            return None
        if ch in ("r", "R"):
            return "rescan"
        if ch in ("q", "Q") or key == KEY_ESC:
            return "cancel"
        return None


def discover_cameras(
    probe_max_index: int,
    open_fn: Callable[[int], object],
    read_fn: Callable[[object], Tuple[bool, Optional[np.ndarray]]],
    release_fn: Callable[[object], None],
    first_frame_attempts: int = 5,
    log: Optional[Callable[[str], None]] = None,
) -> CameraProbeResult:
    """Probe indexes ``0..probe_max_index``; keep only frame-delivering cameras.

    A camera is usable only when ``open_fn`` succeeds **and** at least one
    frame is delivered within ``first_frame_attempts`` reads (some drivers
    return a few black/failed frames on first opens). Usable handles are kept
    open for the live preview and returned in ``result.handles``; every other
    handle is released here. Sparse indexes are naturally supported (missing
    indexes simply fail to open).
    """
    result = CameraProbeResult()
    attempts = max(1, int(first_frame_attempts))
    for idx in range(int(probe_max_index) + 1):
        cap = None
        try:
            cap = open_fn(idx)
        except Exception as e:  # noqa: BLE001 — a missing/unplugged camera must not abort probing
            result.candidates.append(CameraCandidate(idx, False, error=f"open failed: {e}"))
            continue
        frame = None
        error = None
        try:
            for _ in range(attempts):
                ok, f = read_fn(cap)
                if ok and f is not None:
                    frame = f
                    break
        except Exception as e:  # noqa: BLE001
            error = f"read failed: {e}"
        if frame is not None:
            result.candidates.append(CameraCandidate(idx, True, frame=frame))
            result.handles[idx] = cap
        else:
            result.candidates.append(
                CameraCandidate(idx, False, error=error or "opened but delivered no frame")
            )
            _safe_release(release_fn, cap)
    if log is not None:
        for cand in result.candidates:
            if cand.usable:
                log(f"[camera-pick] CAM {cand.index}: usable")
            else:
                log(f"[camera-pick] CAM {cand.index}: unusable ({cand.error})")
    return result


def _safe_release(release_fn, handle) -> None:
    try:
        release_fn(handle)
    except Exception:  # noqa: BLE001 — release must never mask the primary error
        pass


def release_all(handles: Dict[int, object], release_fn) -> None:
    """Release every open probe handle exactly once (idempotent)."""
    for idx in list(handles.keys()):
        cap = handles.pop(idx)
        _safe_release(release_fn, cap)


def _draw_tile(frame: Optional[np.ndarray], index: int, session: "CameraSelectionSession") -> np.ndarray:
    if frame is None:
        tile = np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8)
        cv2.putText(tile, f"CAM {index}: NO SIGNAL", (12, TILE_H // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
        return tile
    tile = cv2.resize(frame, (TILE_W, TILE_H))
    if tile.ndim == 2:
        tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)

    # Label chip: "CAM n" always visible.
    cv2.rectangle(tile, (0, 0), (120, 34), (0, 0, 0), -1)
    cv2.putText(tile, f"CAM {index}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2, cv2.LINE_AA)

    # Role tag + border color: LEFT green, RIGHT blue, unassigned gray.
    if session.left == index:
        role, color = "LEFT", (0, 220, 0)
    elif session.right == index:
        role, color = "RIGHT", (255, 160, 0)
    else:
        role, color = "", (128, 128, 128)
    if role:
        cv2.rectangle(tile, (TILE_W - 150, TILE_H - 42), (TILE_W, TILE_H - 6), (0, 0, 0), -1)
        cv2.putText(tile, role, (TILE_W - 140, TILE_H - 15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, color, 2, cv2.LINE_AA)
    cv2.rectangle(tile, (0, 0), (TILE_W - 1, TILE_H - 1), color, 3)
    return tile


def render_canvas(frames: Dict[int, np.ndarray], session: CameraSelectionSession) -> np.ndarray:
    """Compose the preview window: labeled live tiles + status/instruction bar."""
    usable = session.usable
    cols = min(TILES_PER_ROW, max(1, len(usable)))
    rows = max(1, (len(usable) + cols - 1) // cols) if usable else 1
    grid = np.zeros((rows * TILE_H, cols * TILE_W, 3), dtype=np.uint8)
    for i, idx in enumerate(usable):
        r, c = divmod(i, cols)
        tile = _draw_tile(frames.get(idx), idx, session)
        grid[r * TILE_H:(r + 1) * TILE_H, c * TILE_W:(c + 1) * TILE_W] = tile

    bar_h = MESSAGE_BAR_LINES * MESSAGE_BAR_LINE_H + 10
    canvas = np.zeros((grid.shape[0] + bar_h, grid.shape[1], 3), dtype=np.uint8)
    canvas[: grid.shape[0]] = grid

    status = f"LEFT camera = {session.left if session.left is not None else '?'}   " \
             f"RIGHT camera = {session.right if session.right is not None else '?'}"
    if not usable:
        status = "No usable cameras found. Connect two USB webcams, then press R to rescan."
    elif len(usable) < 2:
        status = f"Only {len(usable)} usable camera found (CAM {usable}). " \
                 f"Connect two USB webcams, then press R to rescan."

    y = grid.shape[0] + 22
    cv2.putText(canvas, status, (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                0.68, (255, 255, 255), 2, cv2.LINE_AA)
    y += MESSAGE_BAR_LINE_H
    cv2.putText(canvas, INSTRUCTION_LINE, (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (200, 200, 200), 1, cv2.LINE_AA)
    y += MESSAGE_BAR_LINE_H
    if session.message:
        cv2.putText(canvas, session.message[:110], (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 220, 255), 1, cv2.LINE_AA)
    return canvas


def _selection_loop(
    session: CameraSelectionSession,
    probe: CameraProbeResult,
    read_fn,
    release_fn,
    wait_key: Callable[[], int],
    show_fn: Callable[[np.ndarray], None],
    max_loop_frames: Optional[int],
) -> Tuple[str, Optional[CameraChoice]]:
    """Run the interactive preview loop for one probe scan.

    Always releases every probe handle (confirm / cancel / rescan / error)
    before returning, so the stereo pipeline starts from a clean device state.
    """
    frames = {c.index: c.frame for c in probe.candidates if c.usable}
    iterations = 0
    try:
        while True:
            # Refresh live previews; keep the last good frame on transient failure.
            for idx, cap in list(probe.handles.items()):
                try:
                    ok, f = read_fn(cap)
                    if ok and f is not None:
                        frames[idx] = f
                except Exception:  # noqa: BLE001 — a dying preview must not kill the picker
                    pass
            show_fn(render_canvas(frames, session))
            action = session.handle_key(wait_key())
            if action is not None:
                choice = CameraChoice(session.left, session.right) if action == "confirm" else None
                return action, choice
            iterations += 1
            if max_loop_frames is not None and iterations >= int(max_loop_frames):
                raise RuntimeError("camera selection loop limit exceeded (no terminal key)")
    finally:
        release_all(probe.handles, release_fn)


def save_camera_choice(config_path, left: int, right: int) -> None:
    """Atomically persist ``camera.left``/``camera.right`` into the config JSON.

    * unrelated user settings are preserved verbatim;
    * a malformed existing config raises before anything is written;
    * the write goes to a temp file in the same directory followed by
      ``os.replace`` (atomic), so a failed/interrupted write cannot corrupt
      the previous config; the temp file is removed on failure.
    """
    p = Path(config_path)
    left, right = int(left), int(right)
    if left < 0 or right < 0 or left == right:
        raise ValueError(f"invalid camera choice: left={left}, right={right}")

    data: dict = {}
    if p.exists():
        with open(p, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{p} must contain a JSON object")

    camera = data.get("camera")
    if not isinstance(camera, dict):
        camera = {}
    camera["left"] = left
    camera["right"] = right
    data["camera"] = camera

    fd, tmp_name = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(p))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def run_camera_selection(
    config_path,
    cfg: Optional[dict] = None,
    *,
    open_fn: Optional[Callable[[int], object]] = None,
    read_fn: Optional[Callable[[object], Tuple[bool, Optional[np.ndarray]]]] = None,
    release_fn: Optional[Callable[[object], None]] = None,
    wait_key: Optional[Callable[[], int]] = None,
    show_fn: Optional[Callable[[np.ndarray], None]] = None,
    destroy_fn: Optional[Callable[[], None]] = None,
    max_loop_frames: Optional[int] = None,
    log: Callable[[str], None] = print,
) -> Optional[CameraChoice]:
    """Run the full interactive camera picker.

    Returns the confirmed :class:`CameraChoice` (already persisted to the
    config), or ``None`` when cancelled / not persistable — in which case the
    previous config is left untouched. All probes' camera handles are released
    before returning on every path.
    """
    if cfg is None:
        cfg = load_config(config_path if Path(config_path).exists() else None)
    cam_cfg = cfg["camera"]
    sel_cfg = cam_cfg.get("selection", {})
    probe_max_index = int(sel_cfg.get("probe_max_index", 7))
    first_frame_attempts = int(sel_cfg.get("first_frame_attempts", 5))

    if open_fn is None:
        def open_fn(idx):  # noqa: F811 — default: the real capture open path
            return open_camera(
                idx, cam_cfg["width"], cam_cfg["height"], cam_cfg["fps"], cam_cfg["backend"],
                fourcc=cam_cfg.get("fourcc", "MJPG"),
                buffer_size=cam_cfg.get("buffer_size", 1),
            )
    if read_fn is None:
        read_fn = lambda cap: cap.read()  # noqa: E731
    if release_fn is None:
        release_fn = lambda cap: cap.release()  # noqa: E731
    if wait_key is None:
        wait_key = lambda: cv2.waitKey(30) & 0xFF  # noqa: E731
    if show_fn is None:
        window_initialized = False
        def show_fn(canvas):  # noqa: F811
            nonlocal window_initialized
            if not window_initialized:
                from stereo_pose.app.desktop import configure_highgui
                configure_highgui(WINDOW_NAME,canvas.shape)
                window_initialized=True
            cv2.imshow(WINDOW_NAME, canvas)
    if destroy_fn is None:
        destroy_fn = cv2.destroyAllWindows

    try:
        while True:
            probe = discover_cameras(
                probe_max_index, open_fn, read_fn, release_fn,
                first_frame_attempts=first_frame_attempts, log=None,
            )
            usable = probe.usable_indexes
            if len(usable) < 2:
                log(
                    f"[camera-pick] WARNING: only {len(usable)} usable camera(s) found "
                    f"(CAM {usable}). Connect the two USB webcams, then rescan."
                )
            else:
                log(f"[camera-pick] usable cameras: CAM {usable} — pick LEFT first, then RIGHT")

            session = CameraSelectionSession(usable)
            action, choice = _selection_loop(
                session, probe, read_fn, release_fn, wait_key, show_fn, max_loop_frames,
            )
            if action == "rescan":
                continue
            if action == "confirm" and choice is not None:
                try:
                    save_camera_choice(config_path, choice.left, choice.right)
                except Exception as e:  # noqa: BLE001 — keep previous config, make failure visible
                    log(f"[camera-pick] ERROR: could not save camera choice to {config_path}: {e}")
                    log("[camera-pick] previous config.json left unchanged")
                    return None
                log(
                    f"[camera-pick] confirmed and saved: LEFT=CAM {choice.left} "
                    f"RIGHT=CAM {choice.right} -> {config_path}"
                )
                return choice
            log("[camera-pick] cancelled — config.json left unchanged")
            return None
    finally:
        try:
            destroy_fn()
        except Exception:  # noqa: BLE001 — headless teardown must not mask the result
            pass


def selection_requested(cfg: dict, env: Optional[dict] = None) -> bool:
    """Whether the RUN_ME startup flow should offer the interactive picker.

    ``camera.selection.startup_pick`` (default true) controls the launcher;
    the ``STEREO_POSE_NO_CAMERA_PICK`` environment variable (any non-empty
    value) force-disables it for automated/noninteractive runs.
    """
    env = os.environ if env is None else env
    if env.get("STEREO_POSE_NO_CAMERA_PICK"):
        return False
    sel = cfg.get("camera", {}).get("selection", {})
    return bool(sel.get("startup_pick", True))
