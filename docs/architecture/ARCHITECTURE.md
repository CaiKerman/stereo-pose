# Architecture

Formal architecture of the `stereo_pose` package (Task 001).

## Purpose

Separate the validated v1.2 pipeline into explicit, testable module boundaries
**without changing validated numerical behavior**. The package is a measurement
system: numerical behavior, coordinate conventions, and units are part of the
product contract.

## Module boundaries

Each subsystem is a Python subpackage under `src/stereo_pose/`:

| Subpackage | Responsibility | Key types / entry points |
|---|---|---|
| `capture/` | Open webcams and read matched stereo pairs | `open_camera`, `read_stereo_pair` |
| `calibration/` | Collect stable checkerboard pairs and solve stereo calibration | `RuntimeCalibration`, `newest_calibration`, `load_calibration_metadata`, `validate_calibration_compatibility` |
| `pose/` | YOLO Pose inference and device resolution | `PoseEstimator`, `resolve_device` |
| `geometry/` | Rectified triangulation + error metrics | `StereoTriangulator` |
| `quality/` | Measurement quality score and accept/reject gates | `evaluate_measurement`, `heuristic_quality_score`, `TemporalSpeedGate` |
| `filtering/` | One Euro temporal smoothing | `OneEuroVectorFilter`, `JointSmoother` |
| `coordinates/` | Rigid-transform math scaffold | `RigidTransform` |
| `outputs/` | Publishers and `stereo_pose_3d/v1.2` adapter | `build_publisher`, `to_v1_message` |
| `diagnostics/` | Structured logging + offline doctor | `configure_logging`, `doctor.main` |
| `persistence/` | Runtime artifact cleanup within managed roots + promote to saved library | `cleanup_project`, `promote_calibration`, `auto_dir`, `saved_dir` |
| `app/` | Live pipeline orchestration + visualization | `app.runner.run` |

Cross-cutting modules at package root (shared vocabulary / configuration):

- `config.py` — defaults, deep merge, validation.
- `models.py` — typed dataclasses (see below).
- `joints.py` — joint vocabulary, indices, group selection.

## Typed data models (`models.py`)

Explicit dataclasses preserve the required distinctions between raw, accepted,
filtered, coordinate system, units, timestamps, and quality:

- `FrameTiming` — host-side timing diagnostics (grab skew is host-only).
- `StereoFramePair` — a matched left/right image pair + timing.
- `Joint2DObservation` — a joint observed in both views.
- `RawJoint3D` — raw triangulation before acceptance/filtering.
- `JointQuality` — per-joint quality metrics.
- `FilteredJoint3D` — accepted + filtered joint (keeps raw + filtered).
- `StereoCalibrationMetadata` — calibration NPZ metadata.
- `CoordinateTransformMetadata` — transform description.
- `PoseFrame` — assembled per-frame output.

## Configuration

Centralized in `config.py` with a `DEFAULT_CONFIG`, `deep_merge`, and an
in-process `validate_config` that produces aggregated, helpful errors. A JSON
Schema document (documentation/tooling) lives at
`configs/schemas/default.schema.json`; the Python validator is authoritative.

## Offline-first

- Package import, deterministic tests, and the doctor never import
  `torch`/`ultralytics`.
- `pose/estimator.py` imports `ultralytics` lazily and raises a clear error if
  weights/package are missing.
- No automatic model downloads.

## Reference

`reference/v1_2/` is immutable baseline evidence. Formal implementation lives
here. Any reference bug is documented, reproduced in a test when possible, and
fixed only in the formal implementation.

## Deliberately not built (this task)

Final desktop UI, Unreal Engine plugin, ArUco/ChArUco world workflow, hardware
synchronization, learned 3D pose, IK/bone fitting, export formats, WebSocket/ROS,
and multi-person tracking. Interfaces/placeholders are added only where clearly
useful.