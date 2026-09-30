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

## Review round 1 (PR #1 feedback)

### Added

- `persistence/paths.py` — `auto/` / `saved/` managed subdirectory helpers.
- `persistence/promote.py` — `promote_calibration` (copies a generated artifact
  into `saved/` and writes a `*.meta.json` sidecar with name / provenance /
  notes / original path / SHA-256) and `library_meta_path`.
- `calibration.metadata.validate_calibration_compatibility` — returns
  resolution / board / FPS mismatch warnings for the live load path.
- `RuntimeCalibration.set_camera_context` and `StereoCalibrationMetadata` camera
  fields (left/right index, backend, requested/actual resolution and FPS).
- Config keys `camera.fourcc`, `camera.buffer_size`, `runtime.root` (schema +
  validation), wired into `open_camera` and cleanup.
- Tests: `test_promote.py`, `test_calibration_metadata.py`, `test_camera.py`;
  rewrote `test_cleanup.py` and `test_calibration_selection.py`; extended
  `test_config.py`. Suite grew from 63 to 88 tests.

### Modified

- `persistence/cleanup.py` — trusted-runtime-root guard; deletes only `auto/`
  and the session area, never `saved/`; raises `CleanupSafetyError` on
  out-of-bound paths; bails if >10000 items would be removed.
- `calibration/collection.py` — new solves land in `auto/` and embed camera
  context metadata.
- `calibration/selection.py` — prefers `auto/`, ignores `saved/` unless explicit.
- `app/runner.py` — `P` hotkey pins the active calibration; startup
  compatibility report; passes `runtime.root` to cleanup; fourcc/buffer_size from
  config; restored `readiness < recommended_readiness` pre-solve warning.
- `diagnostics/doctor.py` — reports `auto` / `saved` / `legacy` calibration counts.

### Behavior changes

- Calibration artifacts are now split into `auto/` (rolling, cleanup-managed)
  and `saved/` (pinned, never auto-deleted).
- Cleanup requires resolved paths to be inside a trusted runtime root.
- Camera `fourcc` and `buffer_size` are configurable (defaults `MJPG` / `1`
  preserved for backward compatibility).

### Numerical behavior changes

- None. Measurement math is unchanged; the new compatibility checks are
  warn-only and never reject a calibration.

## Review round 2 (PR #1 feedback)

### Modified

- `persistence/cleanup.py` — `runtime_root` is now a required parameter
  (omission is a `TypeError`, falsy value raises `CleanupSafetyError`), so the
  containment guard can no longer be bypassed. Deletion candidates are computed
  and checked against `_MAX_REMOVED_GUARD` *before* anything is removed.
- `calibration/selection.py` — `newest_calibration` now enforces strict order:
  explicit file → newest `auto/*.npz` → (only if `auto/` empty) newest legacy
  root `stereo_*.npz` → legacy `./stereo_calib.npz`. A newer legacy flat file
  can no longer override managed auto history.
- `persistence/promote.py` — destination created via exclusive creation
  (`open(..., "xb")`) with an incrementing counter; sidecar uses
  `open(..., "x")`. Same-name promotions can no longer overwrite a saved NPZ or
  its sidecar.
- `app/runner.py` — three `cleanup_project` call sites pass the now-mandatory
  `runtime_root`.

### Behavior changes

- Automatic cleanup is impossible without a trusted runtime root.
- Mass-deletion safety guard fires before any deletion, not after.
- Auto calibration history always wins over a newer legacy flat file.
- Promotion never overwrites an existing pinned artifact.

### Numerical behavior changes

- None. These are containment/selection/persistence safety fixes; measurement
  math is untouched.

### Tests

- Added `test_omitting_runtime_root_refuses_cleanup`,
  `test_none_runtime_root_refuses_before_deletion`,
  `test_over_limit_cleanup_aborts_before_deleting_anything`,
  `test_auto_beats_newer_legacy_flat_file`,
  `test_rapid_same_name_promotions_stay_distinct`. Suite grew from 88 to 93
  tests.