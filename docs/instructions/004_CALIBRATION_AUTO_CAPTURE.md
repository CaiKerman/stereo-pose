# Task004 P0 — checkerboard automatic capture repair

Owner instruction 2026-10-13 09:42 Asia/Shanghai: repair static-board capture,
implement/tests/submit autonomously; do not replace repair with user recalibration.

## Branch and preserved scope

- `fix/004-calibration-auto-capture` from exact latest midpoint/startup delivery
  `082ba5e41e9f3dae47e4d2bfc787a4877523868b`.
- New independent PR base `feat/003b-default-camera-midpoint`; existing PR
  #2/#3/#6 unchanged and unmerged. No merge/retarget/rebase/force-push/deletion.
- Scope: capture evidence, auto/manual state, diagnostic panel, config default
  merge, synthetic tests. No P1/P2 or triangulation/solver math changes.
- Preserve C/R/SPACE/X/P/F/G/S/M/D/V/W/T and all world/default XYZ/NPZ/CSV paths.

## Confirmed software defect and limits

Old gate requires >=3 observations inside 0.30s, plus >=0.24s span. Static
synthetic controls over 10s: 30Hz reaches stability; 5Hz and 2Hz never do
(at most 2 and 1 observations in that window). This reproduces a sufficient
software cause. Owner hardware detector cadence/order/noise has not been recorded;
do not assert this is the sole physical cause or explains Stereo RMS=3.2548.
Old SPACE additionally re-detected the same pair. Old state label concealed
insufficient observations, capture interval and duplicate-pose rejection.

## Implemented contract

- Timestamped stable run requires BOTH valid grids, >=stable_min_frames and
  >=stable_dwell_s actual observed duration, without a narrow sliding time window.
- Missing detections never capture. Brief misses pause accumulated duration;
  loss/stall beyond max(stable_loss_grace_s, 3*prior median attempt period) resets
  evidence. Current interval is excluded when selecting timeout; a sudden stall
  cannot justify itself. Invalid/backwards/duplicate timestamps do not inflate
  observations. History/cadence/rate storage is bounded.
- Preserve 5px mean corner excursion budget in each view. Additionally reject
  coherent drift (>=80% trend fit and >=max(0.5px, motion budget/4) distance),
  preventing slow ongoing movement from accumulating a false stable run.
- Normalize known direct/reverse-180 ordering only for temporal comparisons;
  reject invalid/shuffled grid order, reset evidence. Solver input corners and
  calibration/triangulation algorithms are untouched.
- Circular 180-degree orientation descriptor and readiness angle span prevent
  detector flips masquerading as new pose/coverage. Diversity threshold remains
  0.12; descriptor shape is internal transient state, not an NPZ/protocol field.
- First stable valid pose captures once. Next automatic capture needs changed
  observed pose, original diversity requirement and original 0.7s interval.
  Same held pose does not repeat, even if diversity threshold is set to zero.
- SPACE uses cached current pair; no extra detection or camera read. It bypasses
  stability/diversity/interval, still needs full stereo detection + min area;
  duplicate warning preserves forced sampling. Cache cleared on mode exit/reset.
- Both image writes must succeed before counting a sample. Failure is visible
  and partial files removed. Capture sessions use unique names.
- Panel shows LEFT/RIGHT detection, observed both-valid Hz and calibration-loop
  Hz, per-view SB cost/area/motion/drift/order, time/count/progress/loss timeout,
  capture reason/interval/diversity, auto ON/OFF, solve sample sufficiency and
  manual/duplicate/write-failure notices. Data shortage is not called motion.

## Defaults and acceptance

Existing defaults kept: dwell=.30s, min_frames=3, motion=5px, interval=.7s,
diversity=.12. New `calibration_runtime.stable_loss_grace_s=1.25` merges into old
configs without rewriting them. Explicit auto_capture=false remains respected.

Ideal first-capture times measured from first processed observation:
30Hz ~.30s, 5Hz ~.40s, 2Hz ~1.00s. Detection/render/IO latency is additional;
these are synthetic verification times, not a hardware guarantee.

Required deterministic cases include all owner cases plus slow drift/rotation,
jitter, corner-order flips/permutations, duplicate timestamps, disabled auto,
write failure, cached SPACE integration, real OpenCV SB on generated board,
real existing solver on ideal synthetic stereo controls and NPZ reload.

Owner minimal test: update code keeping local config/runtime/model; RUN_ME -> C,
full board in BOTH views, AUTO ON; hold for 2–3s, see AUTO CAPTURED/count+1;
keep still (no repeat); move/tilt to a sufficiently distinct pose and hold again
(count+1). Inspect the explicit blocker if not captured. C returns to tracking
without replacing current NPZ; no R solve required for this short acceptance.
