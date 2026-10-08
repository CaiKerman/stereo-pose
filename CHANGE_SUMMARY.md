# Change summary — Task 002 (metric validation + joint rejection diagnostics)

## Added

- `src/stereo_pose/validation/` — checkerboard 3D metric validation:
  `metrics.py` (synthetic-ready metric math: spacing, scale error, plane fit,
  epipolar/reprojection, depth range), `report.py` (exclusive JSON persistence
  under `runtime/validation/` that never overwrites and never escapes the
  managed root), and package exports.
- `src/stereo_pose/diagnostics/joint_diagnostics.py` — pure, deterministic
  formatter for the per-joint diagnostic summary and aggregate footer.
- `models.py` — `JointRejection` and `FrameDiagnostics` dataclasses, plus the
  optional, internal `PoseFrame.diagnostics` field.
- `quality/scoring.py` — `RejectionReason` fine-grained terminal states,
  `classify_joint`, and `aggregate_bucket` mapping fine states to coarse v1.2
  buckets.
- `config.py` / `configs/default.json` / `configs/schemas/default.schema.json` —
  new `diagnostics` section (`enabled`, `every_n_frames`).
- `docs/validation/METRIC_VALIDATION.md` — validation procedure documentation.
- Tests: `test_joint_rejection.py`, `test_metric_validation.py`,
  `test_diagnostics_render.py`, `test_validation_report.py` (33 new tests).

## Modified

- `app/runner.py` — per-joint classification in the tracking loop; `D` hotkey
  toggles the diagnostic summary, `V` hotkey captures a single-frame metric
  validation; startup/overlay help text updated.
- `docs/architecture/ARCHITECTURE.md`, `docs/architecture/DATA_FLOW.md` — new
  `validation/` subsystem, fine-grained rejection path, and the
  `runtime/validation/` artifact.
- `README.md`, `README_先看我.txt`, `RUN_ME.py`, `RUN_ME.bat` — operator help
  updated with accurate `D`/`V` hotkeys and AUTO/SPACE calibration semantics.

## Deleted

- None.

## Behavior changes

- Tracking now classifies every selected joint into a single terminal state each
  frame; this is observability only, and does not change acceptance/rejection.
- `D` and `V` hotkeys are available in tracking mode.
- Metric validation reports are written under `runtime/validation/`, which is
  never removed by calibration-history cleanup.

## Numerical behavior changes

- None. Measurement thresholds, quality score, triangulation, filtering, and the
  v1.2 `rejected` aggregate counters are preserved. `accepted`, missing-pose, and
  no-calibration states map to no aggregate bucket, exactly matching the v1.2
  behavior of skipping the joint loop in those cases.

## Protocol/config changes

- `stereo_pose_3d/v1.2` output message unchanged.
- New optional `diagnostics` config section (defaults `enabled=false`,
  `every_n_frames=10`).
- New metric-validation report schema `stereo_pose_3d/metric_validation/v1`
  (internal, single-frame), stored separately from calibration artifacts.

## Known issues

- Metric validation is single-frame only (`sample_mode=single_frame`); a stable
  multi-frame aggregate was deferred to avoid unnecessary complexity. The report
  records `sample_mode` so the distinction is never hidden.
- Live-camera path was not executed in this environment (no cameras/model
  weights); the `D`/`V` hotkeys and report files were exercised via the
  deterministic tests and pure functions only. See `TEST_REPORT.md`.

## Review round 1 (PR #2 feedback)

### Added

- `validation/metrics.py` — `normalize_correspondence` (correspondence
  normalization choosing between `direct` and `reversed_180` orderings using
  aggregate rectified epipolar geometry), `_candidate_fit`, and
  `MetricValidationError`. The `MetricValidationResult` report gains a
  `corner_order_mode` field.
- Tests in `tests/unit/test_metric_validation.py`
  (`TestCorrespondenceNormalization`): direct selects direct, reversed right is
  corrected, implausible fails cleanly, and reversed input still recovers the
  expected 25 mm grid. `test_validation_report.py` now asserts
  `corner_order_mode` round-trips and is a required key.

### Modified

- `validation/metrics.py` — `compute_metric_validation` normalizes corner
  correspondence before triangulation and raises `MetricValidationError` when
  neither ordering is geometrically plausible.
- `validation/__init__.py` — exports `normalize_correspondence`,
  `MetricValidationError`, `MAX_PLAUSIBLE_MEAN_EPIPOLAR_PX`.
- `app/runner.py` — the `V` path catches `MetricValidationError` and reports
  failure instead of writing a misleading report.
- `docs/validation/METRIC_VALIDATION.md` — documents correspondence
  normalization, the `corner_order_mode` field, and the failure behavior.

### Behavior changes

- A checkerboard whose two detected corner orderings disagree by 180 degrees is
  now corrected to a consistent matching before triangulation; previously the
  positional pairing could create wrong correspondences and inflate the metric
  error.
- A capture whose correspondence is implausible under both orderings is rejected
  (validation failure) rather than emitting misleading 25 mm statistics.

### Numerical behavior changes

- None for the measured metrics on an already-consistent board. The new
  normalization is evidence-based (epipolar geometry) and records `corner_order_mode`;
  it never changes the spacing/plane/scale math. No v1.2 output or measurement
  threshold is affected.

## Task 002A — pre-test camera discovery & LEFT/RIGHT selection (owner request)

### Added

- `src/stereo_pose/capture/selection.py` — camera discovery, preview, and
  interactive LEFT/RIGHT selection: `discover_cameras` (bounded index probing,
  frame-delivering-only usability, sparse-index support), pure
  `CameraSelectionSession` state machine (number keys assign LEFT then RIGHT,
  distinct cameras only; `U` undo, `R` rescan, `ENTER` confirm, `Q`/`ESC`
  cancel), `render_canvas` (labeled live tiles: `CAM n` + LEFT green / RIGHT
  blue role tags + status/instruction bar), `save_camera_choice` (atomic
  temp-file + `os.replace` persistence preserving unrelated fields),
  `run_camera_selection` (full picker; releases every probe handle on every
  path), and `selection_requested` (launcher gating). All device/GUI access is
  injectable for hardware-free deterministic tests.
- `calibration/metadata.py` — `camera_identity_warnings`: compares the active
  calibration NPZ's recorded left/right indexes with the currently selected
  pair; warn-only, never deletes/rewrites the NPZ.
- Config `camera.selection` section (`startup_pick` default true,
  `probe_max_index` default 7, `first_frame_attempts` default 5) in
  `config.py` defaults + validation, `configs/default.json`, and
  `configs/schemas/default.schema.json`.
- CLI `--camera-pick` flag on `stereo_pose run` (opt-in; suppressed by explicit
  `--left-cam`/`--right-cam`).
- Tests: `tests/unit/test_camera_selection.py` (43 tests: discovery/assignment/
  rescan/error paths, handle release on every path, atomic + field-preserving
  config write, cancel-never-writes, malformed-config safety, CLI precedence,
  noninteractive gating, calibration identity warnings).

### Modified

- `RUN_ME.py` — offers the picker before doctor/tracking when
  `selection_requested` (default on); failure of the picker never blocks
  startup; config reloaded after confirmation. `RUN_ME.bat` banner explains
  the selection step.
- `app/runner.py` — `--camera-pick` flag; `should_pick_cameras` precedence
  (explicit CLI indexes > `--camera-pick` > nothing); startup and post-solve
  calibration compatibility reports now also surface camera-index identity
  warnings as a prominent banner.
- `tests/unit/test_cleanup.py::test_rejects_symlink_escape` — made
  deterministic: the symlink target's mtime is aged explicitly, because
  the candidate sort key `stat().st_mtime` follows the link and tied
  timestamps let directory order decide which file was "newest".
- `README_先看我.txt` (visual LEFT/RIGHT picking instructions + 3-camera
  manual acceptance checklist + calibration-identity reminder),
  `README.md`, `docs/architecture/DATA_FLOW.md` (camera-selection path,
  identity-warning behavior).

### Behavior changes

- `RUN_ME.bat` now opens the visual camera picker by default before tracking
  (`camera.selection.startup_pick: true`; disable via config or the
  `STEREO_POSE_NO_CAMERA_PICK` environment variable). Confirmed choices are
  persisted to the local config.json; cancellation leaves it unchanged.
- Startup prints a prominent warning banner when the active calibration's
  recorded camera indexes differ from the selected pair (or cannot be
  verified). The warning is advisory: no calibration file is deleted,
  overwritten, or auto-invalidated.

### Numerical behavior changes

- None. No measurement thresholds, quality gates, filters, or v1.2 outputs
  changed.

---

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