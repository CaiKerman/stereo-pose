# Instruction 002 — Metric validation and joint rejection diagnostics

## Goal

Before adding world-coordinate calibration, make the existing stereo measurement pipeline quantitatively inspectable on real hardware.

Task 002 has two primary outputs:

1. a checkerboard-based 3D metric validation mode using the already printed 9 x 6 internal-corner / 25 mm board;
2. transparent per-joint rejection diagnostics so intermittent missing joints can be explained rather than guessed at.

Do not change measurement thresholds merely to make more joints appear. Diagnose first.

## Context from Task 001 hardware acceptance

Real-hardware validation passed:

- CUDA pose inference works;
- dual-camera calibration solves successfully;
- Stereo RMS = 0.5074 px;
- sample epipolar mean/max = 0.735 / 1.190 px;
- solved T = [266.63, -65.858, 90.818] mm;
- baseline norm is approximately 289.3 mm;
- owner physically measured camera-center spacing and reported millimeter-level agreement;
- NPZ persistence, pin/save, restart and automatic reload all work.

Remaining observation:

- only upper body was in frame;
- shoulders were expected to remain visible;
- some shoulder outputs intermittently disappeared.

Task 002 must expose why.

## Part A — Per-joint rejection diagnostics

### Required rejection stages

For every selected joint, classify the frame result into exactly one terminal state:

- accepted;
- left keypoint confidence too low;
- right keypoint confidence too low;
- both keypoint confidences too low;
- triangulation/geometry unavailable;
- epipolar threshold exceeded;
- reprojection threshold exceeded;
- depth below minimum;
- depth above maximum;
- combined quality score below minimum;
- temporal speed gate rejected;
- missing person / missing pose on one or both cameras.

Keep the current aggregate counters, but add per-joint observability.

### Live diagnostic UX

Add a toggleable diagnostic view/hotkey, suggested `D`.

When enabled, show a compact summary at a configurable cadence, for example:

```text
frame=1234 accepted=7/12
left_shoulder   ACCEPT xyz=(...)
right_shoulder  REJECT epipolar 4.2 > 3.0 px
left_elbow      REJECT right_conf 0.31 < 0.45
...
aggregate: conf=2 epi=1 reproj=1 depth=0 quality=1 speed=0
```

Do not flood the console every frame by default.

Also make the current frame's diagnostic summary available as structured internal data so a future UI can display it without parsing text.

### Threshold discipline

Do not alter the current confidence / geometry / quality / speed thresholds in this task unless a deterministic bug is proven.

If real data later shows a threshold is inappropriate, report evidence first.

## Part B — Checkerboard 3D metric validation mode

Use the current active stereo calibration and the same checkerboard already used for calibration:

- 9 x 6 internal corners;
- square spacing = `stereo.square_mm` (currently 25.0 mm).

Suggested hotkey: `V`.

### Validation workflow

1. User holds the checkerboard fully visible in both cameras.
2. Detect the full corner grid in both images.
3. Triangulate all detected corresponding corners using the active stereo calibration.
4. Compute 3D distances between horizontally adjacent corners.
5. Compute 3D distances between vertically adjacent corners.
6. Compare each distance to `square_mm`.
7. Fit a best-fit 3D plane to all reconstructed grid corners.
8. Compute point-to-plane flatness residuals.
9. Report useful stereo geometry metrics for the validation capture.

Prefer a short stable multi-frame validation sample rather than one arbitrary frame if it can be implemented without unnecessary complexity. The implementation must make clear whether reported values are single-frame or aggregated.

### Required metrics

At minimum report:

- expected spacing in mm;
- number of valid reconstructed corners;
- horizontal edge count;
- vertical edge count;
- horizontal mean / standard deviation / RMSE / max absolute error;
- vertical mean / standard deviation / RMSE / max absolute error;
- combined mean spacing;
- combined scale error percent;
- best-fit plane RMS residual in mm;
- best-fit plane max absolute residual in mm;
- mean / max epipolar error for the reconstructed corners;
- mean / max reprojection error;
- approximate board depth range;
- calibration file used;
- timestamp.

A result should look conceptually like:

```text
Metric validation
expected spacing : 25.000 mm
corners          : 54/54
horizontal       : mean 25.08, std 0.31, RMSE 0.32, max abs err 0.77 mm
vertical         : mean 24.94, std 0.35, RMSE 0.36, max abs err 0.91 mm
combined mean    : 25.01 mm
scale error      : +0.04 %
plane RMS        : 0.48 mm
plane max        : 1.12 mm
epi mean/max     : ...
reproj mean/max  : ...
depth range      : ...
```

Do not hard-code pass/fail thresholds yet. First expose the measurements.

### Persist validation reports

Save each validation result under a managed runtime directory, e.g.

```text
runtime/validation/
  metric_YYYYMMDD_HHMMSS.json
```

The report must be human-readable JSON and include schema/version metadata.

Validation reports are evidence and must not be removed by the ordinary calibration-history cleanup.

## Part C — Tests

Add deterministic tests with synthetic cameras and a synthetic planar checkerboard.

Mandatory tests:

- exact projected checkerboard reconstructs expected 3D spacing within tight tolerance;
- noisy 2D observations produce finite and sensible error metrics;
- plane fit returns near-zero residual for an exact planar grid;
- scale error calculation is correct;
- missing/invalid corners are reported cleanly;
- per-joint rejection classifier assigns the expected terminal reason for each rejection stage;
- diagnostics do not change acceptance/rejection behavior;
- validation report serialization round-trips;
- validation output path remains inside managed runtime validation root.

Tests must not require cameras, model weights, CUDA, or network.

## Part D — Operator UX cleanup

Fix any stale RC2 help text so runtime instructions match actual behavior:

- automatic capture waits for stability;
- SPACE is manual force capture subject to complete dual-camera detection + minimum board area;
- diagnostic and validation hotkeys must be listed accurately.

Avoid adding a full GUI in this task.

## Compatibility

- Preserve `stereo_pose_3d/v1.2` external message compatibility.
- Diagnostic structures may be added internally.
- If diagnostic data is exposed externally, it must be optional/non-breaking.
- Coordinate system remains `rectified_left_camera`.
- Units remain mm.
- No world-coordinate convention is introduced.

## Do NOT implement yet

Do not implement:

- ground plane / world origin / X-Y-Z world alignment;
- ArUco / ChArUco world-coordinate workflows;
- final desktop UI;
- Unreal Engine integration;
- multi-person correspondence;
- hardware synchronization;
- IK or body fitting;
- Kimodo/RAMSIS export.

## Deliverables

1. per-joint rejection diagnostic model/classification;
2. diagnostic live view/toggle;
3. checkerboard metric validation implementation;
4. validation report JSON persistence;
5. tests;
6. documentation for validation procedure;
7. updated RUN_ME instructions/hotkeys;
8. CHANGE_SUMMARY.md;
9. TEST_REPORT.md;
10. REVIEW_FOR_OWNERS.md;
11. REVIEW_INBOX.md ready for reviewer feedback.

## Acceptance criteria

Task 002 is complete when:

- a real user can identify exactly why a shoulder/joint disappeared from accepted 3D output;
- the same 25 mm checkerboard can produce a quantitative 3D spacing/flatness report;
- deterministic synthetic validation tests pass;
- no existing measurement thresholds are silently relaxed;
- v1.2 message compatibility is preserved;
- validation reports persist safely under runtime;
- no world-coordinate convention is introduced.
