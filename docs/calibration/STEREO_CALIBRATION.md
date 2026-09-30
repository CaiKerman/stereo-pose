# Stereo calibration

Artifact policy, metadata, and loading behavior.

## Coordinate frame

The current PoC triangulates into the **rectified-left-camera** frame. The
future world frame requires ground `Z=0`, `+Z` upward, and a user-calibrated
origin/X/Y — none of which is defined in this task.

## Artifact policy

Stereo calibration files are **versioned, not overwritten**:

```text
runtime/calibrations/stereo_YYYYMMDD_HHMMSS.npz
```

Loading uses the newest versioned file by modification time
(`calibration.selection.newest_calibration`), with a legacy fallback to
`stereo_calib.npz` for compatibility.

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

## Loading and compatibility

`calibration.metadata.load_calibration_metadata` checks required keys and
emits warnings (rather than silently assuming validity) when
`image_size` or board geometry mismatch caller expectations.

`geometry.StereoTriangulator` accepts either an NPZ path or a mapping of the
required matrices, so synthetic geometry can be tested without a real
calibration artifact.

## Runtime recalibration constraints

Capture only accepts checkerboards that are visible, large enough, and stable
in **both** cameras for a configurable dwell. Ordinary webcams are not hardware
synchronized; host grab skew is not sensor exposure timing.

## Cleanup

`persistence.cleanup.cleanup_project` keeps the latest N calibration NPZs and
removes abandoned sessions older than a configurable age. It only touches
managed runtime roots and never recursively deletes arbitrary user paths.