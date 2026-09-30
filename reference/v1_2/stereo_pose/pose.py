from pathlib import Path
import numpy as np
from ultralytics import YOLO

class PoseEstimator:
    def __init__(self, model_path, device="cpu", detection_confidence=0.35):
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Pose weight file not found: {model_path}\n"
                "This program intentionally does not auto-download weights. "
                "Put the .pt file locally and point config.pose.model to it."
            )
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
    def best_person_keypoints(result):
        if result.keypoints is None or len(result.keypoints) == 0:
            return None, None

        xy = result.keypoints.xy.cpu().numpy()
        conf = result.keypoints.conf
        if conf is None:
            # Fallback if the backend does not provide confidence.
            conf = np.ones((xy.shape[0], xy.shape[1]), dtype=np.float32)
        else:
            conf = conf.cpu().numpy()

        scores = conf.mean(axis=1)
        i = int(np.argmax(scores))
        return xy[i], conf[i]
