Task005 delivery: PR #8 https://github.com/CaiKerman/stereo-pose/pull/8
Tested implementation commit: `5bcc3135f2ebe93bf5785fef90a4ca3b0c98f738`; following completion commit changes documentation only.

# Task005 owner review

Interface software implementation and full regression complete. Independent
branch `feat/005-responsive-desktop-ui` -> `fix/004-calibration-auto-capture`;
PR #8 contains tested implementation 5bcc3135f2ebe93bf5785fef90a4ca3b0c98f738 followed by documentation only. Existing PRs remain
unchanged/unmerged. No mathematical or data-contract decision requested.
Remaining owner acceptance: actual Windows resizing/maximize/display scaling,
physical LEFT/RIGHT camera picker, existing NPZ restore and buttons/W reference
form with real printed markers. Processing remains synchronous; long detection
or solve still delays event handling. This is a UI change, not accuracy closure.

## Previous review records

# Review for owners — Task004 capture repair

- Ready software delivery: https://github.com/CaiKerman/stereo-pose/pull/7 ;
  `fix/004-calibration-auto-capture` -> `feat/003b-default-camera-midpoint`.
- Latest tested code: `b2922dbaa3ffe4cfdaa593a28f15737a9318adb4`; following
  completion commit changes documentation only. Full 312-method/48-subtest
  pytest and 312-test unittest pass. No code blocker found in self-review.
- Remaining material limitation: owner actual detector cadence/noise/mounts and
  Windows camera hardware are unavailable here. Old .30s-window defect is
  reproduced, but not established as the owner's sole physical cause. RMS=3.2548
  is not explained or improved by claim; original solver/re-detection unchanged.
- Temporal order normalization does not certify left/right physical corner
  identity in the calibration solver. Physical accuracy/correspondence closure
  remains outside this P0 auto-capture repair. Ordinary webcam exposure sync and
  motion between observations cannot be certified.
- Owner minimal acceptance: full board in BOTH views and AUTO ON, hold 2–3s;
  count rises once, stays fixed while held, rises again after meaningful move/
  tilt + settling. Inspect exact blocker instead of repeatedly forcing SPACE.
  C returns without changing active NPZ; no need to delete/re-solve old calibration.
- Existing default/world XYZ, explicit NPZ selection, 5Hz manual CSV and hotkeys
  remain regression-tested. Old config automatically merges new grace; only
  explicit auto_capture=false requires enabling AUTO. No routine approval needed,
  no merge authorized or requested; existing PR #2/#3/#6 intact.

## Historical Task003B owner record

# Review for owners — Task003B default midpoint

2026-10-13 readiness audit: latest tested implementation
`3d977f45f65f77f75eac29351724ceb124d717e8`, same PR #6; following completion
commit contains documentation only. 285 methods + 35 subtests and unittest 285
pass. Startup omissions have been corrected and exact identity migration tested.
Safest owner operation: update code in the already working directory, keeping
config.json/runtime/model and the same Python environment, then RUN_ME.bat.
Windows/webcam/model/GPU execution cannot be certified here; physical frame-up
assumption still applies. No additional permission question or merge requested.

## Original midpoint delivery record

- Delivery PR: https://github.com/CaiKerman/stereo-pose/pull/6 .
- Branch: `feat/003b-default-camera-midpoint`; base `trae/agent-c3dfMx`, starting
  commit `cf408cdd252ae3f277e5d7b6cba48f7b31e7a899`.
- Tested implementation head: `59b2e90e312244976372fb001da07f138b37fc6f`.
  Following delivery commit changes reports/status only; code is unchanged.
- No code blocker found in self-review; 274 methods + 32 subtests and unittest
  274 pass. Original PR #2/#3 remain unchanged/unmerged. No merge authorized.
- Material limit: actual gravity is not observed by relative camera geometry.
  Default +Z assumes level optical centers and upright/level camera mounts.
  Confirm this installation or use existing W with measured horizontal controls
  for actual world-up. The default origin is at optical-center height, not floor.
- Owner acceptance: update code keeping local config/runtime/model, run RUN_ME,
  expect DEFAULT: CAMERA MIDPOINT before W. Verify +X on forward movement, +Y
  toward LEFT, +Z on upward movement and Y near zero on rig midline; test T CSV,
  saved W priority/cancel/restart and optional zero. Parent XYZ usability was
  reported by the owner, but new physical signs remain untested here.
- If camera order/mounting is incompatible with forward/Y/up or known capture
  size mismatches the NPZ, default is refused with a visible reason. Camera
  indexes/hashes cannot prove mounts unchanged. Absolute accuracy remains open.

## Historical Task003A owner record

# Review for owners — Task003A P0 delivery

- Latest owner instruction at 2026-10-12 19:30 Asia/Shanghai authorized GPT to finish if the other coding agent had not delivered. GitHub still had only handoff commit `389042e` at takeover; no remote implementation/new branch/PR was found. Unpublished work in another agent's environment is not observable.
- **Implementation completed and deterministic verification passed.** Implementation head: `08da0e6ef0e10711bc1c341302bdec3b5daac312`.
- Existing PR: https://github.com/CaiKerman/stereo-pose/pull/3 ; branch `trae/agent-c3dfMx`, unchanged base `feat/002-metric-validation-diagnostics`. Parent PR #2/main are unchanged/unmerged.
- No routine implementation decision awaits permission. Required next decision is owner acceptance on the physical Windows installation before merge. No merge authorization is requested/assumed by this delivery.
- Material limits: physical rig movement cannot be established from numeric camera indexes/file hashes; verify unchanged mounts/order or recalibrate/re-register. Registration residual and repeated eye points do not prove eye absolute accuracy. Three controls have no independent redundancy.
- Owner should test W -> entered real XYZ -> R/U/Enter, restart same W, optional Z/one-point zero, fresh accepted vs candidate eye/joint values, T start/stop CSV and old hotkeys/picker cancel-rescan. Use the existing valid stereo calibration when the physical rig is unchanged.
- See TEST_REPORT.md for exact results/platform and docs/protocols/WORLD_NPZ_CSV_V1.md for actual behavior. The implementing GPT performed self-review and reproduced tests; this is not a second independent human/code-owner review.

## Historical owner records

# Review for owners

## Task003A P0 — owner decision and review handoff (2026-10-12)

- Owner approved continuation on existing `trae/agent-c3dfMx` / PR #3 at 17:16 Asia/Shanghai; base remains `feat/002-metric-validation-diagnostics`. Earlier separate-branch proposals are superseded. No merge/topology authorization.
- Reviewer prepared instructions only; owner will notify another coding agent. No Task003A feature or test run is claimed by this preparation.
- Binding scope: world + translation-only zero, unified NPZ/restart, live eye/joint XYZ, manual T 5Hz CSV; Task002C deferred and P1/P2 excluded.
- No unresolved routine owner decision blocks the specified implementation. GPT reviews implementation/reproduction first; owner verifies physical axes, camera arrangement, W restart and recording afterward.
- Risk requiring explicit review: physical camera movement cannot be established from index/file equality; present clear operator guidance and refuse known geometry mismatches. Registration residual does not prove eye absolute accuracy.
- Implementation agent must replace this section's readiness with actual implementation head SHA, PR #3 URL, remaining material risks and any untested hardware paths when requesting review.
- Canonical coding/reviewer handoff: `docs/handoffs/20261012_TASK003A_HANDOFF.md`.

## Historical owner-review records

Only decisions/risks requiring owner or architecture review. Ordinary
implementation detail is omitted.

## Task 002 — metric validation + joint rejection diagnostics

### Decisions (resolved by reviewer, round 1)

1. **Metric validation reports measurements only — no pass/fail thresholds.**
   → **Approved.** Task 002 exposes measurements first; no acceptance thresholds.
2. **Scale-error baseline is the nominal 25 mm grid.** → **Approved for Task 002.**
   A future optional as-measured board spacing may be added if metrology warrants.

### Notes / risks (no action strictly required)

3. **Diagnostics are internal-only and default off.** `D` surfaces the
   fine-grained per-joint classification as console text; the structured
   `FrameDiagnostics` is never placed on the `stereo_pose_3d/v1.2` wire, and
   `diagnostics.enabled` defaults to `false`. No downstream consumer is affected.

4. **Validation is single-frame (`sample_mode=single_frame`).** → **Approved.**
   `sample_mode` stays explicit in console/report.

### Round 1 (PR #2) — resolved

- `R1-1` (blocking): checkerboard corner correspondence is now canonicalized
  before triangulation. `normalize_correspondence` chooses between `direct` and
  `reversed_180` orderings via aggregate rectified epipolar geometry (never the
  expected `square_mm`), records `corner_order_mode` in the report, and raises
  `MetricValidationError` when neither ordering is plausible. See `REVIEW_INBOX.md`.

### Handoff

- Task branch: `feat/002-metric-validation-diagnostics`
- Pull request: https://github.com/CaiKerman/stereo-pose/pull/2
- Head commit SHA (round 1): `9a68f428956a28a2a0d36629bac9810a91a15c31`

## Task 002A — camera discovery & LEFT/RIGHT selection (owner pre-test request)

Implemented per `docs/instructions/002A_CAMERA_SELECTION_PRETEST.md` on the
same Task 002 branch / PR #2.

### Decisions taken (no new owner input required)

1. **Picker is on by default for the RUN_ME launcher** (`camera.selection.startup_pick: true`) — this is what the owner asked for (double-click, pick, go). It can be disabled via config or `STEREO_POSE_NO_CAMERA_PICK=1`. The project CLI stays opt-in (`--camera-pick`), so automated/noninteractive workflows never see a GUI.
2. **Index identity ≠ physical identity.** When the active calibration's recorded left/right indexes differ from the selected pair (or are missing), a prominent warning banner is printed at startup. The warning is advisory only: no NPZ is deleted, rewritten, or auto-invalidated. The operator decides whether the physical pairing is unchanged (keep calibration) or to recalibrate.
3. **No new dependencies / no pip at runtime.** The picker is plain OpenCV (`imshow` + `waitKey`) on the existing capture backend settings.

### Notes / risks

- Numeric camera indexes can change between boots (Windows enumeration). The
  persisted choice is the current best knowledge; the picker + identity banner
  is the mitigation. Physical identity cannot be proven programmatically with
  plain OpenCV on Windows — device names are not reliably exposed.
- The deterministic suite covers all selection logic with injected fakes; the
  real 3-camera acceptance (visual tiles, hotplug rescan, actual window) is
  left to the owner via the checklist in `README_先看我.txt`.
- One pre-existing test (`test_rejects_symlink_escape`) was made deterministic
  (aged symlink-target mtime); no product code changed for it.

### Handoff (Task 002A)

- Task branch: `feat/002-metric-validation-diagnostics`
- Pull request: https://github.com/CaiKerman/stereo-pose/pull/2
- Head commits (002A): implementation `1c73556` + docs commit on top (see `git log` / PR #2)
- Not merged; awaiting reviewer re-review.

## Task 002B — on-demand diagnostic snapshot (`S`) + compact developer menu (`M`)

Implemented per `docs/instructions/002B_STEREO_SNAPSHOT_AND_DEBUG_MENU.md` on
the existing working branch `trae/agent-c3dfMx` / PR #3.

### Decisions taken (no new owner input required)

1. **`S` saves only what the loop already holds.** The snapshot module receives
   the exact left/right frames and pose results from the current tracking
   iteration; it never opens another camera pair and never reruns YOLO. A
   self-contained `calibration_snapshot.npz` (intrinsics/distortion/
   rectification/projection) is copied out so rectified `uv` and signed
   epipolar deltas can be reproduced offline without the active NPZ or any
   model/hardware dependency.
2. **Privacy: snapshots are runtime-only and never committed.** Outputs live
   under `runtime/diagnostics/snapshots/`, are written atomically and never
   overwrite history; `G` cleanup does not touch them. Human imagery is
   sensitive — the code and README both instruct the operator never to upload a
   snapshot to GitHub or any external service.
3. **`M` is a pure overlay toggle.** Default collapsed shows camera indexes,
   calibration state, accepted-joint count, FPS and live alarms; expanded adds
   the full hotkey row and One Euro internals. No hotkey is remapped or
   disabled, and no numerical/measurement behavior changes.

### Notes / risks

- The 3 px epipolar acceptance gate is **untouched**, and no speculative
  left/right joint-order swap was made. That evidence-gathering is exactly what
  `S` is for: the owner should press `S` on 1–3 static upper-body frames with
  known large epipolar failures, then inspect them offline before Task 002C
  proposes a fix.
- The snapshot/replay path is verified with synthetic frames + exact synthetic
  calibration only; real hardware `S` capture is left to the owner (no claim of
  hardware acceptance from fake inputs).

### Handoff (Task 002B)

- Working branch: `trae/agent-c3dfMx` (existing)
- Pull request: https://github.com/CaiKerman/stereo-pose/pull/3
- Not merged; awaiting GPT review, then owner `S`-capture acceptance.

## Task 001 — Need decision

1. **Module layout additions beyond the literal skeleton.** The instruction's
   skeleton omits `quality/` and `persistence/`, but section 4 explicitly
   requires separating "measurement quality" and "persistence/artifact
   management". I therefore added `src/stereo_pose/quality/` and
   `src/stereo_pose/persistence/`, plus package-root `models.py`/`joints.py`
   (shared vocabulary/config). Please confirm this adaptation is acceptable.

2. **Default runtime paths moved under `runtime/`.** Config *keys* are
   unchanged, but `stereo.calibration_dir` defaults to
   `"runtime/calibrations"` and `calibration_runtime.session_dir` to
   `"runtime/sessions"` (previously `"calibrations"`/`"calib_sessions"`), and a
   new optional `runtime.log_dir` was added. This aligns with the runtime-truth
   intent and `.gitignore`. Confirm no downstream tooling depends on the old
   default paths.

## Notes / risks (no action strictly required)

3. **`ultralytics` is now an optional dependency** (`[live]` extra) and imported
   lazily so package import/tests/doctor run offline. Live inference raises a
   clear error if the extra is absent.

4. **Reference checksum not independently verified.** `reference/README.md`
   records a v1.2 package SHA-256 (`987d8abe...`). I did not receive an
   owner-provided archive to verify it against and preserved the committed
   `reference/v1_2/` files as-is. If a source archive exists, please share it so
   the checksum can be confirmed.

5. **No final world X/Y convention invented** — the rigid-transform scaffold is
   geometry-only, and the current output remains rectified-left-camera.

## Review round 1 (response notes)

Implemented in response to PR #1 review:

- Calibration artifacts split into `auto/` (rolling, cleanup) and `saved/`
  (pinned) with a `promote_calibration` API + live `P` hotkey.
- Cleanup gated behind a trusted-runtime-root path guard; `saved/` is never
  auto-deleted.
- Calibration NPZ records camera context (indices/backend/requested+actual
  size+FPS), and the load path warns on resolution/board/FPS mismatch.
- Restored the `readiness < recommended_readiness` pre-solve warning.
- `camera.fourcc` and `camera.buffer_size` are configurable (defaults
  `MJPG`/`1` preserve prior behavior).

No new owner decisions result from this round; the only convention worth
confirming is the `saved/` sidecar naming (`<name>.npz` + `<name>.meta.json`) and
that a promoted artifact is selected only via an explicit path, never by
newest-file auto-selection.

## Task 001 — Handoff

- Task branch: `feat/001-engineering-foundation`
- Pull request: https://github.com/CaiKerman/stereo-pose/pull/1
- Head commit SHA: `2b124fb93534ae8f52d38df693140a421f1a85d2`

Review round 2 (containment guard, pre-delete mass guard, auto-calibration
precedence, collision-proof promote) is resolved; see `REVIEW_INBOX.md`.
