# Migration notes — v1.2 reference → formal package

Mapping from the validated `reference/v1_2/` implementation to the formal
`src/stereo_pose/` package. Numerical behavior is preserved; only structure and
a few documented changes apply.

## Module mapping

| v1.2 reference file | Formal location | Notes |
|---|---|---|
| `stereo_pose/camera.py` | `capture/camera.py` | unchanged |
| `stereo_pose/stereo.py` | `geometry/triangulation.py` | `StereoTriangulator`; now also accepts a mapping |
| `stereo_pose/stereo.py` (`newest_calibration`) | `calibration/selection.py` | unchanged |
| `stereo_pose/calibration.py` | `calibration/collection.py` | `RuntimeCalibration`; unchanged |
| `stereo_pose/pose.py` | `pose/estimator.py` | `ultralytics` import made lazy |
| `stereo_pose/device.py` | `pose/device.py` | unchanged |
| `stereo_pose/filtering.py` (`OneEuro*`, `JointSmoother`) | `filtering/one_euro.py` | unchanged |
| `stereo_pose/filtering.py` (`TemporalSpeedGate`) | `quality/speed_gate.py` | moved to quality boundary |
| `stereo_pose/joints.py` | `joints.py` (package root) | unchanged vocabulary |
| `stereo_pose/publishers.py` | `outputs/publishers.py` | unchanged |
| `stereo_pose/cleanup.py` | `persistence/cleanup.py` | unchanged |
| (inline in `main.py`) `heuristic_quality_score` | `quality/scoring.py` | extracted + `evaluate_measurement` |
| `main.py` | `app/runner.py` | orchestrates typed modules; builds `PoseFrame` |
| (new) | `calibration/metadata.py` | `StereoCalibrationMetadata` + load checks |
| (new) | `diagnostics/doctor.py` | offline doctor |
| (new) | `coordinates/rigid.py` | rigid transform scaffold |

## Documented behavior changes

1. **Lazy `ultralytics` import** — `pose/estimator.py` no longer imports
   `ultralytics` at module load. Importing the package (and running the doctor
   or tests) requires no torch/ultralytics. Constructing `PoseEstimator`
   without `ultralytics` installed raises a clear `ImportError` instead of an
   import-time `ModuleNotFoundError`.

2. **Default runtime paths moved under `runtime/`** — config defaults changed:
   `stereo.calibration_dir` `"calibrations"` → `"runtime/calibrations"`, and
   `calibration_runtime.session_dir` `"calib_sessions"` → `"runtime/sessions"`.
   Config keys are unchanged; only default values moved to keep runtime
   artifacts out of the source tree.

3. **New config field** — `runtime.log_dir` (default `"runtime/logs"`) for
   structured log output.

4. **New NPZ metadata field** — `_schema_version` is written alongside
   calibration artifacts for forward compatibility.

## Preserved (unchanged) semantics

- Triangulation math and epipolar/reprojection metrics.
- One Euro filter parameters and gap-reset behavior.
- Temporal speed gate.
- `heuristic_quality_score` formula.
- Calibration stability/diversity/readiness and robust-prune logic.
- v1.2 message field names, units, and `"stereo_pose_3d/v1.2"` schema string.
- Cleanup glob scope (only `stereo_*.npz` / `session_*` under managed roots).