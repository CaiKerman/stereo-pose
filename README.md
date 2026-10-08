# stereo-pose

Stereo-camera 3D human pose measurement and calibration system.

The proof-of-concept stereo pipeline (v1.2) is validated and preserved under
[`reference/v1_2/`](reference/v1_2/). The repository is now entering formal
engineering; the formal implementation lives under [`src/stereo_pose/`](src/stereo_pose/).

## Project status

Current work is always declared in [CURRENT_TASK.md](CURRENT_TASK.md).

- Task 001 (baseline freeze + engineering foundation) — see
  [docs/instructions/001_BASELINE_ENGINEERING.md](docs/instructions/001_BASELINE_ENGINEERING.md).
- Task 002 (metric validation + joint rejection diagnostics) — see
  [docs/instructions/002_METRIC_VALIDATION_DIAGNOSTICS.md](docs/instructions/002_METRIC_VALIDATION_DIAGNOSTICS.md).

## For coding agents

Before changing any file:

1. Read [AGENTS.md](AGENTS.md).
2. Read [CURRENT_TASK.md](CURRENT_TASK.md).
3. Read the instruction linked by the current task.
4. Work only on the task branch named there.
5. Do **not** commit directly to `main`.
6. Finish by updating the review artifacts required by `AGENTS.md` and opening/updating a pull request.

## Repository layout

```text
stereo-pose/
├─ AGENTS.md                 # repo-wide agent contract
├─ CURRENT_TASK.md           # active task declaration
├─ pyproject.toml            # packaging (src layout)
├─ configs/
│  ├─ default.json           # validated default configuration
│  └─ schemas/default.schema.json
├─ src/stereo_pose/          # formal implementation
│  ├─ capture/               # camera acquisition
│  ├─ calibration/           # collection, solver, selection, metadata
│  ├─ pose/                  # pose inference + device resolution
│  ├─ geometry/              # rectified triangulation
│  ├─ filtering/             # One Euro smoothing
│  ├─ quality/               # measurement quality gates
│  ├─ coordinates/           # rigid transform scaffold
│  ├─ outputs/               # publishers + v1 message adapter
│  ├─ diagnostics/           # logging + offline doctor
│  ├─ persistence/           # runtime artifact cleanup + save/promote library
│  └─ app/                   # live pipeline orchestration
├─ tests/                    # unit + regression + integration
├─ runtime/                  # managed runtime artifacts (gitignored)
└─ reference/v1_2/           # immutable validated PoC baseline
```

## Installing and running

The core package needs only NumPy and OpenCV. Install:

```bash
pip install -e .
```

For live-camera pose inference, also install the optional dependency set
(ultralytics + torch):

```bash
pip install -e .[live]
```

### Offline doctor

Check environment health without network, cameras, CUDA, or model weights:

```bash
python -m stereo_pose doctor
```

### Runtime

Put a local pose model (e.g. `yolo11n-pose.pt`) at the path configured in
`config.pose.model`, then run the live pipeline:

```bash
python -m stereo_pose run --config config.json
```

The bundled `RUN_ME.bat`/`RUN_ME.py` launcher first opens an interactive
camera-selection window (discover → live preview → assign LEFT/RIGHT by
number keys; `camera.selection.startup_pick`, default true) so the operator
can visually pick the two physical cameras without editing config.json. The
confirmed choice is atomically persisted to the local config; cancelling
leaves it untouched. From the CLI the picker is opt-in via
`python -m stereo_pose run --camera-pick` (explicit `--left-cam`/`--right-cam`
always take precedence; noninteractive runs never open a GUI). The environment
variable `STEREO_POSE_NO_CAMERA_PICK` force-disables the startup picker.

Run-time generated artifacts (calibrations, sessions, logs, captures) stay
under `runtime/` and are not committed.

### Tracking hotkeys and on-demand snapshots

During tracking, `S` saves a single paired-frame diagnostic snapshot into
`runtime/diagnostics/snapshots/<timestamp>/`: left/right raw PNGs, annotated
PNGs (keypoint name + confidence), a versioned `manifest.json`
(`stereo_pose_3d/snapshot/v2`) that always preserves the RAW observed
keypoint uv/confidence (including zero-confidence placeholders) and marks
usability separately (`missing`/`missing_reason`/`low_confidence`), plus a
self-contained `calibration_snapshot.npz` when a calibration is active. The
snapshot reuses the already-captured frames and the already-completed pose
inference — no second camera read, no second YOLO pass. Writes are staged in
a `.partial` directory and atomically renamed, so a failed save can never
leave a half-written folder. Replay the epipolar evidence offline with
`python tools/inspect_snapshot.py <snapshot_dir>` (NumPy + OpenCV only; exit
0 = matched, 1 = replay impossible, 2 = stored values mismatch). `M`
toggles the developer overlay: the collapsed default keeps the display
uncluttered (cameras, calibration state, accepted joints, full-loop FPS,
live warnings); the expanded view adds rejection counts, stereo
RMS/epipolar/reprojection, host grab skew, One Euro internals, the
capture-only grab period, and the full hotkey row. Live warnings are always
shown in both views, and the reported FPS is the measured end-to-end loop
rate, not the camera capture cycle.

Snapshot folders contain human imagery — never commit or upload them.

## Running tests

```bash
python -m unittest discover -s tests -t .
```

The `src/` package must be importable for the tests; install it first
(`pip install -e .`) or run with `PYTHONPATH=src`. `python -m pytest` runs the
same suite out of the box (pytest auto-detects the `src` layout).

All deterministic tests run without webcams, CUDA, or model weights.

## Core product scope

- dual-camera acquisition and diagnostics;
- stereo calibration and runtime recalibration;
- human 2D pose detection;
- metric 3D triangulation;
- geometry quality control;
- temporal smoothing/noise reduction;
- world-coordinate alignment;
- configurable output interfaces;
- visualization and diagnostics;
- user-friendly desktop UI;
- Unreal Engine integration.

## Important coordinate convention

The current proof-of-concept outputs coordinates in the **rectified-left-camera**
coordinate system.

The future world coordinate system will require:

- ground plane = `Z = 0`;
- `+Z` = upward;
- origin and X/Y direction = user calibrated;
- no X/Y convention may be invented without an explicit project decision.

## Documentation

- [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) — modules and boundaries
- [docs/architecture/DATA_FLOW.md](docs/architecture/DATA_FLOW.md) — pipeline data flow
- [docs/protocols/POSE_MESSAGE_V1.md](docs/protocols/POSE_MESSAGE_V1.md) — output message contract
- [docs/calibration/STEREO_CALIBRATION.md](docs/calibration/STEREO_CALIBRATION.md) — calibration artifact + policy
- [docs/validation/METRIC_VALIDATION.md](docs/validation/METRIC_VALIDATION.md) — checkerboard 3D metric validation procedure
- [MIGRATION_NOTES.md](MIGRATION_NOTES.md) — v1.2 → formal migration notes

## Collaboration

The repository is the source of truth shared by the owner, architecture/review
agent, and implementation agents. See [docs/agent/WORKFLOW.md](docs/agent/WORKFLOW.md).