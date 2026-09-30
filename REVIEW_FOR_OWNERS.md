# Review for owners

Only decisions/risks requiring owner or architecture review. Ordinary
implementation detail is omitted.

## Task 002 — metric validation + joint rejection diagnostics

### Need decision

1. **Metric validation reports measurements only — no pass/fail thresholds.**
   The `V`-hotkey capture writes spacing, scale error, plane-fit residuals,
   epipolar/reprojection, and depth range to `runtime/validation/`, but does not
   classify the board as pass/fail and adds no tolerance limits. Please confirm
   whether acceptance thresholds should be defined (and their values), or whether
   measurement-only reporting is the intended scope.

2. **Scale-error baseline is the nominal 25 mm grid.** Both metric validation
   and the plane-fit scale assume the physical board is exactly 25.00 mm per
   square at 9x6 inner corners, so printer scaling error is indistinguishable
   from stereo error in the scale metric. If an as-measured board size is wanted
   as the reference, the report would need a pluggable `reference_square_mm`.
   Confirm the 25 mm nominal is acceptable.

### Notes / risks (no action strictly required)

3. **Diagnostics are internal-only and default off.** `D` surfaces the
   fine-grained per-joint classification as console text; the structured
   `FrameDiagnostics` is never placed on the `stereo_pose_3d/v1.2` wire, and
   `diagnostics.enabled` defaults to `false`. No downstream consumer is affected.

4. **Validation is single-frame (`sample_mode=single_frame`).** Reports are a
   single capture with no temporal averaging; a multi-frame average would reduce
   noise but is out of scope for this task.

### Handoff

- Task branch: `feat/002-metric-validation-diagnostics`
- Pull request: https://github.com/CaiKerman/stereo-pose/pull/2
- Head commit SHA: `88eb4ec06d06813d7f3e164008ad6168dfac7801`

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