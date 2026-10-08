"""Pose inference (YOLO Pose) wrapper.

``ultralytics`` is imported lazily so the rest of the package (config, geometry,
doctor, tests) can be imported without torch/ultralytics installed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class PoseEstimator:
    def __init__(self, model_path, device="cpu", detection_confidence=0.35):
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Pose weight file not found: {model_path}\n"
                "This program intentionally does not auto-download weights. "
                "Put the .pt file locally and point config.pose.model to it."
            )
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise ImportError(
                "ultralytics is required for live pose inference but is not installed. "
                "Install the 'live' extra (pip install .[live]) or run offline tests."
            ) from e

        self.model = YOLO(str(model_path))
        self.device = device
        self.det_conf = float(detection_confidence)

    def infer_pair(self, left_frame, right_frame):
        results = self.model.predict(
            [left_frame, right_frame],
            device=self.device,
            verbose=False,
            conf=self.det_conf,
        )
        return results[0], results[1]

    @staticmethod
    def best_person(result):
        """Return the best-scoring person's keypoints, confidence, chosen
        index, and the total person detection count.

        ``(keypoints_xy, keypoints_conf, chosen_index, detection_count)``;
        ``(None, None, None, 0)`` when no person/keypoints are present.
        """
        if result.keypoints is None or len(result.keypoints) == 0:
            return None, None, None, 0

        xy = result.keypoints.xy.cpu().numpy()
        conf = result.keypoints.conf
        if conf is None:
            conf = np.ones((xy.shape[0], xy.shape[1]), dtype=np.float32)
        else:
            conf = conf.cpu().numpy()

        scores = conf.mean(axis=1)
        i = int(np.argmax(scores))
        return xy[i], conf[i], i, int(xy.shape[0])

    @staticmethod
    def best_person_keypoints(result):
        xy, conf, _, _ = PoseEstimator.best_person(result)
        return xy, conf
