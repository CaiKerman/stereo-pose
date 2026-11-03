## Task005 Windows Tk live preview regression — 2026-11-03

Owner reproduced blank native Tk previews; forced `STEREO_POSE_UI=opencv` restores live video. The affected presentation-only path used raw binary PPM through Tk PhotoImage. Fix: PNG/base64 frame transport and redraw after video-label viewport size becomes valid.

Added unit tests in `tests/unit/test_desktop_presentation.py` for OpenCV BGR pixel round-trip through PNG, and failure handling; added native UI test in `tools/smoke_desktop_ui.py` that reads RGB pixels from real Tk PhotoImage objects across sequential LEFT/RIGHT frames and after resize.

Independent isolated Tk/Xvfb demonstration in this session: 3 consecutive synthetic BGR frames rendered in 2 PhotoImage labels via PNG/base64, all 6 sampled pixel colors matched the expected RGB values. **This is not a full repository test run**. The exact repository suites and Windows/webcam hardware have not been run in this editing environment, and no new suite pass counts are claimed. Prior delivery's test counts below predate this repair.

Pending acceptance: Windows Python 3.12 Tk preview, camera left/right changing independently, C calibration preview, W intentionally frozen preview then return to live view, resize and maximize, plus `python -m pytest -q` and native smoke in an environment with source checkout.

Task005 delivery: PR #8 https://github.com/CaiKerman/stereo-pose/pull/8
Tested implementation commit: `5bcc3135f2ebe93bf5785fef90a4ca3b0c98f738`; following completion commit changes documentation only.

# Task005 — verified interface regression (2026-10-14)

Baseline before edits, exact Task004 parent b093e2d327b358c4571f5358d7e797930399774d:
pytest **312 methods + 48 subtests passed**, 0 failed/skipped (3.78s).

Final deterministic full suite: **331 methods + 60 subtests passed**, 0 failed/
skipped (4.98s); unittest **331 tests OK**, 0 failed/skipped (4.653s). JUnit has
391 method/subtest entries. Commands from repository root:

```bash
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q --junitxml=/workspace/scratch/5f3b60f3eba2/task005-pytest.xml
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m unittest discover -s tests -t . -q
```

Added tests: viewport fit/initial DPI bounds; no distortion/cropping of display
copies; single action/disabled button/stale mode dispatch; accepted/candidate/
missing display separation; explicit coordinate frame provenance; no calibration
button gating; insufficient detections distinct from motion; manual duplicate
notice survives next frame until backend expiry; optional Tk fallback/window
close; reference editing atomicity/partial XYZ/unused templates/zero-first-row;
native adapter original C/SPACE/C, CSV/W segmentation, inference count and cleanup.
Existing capture/real SB/synthetic original solver/NPZ/world/default XYZ/CSV and
legacy protocol tests continue passing. No cameras, GPU, model or internet needed.

Native Tk smoke: `PYTHONPATH=src:. python tools/smoke_desktop_ui.py` with Xvfb and
Chinese bitmap font. **10 methods passed at EACH of three virtual desktop profiles**:
1920x1080 at 96 DPI (2.176s), 3840x2160 at 144 DPI (5.934s), 3840x2160 at 192 DPI
(6.307s); 30 native method executions, no failures or Tk callback errors. Includes
viewport requests 800x600, 1024x768, 1366x768, 1920x1080, 600x900, 520x420 (DPI-aware
minimum applies), control visibility, image aspect ratios, read-only help/diagnostic focus retaining shortcuts, real widget button/
keyboard actions, entry typing isolation, dirty preview refusal, same-event
mode/fit ordering, close/cancel, and complete original world fit -> confirmation
-> NPZ save/activate/reload using synthetic controls. Screenshot visual review of
real Chinese Tk labels and 800x600/1366x768 layout performed; no user images used.
Test Xvfb/fonts are scratch-only QA dependencies, never app/repository dependencies.

Compatibility identity check vs parent: geometry/triangulation, coordinates/
camera_midpoint, rigid, markers, calibration/package, collection, stability,
app/measurements, outputs/csv_recorder, v1_message, quality/scoring, speed_gate,
filtering/one_euro, capture/camera, persistence and config are byte-identical.
RUN_ME.py is byte-identical. Original world fit/zero/metadata and save/activate
blocks are byte-identical. Only UI orchestration/presentation changed.
`git diff --check` clean. No config rewrite, math/quality threshold or protocol
change. Actual Windows/toolkit/backend, physical cameras, model/GPU, multi-monitor
DPI transitions and absolute accuracy remain untested; no hardware acceptance.
Processing remains synchronous, so slow detection/solve can delay UI events.
OpenCV compatibility/picker native HWND path injected, not physically exercised.

## Previous task reports

# Task004 automatic capture verification — 2026-10-13

Tested implementation: `b2922dbaa3ffe4cfdaa593a28f15737a9318adb4`.
PR #7: https://github.com/CaiKerman/stereo-pose/pull/7 ; branch
`fix/004-calibration-auto-capture` from `082ba5e41e9f3dae47e4d2bfc787a4877523868b`.
Completion commit changes documentation only; tested code unchanged.

## Root reproduction

Old _update_stability, static synthetic points for 10s:

| Effective detection rate | Old stable events | Old first stable observation |
|---|---|---|
| 30Hz | 293 | .266667s |
| 5Hz | 0 | never |
| 2Hz | 0 | never |

>=3 observations in .30s is impossible at 5/2Hz. This confirms a sufficient
software defect; actual owner's detection cadence was not observed. New ideal
first capture: 30Hz=.30s, 5Hz=.40s, 2Hz=1.00s from first processed observation,
with one capture per held pose. Those times exclude detection/render/IO latency.

## Exact commands and results

Working directory `/workspace/scratch/5f3b60f3eba2/stereo-auto-capture`;
Linux CPython 3.12.14, NumPy 2.3.5, OpenCV 5.0.0 headless, pytest 9.1.1.
Existing isolated interpreter; no installations/model/network downloads.

```bash
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q tests/unit/test_calibration_capture_policy.py
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q --junitxml=/workspace/scratch/5f3b60f3eba2/task004-pytest.xml
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m unittest discover -s tests -t . -q > /workspace/scratch/5f3b60f3eba2/task004-unittest.log 2>&1
git diff --check
```

- Incoming latest midpoint/startup baseline: **285 methods + 35 subtests pass**,
  no failures/skips (3.15s).
- Focused capture checkpoint including real SB: **28 methods + 13 subtests pass**
  (0.77s). Final cached-SPACE-after-AUTO regression added afterward.
- Final pytest: **312 methods + 48 subtests passed**, no failure/skip (5.06s).
  JUnit contains 360 entries including subtests, not 360 unique methods.
- Final unittest: **312 tests, OK**, no failures/skips (4.649s).
- Diff whitespace clean. Protected-module byte comparison and actual method
  source comparison confirmed unchanged detector/loader/solver/epipolar math.
- Synthetic panel rendered and visually inspected: all diagnostic lines fit the
  production 1706x786 layout; camera view remains unobscured above the panel.

## Covered acceptance cases

30/5/2Hz still board; fixed pose no repeats (also diversity0); new moved pose
resumes; continuous translation in left/right/both at each rate, rotation and
slow coherent drift rejected; independent subpixel jitter allowed; brief loss
pauses time, long loss/large stall resets; slower consistent .5Hz eventually
captures; repeated timestamps cannot inflate observation count. Direct/reverse180
flips do not fake motion/diversity, persistently rolled grid order never captures.

SPACE unstable/off/duplicate paths retain force semantics while requiring full
stereo visibility and area; cache prevents a second detector pass; manual after
AUTO and repeated SPACE on the same pair warn but save. Missing/small data and
exited calibration cannot use stale cache. Both PNG writes must succeed; IO
failure produces visible status without increasing sample count. Interval,
duplicate-pose and insufficient-observation states have explicit diagnostics.
Config defaults match shipped JSON and old config merges grace without rewrite.

Runner integration exercises C -> calibration -> SPACE -> C -> tracking, one
process/detector pass per frame, existing hotkeys/model behavior. Existing full
world/default/NPZ/CSV/protocol/restart/picker/cleanup regressions remain passing.

Actual OpenCV findChessboardCornersSB (not stubbed) detects a generated 10x7
square board and triggers capture. Existing actual calibrateCamera/stereoCalibrate/
stereoRectify run on 16 ideal synthetic projected poses, saved complete NPZ
reloads and recovers known stereo translation within .05mm and a holdout point
within .1mm in that ideal synthetic setup. These tolerances verify numerical
compatibility, not accuracy on owner hardware. No private images/NPZ committed.

## Boundaries

Windows GUI, webcams, sensor exposure synchronization and actual YOLO/GPU not
available. Owner RMS=3.2548 cause not confirmed or improved by claim. Temporal
order handling changes capture evidence, not solver's raw point correspondence;
solver/high-accuracy closure remains deferred. No P1/P2, dependencies or merges.
Owner quick acceptance needs only two auto samples at distinct poses, then C;
no R solve or deletion of existing calibration needed to test software repair.

## Earlier Task003B and historical reports

# Task003B startup readiness verification — 2026-10-13

Latest tested code: `3d977f45f65f77f75eac29351724ceb124d717e8`.
Same branch `feat/003b-default-camera-midpoint`, PR #6 -> `trae/agent-c3dfMx`.
Following completion commit changes documentation only.

## Results and reproduction

Linux CPython 3.12.14, NumPy 2.3.5, OpenCV 5.0.0 headless, pytest 9.1.1;
same existing isolated interpreter, no installs/network/model downloads.
Run from `/workspace/scratch/5f3b60f3eba2/stereo-pose`:

```bash
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q tests/unit/test_launch_readiness.py tests/unit/test_camera_selection.py tests/integration/test_task003_runtime.py
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q --junitxml=/workspace/scratch/5f3b60f3eba2/task003b-readiness-pytest.xml
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m unittest discover -s tests -t . -q > /workspace/scratch/5f3b60f3eba2/task003b-readiness-unittest.log 2>&1
git diff --check
```

- Incoming midpoint baseline: **274 methods + 32 subtests**, no failure/skip (2.80s).
- Focused startup/picker/runtime checkpoint: **68 methods + 6 subtests**, no failure/skip (0.70s); four additional readiness methods and another startup failure stage were then added.
- Final pytest: **285 methods + 35 subtests passed**, no failures/skips (3.97s).
- Final unittest: **285 tests, OK**, no failures/skips (3.758s).
- JUnit includes 320 entries (methods plus subtests), not 320 unique methods.
- `git diff --check` clean. Synthetic files/weights and injected GUI/model/devices;
  test weights are never loaded as a real YOLO model.

## Reproduced startup omissions and fixes

Configured non-default local model in a Chinese/space path previously stopped
because launcher demanded ROOT/yolo11n-pose.pt. BOM config loading failed.
Missing moved absolute NPZ path did not restore copied selected data. A second
camera/model/publisher initialization failure retained previously opened handles.
Tests reproduced these failures before changes; all now pass.

- Launcher honors pose.model and is tested to dispatch to tracking without the
  default-named weight; genuine missing weights stop before picker/tracking.
- Config load, camera-choice write and world activation accept UTF-8 BOM and
  preserve unrelated settings. Same-hash NPZ relocation atomically updates path;
  a same-name/different-content file, changed existing selected file or missing
  hash is never guessed/substituted. Recovered old auto NPZ survives cleanup.
- Headless OpenCV is reported before picker. Resource tests verify both device
  releases and publisher close on setup failures. Original live-loop tests
  exercise clean normal exit, CSV lifecycle, W/default/restart and old protocol.
- Refactoring resource ownership required the existing static S purity test to
  inspect _run instead of its new run wrapper; all purity assertions preserved.

## Practical acceptance boundary

GitHub source ZIP does not include private/local config/runtime/model assets.
For one-attempt update use the same working folder/interpreter and preserve
these assets. A moved explicit archive requires its stored SHA for safe recovery;
without that identity keep the original path/folder or explicitly reselect it.
Windows batch execution, actual GUI/webcams/YOLO/CUDA and physical default signs
remain unavailable in the cloud; no absolute hardware-success guarantee or
precision claim is made. No mathematical/quality/schema changes, no merges.

## Historical midpoint verification (2026-10-12)

# Task003B verification — 2026-10-12

Tested implementation head: `59b2e90e312244976372fb001da07f138b37fc6f`.
PR: https://github.com/CaiKerman/stereo-pose/pull/6 ; following commit contains
verification/governance/report documentation only, no code/test changes.

Tested exact local source snapshot for `feat/003b-default-camera-midpoint`,
derived from remote `cf408cdd252ae3f277e5d7b6cba48f7b31e7a899`.
All 131 parent files were matched against the remote Git blob identities before
edits (3 differing/missing local documentation fixtures restored from GitHub).

## Environment and reproduction

Linux, CPython 3.12.14, NumPy 2.3.5, OpenCV 5.0.0 (headless), pytest 9.1.1.
No installed torch/YOLO/camera/window dependency needed for deterministic tests.
Use the already working Python environment; no dependency downloads/changes.
The verification interpreter was an existing isolated environment:
`/workspace/scratch/d466de06fca2/stereo-test-env/bin/python`.
The task working directory was `/workspace/scratch/5f3b60f3eba2/stereo-pose`.

Exact completed commands from repository root:

```bash
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q tests/unit/test_camera_midpoint.py tests/integration/test_task003_runtime.py tests/unit/test_live_world.py
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest -q --junitxml=/workspace/scratch/5f3b60f3eba2/task003b-pytest.xml
PYTHONPATH=src:. /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m unittest discover -s tests -t . -q > /workspace/scratch/5f3b60f3eba2/task003b-unittest.log 2>&1
git diff --check
```

- Parent baseline: **261 methods + 26 subtests passed**, 0 failed/skipped (27.88s).
- Focused midpoint/live/W suite at that checkpoint: **31 methods + 10 subtests
  passed**, 0 failed/skipped (6.22s). One further W override lifecycle method
  was then added and exercised by the complete run below.
- Final pytest: **274 methods + 32 subtests passed**, 0 failed/skipped (56.12s).
  JUnit counts include subtests, not 306 unique methods.
- Final unittest: **274 tests, OK**, 0 failures/skips (37.530s).
- Local source and test __file__ paths were verified to resolve to this task's
  checkout. All fixtures are synthetic. `git diff --check` clean.

For another machine, use `python -m pytest -q` and
`python -m unittest discover -s tests -t . -q` in the project root with its
working dependencies. Tests bootstrap local src without installing the package.

## Behavior verified

- Optical centers at +/-baseline/2 on Y, true midpoint zero, +X forward, +Y
  right->left, +Z camera-up, proper rotation, inverse and mm preservation.
- Actual cv2.stereoRectify on a 420mm, 12-degree-per-camera toe-in rig;
  transformed metric points follow the physical rig axes (not raw T/2).
- Projection-only legacy NPZ, no default write to source NPZ, saved W priority,
  invalid W warnings/default fallback, size mismatch and ambiguous rig refusal.
- One shared inference loop; live and CSV accepted/raw/filtered/candidate
  coordinates consistent; candidate/missing separation and original v1.2 C intact.
- W cancellation/restart/default preservation, confirmed W immediate override,
  zero keeps default axes/up assumption through saved NPZ restart; new stereo
  solve clears old W and recomputes midpoint from the new baseline.
- Existing cleanup, camera picker, snapshots, menus, quality/filtering, explicit
  NPZ selection and manual recorder regression suite remains passing.
- Added failures found during focused development (OpenCV test T shape and
  optional metadata test fixture) were corrected before the passing final run.

## Not certified

Real Windows windows/webcams, YOLO/CUDA, true exposure synchronization, gravity,
camera mounting and absolute eye/joint accuracy. Default up assumes a level,
upright rig; common pitch/roll is unobservable from stereo-only geometry.
Owner already confirmed parent XYZ usable, not this new branch's sign/axis test.
No merge performed; precision closure and P1/P2 remain deferred.

## Historical test reports (prior tasks and checkpoints)


# Task003A P0 implementation verification — 2026-10-12

Implementation head: `08da0e6ef0e10711bc1c341302bdec3b5daac312`. Existing branch `trae/agent-c3dfMx`, PR #3 -> `feat/002-metric-validation-diagnostics`. No merge/topology change.

## Executed results

| Check | Actual result |
|---|---|
| Original baseline before edits | 214 passed, 0 failed/skipped (pytest, 2.44s) |
| 003A-1 checkpoint | 229 passed + 13 subtests |
| 003A-2 checkpoint | 238 passed + 13 subtests |
| Final complete pytest | **261 passed + 26 subtests passed**, 0 failed/skipped, 3.87s |
| Final unittest discover | **Ran 261 tests, OK**, 0 failures/skips, 2.736s |
| JUnit XML | 287 entries = 261 methods + 26 pytest subtest cases; errors=failures=skipped=0 |
| Offline doctor | valid config, ArUco available; weights/torch absent accurately reported |
| compileall | src and RUN_ME.py compiled successfully before final small refinements; final modules also imported/executed by the full suite |

Exact commands (dedicated test interpreter; no application dependency installation behavior changed):

```bash
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest tests/ -q
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m pytest tests/ -q --junitxml=/workspace/scratch/d466de06fca2/task003-test-results/regression.xml
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m unittest discover -s tests -t .
PYTHONPATH=src /workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m stereo_pose doctor --json
/workspace/scratch/d466de06fca2/stereo-test-env/bin/python -m compileall -q src RUN_ME.py
```

## Environment and what was real

Linux, CPython 3.12.14, NumPy 2.3.5, OpenCV 5.0.0.93 (headless), pytest 9.1.1.
No torch, ultralytics, CUDA, model weights or physical cameras in this verification environment.
Real NumPy/OpenCV rigid geometry, rectification/triangulation, generated ArUco detection, NPZ/JSON/CSV filesystem IO.
Injected/fake clocks, camera acquisition, YOLO results, GUI key events/windows, disk-full/errors and stereo-solve output.
Do not infer Windows GUI/camera/GPU/physical accuracy acceptance from these tests.

## New regression coverage (47 methods)

- test_world_alignment.py: 18 methods — proper arbitrary R/t, inverse/distance/no scale; three/coplanar/tilted controls; collinear/near-collinear/NaN; scale/outlier rejection; zero axes; CSV IDs/features; real generated ArUco and duplicate IDs; tilted physical center; old/full NPZ, D shapes, immutable save, atomic archive collision/write failure, explicit activation/restart, geometry/size/schema/object refusal.
- test_live_world.py: 10 methods — legacy bytes/statistics invariant with extra eyes, accepted/candidate/missing/raw/filtered W/C, midpoint validity, no old-frame reuse, rendering; W fit/U/confirm/cancel, zero preserving R, one-row zero with other template rows blank, axis projection.
- test_csv_recorder.py: 10 methods — default OFF, 30/7/5/2FPS cadence, jitter/stale/repeated frame refusal, blank missing columns/candidate isolation, nonfinite cells, frozen metadata and calibration swap, disk full, start failure, rapid unique sessions/exit, recording cleanup protection and active NPZ protection.
- test_task003_runtime.py: 9 methods — whole injected tracking loop with exactly one pair acquisition/inference per tracking iteration; legacy group unchanged, T lifecycle, W/F segmentation, path failure, restart W without markers, C/R clearing and persisting selection, config/schema-default parity and auto-start/nonfinite/bad joint rejection.
- All original 214 methods pass, including the 33 S snapshot/replay cases and original camera-picker/quality/filter/geometry/protocol tests.

## Owner checks still required

Windows RUN_ME and the actual OpenCV GUI; real two-camera + model/CUDA execution; W marker inputs and physically right-handed axes/up; selected W restart on the owner's installation; live eye/selected joint validity; T CSV cadence on actual inference throughput; M/camera-picker cancel/rescan and S/M/D/V/C/R/P/F/G.
Absolute eye/shoulder/elbow P95 accuracy remains deferred and unproven. This is implementation/deterministic verification, not permission to merge.

## Historical reports

# Task003A handoff preparation — 2026-10-12

**This update changes documentation only; it does not implement Task003A or claim code/hardware acceptance.**

- Preparation verification: current PR #2/#3 refs and ancestor relationships, reviewed-code→current-head changed files, current task/spec/rules consistency, and documentation diff/content checks.
- Existing baseline below reports 214 passed / 0 failed / 0 skipped from the prior coding agent; no independent rerun was performed for this documentation update.
- Live cameras, CUDA/YOLO, Windows GUI/launcher and Task003A functionality were not exercised by the handoff preparer.
- Coding agent must run baseline before edits and report fresh exact commands/counts/platform after each phase and full regression.

## Previous implementation test report

# Test report — Task 002

## Exact test commands

From the repository root, with `src/` importable (see note):

```bash
# pytest (auto-detects the src layout via tests/__init__.py bootstrap)
python -m pytest -q

# unittest discover (top-level dir makes tests a package so the src bootstrap runs)
python -m unittest discover -s tests -t .

# offline doctor (PYTHONPATH=src since the package is not pip-installed here)
# PowerShell:
$env:PYTHONPATH="src"; python -m stereo_pose doctor
```

On Windows PowerShell use `$env:PYTHONPATH="src";` (not `&&`). Without `-t .`
or `PYTHONPATH=src`, `unittest discover -s tests` skips the `tests/__init__.py`
source-path bootstrap and cannot import `stereo_pose`.

## Results

Latest full-suite run (after Task 002B round-2 B5 fix):

- Ran: 214 tests
- Passed: 214
- Failed: 0
- Skipped: 0
- Duration: ~3.2s (pytest)

Task 002B snapshot/debug-menu tests: 33 (`tests/unit/test_snapshot.py`,
`python -m pytest tests/unit/test_snapshot.py -q` → 33 passed). All other
181 tests (Task 001 + 002 + 002A) are unchanged and still pass.

`test_rejects_symlink_escape` now runs and passes on this platform (Linux,
symlinks allowed); it also became deterministic — the symlink target's mtime is
aged explicitly because the cleanup candidate sort key `stat().st_mtime`
follows the link, and tied timestamps let directory order decide which file
was "newest".

Task 002 round 1 previously ran 133 tests (132 passed, 1 skipped on Windows
where symlinks need elevation). Test totals by area:

- Task 002 core: 33 tests (`test_joint_rejection.py`,
  `test_metric_validation.py`, `test_diagnostics_render.py`,
  `test_validation_report.py`).
- Review round 1: 4 correspondence-normalization tests.
- Task 002A: 48 tests (`tests/unit/test_camera_selection.py`) — discovery/
  assignment/rescan/error paths, handle release on every path, atomic +
  field-preserving config write, cancel-never-writes, malformed-config
  safety, CLI precedence, noninteractive gating, calibration identity
  warnings, plus the PR #3 round-2 fixes below.
- PR #3 round 2: 5 tests — `probe_max_index` bounded to 0..9 (B3) and
  fail-closed camera selection (`TestFailClosed`: RUN_ME and CLI `--camera-pick`
  never start tracking on cancel or failure; B1).
- Task 002B: 33 tests (`tests/unit/test_snapshot.py`) — see the coverage
  table below; includes the round-1 review fixes (B1 raw-evidence
  preservation, B2 replay robustness/exit codes, B4 full-loop FPS +
  expanded-menu alarms, atomic staged writes, effective mutation test,
  S-purity/no-second-read/no-YOLO) and the round-2 B5 distortion-vector
  shape tests.

## Environment (latest run — Task 002B round-2 fix)

- OS: Linux (container sandbox)
- Python: 3.14.4 (CPython)
- pytest: 9.0.3
- NumPy: 2.5.3
- OpenCV (cv2): 5.0.0 (headless; no GUI windows exercised in tests)
- torch: NOT installed
- ultralytics: NOT installed
- CUDA: not available (not present)

Tests run with no webcams, no CUDA, and no model weights. The camera-selection
tests inject fake open/read/release/waitKey/show functions — no real devices
and no display are required.

Environment of the Task 002 round-1 run (for reference): Windows 10 Pro,
Python 3.10.11, pytest 9.1.1, NumPy 2.2.6, OpenCV 4.13.0.

## Coverage by requirement (Task 002, Part C)

| Requirement | Test |
|---|---|
| exact projected checkerboard reconstructs expected spacing | `test_metric_validation.py::TestExactCheckerboard` |
| noisy 2D observations yield finite sensible metrics | `test_metric_validation.py::TestNoisyObservations` |
| plane fit near-zero residual for exact grid | `test_metric_validation.py::TestExactCheckerboard::test_plane_residual_near_zero_for_exact_grid` |
| scale error calculation | `test_metric_validation.py::TestMetricsMath::test_scale_error_calculation` |
| missing/invalid corners reported cleanly | `test_metric_validation.py::TestMetricsMath` |
| per-joint classifier terminal reason per stage | `test_joint_rejection.py::TestClassifyJoint` |
| diagnostics do not change acceptance/rejection | `test_joint_rejection.py::TestNoBehaviourChange` |
| validation report serialization round-trips | `test_validation_report.py::TestSerialization` |
| output path stays inside managed validation root | `test_validation_report.py::TestReportPersistence` |
| correspondence normalization (direct / reversed_180 / implausible) | `test_metric_validation.py::TestCorrespondenceNormalization` |

## Coverage by requirement (Task 002A, instruction section E)

| Requirement | Test(s) |
|---|---|
| E1 — 3 detected inputs, user picks LEFT=1 / RIGHT=2, confirmed order reaches startup | `TestRunCameraSelection::test_confirm_persists_choice_and_feeds_startup_config`, `TestDiscovery::test_three_cameras_all_usable` |
| E2 — sparse indexes; opens-but-no-frames device excluded; <2 usable cameras handled | `TestDiscovery` (`test_sparse_indexes_supported`, `test_opens_but_no_frames_is_not_usable_and_released`, `test_read_error_is_not_usable_and_released`), `TestRunCameraSelection::test_fewer_than_two_cameras_warns_and_cancel_keeps_config` |
| E3 — same camera for both roles rejected | `TestSessionState::test_duplicate_camera_rejected`, `test_enter_requires_complete_assignment` |
| E4 — preview/cancel/rescan/error paths always release camera resources | `TestRunCameraSelection` (`test_rescan_releases_then_reprobes`, `test_show_error_still_releases_all_handles`, `test_loop_limit_guard`, `test_failed_save_returns_none_and_keeps_previous_config`), `TestDiscovery` release assertions |
| E5 — config persistence keeps unrelated fields; cancel never writes; failed write never corrupts | `TestSaveCameraChoice` (`test_preserves_unrelated_fields_and_updates_cameras`, `test_malformed_config_raises_and_leaves_file_untouched`, `test_failed_write_does_not_corrupt_previous_config`), `TestRunCameraSelection::test_cancel_never_writes_config` |
| E6 — CLI override / noninteractive entry works, never blocks on GUI | `TestNoninteractiveSafety` (flagless CLI never offers selection; `--camera-pick` enables; explicit `--left-cam`/`--right-cam` override; `startup_pick` config + `STEREO_POSE_NO_CAMERA_PICK` env; CLI help lists the flag) |
| E7 — NPZ camera-index mismatch warning shown without discarding calibration | `TestCalibrationIdentityWarning` (mismatch banner, silent-on-match, missing-camera-fields warning, runner banner without discarding) |
| E8 — existing Task 002 deterministic suite continues to pass | full suite: 181 passed, 0 failed |
| B1 — cancelling/failing camera selection must never start tracking | `TestFailClosed` (CLI `--camera-pick` cancel + failure, RUN_ME cancel + failure all assert the tracking entry point is never called) |
| B3 — `probe_max_index` bounded to the 0..9 single-digit picker keys | `test_probe_max_index_boundary_accepted` (0 and 9 valid), `test_bad_probe_max_index_raises` (10 invalid) |

## Coverage by requirement (Task 002B + round-1 review)

| Requirement | Test(s) |
|---|---|
| exact synthetic geometry round-trips through `compute_epipolar` | `TestComputeEpipolar` (`test_known_delta`, `test_non_finite_returns_none`) |
| snapshot writes all expected files; caller's raw frame buffers never mutated | `TestSaveSnapshot::test_writes_expected_files_and_raw_frames_unchanged` (asserts the exact buffers passed into `save_snapshot`) |
| manifest schema v2, joint mapping, rectified geometry | `TestSaveSnapshot::test_manifest_maps_joints_and_schema` |
| no active calibration is recorded with an explicit reason | `TestSaveSnapshot::test_no_calibration_reason` |
| snapshots never overwrite each other and stay inside the managed root | `TestSaveSnapshot::test_no_overwrite_and_containment` |
| calibration-history cleanup never deletes snapshots | `TestSaveSnapshot::test_cleanup_does_not_delete_snapshots` |
| B1 — raw zero-placeholder uv/confidence preserved, missing reason recorded | `TestSaveSnapshot::test_manifest_maps_joints_and_schema`, `TestRawEvidencePreserved` |
| B1 — non-finite uv marked missing; sibling keypoints survive | `TestRawEvidencePreserved::test_nan_uv_is_missing_but_valid_keypoints_survive` |
| B1 — subthreshold confidence flagged `low_confidence`, raw values kept | `TestRawEvidencePreserved::test_subthreshold_confidence_flagged_but_preserved` |
| B1 — absent pose recorded as `absent pose` | `TestRawEvidencePreserved::test_absent_pose_marked_missing` |
| B1 — non-finite uv/confidence never crash `annotate_frame` | `TestRawEvidencePreserved::test_annotate_frame_skips_non_finite_without_crashing` |
| atomic writes: failed save leaves no `.partial`, publishes nothing | `TestAtomicSnapshotWrite::test_failed_save_leaves_no_partial_directory` |
| atomic writes: failed save never disturbs prior snapshots | `TestAtomicSnapshotWrite::test_failed_save_never_touches_previous_snapshots` |
| atomic writes: retry after failure publishes exactly one complete folder | `TestAtomicSnapshotWrite::test_failed_save_can_retry_with_fresh_directory` |
| offline replay matches stored values incl. rectified uv cross-check | `TestOfflineReplay::test_inspect_snapshot_cli_matches` (`uv_ok`, exit 0) |
| no-calibration snapshot cannot be replayed (exit 1) | `TestOfflineReplay::test_inspect_snapshot_cli_no_calibration` |
| B2 — missing manifest / corrupt manifest / bad schema / corrupt NPZ / bad path → exit 1, no traceback | `TestOfflineReplayRobustness` (`test_missing_manifest_directory_exit_1`, `test_corrupt_manifest_exit_1`, `test_unsupported_schema_exit_1`, `test_corrupt_calibration_npz_exit_1`, `test_nonexistent_path_exit_1`) |
| B2 — null stored residual reported as mismatch (exit 2), no `TypeError` | `TestOfflineReplayRobustness::test_missing_stored_residual_reported_not_crash` |
| B2 — tampered stored delta / tampered rectified uv → exit 2 with explicit diff | `TestOfflineReplayRobustness` (`test_tampered_stored_delta_exit_2`, `test_tampered_rectified_uv_exit_2`) |
| S purity — snapshot module has no camera/inference dependency | `TestSnapshotPurity::test_snapshot_module_has_no_camera_or_inference_dependencies` |
| S purity — runner S handler reuses captured frames/pose, no second read/inference | `TestSnapshotPurity::test_runner_s_handler_reuses_captured_data_only` |
| B4 — collapsed menu keeps alarms + hint | `TestMenuLines::test_collapsed_keeps_warnings_and_hint` |
| B4 — expanded menu shows full-loop fps + separate grab period | `TestMenuLines::test_expanded_has_hotkeys_and_internals` |
| B4 — expanded menu also prepends live alarms | `TestMenuLines::test_expanded_also_prepends_alarms` |
| B5 — real OpenCV `(1,5)` row-vector distortion replays end-to-end | `TestRealOpenCVDistortionShape::test_row_vector_d_1x5_replays` |
| B5 — `(5,1)` column-vector distortion replays end-to-end | `TestRealOpenCVDistortionShape::test_column_vector_d_5x1_replays` |
| B5 — flat `(5,)` distortion remains accepted | `TestRealOpenCVDistortionShape::test_flat_d_vector_still_replays` |
| B5 — true `(2,5)` matrix distortion still rejected (exit 1) | `TestRealOpenCVDistortionShape::test_true_2d_distortion_matrix_rejected` |

## Untested hardware/physical paths

- Live two-webcam acquisition, real-time tracking, and the `D`/`V`/`S`/`M`
  hotkeys (require cameras).
- A real `S` snapshot on the physical rig (real imagery through the live
  pipeline; the deterministic tests inject synthetic frames/poses/geometry).
- Real checkerboard metric validation on hardware (requires a printed 25 mm
  board + cameras + a solved calibration).
- CUDA device selection and actual YOLO inference (require torch + weights).
- The interactive camera picker itself on real hardware (real `cv2.imshow`
  window, real hotplug rescan) — injected-fake tests cover the logic; the
  3-camera manual acceptance checklist in `README_先看我.txt` is left for the
  owner to exercise physically.

The deterministic suite exercises all numerical logic that does not require
hardware or network.

---

# Test report — Task 001 (+ review rounds 1 & 2)

## Exact test commands

From the repository root, with `src/` on the path (see note below):

```bash
# Python on Windows (PowerShell)
$env:PYTHONPATH="src"; python -m unittest discover -s tests -t .

# Or, equivalently, pytest auto-detects the src layout:
python -m pytest -q
```

Note: the `src/` package must be importable for `unittest discover`. Either
`pip install -e .` first, or set `PYTHONPATH=src` on the command line.

## Results

- Ran: 93 tests
- Passed: 92
- Failed: 0
- Skipped: 1 (`test_rejects_symlink_escape` — symlinks not supported on this
  platform without elevation)
- Duration: ~1.2s (pytest), ~0.7s (unittest)

## Environment

- OS: Windows 10 Pro
- Python: 3.10.11 (CPython)
- pytest: 9.1.1
- NumPy: 2.2.6
- OpenCV (cv2): 4.13.0
- torch: NOT installed
- ultralytics: NOT installed
- CUDA: not available (not present)

Tests run with no webcams, no CUDA, and no model weights.

## Coverage by requirement

| Requirement | Test |
|---|---|
| synthetic stereo triangulation | `tests/regression/test_geometry.py` |
| epipolar error | `tests/regression/test_geometry.py` |
| reprojection error | `tests/regression/test_geometry.py` |
| calibration selection (auto/ vs saved/ + auto-vs-legacy precedence) | `tests/unit/test_calibration_selection.py` |
| calibration metadata + compatibility warnings | `tests/unit/test_calibration_metadata.py` |
| calibration promote/pin to saved library (incl. collision-proof) | `tests/unit/test_promote.py` |
| cleanup safety boundaries (mandatory root guard, auto-only, pre-delete mass guard) | `tests/unit/test_cleanup.py` |
| camera fourcc validation | `tests/unit/test_camera.py` |
| configuration merge + validation (incl. fourcc/buffer_size/runtime.root) | `tests/unit/test_config.py` |
| quality accept/reject | `tests/unit/test_quality.py` |
| One Euro filter behavior + reset | `tests/unit/test_one_euro.py` |
| joint-group selection | `tests/unit/test_joints.py` |
| v1 message serialization | `tests/unit/test_v1_message.py` |
| rigid transform math scaffold | `tests/unit/test_rigid_transform.py` |
| package import (offline) | `tests/integration/test_imports.py` |
| doctor command (offline) | `tests/integration/test_doctor.py` |

## Untested hardware/physical paths

- Live two-webcam acquisition and real-time tracking (requires cameras).
- Real checkerboard stereo calibration solve (requires boards + cameras).
- CUDA device selection and actual YOLO inference (requires torch + weights).
- Symlink-escape path is skipped on this platform (no symlink privilege); the
  guard logic is still asserted on a resolved-outside path in
  `test_rejects_dirs_outside_trusted_root_without_deletion`.

The deterministic suite intentionally exercises all numerical logic that does
not require hardware or network.
