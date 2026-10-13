# Task004 P0 — checkerboard auto capture repair (2026-10-13)

## Added
- Pure timestamped BoardStability with bounded evidence/cadence, adaptive loss,
  time pause during missing observations, per-view excursion/coherent drift,
  temporal reverse-180 correspondence and malformed grid/order rejection.
- Explicit capture reasons and readable separate diagnostic panel with actual
  calibration detection Hz/cost, motion/order/time/count/progress and blockers.
- Cached SPACE method, duplicate warning (including immediately after AUTO),
  strict both-image write success and unique capture session folders.
- 27 new test methods + 13 subtest cases; real SB synthetic-image detection and
  original real solver/complete NPZ/triangulation reload regression.

## Modified
- Automatic capture state: fixed pose captured once; new distinct pose captured
  after settling, original interval/diversity retained. Manual force still bypasses
  stillness/interval/diversity and requires stereo visibility/min area.
- Circular orientation descriptor/readiness span prevents 180-degree detector
  flips producing fake diversity. Internal transient descriptor now 10 values;
  this is not a saved NPZ or external protocol field.
- Runner appends diagnostic panel and SPACE reuses already processed data;
  no extra read/detector/inference call. Reset/exit clears cached frame evidence.
- Config/default/schema adds stable_loss_grace_s=1.25; old config merges it.
- Task, review and operator documentation now describes this independent fix.

## Deleted
No files. Removed impossible >=3 observations-in-.30s constraint and generic
WAITING FOR STILLNESS catchall; removed duplicate SPACE detector pass.

## Behavior/numerical/protocol/config changes
- Stillness is actual observed duration + evidence count, not a high-FPS window.
  Brief misses pause; sustained loss/stall resets. Motion cap stays 5px, added
  coherent drift guard explicitly shown. Same pose does not repeat at threshold0.
- Defaults .30s/3/5px/.7s/.12 unchanged. Explicit AUTO OFF respected.
- Original detector, point loader, solver and epipolar method bodies identical;
  12 protected math/world/CSV/quality/filtering/launcher modules byte-identical.
  No triangulation/solver math, NPZ fields, external v1.2, world/default XYZ or
  CSV schema changes. No dependencies/P1/P2. PNG failures do not count as samples.

## Verification and limits
312 pytest methods + 48 subtests pass; unittest 312 OK. Code:
`b2922dbaa3ffe4cfdaa593a28f15737a9318adb4`, PR #7. Synthetic clock/points/images,
actual OpenCV/files/solver, injected hardware/model/windows. Real hardware and
RMS=3.2548 cause not certified. Original PR #2/#3/#6 unchanged/unmerged.

## Historical Task003B changes

# Task003B — default camera midpoint (2026-10-12)

## 2026-10-13 startup readiness follow-up

- Added: exact complete-file SHA recovery for a moved explicit NPZ inside the
  configured managed calibration directory, before picker/cleanup; no filename
  or latest-artifact substitution. 11 new startup tests + 3 subtest cases.
- Modified: RUN_ME honors configured model path, reports selected interpreter
  and headless OpenCV, restores sys.argv; config/camera-choice/activation accept
  UTF-8 BOM; ExitStack releases acquired camera/publisher/window resources when
  initialization or the main loop fails. Snapshot purity test inspects the same
  live handler in its new _run core, preserving all assertions.
- Deleted: no files; obsolete hardcoded default-weight check and late-only
  resource ownership removed.
- Behavior: existing working folder is the recommended update path; a fresh
  folder still needs local config, runtime and configured model. A missing/hash-
  mismatched explicit selection fails visibly rather than changing geometry.
- Numerical/protocol/config: no coordinate math, quality, dependency, schema or
  new config-key change. Existing settings/source archives remain intact.
- Verification: 285 methods + 35 subtests pass; unittest 285 OK. Same branch/PR
  #6, tested code `3d977f45f65f77f75eac29351724ceb124d717e8`. Physical Windows
  camera/model/GPU paths untested here; earlier user's parent run worked.

## Original midpoint change summary

## Added
- Derived proper no-scale default optical-center midpoint frame: +X forward,
  +Y right->left, +Z assumed up for a level/upright rig.
- Projection-center and toe-in rig tests, live/CSV consistency, W override,
  cancel/restart, zero-axis provenance and new stereo default recomputation.
- 13 new test methods and 6 subtest cases; Task003B instruction and operator docs.

## Modified
- Registration loading prefers valid owner W/zero then derives default; runtime
  startup and stereo solve use it. UI labels DEFAULT and gravity assumption.
- Default/zero metadata freezes coordinate provenance in CSV/session and saved
  zero NPZ; a full W fit supersedes assumed axes.
- Current branch/review documents follow latest owner-authorized new branch.

## Deleted
No files, hotkeys, quality gates or existing output fields.

## Behavior and numerical changes
- Default live/CSV XYZ is translated to optical midpoint and rotated to requested
  rig axes. Legacy v1.2 raw/filtered C and all triangulation/filtering/gates stay
  unchanged. No scale correction, fabricated missing coordinates or second YOLO.
- Old stereo NPZ/configs remain intact; default recomputes on restart/C-R,
  requires no markers, no extra dependency and no new config key.

## Protocol/config changes
CSV columns/schema unchanged. W fields can now contain the explicitly named
`camera_midpoint` frame; session definition carries origin/baseline/axes/R/t,
stereo fingerprint, up_reference and unconfirmed gravity. Existing saved W/zero
is preferred. Ground is not automatically Z=0 in the default frame.

## Verification and known issues
274 pytest methods + 32 subtests passed; unittest 274 OK. Exact commands/platform
in TEST_REPORT.md. Relative geometry cannot measure absolute gravity; level,
upright installation is an explicit default assumption, W establishes world-up.
Owner Windows camera sign verification remains pending. Precision and P1/P2
deferred. New branch bases on `cf408cdd`; original PR #2/#3 untouched/unmerged.

## Historical Task003A summary

# Task003A P0 — implementation complete (2026-10-12)

## Added
- Pure no-scale proper rigid fit/degeneracy/residual reporting and translation-only origin.
- ArUco ID/feature CSV adapter with triangulated physical centers; W frozen-pair preview/axes/up/name/confirm/cancel.
- Immutable stereo+world NPZ and explicit file/hash activation/restart.
- Shared measurement pass with legacy projection and fresh eye/joint/candidate readout.
- Manual T CSV recorder, true monotonic cadence, frozen metadata, streaming/error/exit handling.
- 47 new deterministic methods; operator/protocol documentation and synthetic examples.

## Modified
- runner/config/schema/defaults, doctor ArUco diagnostics, launcher labels, review/status documents.
- Cleanup excludes recording subtrees and protects active auto NPZ; G errors stay local to cleanup.
- Stereo solver archive publication now unique/atomic/no-overwrite; its solve algorithm and numerical arrays remain unchanged.
- Runtime private world/recording paths excluded from tracking.

## Deleted
No files. The inline joint loop was replaced by a shared function preserving the legacy selected-joint projection.

## Behavior/numerical/protocol/config changes
- New W view is an additional no-scale C->W coordinate transform after original quality/filtering; no gate changes or numerical reinterpretation of old v1.2.
- Eyes processed without extra YOLO; legacy selected joints, coordinates, fields and aggregate means/counts preserved.
- Defaults: readout upper + eyes/midpoint; world DICT_4X4_50 with editable runtime CSV; recording enabled feature but auto_start=false, nominal 5Hz.
- W confirmation saves/activates a new saved NPZ; C/R clears W and persists new stereo selection. P remains preserve-copy only.
- T/C/W/F/exit session behavior and NPZ/CSV contracts in docs/protocols/WORLD_NPZ_CSV_V1.md.

## Verification / remaining limits
261 methods + 26 pytest subtest cases passed; unittest 261 OK. Real geometry/ArUco/files, fake hardware/model/windows. Windows/live rig and absolute accuracy not certified. P1/P2 excluded.
Implementation head: `08da0e6ef0e10711bc1c341302bdec3b5daac312`; same PR #3/base, PR #2 unmerged, no topology changes.

## Previous summaries

# Task003A handoff update — 2026-10-12

- **Added:** owner-authorized current-branch startup, architecture pre-review, phased development and acceptance matrix in the handoff.
- **Modified:** AGENTS.md, CURRENT_TASK.md, Task003A instruction/handoff, REVIEW_INBOX.md, REVIEW_FOR_OWNERS.md and this/test report's preparation notices.
- **Deleted:** no files; obsolete active new-branch approval wording replaced. Historical reviewer records preserved and labeled as history.
- **Behavior/numerical/protocol/config changes:** none; documentation only. Task003A is not implemented by this commit.
- **Git:** owner authorized implementation on existing `trae/agent-c3dfMx` / PR #3; base unchanged. PR #2 remains open/unmerged; no new branch/PR, merge, rebase, force-push or deletion.
- **Known issues:** absolute accuracy not established; previous hardware checks remain unclaimed. Baseline 214 passes are the prior developer report, not a new run.

## Previous change summaries

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
- Tests: `tests/unit/test_camera_selection.py` (48 tests: discovery/assignment/
  rescan/error paths, handle release on every path, atomic + field-preserving
  config write, cancel-never-writes, malformed-config safety, CLI precedence,
  noninteractive gating, calibration identity warnings, fail-closed B1 +
  range B3).

### Modified

- `RUN_ME.py` — offers the picker before doctor/tracking when
  `selection_requested` (default on); this gate fails closed (cancel / failure
  aborts startup, no cameras opened); config reloaded after confirmation.
  `RUN_ME.bat` banner explains the selection step.
- `app/runner.py` — `--camera-pick` flag; `should_pick_cameras` precedence
  (explicit CLI indexes > `--camera-pick` > nothing); `--camera-pick` also
  fails closed on cancel/failure; startup and post-solve
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
  Cancelling or failing the picker fails closed: startup aborts instead of
  reusing possibly-stale indexes.
- Startup prints a prominent warning banner when the active calibration's
  recorded camera indexes differ from the selected pair (or cannot be
  verified). The warning is advisory: no calibration file is deleted,
  overwritten, or auto-invalidated.

### Numerical behavior changes

- None. No measurement thresholds, quality gates, filters, or v1.2 outputs
  changed.

## Review round 2 (PR #3 feedback)

### Behavior changes (B1 — fail closed)

- `RUN_ME.py` and `app/runner.py --camera-pick` no longer catch-and-continue
  on picker exception, and now treat a `None` (cancel / failed save) result as
  an abort: they exit `SystemExit(1)` without opening cameras or starting
  stereo tracking. Only a confirmed, persisted choice proceeds.

### Config changes (B3 — probe range)

- `camera.selection.probe_max_index` validation upper bound lowered from 63 to
  9 (matching the picker's single-digit number keys), in `config.py` and
  `configs/schemas/default.schema.json`. `configs/default.json` (7) unchanged.

### Artifacts (B2)

- Verified all round-1 claimed artifacts are committed; `TEST_REPORT.md`,
  `CHANGE_SUMMARY.md`, and `REVIEW_INBOX.md` updated to match the code and the
  181-test count.

### Tests

- `tests/unit/test_camera_selection.py`: `test_probe_max_index_boundary_accepted`
  (0 and 9 valid; B3) and `TestFailClosed` (4 tests asserting tracking never
  starts on CLI/RUN_ME cancel or failure; B1). Full suite: 181 passed.

## Task 002B — on-demand stereo snapshot + collapsible developer overlay (owner request)

### Added

- `src/stereo_pose/diagnostics/snapshot.py` — on-demand single paired-frame
  diagnostic snapshot (`S` hotkey): writes left/right raw PNGs, annotated
  PNGs (name + confidence labels), a `stereo_pose_3d/snapshot/v2`
  `manifest.json` (capture metadata, host timing with an explicit
  capture-only note for `pair_cycle_ms`, calibration provenance incl.
  SHA-256, per-keypoint pose observations, per-joint rectified geometry and
  rejection states), a self-contained `calibration_snapshot.npz`
  (K/D/R/P matrices, only when a calibration is active), and a `README.txt`.
  Schema v2 semantics: the RAW finite `uv`/`confidence` are always
  preserved — including Ultralytics zero placeholders — while usability is
  expressed by independent `missing`/`missing_reason`/`low_confidence`
  fields (round-1 B1). All writes are staged in a fresh `<name>.partial`
  directory and atomically renamed on completion; any failure deletes only
  that staging directory, so a failed save can never leave a half-written
  folder that looks like valid evidence (round-1 follow-up).
- `tools/inspect_snapshot.py` — offline epipolar replay from the saved raw
  keypoints + `calibration_snapshot.npz`: recomputes rectified uv / signed
  delta / epipolar error, cross-checks the stored signed deltas AND the
  stored rectified uv coordinates (`uv_ok` column), and reports structured
  exit codes: 0 = replayed and matched, 1 = replay impossible
  (missing/corrupt manifest, unsupported schema, missing/corrupt geometry,
  bad arguments), 2 = replayed but mismatches. Null/non-numeric stored
  values render as `n/a` mismatches instead of raising `TypeError`
  (round-1 B2). Requires only NumPy + OpenCV.
- Tests: `tests/unit/test_snapshot.py` — 29 deterministic tests (synthetic
  exact rectified geometry; no camera/torch/CUDA/weights).

### Modified

- `src/stereo_pose/app/runner.py` —
  - `S` hotkey saves a snapshot from the **already captured** `fl`/`fr`
    frames and the **already chosen** `pts_l`/`pts_r` keypoints — no second
    camera read, no second YOLO inference — and passes the runner's
    `keypoint_confidence` as the manifest's `confidence_threshold`.
  - `M` hotkey toggles the developer overlay (`build_menu_lines`):
    collapsed default shows cameras, calibration state, accepted joints,
    full-loop FPS, live alarms, and the `M: Developer tools` hint; expanded
    adds device, rejection counts, stereo RMS/epipolar/reprojection, host
    grab skew, One Euro internals, and the full hotkey row. Alarms are
    prepended in BOTH views (round-1 B4).
  - Overlay FPS now reports the measured **full-loop** rate (capture +
    inference + triangulation + publish + render + waitKey, EMA-smoothed);
    the capture-only `pair_cycle_ms` is displayed separately as
    `grab=NNms` in the expanded menu and documented as capture-only in the
    manifest (round-1 B4: 1000/pair_cycle_ms previously overstated the
    real frame rate).
- `README.md`, `README_先看我.txt` — S/M hotkey documentation, snapshot
  folder layout, offline replay usage (Chinese + English).
- `REVIEW_INBOX.md`, `TEST_REPORT.md`, PR #3 body — review-handoff
  artifacts updated for round 1 (round-1 B3).

### Behavior changes

- New hotkeys `S` (snapshot) and `M` (developer overlay toggle) in tracking
  mode; all existing hotkeys unchanged. Snapshot folders are written under
  `runtime/diagnostics/snapshots/` only, never overwrite prior snapshots
  or calibrations, and are never removed by calibration-history cleanup.
- The tracking overlay FPS is now a measured end-to-end value instead of
  the capture-only pair cycle; live alarms remain visible with the
  developer overlay expanded.

### Numerical behavior changes

- None. No camera geometry, pose association, quality threshold, 3 px
  epipolar gate, v1.2 protocol field, or Task 003 world-coordinate work was
  touched. The snapshot only records what the live loop already computed.

### Known issues

- The live `S`/`M` paths were NOT exercised on real hardware in this
  environment (no cameras/model weights); they are covered by the 33
  deterministic tests (injected synthetic frames/poses/geometry). Real-rig
  owner acceptance is still pending — see TEST_REPORT.md and
  REVIEW_INBOX.md.

### Review round 2 (B5 — real distortion arrays)

- `tools/inspect_snapshot.py::_load_calibration` no longer requires a 1-D
  distribution vector: it now accepts the `(1, N)` row vector (and `(N, 1)`
  column vector) that real `cv2.calibrateCamera` / `cv2.stereoCalibrate`
  produce in `calibration/collection.py`, normalizing accepted row/column
  vectors to a flat 1-D vector before `cv2.undistortPoints`. A genuine 2-D
  matrix (`(2, 5)`) is still rejected with exit 1. No calibration file,
  geometry, or quality threshold was changed — the fix is confined to the
  offline replay tool.
- Tests: `TestRealOpenCVDistortionShape` in `tests/unit/test_snapshot.py`
  (`(1,5)` and `(5,1)` each round-trip the full snapshot-write → offline-replay
  path with exit 0, asserting the saved NPZ preserved the real distortion
  shape; flat `(5,)` still replays; `(2,5)` still rejected). Full suite
  grew from 210 to 214 tests.

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
