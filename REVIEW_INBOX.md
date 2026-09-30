# REVIEW_INBOX.md

## Task 002 — Review round 1

Status: **RESOLVED — pending reviewer re-review**

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
