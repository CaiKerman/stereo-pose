# Review for owners — Task 001

Only decisions/risks requiring owner or architecture review. Ordinary
implementation detail is omitted.

## Need decision

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

## Handoff

- Task branch: `feat/001-engineering-foundation`
- Pull request: https://github.com/CaiKerman/stereo-pose/pull/1
- Head commit SHA: `2b124fb93534ae8f52d38df693140a421f1a85d2`

Review round 2 (containment guard, pre-delete mass guard, auto-calibration
precedence, collision-proof promote) is resolved; see `REVIEW_INBOX.md`.