# Test report — Task 001

## Exact test command

```bash
python -m unittest discover -s tests -t .
```

From the repository root.

## Results

- Ran: 63 tests
- Passed: 63
- Failed: 0
- Skipped: 0
- Duration: ~0.25 s

## Environment

- OS: Windows 10 Pro
- Python: 3.10.11 (CPython)
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
| calibration newest-file selection | `tests/unit/test_calibration_selection.py` |
| configuration merge + validation | `tests/unit/test_config.py` |
| quality accept/reject | `tests/unit/test_quality.py` |
| One Euro filter behavior + reset | `tests/unit/test_one_euro.py` |
| joint-group selection | `tests/unit/test_joints.py` |
| v1 message serialization | `tests/unit/test_v1_message.py` |
| cleanup safety boundaries | `tests/unit/test_cleanup.py` |
| rigid transform math scaffold | `tests/unit/test_rigid_transform.py` |
| package import (offline) | `tests/integration/test_imports.py` |
| doctor command (offline) | `tests/integration/test_doctor.py` |

## Untested hardware/physical paths

- Live two-webcam acquisition and real-time tracking (requires cameras).
- Real checkerboard stereo calibration solve (requires boards + cameras).
- CUDA device selection and actual YOLO inference (requires torch + weights).

The deterministic suite intentionally exercises all numerical logic that does
not require hardware or network.