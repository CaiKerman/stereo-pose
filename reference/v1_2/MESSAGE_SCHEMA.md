# Stereo Pose 3D v1.2 Message Schema

每帧一个 JSON 对象。

```json
{
  "schema": "stereo_pose_3d/v1.2",
  "timestamp_ns": 1790701200123456789,
  "frame_index": 152,
  "unit": "mm",
  "coordinate_system": "rectified_left_camera",
  "calibration_file": "calibrations/stereo_20260929_183500.npz",
  "timing": {
    "host_grab_skew_ms": 0.42,
    "pair_cycle_ms": 14.8,
    "warning": "host timing only; not sensor exposure timestamps"
  },
  "filtering": {
    "enabled": true,
    "type": "one_euro",
    "min_cutoff": 1.2,
    "beta": 0.015,
    "d_cutoff": 1.0
  },
  "frame_quality": {
    "accepted_joints": 10,
    "rejected": {
      "keypoint_confidence": 1,
      "geometry": 1,
      "depth": 0,
      "quality_score": 0,
      "speed": 0
    },
    "mean_epipolar_error_px": 0.71,
    "mean_reprojection_error_px": 0.36
  },
  "joints": {
    "left_wrist": {
      "xyz_mm": [-492.2, 31.6, 1759.4],
      "xyz_raw_mm": [-500.1, 28.2, 1773.8],
      "confidence": {
        "left": 0.96,
        "right": 0.93
      },
      "quality": {
        "score": 0.67,
        "epipolar_error_px": 0.81,
        "reprojection_error_mean_px": 0.40,
        "reprojection_error_max_px": 0.41,
        "speed_mm_s": 640.0
      },
      "uv": {
        "left": [542.1, 311.8],
        "right": [438.7, 312.5],
        "rectified_left": [535.2, 309.9],
        "rectified_right": [431.5, 310.7]
      }
    }
  }
}
```

## 注意

`host_grab_skew_ms` 不是两只摄像头的真实曝光时间差。普通 webcam 通常无法通过 OpenCV 提供可靠的传感器曝光时间戳。

`quality.score` 是综合 Pose 置信度与几何误差的启发式质量分，不是概率。
