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

Latest full-suite run (after Task 002A camera selection):

- Ran: 176 tests
- Passed: 176
- Failed: 0
- Skipped: 0
- Duration: ~0.6s (pytest)

`test_rejects_symlink_escape` now runs and passes on this platform (Linux,
symlinks allowed); it also became deterministic — the symlink target's mtime is
aged explicitly because the cleanup candidate sort key `stat().st_mtime`
follows the link, and tied timestamps let directory order decide which file
was "newest".

Task 002 round 1 previously ran 133 tests (132 passed, 1 skipped on Windows
where symlinks need elevation). New test totals:

- Task 002 core: 33 tests (`test_joint_rejection.py`,
  `test_metric_validation.py`, `test_diagnostics_render.py`,
  `test_validation_report.py`).
- Review round 1: 4 correspondence-normalization tests.
- Task 002A: 43 tests (`tests/unit/test_camera_selection.py`) — discovery/
  assignment/rescan/error paths, handle release on every path, atomic +
  field-preserving config write, cancel-never-writes, malformed-config
  safety, CLI precedence, noninteractive gating, calibration identity
  warnings.

## Environment (latest run — Task 002A)

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
| E8 — existing Task 002 deterministic suite continues to pass | full suite: 176 passed, 0 failed |

## Untested hardware/physical paths

- Live two-webcam acquisition, real-time tracking, and the `D`/`V` hotkeys
  (require cameras).
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