# Task003A P0 implementation verification — 2026-10-12

Implementation head: `08da0e6ef0e10711bc1c341302bdec3b5daac312`. Existing branch `trae/agent-c3dfMx`, PR #3 -> `feat/002-metric-validation-diagnostics`. No merge/topology change.

## Executed results

| Check | Actual result |
|---|---|
| Original baseline before edits | 214 passed, 0 failed/skipped (pytest, 2.44s) |
| 003A-1 checkpoint | 229 passed + 13 subtests |
| 003A-2 checkpoint | 238 passed + 13 subtests |
| Final complete pytest | **261 passed + 26 subtests passed**, 0 failed/skipped, 3.87s |
| Final unittest discover | **Ran 261 tests, OK**, 0 failures/skips, 2.736s |
| JUnit XML | 287 entries = 261 methods + 26 pytest subtest cases; errors=failures=skipped=0 |
| Offline doctor | valid config, ArUco available; weights/torch absent accurately reported |
| compileall | src and RUN_ME.py compiled successfully before final small refinements; final modules also imported/executed by the full suite |

Exact commands (dedicated test interpreter; no application dependency installation behavior changed):

```bash
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest tests/ -q
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest tests/ -q --junitxml=/workspace/scratch/d466de06fca2/task003-test-results/regression.xml
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m unittest discover -s tests -t .
PYTHONPATH=src /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m stereo_pose doctor --json
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m compileall -q src RUN_ME.py
```

## Environment and what was real

Linux, CPython 3.12.14, NumPy 2.3.5, OpenCV 5.0.0.93 (headless), pytest 9.1.1.
No torch, ultralytics, CUDA, model weights or physical cameras in this verification environment.
Real NumPy/OpenCV rigid geometry, rectification/triangulation, generated ArUco detection, NPZ/JSON/CSV filesystem IO.
Injected/fake clocks, camera acquisition, YOLO results, GUI key events/windows, disk-full/errors and stereo-solve output.
Do not infer Windows GUI/camera/GPU/physical accuracy acceptance from these tests.

## New regression coverage (47 methods)

- test_world_alignment.py: 18 methods — proper arbitrary R/t, inverse/distance/no scale; three/coplanar/tilted controls; collinear/near-collinear/NaN; scale/outlier rejection; zero axes; CSV IDs/features; real generated ArUco and duplicate IDs; tilted physical center; old/full NPZ, D shapes, immutable save, atomic archive collision/write failure, explicit activation/restart, geometry/size/schema/object refusal.
- test_live_world.py: 10 methods — legacy bytes/statistics invariant with extra eyes, accepted/candidate/missing/raw/filtered W/C, midpoint validity, no old-frame reuse, rendering; W fit/U/confirm/cancel, zero preserving R, one-row zero with other template rows blank, axis projection.
- test_csv_recorder.py: 10 methods — default OFF, 30/7/5/2FPS cadence, jitter/stale/repeated frame refusal, blank missing columns/candidate isolation, nonfinite cells, frozen metadata and calibration swap, disk full, start failure, rapid unique sessions/exit, recording cleanup protection and active NPZ protection.
- test_task003_runtime.py: 9 methods — whole injected tracking loop with exactly one pair acquisition/inference per tracking iteration; legacy group unchanged, T lifecycle, W/F segmentation, path failure, restart W without markers, C/R clearing and persisting selection, config/schema-default parity and auto-start/nonfinite/bad joint rejection.
- All original 214 methods pass, including the 33 S snapshot/replay cases and original camera-picker/quality/filter/geometry/protocol tests.

## Owner checks still required

Windows RUN_ME and the actual OpenCV GUI; real two-camera + model/CUDA execution; W marker inputs and physically right-handed axes/up; selected W restart on the owner's installation; live eye/selected joint validity; T CSV cadence on actual inference throughput; M/camera-picker cancel/rescan and S/M/D/V/C/R/P/F/G.
Absolute eye/shoulder/elbow P95 accuracy remains deferred and unproven. This is implementation/deterministic verification, not permission to merge.

## Historical reports

# Task003A handoff preparation — 2026-10-12

**This update changes documentation only; it does not implement Task003A or claim code/hardware acceptance.**

- Preparation verification: current PR #2/#3 refs and ancestor relationships, reviewed-code→current-head changed files, current task/spec/rules consistency, and documentation diff/content checks.
- Existing baseline below reports 214 passed / 0 failed / 0 skipped from the prior coding agent; no independent rerun was performed for this documentation update.
- Live cameras, CUDA/YOLO, Windows GUI/launcher and Task003A functionality were not exercised by the handoff preparer.
- Coding agent must run baseline before edits and report fresh exact commands/counts/platform after each phase and full regression.

## Previous implementation test report

# Test report — Task 002

## Exact test commands

From the repository root, with `src/` importable (see note):

```bash
# pytest (auto-detects the src layout via tests/__init__.py bootstrap)
python -m pytest -q

# unittest discover (top-level dir makes tests a package so the src bootstrap runs)
python -m unittest discover -s tests -t .

# offline doctor (PYTHONPATH=src since the package is not pip-installed here)
# PowerShell:
$env:PYTHONPATH="src"; python -m stereo_pose doctor
```

On Windows PowerShell use `$env:PYTHONPATH="src";` (not `&&`). Without `-t .`
or `PYTHONPATH=src`, `unittest discover -s tests` skips the `tests/__init__.py`
source-path bootstrap and cannot import `stereo_pose`.

## Results

Latest full-suite run (after Task 002B round-2 B5 fix):

- Ran: 214 tests
- Passed: 214
- Failed: 0
- Skipped: 0
- Duration: ~3.2s (pytest)

Task 002B snapshot/debug-menu tests: 33 (`tests/unit/test_snapshot.py`,
`python -m pytest tests/unit/test_snapshot.py -q` → 33 passed). All other
181 tests (Task 001 + 002 + 002A) are unchanged and still pass.

`test_rejects_symlink_escape` now runs and passes on this platform (Linux,
symlinks allowed); it also became deterministic — the symlink target's mtime is
aged explicitly because the cleanup candidate sort key `stat().st_mtime`
follows the link, and tied timestamps let directory order decide which file
was "newest".

Task 002 round 1 previously ran 133 tests (132 passed, 1 skipped on Windows
where symlinks need elevation). Test totals by area:

- Task 002 core: 33 tests (`test_joint_rejection.py`,
  `test_metric_validation.py`, `test_diagnostics_render.py`,
  `test_validation_report.py`).
- Review round 1: 4 correspondence-normalization tests.
- Task 002A: 48 tests (`tests/unit/test_camera_selection.py`) — discovery/
  assignment/rescan/error paths, handle release on every path, atomic +
  field-preserving config write, cancel-never-writes, malformed-config
  safety, CLI precedence, noninteractive gating, calibration identity
  warnings, plus the PR #3 round-2 fixes below.
- PR #3 round 2: 5 tests — `probe_max_index` bounded to 0..9 (B3) and
  fail-closed camera selection (`TestFailClosed`: RUN_ME and CLI `--camera-pick`
  never start tracking on cancel or failure; B1).
- Task 002B: 33 tests (`tests/unit/test_snapshot.py`) — see the coverage
  table below; includes the round-1 review fixes (B1 raw-evidence
  preservation, B2 replay robustness/exit codes, B4 full-loop FPS +
  expanded-menu alarms, atomic staged writes, effective mutation test,
  S-purity/no-second-read/no-YOLO) and the round-2 B5 distortion-vector
  shape tests.

## Environment (latest run — Task 002B round-2 fix)

- OS: Linux (container sandbox)
- Python: 3.14.4 (CPython)
- pytest: 9.0.3
- NumPy: 2.5.3
- OpenCV (cv2): 5.0.0 (headless; no GUI windows exercised in tests)
- torch: NOT installed
- ultralytics: NOT installed
- CUDA: not available (not present)

Tests run with no webcams, no CUDA, and no model weights. The camera-selection
tests inject fake open/read/release/waitKey/show functions — no real devices
and no display are required.

Environment of the Task 002 round-1 run (for reference): Windows 10 Pro,
Python 3.10.11, pytest 9.1.1, NumPy 2.2.6, OpenCV 4.13.0.

## Coverage by requirement (Task 002, Part C)

| Requirement | Test |
|---|---|
| exact projected checkerboard reconstructs expected spacing | `test_metric_validation.py::TestExactCheckerboard` |
| noisy 2D observations yield finite sensible metrics | `test_metric_validation.py::TestNoisyObservations` |
| plane fit near-zero residual for exact grid | `test_metric_validation.py::TestExactCheckerboard::test_plane_residual_near_zero_for_exact_grid` |
| scale error calculation | `test_metric_validation.py::TestMetricsMath::test_scale_error_calculation` |
| missing/invalid corners reported cleanly | `test_metric_validation.py::TestMetricsMath` |
| per-joint classifier terminal reason per stage | `test_joint_rejection.py::TestClassifyJoint` |
| diagnostics do not change acceptance/rejection | `test_joint_rejection.py::TestNoBehaviourChange` |
| validation report serialization round-trips | `test_validation_report.py::TestSerialization` |
| output path stays inside managed validation root | `test_validation_report.py::TestReportPersistence` |
| correspondence normalization (direct / reversed_180 / implausible) | `test_metric_validation.py::TestCorrespondenceNormalization` |

## Coverage by requirement (Task 002A, instruction section E)

| Requirement | Test(s) |
|---|---|
| E1 — 3 detected inputs, user picks LEFT=1 / RIGHT=2, confirmed order reaches startup | `TestRunCameraSelection::test_confirm_persists_choice_and_feeds_startup_config`, `TestDiscovery::test_three_cameras_all_usable` |
| E2 — sparse indexes; opens-but-no-frames device excluded; <2 usable cameras handled | `TestDiscovery` (`test_sparse_indexes_supported`, `test_opens_but_no_frames_is_not_usable_and_released`, `test_read_error_is_not_usable_and_released`), `TestRunCameraSelection::test_fewer_than_two_cameras_warns_and_cancel_keeps_config` |
| E3 — same camera for both roles rejected | `TestSessionState::test_duplicate_camera_rejected`, `test_enter_requires_complete_assignment` |
| E4 — preview/cancel/rescan/error paths always release camera resources | `TestRunCameraSelection` (`test_rescan_releases_then_reprobes`, `test_show_error_still_releases_all_handles`, `test_loop_limit_guard`, `test_failed_save_returns_none_and_keeps_previous_config`), `TestDiscovery` release assertions |
| E5 — config persistence keeps unrelated fields; cancel never writes; failed write never corrupts | `TestSaveCameraChoice` (`test_preserves_unrelated_fields_and_updates_cameras`, `test_malformed_config_raises_and_leaves_file_untouched`, `test_failed_write_does_not_corrupt_previous_config`), `TestRunCameraSelection::test_cancel_never_writes_config` |
| E6 — CLI override / noninteractive entry works, never blocks on GUI | `TestNoninteractiveSafety` (flagless CLI never offers selection; `--camera-pick` enables; explicit `--left-cam`/`--right-cam` override; `startup_pick` config + `STEREO_POSE_NO_CAMERA_PICK` env; CLI help lists the flag) |
| E7 — NPZ camera-index mismatch warning shown without discarding calibration | `TestCalibrationIdentityWarning` (mismatch banner, silent-on-match, missing-camera-fields warning, runner banner without discarding) |
| E8 — existing Task 002 deterministic suite continues to pass | full suite: 181 passed, 0 failed |
| B1 — cancelling/failing camera selection must never start tracking | `TestFailClosed` (CLI `--camera-pick` cancel + failure, RUN_ME cancel + failure all assert the tracking entry point is never called) |
| B3 — `probe_max_index` bounded to the 0..9 single-digit picker keys | `test_probe_max_index_boundary_accepted` (0 and 9 valid), `test_bad_probe_max_index_raises` (10 invalid) |

## Coverage by requirement (Task 002B + round-1 review)

| Requirement | Test(s) |
|---|---|
| exact synthetic geometry round-trips through `compute_epipolar` | `TestComputeEpipolar` (`test_known_delta`, `test_non_finite_returns_none`) |
| snapshot writes all expected files; caller's raw frame buffers never mutated | `TestSaveSnapshot::test_writes_expected_files_and_raw_frames_unchanged` (asserts the exact buffers passed into `save_snapshot`) |
| manifest schema v2, joint mapping, rectified geometry | `TestSaveSnapshot::test_manifest_maps_joints_and_schema` |
| no active calibration is recorded with an explicit reason | `TestSaveSnapshot::test_no_calibration_reason` |
| snapshots never overwrite each other and stay inside the managed root | `TestSaveSnapshot::test_no_overwrite_and_containment` |
| calibration-history cleanup never deletes snapshots | `TestSaveSnapshot::test_cleanup_does_not_delete_snapshots` |
| B1 — raw zero-placeholder uv/confidence preserved, missing reason recorded | `TestSaveSnapshot::test_manifest_maps_joints_and_schema`, `TestRawEvidencePreserved` |
| B1 — non-finite uv marked missing; sibling keypoints survive | `TestRawEvidencePreserved::test_nan_uv_is_missing_but_valid_keypoints_survive` |
| B1 — subthreshold confidence flagged `low_confidence`, raw values kept | `TestRawEvidencePreserved::test_subthreshold_confidence_flagged_but_preserved` |
| B1 — absent pose recorded as `absent pose` | `TestRawEvidencePreserved::test_absent_pose_marked_missing` |
| B1 — non-finite uv/confidence never crash `annotate_frame` | `TestRawEvidencePreserved::test_annotate_frame_skips_non_finite_without_crashing` |
| atomic writes: failed save leaves no `.partial`, publishes nothing | `TestAtomicSnapshotWrite::test_failed_save_leaves_no_partial_directory` |
| atomic writes: failed save never disturbs prior snapshots | `TestAtomicSnapshotWrite::test_failed_save_never_touches_previous_snapshots` |
| atomic writes: retry after failure publishes exactly one complete folder | `TestAtomicSnapshotWrite::test_failed_save_can_retry_with_fresh_directory` |
| offline replay matches stored values incl. rectified uv cross-check | `TestOfflineReplay::test_inspect_snapshot_cli_matches` (`uv_ok`, exit 0) |
| no-calibration snapshot cannot be replayed (exit 1) | `TestOfflineReplay::test_inspect_snapshot_cli_no_calibration` |
| B2 — missing manifest / corrupt manifest / bad schema / corrupt NPZ / bad path → exit 1, no traceback | `TestOfflineReplayRobustness` (`test_missing_manifest_directory_exit_1`, `test_corrupt_manifest_exit_1`, `test_unsupported_schema_exit_1`, `test_corrupt_calibration_npz_exit_1`, `test_nonexistent_path_exit_1`) |
| B2 — null stored residual reported as mismatch (exit 2), no `TypeError` | `TestOfflineReplayRobustness::test_missing_stored_residual_reported_not_crash` |
| B2 — tampered stored delta / tampered rectified uv → exit 2 with explicit diff | `TestOfflineReplayRobustness` (`test_tampered_stored_delta_exit_2`, `test_tampered_rectified_uv_exit_2`) |
| S purity — snapshot module has no camera/inference dependency | `TestSnapshotPurity::test_snapshot_module_has_no_camera_or_inference_dependencies` |
| S purity — runner S handler reuses captured frames/pose, no second read/inference | `TestSnapshotPurity::test_runner_s_handler_reuses_captured_data_only` |
| B4 — collapsed menu keeps alarms + hint | `TestMenuLines::test_collapsed_keeps_warnings_and_hint` |
| B4 — expanded menu shows full-loop fps + separate grab period | `TestMenuLines::test_expanded_has_hotkeys_and_internals` |
| B4 — expanded menu also prepends live alarms | `TestMenuLines::test_expanded_also_prepends_alarms` |
| B5 — real OpenCV `(1,5)` row-vector distortion replays end-to-end | `TestRealOpenCVDistortionShape::test_row_vector_d_1x5_replays` |
| B5 — `(5,1)` column-vector distortion replays end-to-end | `TestRealOpenCVDistortionShape::test_column_vector_d_5x1_replays` |
| B5 — flat `(5,)` distortion remains accepted | `TestRealOpenCVDistortionShape::test_flat_d_vector_still_replays` |
| B5 — true `(2,5)` matrix distortion still rejected (exit 1) | `TestRealOpenCVDistortionShape::test_true_2d_distortion_matrix_rejected` |

## Untested hardware/physical paths

- Live two-webcam acquisition, real-time tracking, and the `D`/`V`/`S`/`M`
  hotkeys (require cameras).
- A real `S` snapshot on the physical rig (real imagery through the live
  pipeline; the deterministic tests inject synthetic frames/poses/geometry).
- Real checkerboard metric validation on hardware (requires a printed 25 mm
  board + cameras + a solved calibration).
- CUDA device selection and actual YOLO inference (require torch + weights).
- The interactive camera picker itself on real hardware (real `cv2.imshow`
  window, real hotplug rescan) — injected-fake tests cover the logic; the
  3-camera manual acceptance checklist in `README_先看我.txt` is left for the
  owner to exercise physically.

The deterministic suite exercises all numerical logic that does not require
hardware or network.

---

# Test report — Task 001 (+ review rounds 1 & 2)

## Exact test commands

From the repository root, with `src/` on the path (see note below):

```bash
# Python on Windows (PowerShell)
$env:PYTHONPATH="src"; python -m unittest discover -s tests -t .

# Or, equivalently, pytest auto-detects the src layout:
python -m pytest -q
```

Note: the `src/` package must be importable for `unittest discover`. Either
`pip install -e .` first, or set `PYTHONPATH=src` on the command line.

## Results

- Ran: 93 tests
- Passed: 92
- Failed: 0
- Skipped: 1 (`test_rejects_symlink_escape` — symlinks not supported on this
  platform without elevation)
- Duration: ~1.2s (pytest), ~0.7s (unittest)

## Environment

- OS: Windows 10 Pro
- Python: 3.10.11 (CPython)
- pytest: 9.1.1
- NumPy: 2.2.6
- OpenCV (cv2): 4.13.0
- torch: NOT installed
- ultralytics: NOT installed
- CUDA: not available (not present)

Tests run with no webcams, no CUDA, and no model weights.

## Coverage by requirement

| Requirement | Test |
|---|---|
| synthetic stereo triangulation | `tests/regression/test_geometry.py` |
| epipolar error | `tests/regression/test_geometry.py` |
| reprojection error | `tests/regression/test_geometry.py` |
| calibration selection (auto/ vs saved/ + auto-vs-legacy precedence) | `tests/unit/test_calibration_selection.py` |
| calibration metadata + compatibility warnings | `tests/unit/test_calibration_metadata.py` |
| calibration promote/pin to saved library (incl. collision-proof) | `tests/unit/test_promote.py` |
| cleanup safety boundaries (mandatory root guard, auto-only, pre-delete mass guard) | `tests/unit/test_cleanup.py` |
| camera fourcc validation | `tests/unit/test_camera.py` |
| configuration merge + validation (incl. fourcc/buffer_size/runtime.root) | `tests/unit/test_config.py` |
| quality accept/reject | `tests/unit/test_quality.py` |
| One Euro filter behavior + reset | `tests/unit/test_one_euro.py` |
| joint-group selection | `tests/unit/test_joints.py` |
| v1 message serialization | `tests/unit/test_v1_message.py` |
| rigid transform math scaffold | `tests/unit/test_rigid_transform.py` |
| package import (offline) | `tests/integration/test_imports.py` |
| doctor command (offline) | `tests/integration/test_doctor.py` |

## Untested hardware/physical paths

- Live two-webcam acquisition and real-time tracking (requires cameras).
- Real checkerboard stereo calibration solve (requires boards + cameras).
- CUDA device selection and actual YOLO inference (requires torch + weights).
- Symlink-escape path is skipped on this platform (no symlink privilege); the
  guard logic is still asserted on a resolved-outside path in
  `test_rejects_dirs_outside_trusted_root_without_deletion`.

The deterministic suite intentionally exercises all numerical logic that does
not require hardware or network.
