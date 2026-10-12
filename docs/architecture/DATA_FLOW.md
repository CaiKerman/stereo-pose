## Task003A additions

The tracking loop processes the union of legacy-selected and live-readout joints once, with the same C geometry/quality/speed/One Euro gates. A projected PoseFrame preserves legacy selected joints and statistics for v1.2. A separate fresh readout contains eyes/midpoint, accepted raw/filtered C/W and distinctly rejected candidate/missing values. It feeds the display and manual recorder without further camera acquisition/YOLO.

W freezes the current pair for on-demand ArUco detection and reference CSV correspondence. Proper no-scale fit/relative zero -> axes preview/up confirmation -> new immutable combined saved NPZ -> explicit config path/hash preference -> restart same artifact. Stereo re-solve uniquely/atomically publishes a new auto archive, persists its selection and invalidates W. P remains preserve-copy only.

T starts a unique recording session; absolute monotonic deadlines select new processed frames only. C/W/F/resolution/calibration change or exit segments/stops. CSV streams accepted/candidate/missing rows; JSON freezes calibration/world/model/actual device/quality/full filtering/camera sizes and lifecycle. Cleanup refuses recording roots and excludes current active auto NPZ.

Contract: ../protocols/WORLD_NPZ_CSV_V1.md. Runtime outputs: runtime/world/reference_points.csv, runtime/calibrations/saved/world_*.npz, runtime/recordings/session_*/joints.csv + session.json. Generated private files are not Git fixtures.

# Data flow

The live pipeline data flow (port of the validated v1.2 behavior).

## Camera selection path (startup, Task 002A)

Before the stereo tracking loop opens its two cameras, the RUN_ME launcher
(`camera.selection.startup_pick`, default true) and the explicit
`--camera-pick` CLI flag can run an interactive picker
(`capture.selection.run_camera_selection`):

1. probe indexes `0..camera.selection.probe_max_index` (default 7) with the
   same backend/fourcc/buffer settings as tracking; sparse indexes are natural
   (missing devices simply fail to open);
2. keep only cameras that open **and deliver a frame** within
   `first_frame_attempts` reads as usable, holding their handles for the live
   preview;
3. render one labeled live tile per usable camera (`CAM n` + assigned role:
   LEFT green / RIGHT blue) plus a status/instruction bar — visual
   identification, no camera-name requirement;
4. number keys assign LEFT then RIGHT (distinct cameras only), `U` undo,
   `R` rescan (after plug/unplug), `ENTER` confirm, `Q`/`ESC` cancel;
5. on confirm, atomically persist `camera.left`/`camera.right` to the local
   config.json (temp file + `os.replace`, unrelated fields preserved); on
   cancel nothing is written;
6. release **every** probe handle on every path (confirm / cancel / rescan /
   error) before returning, so tracking opens its cameras from a clean device
   state.

Noninteractive runs never see this UI: explicit `--left-cam`/`--right-cam`
always win, the flag-less CLI path never opens it, and
`STEREO_POSE_NO_CAMERA_PICK` force-disables the launcher entry.

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

When a calibration is loaded for tracking, `camera_identity_warnings`
(Task 002A) compares the recorded left/right indexes with the currently
selected ones and prints a prominent banner on mismatch or unverifiable
pairing: numeric equality never proves physical identity, and the warning
never deletes or rewrites the NPZ — the operator decides whether to keep the
calibration or recalibrate.

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
