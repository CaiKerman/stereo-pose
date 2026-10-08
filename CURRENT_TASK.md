# CURRENT_TASK

- **Task ID:** 002
- **Title:** Metric validation and joint rejection diagnostics
- **Status:** IN PROGRESS — PRETEST BLOCKER 002A CAMERA SELECTION
- **Target branch:** `feat/002-metric-validation-diagnostics`
- **Base branch:** `main`
- **Instruction:** `docs/instructions/002_METRIC_VALIDATION_DIAGNOSTICS.md`

## Agent startup

Read, in order:

1. `AGENTS.md`
2. this file
3. `REVIEW_INBOX.md` — OPEN Task 002A pre-test camera-selection item
4. `docs/instructions/002A_CAMERA_SELECTION_PRETEST.md` — implement first
5. `docs/instructions/002_METRIC_VALIDATION_DIAGNOSTICS.md`
6. `docs/validation/TASK001_HARDWARE_ACCEPTANCE_20260930.md`

Then work only on `feat/002-metric-validation-diagnostics`.

## Context

Task 001 passed real-hardware acceptance. Current stereo metric scale is physically credible, calibration persistence/reload works, and CUDA 3D pose tracking is operational.

Task 002 must make measurement accuracy and rejection reasons observable before world-coordinate work begins.

**Owner request before hardware testing:** user changed laptop and now has an integrated webcam plus two USB webcams. A visual LEFT/RIGHT camera picker must be implemented and reviewed before asking the owner to run D/V tests. Treat `docs/instructions/002A_CAMERA_SELECTION_PRETEST.md` as the immediate implementation priority, on the same feature branch and existing PR #2.

## Completion

Task 002 is not complete until all acceptance criteria in the instruction pass, review artifacts are updated, the branch is pushed, and a PR to `main` exists.
