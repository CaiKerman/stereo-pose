# Checkerboard 3D metric validation procedure

Task 002 adds a single-frame metric-validation mode that quantifies how well the
active stereo calibration reconstructs the already-printed 9×6 inner-corner /
25 mm checkerboard. It reports scale, flatness, and stereo geometry error
without introducing any world-coordinate convention: all 3D coordinates remain in
the rectified-left-camera frame and all units are millimetres.

## When to use it

Run this after a calibration is active and before trusting the 3D output for
measurement. It is an inspection aid, not a pass/fail gate: Task 002
deliberately exposes measurements and does not hard-code acceptance thresholds.

## How to run

1. Ensure an active stereo calibration exists (press `C` then `R` during
   calibration, or let the app load the newest calibration at startup).
2. Return to the tracking mode.
3. Hold the checkerboard fully visible in both cameras.
4. Press `V`.

The application detects the full corner grid in both views, triangulates every
matched corner with the active calibration, computes the metrics below, prints a
summary to the console, and saves a JSON report under the managed runtime root:

```text
runtime/validation/metric_YYYYMMDD_HHMMSS.json
```

If a report filename already exists within the same second, an incrementing
counter suffix is appended; reports are never overwritten.

## Reported metrics

| Metric | Meaning |
|---|---|
| `expected_spacing_mm` | nominal square size from `stereo.square_mm` (25.0) |
| `corners` | total expected corners vs. validly reconstructed corners |
| `horizontal` / `vertical` | per-edge count, mean, std, RMSE, max abs error (mm) |
| `combined_mean_spacing_mm` | mean of all horizontal + vertical edges |
| `scale_error_percent` | `(combined_mean - expected) / expected × 100` |
| `plane` | best-fit plane RMS and max absolute residual (mm) |
| `epipolar` / `reprojection` | mean/max error over reconstructed corners (px) |
| `depth_range_mm` | min / max / span of reconstructed corner depth (mm) |
| `calibration_file` | NPZ used for triangulation |
| `corner_order_mode` | selected correspondence normalization: `direct` or `reversed_180` |
| `timestamp` | capture time (ISO) |

`schema` is `stereo_pose_3d/metric_validation/v1` and `sample_mode` is
`single_frame` — a single frame is reported, never silently aggregated.

## Corner correspondence normalization

`cv2.findChessboardCornersSB` can report the corners of a rectangular board in
either of two 180-degree-related orderings, so the left and right cameras may
disagree on which corner is "first". Pairing the two corner lists positionally
would then create wrong correspondences and spuriously inflate the metric error.

Before triangulation the pipeline therefore evaluates the two physically plausible
orderings — `direct` (pair `left[k]` with `right[k]`) and `reversed_180` (pair
`left[k]` with `right[-1-k]`) — and selects the one with the best aggregate
rectified epipolar geometry. The expected `square_mm` is never consulted for this
decision, so the validation is not circular. The chosen mode is recorded in the
report as `corner_order_mode`.

If neither ordering reconstructs the board with full corner coverage and
plausible epipolar error, the capture is rejected with a validation error and no
metric report is written — the failure is reported instead of emitting
misleading metric statistics.

## Reading the results

- `scale_error_percent` near zero and edge RMSE near the sub-millimetre range
  indicate the calibration recovers metric scale well.
- `plane` residual near zero confirms the reconstructed board is flat even when
  tilted (a large residual on a flat board suggests corner/triangulation noise).
- `epipolar`/`reprojection` reflect the internal stereo geometry quality for the
  capture; they should be consistent with the calibration's sample epipolar and
  the live frame statistics.

## Storage and cleanup

Reports live under `runtime/validation/`, which is intentionally separate from
the calibration `auto/`/`saved/` areas. Ordinary calibration-history cleanup
never removes validation reports.

## Coordinate and unit guarantee

The validation pipeline does not define or depend on any world-coordinate
convention. Output stays in `rectified_left_camera` coordinates in `mm`.