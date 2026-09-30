# Change summary — Task 001

## Added

- `pyproject.toml` — packaging (src layout), minimal deps, optional `live`/`dev` extras.
- `src/stereo_pose/` formal package with subsystem boundaries:
  `capture`, `calibration`, `pose`, `geometry`, `filtering`, `quality`,
  `coordinates`, `outputs`, `diagnostics`, `persistence`, `app`.
- `src/stereo_pose/models.py` — typed dataclasses (StereoFramePair, FrameTiming,
  Joint2DObservation, RawJoint3D, JointQuality, FilteredJoint3D,
  StereoCalibrationMetadata, CoordinateTransformMetadata, PoseFrame).
- `src/stereo_pose/config.py` — defaults, deep merge, in-process validation.
- `configs/default.json` and `configs/schemas/default.schema.json`.
- `runtime/` managed roots (`calibrations`, `sessions`, `logs`, `captures`).
- `tests/` — 63 deterministic unit/regression/integration tests.
- `python -m stereo_pose doctor` offline health check.
- Docs: `README.md`, `docs/architecture/ARCHITECTURE.md`,
  `docs/architecture/DATA_FLOW.md`, `docs/protocols/POSE_MESSAGE_V1.md`,
  `docs/calibration/STEREO_CALIBRATION.md`, `MIGRATION_NOTES.md`.

## Modified

- Root `README.md` — formal package layout, install/run/test instructions.
- (Reference untouched — preserved under `reference/v1_2/`.)

## Deleted

- None.

## Behavior changes

- `pose/estimator.py` imports `ultralytics` lazily; package import no longer
  requires torch/ultralytics. Constructing `PoseEstimator` without the package
  raises a clear `ImportError`.
- `geometry.StereoTriangulator` now also accepts a mapping of matrices in
  addition to an NPZ path (enables synthetic geometry tests).

## Numerical behavior changes

- None. Triangulation, epipolar/reprojection metrics, One Euro filter, speed
  gate, quality score, readiness, and robust-prune logic are preserved. Synthetic
  stereo geometry is verified by regression test to recover known 3D points.

## Protocol/config changes

- v1.2 output message unchanged (`stereo_pose_3d/v1.2`; fields/units preserved).
- Config defaults for `calibration_dir` → `runtime/calibrations` and
  `session_dir` → `runtime/sessions`; added `runtime.log_dir`.
- Calibration NPZ gains `_schema_version` metadata field.

## Known issues

- The interactive calibration/tracking app still uses `print()` for console UX;
  structured logging is currently limited to the diagnostics subsystem. No
  functional impact.
- Live-camera path was not executed in this environment (no cameras/model
  weights); see `TEST_REPORT.md` untested hardware paths.
- `cv2.undistortPoints` returns `float32` rectified UV coordinates (unchanged
  from reference), introducing negligible rounding on rectified pixel positions.