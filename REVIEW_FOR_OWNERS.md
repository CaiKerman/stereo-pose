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
