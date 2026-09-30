"""Persistence / artifact management subsystem.

Exposes the managed runtime path layout, safe cleanup, and the promote-to-saved
library operation.
"""

from stereo_pose.persistence.cleanup import CleanupSafetyError, cleanup_project, ensure_managed_location
from stereo_pose.persistence.paths import AUTO_SUBDIR, SAVED_SUBDIR, auto_dir, saved_dir
from stereo_pose.persistence.promote import library_meta_path, promote_calibration

__all__ = [
    "AUTO_SUBDIR",
    "SAVED_SUBDIR",
    "CleanupSafetyError",
    "auto_dir",
    "saved_dir",
    "cleanup_project",
    "ensure_managed_location",
    "promote_calibration",
    "library_meta_path",
]