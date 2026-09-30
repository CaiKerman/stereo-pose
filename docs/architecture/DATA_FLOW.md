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

Task 002 adds fine-grained per-joint observability on top of this: `classify_joint`
assigns each selected joint exactly one terminal state (`accepted`, left/right/both
keypoint confidence, geometry unavailable, epipolar, reprojection, depth below/above,
quality score, speed, calibration unavailable, missing pose). The coarse
`frame_quality.rejected` buckets are preserved by mapping each fine state through
`aggregate_bucket`; `accepted`, `missing pose`, and `calibration unavailable` map
to no bucket, matching the v1.2 behavior of skipping the joint loop when there was
no person or no calibration. The structured result is stored internally on
`PoseFrame.diagnostics` (`FrameDiagnostics`) and only surfaced as text via the `D`
hotkey — it is never serialized onto the `stereo_pose_3d/v1.2` wire.

## Validation path (V hotkey)

`app.runner` also supports a single-frame metric capture triggered by `V`:

1. detect the full corner grid in both live views
   (`validation.detect_checkerboard`, same detector as calibration);
2. triangulate every matched corner with the active calibration;
3. compute spacing/flatness/stereo metrics
   (`validation.compute_metric_validation`);
4. render a console summary and persist a JSON report under `runtime/validation/`.

All metrics are single-frame (`sample_mode=single_frame`), in rectified-left-camera
coordinates, millimetres, with no world-coordinate convention.

## Calibration path

Runtime calibration (`RuntimeCalibration`) is a separate mode. It:

1. detects the checkerboard in both views;
2. requires stability (dwell + corner motion) and adequate board area;
3. captures pairs (auto or manual), enforcing diversity;
4. solves with `cv2.calibrateCamera` + `cv2.stereoCalibrate` + `cv2.stereoRectify`;
5. optionally robust-prunes outliers and re-solves;
6. writes a versioned NPZ into the calibration `auto/` area
   (`auto/stereo_YYYYMMDD_HHMMSS.npz`).

Metadata recorded in the NPZ includes stereo/left/right RMS, sample epipolar
statistics, sample/prune counts, readiness, image size, board geometry, creation
time, and the capture camera identity/config (indices, backend, requested /
actual resolution and FPS).

## Generated artifacts

```text
runtime/
├─ calibrations/auto/stereo_*.npz          # rolling calibrations (cleanup-managed)
├─ calibrations/saved/<name>.npz(.meta.json)  # user-pinned library (never auto-cleaned)
├─ sessions/session_*/left|right/*.png        # captured calibration source (transient)
├─ validation/metric_YYYYMMDD_HHMMSS.json     # metric-validation reports (evidence)
├─ logs/stereo_pose.log                       # rotating logs
└─ captures/                                  # reserved for future captures
```

Cleanup (`persistence.cleanup`) only operates inside these managed roots, requires
a mandatory trusted runtime root, touches only `calibrations/auto/` and the
session area, checks deletion candidates against the safety guard before
deleting, and never deletes `saved/` or `validation/`.