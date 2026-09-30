# stereo-pose

Stereo-camera 3D human pose measurement and calibration system.

## Project status

The proof-of-concept stereo pipeline is working. The repository is now entering formal engineering.

Current work is always declared in [CURRENT_TASK.md](CURRENT_TASK.md).

## For coding agents

Before changing any file:

1. Read [AGENTS.md](AGENTS.md).
2. Read [CURRENT_TASK.md](CURRENT_TASK.md).
3. Read the instruction linked by the current task.
4. Work only on the task branch named there.
5. Do **not** commit directly to `main`.
6. Finish by updating the review artifacts required by `AGENTS.md` and opening/updating a pull request.

## Core product scope

The planned product covers:

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

The current proof-of-concept outputs coordinates in the rectified-left-camera coordinate system.

The future world coordinate system will require:

- ground plane = `Z = 0`;
- `+Z` = upward;
- origin and X/Y direction = user calibrated;
- no X/Y convention may be invented without an explicit project decision.

## Collaboration

The repository is the source of truth shared by the owner, architecture/review agent, and implementation agents.

See [docs/agent/WORKFLOW.md](docs/agent/WORKFLOW.md).
