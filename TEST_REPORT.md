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

- Ran: 133 tests
- Passed: 132
- Failed: 0
- Skipped: 1 (`test_rejects_symlink_escape` — symlinks not supported on this
  platform without elevation)
- Duration: ~3.1s (pytest), ~0.7s (unittest)

New in Task 002 (33 tests):

- `tests/unit/test_joint_rejection.py` — per-joint terminal-state classifier,
  coarse-bucket mapping, and no-behaviour-change parity with
  `evaluate_measurement`.
- `tests/unit/test_metric_validation.py` — exact/noisy synthetic checkerboard
  reconstruction, plane fit, scale error, missing corners.
- `tests/unit/test_diagnostics_render.py` — diagnostic summary + aggregate text.
- `tests/unit/test_validation_report.py` — JSON round-trip and managed-root
  path containment.

Added in review round 1 (4 tests, `tests/unit/test_metric_validation.py`,
`TestCorrespondenceNormalization`):

- `test_direct_ordering_selects_direct`
- `test_reversed_right_ordering_is_corrected`
- `test_implausible_correspondence_fails_cleanly`
- `test_reversed_right_recovers_expected_grid_metric`

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

## Untested hardware/physical paths

- Live two-webcam acquisition, real-time tracking, and the `D`/`V` hotkeys
  (require cameras).
- Real checkerboard metric validation on hardware (requires a printed 25 mm
  board + cameras + a solved calibration).
- CUDA device selection and actual YOLO inference (require torch + weights).
- Symlink-escape path is skipped on this platform (no symlink privilege); the
  guard logic is still asserted on a resolved-outside path in
  `test_rejects_dirs_outside_trusted_root_without_deletion`.

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