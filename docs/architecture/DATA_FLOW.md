# Data flow

The live pipeline data flow (port of the validated v1.2 behavior).

## Tracking path (steady state)

```text
┌────────────┐   grab/retrieve    ┌──────────────────┐
│ left cam   │───────────────────▶│ read_stereo_pair │
└────────────┘                    │ (alternate order)│   StereoFramePair + FrameTiming
┌────────────┐                    └────────┬─────────┘
│ right cam  │─────────────────────────────┘
└────────────┘
                                  ▼
                       ┌────────────────────┐
                       │ PoseEstimator      │ YOLO Pose, both views
                       └────────┬───────────┘
                                │ best person keypoints (uv + conf) per view
                                ▼
                       ┌────────────────────┐
                       │ StereoTriangulator │ rectified triangulation
                       └────────┬───────────┘
                                │ RawJoint3D (xyz_mm + epipolar + reproj)
                                ▼
                       ┌────────────────────┐
                       │ quality gate       │ epipolar/depth/score
                       └────────┬───────────┘
                                │ accepted RawJoint3D
                       ┌────────▼──────────┐
                       │ TemporalSpeedGate │ speed plausibility
                       └────────┬──────────┘
                                │ speed-ok raw xyz
                       ┌────────▼──────────┐
                       │ JointSmoother     │ One Euro (per joint)
                       └────────┬──────────┘
                                │ FilteredJoint3D (raw + filtered)
                                ▼
                       ┌────────────────────┐
                       │ to_v1_message      │ stereo_pose_3d/v1.2
                       └────────┬───────────┘
                                ▼
                       ┌────────────────────┐
                       │ publisher(s)       │ console / JSONL / UDP
                       └────────────────────┘
```

## Rejection path

Each joint is rejected at the first failed gate and counted in
`frame_quality.rejected`:

1. keypoint confidence (either view below `keypoint_confidence`);
2. geometry (epipolar or reprojection over threshold, or triangulation failed);
3. depth (`min_depth_mm` / `max_depth_mm`);
4. quality score (`min_quality_score`);
5. speed (`max_joint_speed_mm_s`).

## Calibration path

Runtime calibration (`RuntimeCalibration`) is a separate mode. It:

1. detects the checkerboard in both views;
2. requires stability (dwell + corner motion) and adequate board area;
3. captures pairs (auto or manual), enforcing diversity;
4. solves with `cv2.calibrateCamera` + `cv2.stereoCalibrate` + `cv2.stereoRectify`;
5. optionally robust-prunes outliers and re-solves;
6. writes a versioned NPZ (`stereo_YYYYMMDD_HHMMSS.npz`).

Metadata recorded in the NPZ includes stereo/left/right RMS, sample epipolar
statistics, sample/prune counts, readiness, image size, board geometry, and
creation time.

## Generated artifacts

```text
runtime/
├─ calibrations/stereo_YYYYMMDD_HHMMSS.npz   # versioned calibration
├─ sessions/session_*/left|right/*.png        # captured calibration source (transient)
├─ logs/stereo_pose.log                       # rotating logs
└─ captures/                                  # reserved for future captures
```

Cleanup (`persistence.cleanup`) only operates inside these managed roots.