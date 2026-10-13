# Stereo calibration

Artifact policy, metadata, and loading behavior.

## Task004 capture policy

Static evidence requires >=3 valid stereo grid observations and >=.30s observed
time, not three frames inside a .30s window. This supports 30/5/2Hz detection;
short missing detections pause time, loss/stall resets by an adaptive cadence
timeout (minimum new stable_loss_grace_s=1.25). Default 5px excursion budget,
.7s interval and .12 diversity remain. Coherent drift and bad order are rejected;
direct/reverse-180 motion correspondence and circular orientation avoid fake
movement/new poses. Same held pose never repeats. SPACE bypasses stability/
interval/diversity on cached full/large stereo detections, warning on duplicates.
Samples count only after both PNG writes succeed; capture session names are
unique. New diagnostic panel explains observation/time/detection/motion/area/
interval/repeated-pose blockers and actual detection rate. See Task004 instruction.
Solver math, _load_points re-detection and NPZ format remain unchanged; this does
not establish absolute accuracy or close the owner's high-RMS diagnosis.

## Coordinate frame

Triangulation and legacy output use **rectified-left-camera** coordinates.
Live XYZ/CSV applies validated saved W/zero or derived default camera-midpoint
coordinates afterward. Task004 changes capture evidence, not those transforms.

## Artifact policy

Stereo calibration files are **versioned, not overwritten**, and are split into
two managed classes under the runtime calibration directory:

```text
runtime/calibrations/
├─ auto/stereo_YYYYMMDD_HHMMSS.npz        # rolling, auto-generated; rolled by cleanup
└─ saved/<name>.npz + <name>.meta.json    # user-pinned library; never auto-cleaned
```

New solves (`RuntimeCalibration`) land in `auto/`. A generated calibration can
be promoted into the preserved library with
`persistence.promote.promote_calibration` (or the live-app `P` hotkey); the
promotion copies the artifact byte-for-byte and writes a sidecar
`<name>.meta.json` with name, provenance, notes, original path, and a SHA-256
checksum. `saved/` is never touched by automatic cleanup.

Loading (`calibration.selection.newest_calibration`) picks the newest `auto/`
file by modification time, ignores `saved/` unless an explicit path is supplied,
and falls back to legacy flat `stereo_*.npz` / `stereo_calib.npz` for read
compatibility.

## Solver

`calibration.collection.RuntimeCalibration` performs:

1. `cv2.calibrateCamera` per camera (intrinsics initial guess);
2. `cv2.stereoCalibrate` (fixed intrinsics) to get `R`/`T`;
3. `cv2.stereoRectify` to produce `R1,R2,P1,P2,Q`.

Optional robust pruning re-solves after removing a bounded fraction of
outlier samples by rectified epipolar error.

## Metadata written to the NPZ

| Field | Meaning |
|---|---|
| `K1,D1,K2,D2` | per-camera intrinsics + distortion |
| `R,T,E,F` | stereo rotation/translation/essential/fundamental |
| `R1,R2,P1,P2,Q` | rectification + projection + disparity-to-depth |
| `image_size` | (width, height) |
| `board_cols/rows`, `square_mm` | checkerboard geometry |
| `left_rms`, `right_rms`, `stereo_rms` | RMS reprojection errors |
| `sample_count`, `sample_count_initial`, `pruned_count` | sample statistics |
| `sample_epipolar_mean_px`, `sample_epipolar_max_px` | rectified epipolar stats |
| `readiness` | heuristic sample-preparation score (not a confidence) |
| `created_at` | `YYYYMMDD_HHMMSS` |
| `_schema_version` | software/schema version |
| `camera_left`, `camera_right` | camera indices used to capture |
| `camera_backend` | OpenCV backend name used |
| `camera_requested_size` | requested (width, height) |
| `camera_requested_fps` | requested FPS |
| `camera_actual_fps` | reported actual FPS (if available) |

`RuntimeCalibration.set_camera_context` records the capture camera identity and
configuration so a loaded artifact can be checked against the currently active
cameras.

## Loading and compatibility

`calibration.metadata.load_calibration_metadata` checks required keys and
emits warnings (rather than silently assuming validity) when `image_size`,
board geometry, or camera FPS mismatch caller expectations. The live load path
calls `validate_calibration_compatibility(path, image_size, board, fps)` to
surface resolution / board / FPS mismatches against the active capture before a
calibration is activated — it only warns, never rejects.

`geometry.StereoTriangulator` accepts either an NPZ path or a mapping of the
required matrices, so synthetic geometry can be tested without a real
calibration artifact.

## Runtime recalibration constraints

Capture only accepts checkerboards that are visible, large enough, and stable
in **both** cameras for a configurable dwell. Ordinary webcams are not hardware
synchronized; host grab skew is not sensor exposure timing.

## Cleanup

`persistence.cleanup.cleanup_project` keeps the latest N `auto/` calibration
NPZs and removes abandoned sessions older than a configurable age. The trusted
runtime root is **mandatory**: both `calibration_dir` and `session_dir` must
resolve inside it, otherwise `CleanupSafetyError` is raised before any deletion.
Deletion candidates are computed and checked against the mass-deletion safety
guard before anything is removed, `saved/` is never touched, and `saved/`
pinned artifacts survive regardless of age or count.
