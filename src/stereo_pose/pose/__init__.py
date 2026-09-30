"""Pose inference subsystem."""

from stereo_pose.pose.device import resolve_device
from stereo_pose.pose.estimator import PoseEstimator

__all__ = ["PoseEstimator", "resolve_device"]