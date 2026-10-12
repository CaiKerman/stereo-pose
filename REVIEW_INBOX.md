# REVIEW_INBOX.md

## ACTIVE — Task003A P0 delivered / owner hardware acceptance pending

Latest owner authorized GPT takeover at 2026-10-12 19:30; no new remote implementation had been delivered by the other coding agent.
Implementation head: `08da0e6ef0e10711bc1c341302bdec3b5daac312`, same branch/PR #3/base. P0 implemented, 261 methods + 26 subtests passed; unittest 261 OK. No merge/retarget/new branch/rebase/force-push/deletion.
Key verified gates: proper no-scale fit and planar controls, marker identity/physical center, immutable package and explicit restart, C/W/candidate separation and legacy statistics, T default OFF/fresh-frame cadence, frozen full metadata, error recovery, protected recordings/active calibration, complete regression.
Remaining: owner Windows/physical camera/model/marker/axis/restart/CSV/hotkey acceptance; precision closure deferred, P1/P2 excluded.
Read CURRENT_TASK.md, TEST_REPORT.md and docs/protocols/WORLD_NPZ_CSV_V1.md. Historical OPEN/pending statements below do not roll the active task back to earlier handoff readiness.

## Preparation and historical reviewer records

# REVIEW_INBOX.md

## ACTIVE — Task003A P0 owner authorization and coding handoff (2026-10-12)

**Status: HANDOFF READY / OWNER-AUTHORIZED EXISTING BRANCH; implementation pending owner notification.**
Owner at 17:16 Asia/Shanghai: “直接在当前分支继续开发吧。你弄好交接文档后我通知其他智能体开始开发。”

- Continue Task003A on **existing `trae/agent-c3dfMx` / PR #3**; preserve base `feat/002-metric-validation-diagnostics`, parent PR #2 OPEN/unmerged.
- Do not create another branch/PR, merge, retarget/close PRs, rebase/force-push or delete branches.
- Read `CURRENT_TASK.md`, `docs/instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md` and `docs/handoffs/20261012_TASK003A_HANDOFF.md`.
- Scope: P0 world/relative-origin alignment, complete immutable stereo+world NPZ + explicit activation/restart, accepted/candidate/missing eye/joint XYZ, manual T CSV default OFF at 5Hz.
- Task002C precision closure is deferred, not solved. P1/P2 excluded. All quality/protocol/privacy gates remain.
- Architecture checks: proper rigid fit including planar controls; persistent selection not newest-auto takeover; separate world view and original v1.2 joint/statistic projection; record only fresh frames; frozen session calibration; G never deletes recordings.
- Implement/checkpoint 003A-1/2/3, baseline + full regression, exact test commands/results, synthetic examples only; push into PR #3, stop for GPT review and owner hardware acceptance before any merge.

**History notice:** all older sections below remain audit history. Their old OPEN/pending labels, “no Task003 before Task002C” ordering, and previous new-branch approval proposals do not block this latest P0 assignment. Read the latest disposition within each historical task. Previously outstanding M / picker cancel-rescan hardware checks remain unclaimed and join the eventual owner acceptance.

## Historical review records

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

**Status: RESOLVED — pending reviewer re-review.**

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

Resolution (2026-10-08):

- `src/stereo_pose/capture/selection.py` implements the full picker:
  `discover_cameras` probes `0..camera.selection.probe_max_index` (default 7,
  configurable, bounded to 0..9 so every index maps to a single-digit picker
  key; sparse indexes naturally supported) and keeps only cameras
  that open **and deliver a frame** (`first_frame_attempts`, default 5);
  `CameraSelectionSession` is a pure state machine — number keys assign LEFT
  then RIGHT, duplicates rejected, `U` undo, `R` rescan, `ENTER` confirm,
  `Q`/`ESC` cancel; `render_canvas` composes labeled live tiles (`CAM n` +
  LEFT green / RIGHT blue) with a status/instruction bar — visual
  identification, no device-name dependency.
- Every probe handle is released on every path (confirm / cancel / rescan /
  error / loop-limit) before the stereo `open_camera` calls, asserted by tests.
- `save_camera_choice` atomically persists `camera.left`/`camera.right`
  (temp file + `os.replace`), preserves unrelated fields verbatim, never
  writes on cancel, and a failed/malformed write leaves the previous config
  intact.
- `RUN_ME.bat`/`RUN_ME.py` open the picker before doctor/tracking
  (`camera.selection.startup_pick`, default true; disable via config or
  `STEREO_POSE_NO_CAMERA_PICK`). This gate **fails closed**: cancelling the
  picker, or a picker crash / failed save, aborts startup instead of reusing
  possibly-stale config indexes (see Review round 2, B1). The project CLI gains
  an opt-in `--camera-pick` with the same fail-closed behavior; explicit
  `--left-cam`/`--right-cam` always win; flag-less CLI never opens a GUI.
- `calibration/metadata.py:camera_identity_warnings` + `app/runner.py`
  surface a prominent startup banner when the active NPZ's recorded
  left/right indexes mismatch (or are unverifiable). Warn-only: no NPZ is
  deleted, rewritten, or auto-invalidated; numeric index equality is never
  claimed to prove physical identity.
- No new dependencies, no runtime pip, no GUI framework beyond OpenCV
  `imshow`/`waitKey`, no numerical threshold changes.
- Tests: `tests/unit/test_camera_selection.py` — 48 deterministic tests with
  injected fake cameras/UI covering all instruction section E items (E1–E8)
  plus the PR #3 round-2 fail-closed (B1) and range (B3) fixes;
  full suite 181 passed / 0 failed / 0 skipped. User documentation:
  `README_先看我.txt` (visual picking steps + 3-camera manual acceptance
  checklist + calibration-identity reminder), `README.md`,
  `docs/architecture/DATA_FLOW.md`; `CHANGE_SUMMARY.md` / `TEST_REPORT.md` /
  `REVIEW_FOR_OWNERS.md` updated.
- Pre-existing `test_rejects_symlink_escape` made deterministic (aged symlink
  target mtime; no product code change) — it now runs and passes on Linux.

Remaining for the owner (cannot be claimed without hardware): physically run
the 3-camera manual acceptance checklist in `README_先看我.txt`, then the D/V
real-hardware acceptance. Commits `1c73556` (implementation) + docs commit on
top target PR #2; do not merge until the reviewer re-approves.

## Task 002A — Review round 2 (PR #3 feedback)

**Status: RESOLVED — pending reviewer re-review.**

Three blockers raised on PR #3, all fixed on this branch:

### B1 — camera selection must fail closed — RESOLVED

Previously `RUN_ME.py`/`app/runner.py` caught the picker exception and
continued, and a `None` (cancel/failed-save) return also fell through to
tracking — silently reusing whatever indexes were already in `config.json`
(e.g. the built-in laptop camera could be opened as a stereo input).

Now both entry points treat an exception or a `None` result as an abort:
they print why, open **no** cameras, start **no** stereo tracking, and exit
with `SystemExit(1)`. Only a confirmed, persisted choice proceeds.

Added `TestFailClosed` (4 tests): CLI `--camera-pick` cancel + failure and
RUN_ME cancel + failure each assert the tracking entry point is never called.

### B2 — handoff artifacts actually committed — RESOLVED

Verified every artifact the round-1 resolution claimed was updated
(`README.md`, `README_先看我.txt`, `CHANGE_SUMMARY.md`, `TEST_REPORT.md`,
`REVIEW_FOR_OWNERS.md`, `docs/architecture/DATA_FLOW.md`) is committed on the
branch. This round additionally updates `TEST_REPORT.md`, `CHANGE_SUMMARY.md`,
and this file so their claims match the B1/B3 code changes and the 181-test
count.

### B3 — `probe_max_index` bounded to 0..9 — RESOLVED

The picker assigns cameras with single-digit number keys, but the config
validation previously allowed `probe_max_index` up to 63 — so any discovered
index ≥ 10 could never be selected. `config.py` validation and
`default.schema.json` now bound `probe_max_index` to `0..9`; `default.json`
(7) is already in range. Tests cover 0 and 9 as valid, 10 and -1 as invalid.

Do not merge; awaiting reviewer re-review.


## Task 002B — New owner assignment (2026-10-08)

**Status: RESOLVED (implementation complete, round-1 fixes applied) — pending reviewer round-2 re-review. Real-hardware S/M acceptance still outstanding (see below).**

See [GitHub Issue #4](https://github.com/CaiKerman/stereo-pose/issues/4) and `docs/instructions/002B_STEREO_SNAPSHOT_AND_DEBUG_MENU.md`.

Owner specifically requested:
1. `S` on-demand **single paired-frame snapshot** with left/right raw images, annotated 2D pose, coordinate+confidence+geometry manifest and offline epipolar replay **without recapturing or rerunning YOLO**.
2. `M` collapsible developer/debug overlay; default uncluttered screen, keep essential health and warnings, all existing hotkeys remain available.
3. Do NOT lower 3px epipolar gate or any existing measurement thresholds. Do NOT make speculative YOLO joint-order corrections without snapshots.
4. No new branch/PR or merge. Use existing `trae/agent-c3dfMx` head, PR #3 to `feat/002-metric-validation-diagnostics`; PR #2 remains open/unmerged.
5. Deterministic tests + Chinese usage guide + review artifacts; await reviewer after push.
6. Do not save user human images outside project `runtime`, do not upload samples or calibration to GitHub.
7. Outstanding separate manual UX check: camera-picker cancel/re-scan has not been confirmed by owner.

**Completion conditions:** mark OPEN -> RESOLVED only when snapshot export, offline replay, M panel, tests and documentation are committed. State clearly that real S snapshot still needs owner acceptance.

Resolution (2026-10-08): snapshot export (`src/stereo_pose/diagnostics/snapshot.py`,
`stereo_pose_3d/snapshot/v2`), offline replay (`tools/inspect_snapshot.py`), the
`M` collapsible overlay (`app/runner.py build_menu_lines`), 29 deterministic
tests (`tests/unit/test_snapshot.py`), and the Chinese/English usage docs are
all committed on `trae/agent-c3dfMx` targeting PR #3. No camera is re-read and
YOLO is never re-run on `S` (asserted by `TestSnapshotPurity`); no measurement
threshold, epipolar gate, or v1.2 protocol behavior was changed. The real `S`
key has **not** been exercised on hardware in this environment — owner
acceptance on the real rig is still required before merge.



## Task 002B — Reviewer round 1 (2026-10-08)

**Status: all blockers RESOLVED on `trae/agent-c3dfMx` — awaiting reviewer round 2.**
**PR feedback:** https://github.com/CaiKerman/stereo-pose/pull/3#issuecomment-6057978607
**Reviewed head:** `5b69259da10848715af18ff776c3e8b9c367b213`

Positive: `S` integrates the current stereo frames and pose outputs without another read/inference; snapshot includes paired raw+annotated images, self-contained geometry+JSON; `M` overlay implemented; no v1.2 measurement thresholds or topology altered.

Resolve before user real-S testing:

- [x] **B1 — RAW DATA LOSS** in `diagnostics/snapshot.py`: `confidence=0.0` causes both original uv and confidence to become null; preserve observed numeric keypoints/confidence (including zeros), distinguish missing vs low confidence, sanitize non-finite uv in annotated image.

  Resolution: snapshot schema bumped to `stereo_pose_3d/snapshot/v2`. The new
  `_observation` record ALWAYS keeps the raw finite `uv` and numeric
  `confidence` — including the Ultralytics zero placeholder (`uv=(0,0)`,
  `confidence=0.0`) and subthreshold detections. Usability is expressed by
  independent fields: `missing` + `missing_reason` (absent pose / non-finite
  uv / non-finite confidence / `confidence <= 0` zero placeholder) and
  `low_confidence` (detected but below the runner's
  `pose.keypoint_confidence`, now passed to `save_snapshot` as
  `confidence_threshold`). `annotate_frame` skips non-finite or
  non-positive-confidence keypoints safely, so a NaN coordinate can never
  abort the whole snapshot. Tests: `TestRawEvidencePreserved` (zero
  placeholder kept, NaN/Inf uv marked missing while siblings survive,
  subthreshold flagged `low_confidence` with raw values kept, absent pose
  reason, non-finite annotation never crashes).

- [x] **B2 — OFFLINE REPLAY ROBUSTNESS** in `tools/inspect_snapshot.py`: formatting missing signed residual with `:11.4f` throws; handle null/incomplete/corrupt data with interpretable errors and exit codes. Test negative cases and UV replay agreement.

  Resolution: `tools/inspect_snapshot.py` rewritten with structured
  `ReplayError` handling: missing/corrupt manifest, unsupported schema, and
  missing/corrupt/wrong-shape calibration NPZ all print an interpretable
  one-line error and exit 1 (never a traceback). Stored values are read
  through `_as_float`/`_fmt` so null or non-numeric residuals render as
  `n/a` and are reported as mismatches instead of raising `TypeError`. Exit
  codes: 0 = replayed and matched, 1 = replay impossible, 2 = replayed but
  mismatching stored values. The replay now also cross-checks the stored
  rectified `uv_left`/`uv_right` against the recomputation (new `uv_ok`
  column), beyond the signed-delta check. Tests:
  `TestOfflineReplayRobustness` (missing manifest, corrupt manifest, wrong
  schema, corrupt NPZ, tampered stored delta, tampered rectified uv,
  missing stored residual, nonexistent path — each asserting exit code and
  message, no traceback) plus the positive CLI match asserting `uv_ok`.

- [x] **B3 — MISSING HANDOFF**: update Chinese `README_先看我.txt`, README, CHANGE_SUMMARY, TEST_REPORT (currently stale 181 Task002A tests), this REVIEW_INBOX, and PR #3 body. No CI run on latest PR head was found; report own test execution precisely, never misclaim hardware validation.

  Resolution: `README_先看我.txt` (S/M usage in Chinese), `README.md`
  (hotkeys, snapshot folder layout, offline replay), `CHANGE_SUMMARY.md`
  (Task 002B section), `TEST_REPORT.md` (exact commands, 210-test result,
  per-requirement coverage, honest untested-hardware list), this file, and
  the PR #3 body are all updated with this push. Test execution reported
  precisely below and in TEST_REPORT.md; no hardware validation is claimed.

- [x] **B4 — MISLEADING FPS / HIDDEN ALARMS**: `pair_cycle_ms` measures capture only, not full inference-loop fps. Fix or relabel; expanded M menu must also show critical warnings.

  Resolution: the overlay FPS is now the measured **full-loop** rate: the
  runner timestamps each complete iteration (capture + inference +
  triangulation + publish + render + waitKey) and shows an EMA-derived fps.
  The grab-only period is displayed separately as `grab=NNms` in the
  expanded menu (and its manifest field `host_timing.pair_cycle_ms` is
  documented as capture-only). Warnings are now prepended in BOTH the
  collapsed and the expanded `M` view, so opening the developer menu can
  never hide a live alarm. Tests: `TestMenuLines` (expanded view contains
  full-loop fps + separate grab period; expanded alarms are prepended as
  the first line).

- [x] Fix ineffective in-place raw-frame mutation test (compares objects never passed into snapshot call), and add targeted tests confirming no second camera read/YOLO run on S.

  Resolution: `test_writes_expected_files_and_raw_frames_unchanged` now
  creates its own buffers, passes those exact objects into `save_snapshot`
  via the `_save(frames=...)` injection, and asserts the very same objects
  afterwards. `TestSnapshotPurity` adds the targeted no-second-read /
  no-second-inference assertions: the snapshot module has no
  `VideoCapture`/`PoseEstimator`/`infer_pair` dependency and
  `save_snapshot` takes no camera handle; the runner's `S` handler contains
  no `read_stereo_pair`/`infer_pair` call and passes the already-captured
  `fl`/`fr` frames and already-chosen `pts_l`/`pts_r` keypoints.

- [x] Make failed snapshot writes unambiguously incomplete or remove only newly created partial directory safely; never affect historical snapshots.

  Resolution: every save writes into a fresh `<name>.partial` staging
  directory and is atomically renamed (os.replace) to the final folder only
  after ALL files are written. Any failure deletes only that freshly created
  staging directory and re-raises, so historical snapshots are never touched
  and no half-written folder can look like valid evidence; a leftover
  `.partial` directory is unambiguously a failed save. Tests:
  `TestAtomicSnapshotWrite` (failed save leaves no `.partial` and publishes
  nothing; a failed save never disturbs a prior snapshot; retry after
  failure publishes exactly one complete folder).

Test execution for this round (exact, deterministic, no CI claimed):

- `python -m pytest tests/unit/test_snapshot.py -q` → 29 passed
- `python -m pytest tests/ -q` (full suite) → **210 passed, 0 failed, 0 skipped**
  (~2.2s, Linux container, Python 3.14.4, NumPy 2.5.3, OpenCV 5.0.0 headless;
  torch/ultralytics/CUDA/cameras NOT installed — see TEST_REPORT.md).
- No live-camera or real-`S` hardware validation was performed in this
  environment and none is claimed.

Keep existing `trae/agent-c3dfMx` / PR #3, preserve NPZ calibration and all acceptance gates, no new branches/PRs or merges. After corrections and documented tests, push once and wait for GPT round-2 review.


## Task 002B — Reviewer round 2 (2026-10-08)

**Status: RESOLVED — B5 fixed and pushed on `trae/agent-c3dfMx`; awaiting final GPT verification. No merge or owner real-S test yet.**

**PR review:** https://github.com/CaiKerman/stereo-pose/pull/3#issuecomment-6061646573
**Reviewed:** `dae10c2b9c99e57cd36915dff4fbc3141cc7718d`

- [x] B1 raw evidence preservation: `snapshot/v2` keeps finite raw uv/confidence even at zero.
- [x] B2 general missing/corrupt replay robustness: no unconditional float format on missing values; signed delta and rectified uv cross-checked.
- [x] B3 source docs and full suite report: `210 passed` self-reported on Linux 3.14.4, no independent CI.
- [x] B4 real full-loop FPS separate from camera grab-only time; alarms in both M views.
- [x] Staging/partial save and no-repeat camera read/inference tests.
- [x] **B5 BLOCKER: real distortion arrays**: `tools/inspect_snapshot.py::_load_calibration` requires D1/D2 to be 1D, but real `cv2.calibrateCamera/stereoCalibrate` invoked by `calibration/collection.py` returns valid `D1.shape=(1,5)` and `D2.shape=(1,5)` (reproduced on OpenCV 4.13.0). Existing tests use synthetic `np.zeros(5)` and mask the problem. Accept OpenCV valid row/column vectors and test full snapshot-write→offline-replay using `(1,5)` and `(5,1)`. Do NOT change calibration files or quality thresholds. Required for real owner snapshots to replay successfully.

  Resolution: `_load_calibration` now accepts a flat `(N,)`, row `(1, N)`,
  and column `(N, 1)` distortion vector — it rejects any 2-D array that is
  not a true row/column vector and normalizes accepted row/column vectors to
  a flat 1-D vector before `compute_epipolar` passes them to
  `cv2.undistortPoints`. No calibration file, geometry, or quality threshold
  was modified; the change is confined to the offline replay tool. Tests:
  `TestRealOpenCVDistortionShape` — `(1,5)` and `(5,1)` each round-trip the
  full snapshot-write → offline-replay path with exit 0 and matching rectified
  geometry (asserting the saved NPZ preserved the real distortion shape), the
  flat `(5,)` shape still replays, and a true `(2,5)` matrix is still rejected
  with exit 1 (never accepted silently).

- [x] Update **PR #3 body**: body refreshed to reflect the full Task 002B
  scope and the current 214-test suite (the stale 176-test 002A-only summary
  is gone).

Test execution for this round (exact, deterministic, no CI claimed):

- `python -m pytest tests/unit/test_snapshot.py -q` → 33 passed
- `python -m pytest tests/ -q` (full suite) → **214 passed, 0 failed, 0 skipped**
  (~3.2s, Linux container, Python 3.14.4, NumPy 2.5.3, OpenCV 5.0.0
  headless; torch/ultralytics/CUDA/cameras NOT installed — see TEST_REPORT.md).
- No live-camera or real-`S` hardware validation was performed in this
  environment and none is claimed (owner acceptance still pending).

- [x] After only targeted B5 fix and updated tests/docs, push to existing `trae/agent-c3dfMx` / PR #3 and stop for brief GPT verification. No merge, no new branches or PRs.



## Task 002B — Reviewer round 3 (2026-10-08)

**Code review: PASSED FOR OWNER REAL-HARDWARE S/M ACCEPTANCE — NOT APPROVED FOR MERGE.**

- PR reviewer verdict: https://github.com/CaiKerman/stereo-pose/pull/3#issuecomment-6063507171
- Reviewed Trae implementation commit: `288860d297ef32a4258b5f5b5f1d632de6a4497c`.
- B5 confirmed fixed: offline replay normalizes OpenCV distortion coefficients `(1,5)`, `(5,1)` and `(5,)`; rejects invalid `(2,5)`. Snapshot-write → replay regression tests committed.
- B1–B4 previously resolved. Documentation and PR body brought current. Trae reported 214 passed, 0 failed, 0 skipped (Linux/headless, no hardware/weights); reviewer has not independently run the whole suite and GitHub CI results are unavailable.
- [ ] Owner real-hardware check: open existing camera pairing, verify `M` collapsed/expanded, save 1–3 static torso `S` snapshots, inspect complete JSON+PNG+geometry files, rerun `python tools/inspect_snapshot.py <snapshot_dir>` and verify 0 mismatches.
- [ ] Owner still to confirm interactive camera picker cancel/rescan, if needed for complete 002A UX acceptance.
- [ ] Task002C evidence-driven human-joint correspondence fix, then Task002 stable-3D reacceptance; Task003 only afterward.
- Non-blocking: current replay supports current default five-coefficient camera model; extended OpenCV 12/14 coefficients not tested/supported. S writes images synchronously and may cause a one-time UI pause; old README statement 'no real-time effect' is overly broad.

**PR #3 and PR #2 remain open and unmerged; do not delete or merge branches pending owner's measurements.**
