"""Camera acquisition subsystem."""

from stereo_pose.capture.camera import open_camera, read_stereo_pair
from stereo_pose.capture.selection import (
    CameraCandidate,
    CameraChoice,
    CameraSelectionSession,
    discover_cameras,
    run_camera_selection,
    save_camera_choice,
    selection_requested,
)

__all__ = [
    "open_camera",
    "read_stereo_pair",
    "CameraCandidate",
    "CameraChoice",
    "CameraSelectionSession",
    "discover_cameras",
    "run_camera_selection",
    "save_camera_choice",
    "selection_requested",
]
