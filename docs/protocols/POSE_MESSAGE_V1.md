# Pose message protocol — `stereo_pose_3d/v1.2`

Compatibility baseline for externally visible output. Field names and units are
fixed; internal refactors must serialize through this adapter
(`stereo_pose.outputs.v1_message.to_v1_message`).

One frame = one JSON object.

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
      "confidence": { "left": 0.96, "right": 0.93 },
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

## Field notes

- `unit` is always `"mm"`; `coordinate_system` is always
  `"rectified_left_camera"` for the current PoC.
- `calibration_file` is the versioned NPZ path, or `null` when no calibration is
  loaded (3D output disabled).
- `xyz_mm` is the one-euro-filtered value; `xyz_raw_mm` is the value after
  geometric quality acceptance but before smoothing.
- `host_grab_skew_ms` is a host-side diagnostic, **not** the sensor exposure time
  difference.
- `quality.score` is a heuristic combining pose confidence and geometric error;
  it is **not** a probability.

## Joint names

COCO 17-keypoint vocabulary (see `stereo_pose/joints.py`):

```
nose, left_eye, right_eye, left_ear, right_ear,
left_shoulder, right_shoulder, left_elbow, right_elbow,
left_wrist, right_wrist, left_hip, right_hip,
left_knee, right_knee, left_ankle, right_ankle
```

## Compatibility rule

External consumers must keep receiving the same field names and units. Internal
refactors may change internal structure; the adapter keeps the wire format
stable. Field names and units must not be silently renamed or reinterpreted.