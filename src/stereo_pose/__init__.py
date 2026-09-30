"""Stereo Pose — formal engineering package.

The validated v1.2 proof-of-concept lives under ``reference/v1_2/`` and is kept
as immutable baseline evidence. This package is the formal implementation.

Numerical behavior of the v1.2 pipeline is preserved; see
``docs/calibration/STEREO_CALIBRATION.md`` and ``docs/protocols/POSE_MESSAGE_V1.md``.
"""

__version__ = "0.1.0"

# Compatibility reference: the externally-facing message schema produced by the
# v1.2 pipeline. Kept here as an explicit, greppable contract.
V1_SCHEMA = "stereo_pose_3d/v1.2"