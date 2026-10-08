# REVIEW_INBOX.md

## Task 002 — Review round 1

Status: **OPEN — owner-requested camera selection required before hardware validation**

This file is the repository-visible authoritative mirror of actionable review feedback for Task 002.

### R1-1 — Checkerboard corner correspondence must be canonicalized before metric validation — BLOCKING → RESOLVED

The live `V` path currently does:

```python
corner_l = detect_checkerboard(...)
corner_r = detect_checkerboard(...)
compute_metric_validation(..., corner_l, corner_r, ...)
```

and `triangulate_corners()` pairs the two arrays positionally with `zip(left, right)`.

For the current 9 x 6 inner-corner checkerboard, corner ordering can be ambiguous by 180 degrees. Therefore the two cameras can, in principle, return opposite corner orderings for the same physical board. If that happens, positional pairing creates incorrect stereo correspondences and the validation report will falsely attribute the failure to metric accuracy.

Required:

1. add an explicit correspondence-normalization step before triangulation;
2. support at least the two physically plausible orderings for this rectangular board (direct and 180-degree reversed) and choose the consistent one using stereo geometry evidence;
3. the decision must not use the expected 25 mm spacing itself as the primary selector, otherwise the validation becomes circular;
4. prefer an evidence measure such as aggregate rectified epipolar error / reprojection consistency under each candidate ordering;
5. record the selected correspondence mode in the validation report, e.g. `corner_order_mode: direct|reversed_180`;
6. if neither ordering is geometrically plausible, report validation failure instead of producing misleading metric statistics;
7. add deterministic tests:
   - direct ordering selects direct;
   - reversed right-camera ordering is detected/corrected;
   - implausible correspondence fails cleanly;
   - metric results after normalization recover the expected synthetic 25 mm grid.

Do not change the calibration board dimensions or measurement thresholds as a workaround.

Resolution: `validation/metrics.py` adds `normalize_correspondence`, which
evaluates the two physically plausible orderings — `direct`
(`left[k]` ↔ `right[k]`) and `reversed_180` (`left[k]` ↔ `right[-1-k]`) — with
aggregate rectified epipolar geometry only (the expected 25 mm `square_mm` is
never consulted, so the decision is not circular). The consistent ordering is
selected, its mode is recorded in the report as `corner_order_mode`, and
`compute_metric_validation` raises `MetricValidationError` (caught by the `V`
path, which reports failure and writes no report) when neither ordering
triangulates the full board with plausible epipolar error. Tests:
`test_direct_ordering_selects_direct`, `test_reversed_right_ordering_is_corrected`,
`test_implausible_correspondence_fails_cleanly`,
`test_reversed_right_recovers_expected_grid_metric`.

### R1-2 — REVIEW_INBOX handoff must be Task-002 specific — PROCESS — RESOLVED

The branch still carried the closed Task 001 inbox. Keep this Task 002 inbox current, mark each item RESOLVED after fixing, and leave it ready for re-review.

Resolution: this inbox now carries only the Task 002 round-1 items above; the
closed Task 001 round-2 items were dropped with the round-1 refresh.

### Owner decisions resolved by reviewer

- No pass/fail tolerances yet: **approved**. Task 002 should expose measurements first.
- Nominal `stereo.square_mm` (currently 25.0 mm) as the validation reference: **approved for Task 002**. A future optional as-measured board spacing may be added if printer/board metrology warrants it.
- Single-frame validation: **approved for Task 002**, provided `sample_mode=single_frame` remains explicit in console/report.

### Completion

- [x] canonicalize checkerboard corner correspondence before triangulation (R1-1)
- [x] run the complete deterministic suite — 133 tests (132 passed, 1 skipped)
- [x] update TEST_REPORT.md / CHANGE_SUMMARY.md / REVIEW_FOR_OWNERS.md
- [x] mark this inbox RESOLVED — pending reviewer re-review
- [x] push to the existing PR #2 (head commit below)
- [ ] do not merge


## Reviewer disposition — round 2

R1-1 was re-reviewed and is accepted.

Verified:
- direct and reversed_180 candidates are evaluated using stereo epipolar geometry only;
- nominal square_mm is not used to select correspondence;
- selected mode is persisted as corner_order_mode;
- implausible correspondence raises MetricValidationError and the live V path writes no report;
- deterministic direct/reversed/failure/metric-recovery tests are present;
- no existing pose-quality thresholds were relaxed.

Non-blocking note:
- MAX_PLAUSIBLE_MEAN_EPIPOLAR_PX=5.0 is a correspondence-plausibility heuristic, not a measurement acceptance threshold. Current accepted real calibration had ~0.735 px sample mean, so this leaves ample margin. Revisit only if real V captures fail unexpectedly.

Before merge, perform real-hardware acceptance:
1. press D with upper body continuously visible and capture diagnostic output covering intermittent shoulder loss;
2. hold the existing 25 mm checkerboard in both views and press V;
3. preserve the console summary and generated runtime/validation/metric_*.json;
4. confirm restart/load behavior remains intact.

Do not merge until those two live paths are exercised.

**Owner update 2026-10-08:** The real-hardware test is additionally blocked by the multi-camera selection task below. Do not run D/V acceptance until camera selection is implemented and reviewed.


## Task 002A — Multi-camera selection on 3-camera laptop (OWNER REQUEST, PRE-TEST BLOCKER)

**Status: OPEN — implementation required before real-hardware D/V testing.**

The test laptop has **one integrated camera + two USB webcams**. The user must be able to **visually identify all available feeds and select distinct LEFT and RIGHT USB webcams** without Git, manual camera index editing, or pip installation.

**Read the full implementation contract:**

`docs/instructions/002A_CAMERA_SELECTION_PRETEST.md`

Minimum acceptance:

1. `RUN_ME.bat` opens a friendly camera discovery/preview/selection step before starting main stereo tracking; visually labeled CAM indexes, Rescan and Cancel; a 3-device setup lets user choose LEFT=1 and RIGHT=2 (or other actual indexes).
2. Only frame-delivering cameras selectable, no duplicate LEFT=RIGHT; robust failures, hotplug, sparse indexes; every temporary camera handle released before tracking.
3. Confirmed choice persisted safely to local config.json with unrelated config fields intact; cancel never changes config; noninteractive and CLI overrides preserved.
4. Preserve physical camera/calibration safety: on index mismatch or uncertain pairing issue a prominent calibration compatibility warning; do not delete/overwrite an existing NPZ or pretend numerical index identity proves physical camera identity.
5. No external dependencies, automatic pip, new GUI framework, or numerical quality threshold changes.
6. Deterministic tests + user documentation + update CHANGE_SUMMARY / TEST_REPORT / REVIEW_FOR_OWNERS.
7. Push changes to **this existing PR #2** and mark this item **RESOLVED — pending reviewer re-review**. **Do not merge.**

Reviewer will approve this incremental pretest change, then owner will run D and V using the two selected external webcams. Do not start Task 003 yet.
