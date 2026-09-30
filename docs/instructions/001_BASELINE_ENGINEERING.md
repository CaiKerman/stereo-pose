# Instruction 001 — Baseline engineering foundation

## Goal

Turn the validated Stereo Pose v1.2 proof-of-concept into a maintainable formal engineering project **without silently changing validated numerical behavior**.

This task is infrastructure/refactoring/testing work, not feature expansion.

## Known validated PoC behavior

The existing v1.2 pipeline has already been manually verified to:

- open two ordinary USB webcams;
- run YOLO Pose on both views;
- perform stereo checkerboard calibration and save NPZ artifacts;
- triangulate corresponding 2D joints into metric 3D coordinates;
- auto-load the newest calibration;
- support runtime recalibration;
- require a spatially stable checkerboard before calibration capture;
- use grab/retrieve to reduce avoidable host-side sequential capture skew;
- select CPU/CUDA;
- configure output joints;
- evaluate epipolar/reprojection/depth/speed quality;
- apply One Euro filtering;
- retain raw and filtered 3D values;
- publish console/JSONL/UDP-style output;
- clean managed calibration/session artifacts.

Ordinary webcams are **not hardware synchronized**. Host grab skew is not sensor exposure timing.

Current XYZ is in the rectified-left-camera coordinate system.

Future world-coordinate requirements are known only to this extent:

- ground plane = Z=0;
- +Z = upward;
- origin and X/Y direction are user calibrated;
- known-point / ArUco / ChArUco workflows are planned;
- camera XYZ and world XYZ should eventually coexist.

Do **not** invent a final X/Y convention in this task.

## Required work

### 1. Audit the reference implementation

Read actual source/config/docs and produce an inventory covering:

- modules and responsibilities;
- runtime entry points;
- data flow;
- config fields;
- persisted artifacts;
- output message fields;
- dependencies;
- implicit assumptions;
- obvious defects and maintainability risks.

Do not rely only on README text.

### 2. Preserve the reference

The validated PoC is baseline evidence.

Keep it under `reference/v1_2/` or an equivalent immutable reference location.

Formal implementation belongs under `src/`.

Do not “clean up” the reference code.

### 3. Create a formal project layout

Use this intent:

```text
stereo-pose/
├─ README.md
├─ pyproject.toml
├─ .gitignore
├─ configs/
│  ├─ default.json
│  └─ schemas/
├─ src/stereo_pose/
│  ├─ capture/
│  ├─ calibration/
│  ├─ pose/
│  ├─ geometry/
│  ├─ filtering/
│  ├─ coordinates/
│  ├─ outputs/
│  ├─ diagnostics/
│  └─ app/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ regression/
├─ tools/
├─ docs/
│  ├─ architecture/
│  ├─ protocols/
│  └─ calibration/
├─ runtime/
│  ├─ calibrations/
│  ├─ sessions/
│  ├─ logs/
│  └─ captures/
└─ reference/v1_2/
```

Adapt naming only for a strong technical reason.

Runtime artifacts must not be mixed with source.

### 4. Establish module boundaries

Separate at least:

1. camera acquisition;
2. stereo calibration collection/solver;
3. pose inference;
4. stereo geometry/triangulation;
5. measurement quality;
6. temporal filtering;
7. coordinate transforms;
8. output publishers/transports;
9. visualization/UI orchestration;
10. persistence/artifact management;
11. diagnostics/logging.

Avoid both a God class and speculative micro-abstraction.

### 5. Introduce typed internal data models

At minimum model:

- StereoFramePair;
- FrameTiming;
- Joint2DObservation;
- RawJoint3D;
- JointQuality;
- FilteredJoint3D;
- StereoCalibrationMetadata;
- CoordinateTransformMetadata;
- PoseFrame.

Keep explicit distinctions between:

- raw measurement;
- accepted/rejected measurement;
- filtered value;
- coordinate system;
- units;
- timestamps;
- quality metrics.

### 6. Preserve external compatibility

Treat the current `stereo_pose_3d/v1`-style output as a compatibility baseline.

Document it formally.

Internal refactoring may change types/structure, but existing consumers must be supported through an adapter.

Do not silently rename fields or alter units.

### 7. Add deterministic regression tests before substantial refactoring

Tests that must run without webcams, CUDA, or model weights:

- calibration newest-file selection;
- configuration merge and validation;
- synthetic stereo triangulation;
- epipolar error;
- reprojection error;
- quality accept/reject;
- One Euro filter behavior and reset;
- joint-group selection;
- v1 message serialization;
- cleanup safety boundaries;
- rigid coordinate-transform math scaffold.

#### Synthetic stereo geometry test is mandatory

Construct known stereo camera matrices and known 3D points, project them to left/right 2D, triangulate, and assert recovery within a small numerical tolerance.

This proves geometry independently of webcams and YOLO.

### 8. Add an offline doctor command

Provide an equivalent of:

```bash
python -m stereo_pose doctor
```

Report:

- Python/OpenCV/NumPy versions;
- whether PyTorch exists;
- CUDA availability/device when present;
- local pose model path status;
- calibration directory status;
- config validity;
- runtime-directory writability.

It must not download anything.

### 9. Offline-first operation

Pose model files are local.

Do not add automatic GitHub/model downloads.

Missing required assets must produce a clear local-file error.

### 10. Logging

Use structured logging where appropriate:

- INFO;
- WARNING;
- ERROR;
- useful measurement-rejection diagnostics.

Do not flood logs every frame by default.

User-facing errors should be understandable; detailed tracebacks may remain in debug logs.

## Configuration requirements

Centralize and validate at least:

### Camera
- left/right camera IDs or indices;
- resolution;
- requested FPS;
- backend;
- supported buffer options.

### Pose
- local model path;
- device auto/cpu/explicit CUDA index;
- detection confidence;
- keypoint confidence.

### Stereo calibration
- board cols/rows;
- square size in mm;
- calibration directory;
- load-latest behavior.

### Runtime calibration
- stable dwell;
- stable frame count;
- corner-motion threshold;
- auto-capture interval;
- min/target pairs;
- diversity/readiness thresholds.

### Measurement quality
- epipolar threshold;
- reprojection threshold;
- depth bounds;
- quality-score threshold;
- maximum plausible joint speed.

### Smoothing
- enabled;
- One Euro min_cutoff;
- beta;
- derivative cutoff;
- reset timeout.

### Output
- joint groups / explicit joints;
- console;
- JSONL;
- UDP host/port.

### Cleanup
- retained calibration count;
- abandoned-session age;
- keep/delete successful calibration source images.

Invalid values must fail with helpful errors.

## Calibration artifact policy

Stereo calibration files are versioned rather than overwritten:

`stereo_YYYYMMDD_HHMMSS.npz`

Metadata should include:

- creation time;
- calibration-relevant camera configuration;
- image size;
- checkerboard geometry;
- sample count;
- readiness;
- left/right RMS;
- stereo RMS;
- pruning/rejection statistics where available;
- translation vector / baseline information;
- software/schema version.

Loading should check compatibility. Obvious resolution/config mismatch should warn rather than silently assume validity.

## Cleanup safety

Cleanup is allowed only inside project-managed runtime roots.

Never recursively delete arbitrary user-provided locations.

Add tests proving cleanup cannot escape managed roots.

## Do NOT implement yet

Do not spend this task implementing:

- final desktop UI;
- Unreal Engine plugin/project;
- ArUco/ChArUco world-coordinate workflow;
- hardware camera synchronization;
- learned 3D pose;
- IK/bone fitting;
- Kimodo/RAMSIS export;
- WebSocket/ROS integrations;
- multi-person identity tracking.

Interfaces/placeholders are acceptable only where clearly useful.

## Required deliverables

Actual repository files must include:

1. formal project structure;
2. preserved v1.2 reference snapshot;
3. updated README;
4. `docs/architecture/ARCHITECTURE.md`;
5. `docs/architecture/DATA_FLOW.md`;
6. `docs/protocols/POSE_MESSAGE_V1.md`;
7. `docs/calibration/STEREO_CALIBRATION.md`;
8. validated default config/schema;
9. unit/regression tests;
10. offline doctor command;
11. `MIGRATION_NOTES.md`;
12. `CHANGE_SUMMARY.md`;
13. `TEST_REPORT.md`;
14. `REVIEW_FOR_OWNERS.md`.

`REVIEW_FOR_OWNERS.md` should contain only genuine owner/architect decisions or risks.

## Acceptance criteria

Task 001 is complete only when:

- reference baseline is preserved;
- new package imports;
- deterministic tests run without cameras;
- synthetic triangulation passes;
- filtering tests pass;
- cleanup safety tests pass;
- config validation passes;
- doctor works on a machine without CUDA;
- deterministic tests/doctor need no network;
- there remains a clear path to v1.2-equivalent live-camera behavior;
- v1 output compatibility is documented;
- no final world X/Y convention was invented;
- final UI/UE architecture was not prematurely locked in.

## Working style

Follow `AGENTS.md`.

Prefer small reviewable commits.

Before changing geometry/calibration/filter semantics, add/update a regression test.

If a reference bug is found:

1. document it;
2. reproduce with a test if possible;
3. fix the formal implementation;
4. state before/after behavior.

At completion, run the full test suite, push the branch, open/update a PR to `main`, and update the three review artifacts required by `AGENTS.md`.
