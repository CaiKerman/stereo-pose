# Instruction 003A — World Coordinate Alignment, Live Joint XYZ & On-demand CSV

- **Owner decision:** 2026-10-12. **Tracking:** [Issue #5](https://github.com/CaiKerman/stereo-pose/issues/5).
- **Priority:** P0 functionality only; precision closure Task002C **deferred, not solved**. Do not claim eye ±5mm or shoulder/elbow ±10mm attained.
- **Authorized coding branch:** existing `trae/agent-c3dfMx` / PR #3, approved by owner on 2026-10-12 17:16 Asia/Shanghai. Continue here when owner notifies the coding agent; preserve PR base `feat/002-metric-validation-diagnostics`. No new branch/PR; parent PR #2 and #3 remain unmerged.
- **Authoritative handoff:** `docs/handoffs/20261012_TASK003A_HANDOFF.md`. Start by reading `AGENTS.md`, `CURRENT_TASK.md`, `REVIEW_INBOX.md`, this instruction, and Issue #5.

## 0. Intent, out-of-scope, priorities

Turn the current stereo-pose prototype into a practical **local-only engineering coordinate reader** with **manual, optional, low-rate CSV recording**.

**Required P0:** (A) user-defined engineering/world frame from fiducial/known 3D correspondences, (B) save/reload this world transform together with the owning stereo calibration, (C) live eye and joint XYZ readout, (D) manual-start/stop 5Hz CSV data sessions, (E) clear quality/status and compatibility tests.

**Not in this task:** precision root-cause fix, adjusting epipolar/reprojection/gating thresholds, new AI eye model, new stereo calibration algorithm, automatic live fiducial tracking after alignment, video recording, event bookmarks, playback/graphs, historical session browser, full GUI framework, world-to-RAMSIS integration, multi-person identification, auto-upload, hardware synchronization, changes to user webcams/mounting. Existing `S/M/D/V/C/R/P/F/G` remain.

The owner specifically asks that recording be **OFF by default**, that P1/P2 be **postponed**, and that coordinate-zero/reference alignment be **P0**.

## 1. Current architecture to preserve

- The working project is a Windows unzip-and-run Python app: `RUN_ME.bat`, local `yolo11n-pose.pt`, `src/stereo_pose/...`, `config.json` merging `configs/default.json`.
- Camera acquisition `read_stereo_pair` -> `PoseEstimator.infer_pair` once per frame -> `StereoTriangulator.triangulate_with_quality` -> `classify_joint` gates -> OneEuro smoothing -> `PoseFrame` -> `to_v1_message` -> console/JSONL/UDP; outputs now use **rectified-left-camera XYZ (mm)**.
- `src/stereo_pose/joints.py` defines 17 COCO/YOLO joints including `left_eye`, `right_eye`; `ergonomics` default output group excludes eyes. New eye readout must not need extra inference.
- `RuntimeCalibration._solve_core` creates stereo NPZ with K1,D1,K2,D2,R,T,R1,R2,P1,P2,Q and metadata. OpenCV may return D shape `(1,5)`; preserve it. `StereoTriangulator` reads it. `newest_calibration` currently favors newest `auto/` NPZ; `P` promotes to `saved/`. Handle this explicitly for world-aligned packages.
- `S` saves privacy-sensitive raw frames/keypoints; `M` opens developer overlay; `V` checks checkerboard metrics; `D` emits rejection reason; currently no CSV recorder or world alignment.
- `stereo_pose_3d/v1.2` wire schema is a stable compatibility contract, with `xyz_mm` meaning rectified-left-camera XYZ. Never silently reinterpret its coordinate fields.

## 2. Coordinate frames — normative contract

Let `C` be the **rectified-left-camera** frame (mm), and `W` the owner-defined engineering/world frame (mm). User-supplied point correspondences:
`(fiducial_id, C_i, W_i)`, where `C_i` comes from **the same left/right calibration** and `W_i` is an independently entered real position.

Rigid transform **SE(3), no scale/shear**:

```text
P_world_mm = R_wc @ P_camera_mm + t_wc_mm
R_wc^T @ R_wc = I; det(R_wc) = +1
P_camera_mm = R_wc^T @ (P_world_mm - t_wc_mm)
```

- Require >=3 **non-collinear** points in both coordinates; recommend >=4–6 widely spaced points and holdout points where possible. Reject degenerate/poorly conditioned configurations, duplicate IDs, inconsistent units, gross outliers and unmapped landmarks; explain how to fix.
- Use a tested rigid least-squares solve (Kabsch/Umeyama **without scale**) and explicit correspondence matching; prefer inlier/outlier handling with transparent residuals, never silent re-labeling of points or changing accepted physical size.
- Report residual per point, 3D RMS, maximum, inlier count, spatial distribution and whether the solved frame is right-handed. **RMS registration residual is not absolute eye accuracy**. For exactly 3 points, explicitly warn that independent redundancy is absent.
- Owner selects frame name, origin, +X/+Y, and confirms that **+Z is physically upward** when using the engineering frame. Do not infer gravity from an arbitrary vertically mounted sheet. For the WORLD TRIAD sheet on a physically horizontal XY plane, P0 is origin, P1 is +X and P2 is +Y with right-handed +Z (confirm orientation).
- Modes: **full world alignment** (fit R and t) and **zero/relative origin** (change origin only, preserving current axes). On zero, identify a known selected reference point and store the derivation; never imply a translation-only zero set a world-up direction.
- Define `C`, `W`, units, transform direction and calibration identity in every output and status. When absent/invalid world alignment, label `CAMERA FRAME`, do not masquerade as W.

## 3. Use the already printed targets

Previous owner artifact: `StereoPose_Markers_A4_ALL_14pages.pdf` (available in prior project/conversation context; **not** a license to commit private files or reconstruct uncertain IDs).

Known designs:
- ArUco `DICT_4X4_50`, loose IDs 0–7, black square side 60 mm.
- WORLD TRIAD `DICT_4X4_50`, three unique marked centers: P0=(0,0), P1=(100,0), P2=(0,100) **in sheet-local mm**, 100mm center-to-center.
- ChArUco boards 5×7 (square28mm, marker20mm) and 7×10 (square20mm, marker14mm); `DICT_4X4_50`.
- Alternative `DICT_5X5_50` loose IDs 0–5 (black side50mm).
- 50mm crosshair grid, P0..P11, known 2D sheet-local grid.

Implement **automatic identification of unique ArUco IDs in each view**, with matched same-marker IDs and independently measured/entered actual `W_i`. The physical meaning of a feature MUST be explicit: marker center vs designated marker corner vs ChArUco chessboard corner are **different reference points**. Do not assume ArUco numeric ID equals WORLD TRIAD P0/P1/P2 without verifying the printed mapping or a user-supplied association.

P0 detection support minimum: `DICT_4X4_50` free markers and WORLD TRIAD. Design a clean adapter for ChArUco known-corner layout and crosshair/manual points; if adding ChArUco to production this round threatens stability, document as deferred P1 **only after** achieving specified ArUco/WORLD TRIAD acceptance and owner agreement. Since user requested use of these already printed formats, make data schema extensible without rework.

Check the actual installed OpenCV for `cv2.aruco` support. No silent `pip install`, model download or network access; if missing, give actionable local dependency diagnostics and do not break unrelated runtime paths.

**User input UX** (no giant desktop framework): when `W` triggers alignment, show detected marker IDs/centers on a preview and generate/accept a simple editable `reference_points.csv` mapping `dictionary,id,feature_type,X_mm,Y_mm,Z_mm` (or equivalently minimal compact UI). Users can enter real XYZ rather than having them hard-coded. Reject ambiguous/missing/duplicate data; show axes and preview before Confirm/Cancel. A cancelled/failed operation must leave the active calibration and tracking unchanged.

Use the existing stereo frame pair and geometry where feasible; do not run YOLO a second time to support markers. Fiducial detection can be on-demand during W setup. Use multiple stable frames optionally, but no new continuous logging.

## 4. Calibration package & selection — one source of truth

**Owner requirement:** Stereo calibration and world alignment shall be saved and loaded **together as one NPZ artifact**, reusing the stereo calibration library/selection/pinning workflow. Avoid orphan `world.json` as the only owner of active transform.

Suggested additional `np.savez` keys (exact schema to document and test):
- `world_R` float64 (3,3), `world_t_mm` float64 (3,), `world_coordinate_name` string scalar, `world_schema_version` string;
- `world_metadata_json` UTF-8 JSON serialized as a NumPy non-object string scalar: reference IDs/feature definitions/world XYZ, method, per-point residuals, overall RMS/max, creation timestamp, camera-calibration identity/fingerprint, orientation/axes definition and confirmation.

Never use pickle/object arrays; `np.load(...,allow_pickle=False)` must work. Preserve all original NPZ numeric matrices and relevant metadata exactly (including OpenCV D row shape); use atomic temp+rename, unique name, no overwrite, and managed `saved/` to prevent garbage collection.

A new world alignment on existing stereo NPZ must produce a **new immutable combined file**. Selection: once user explicitly activates this complete file, persist the exact selection in config/active preference and reliably reload it after restart. Do not silently revert to latest `auto/` and lose world frame; do not overwrite old NPZ. Legacy stereo-only files remain loadable; show that W is unavailable.

Invalidate or loudly refuse stale world transform when physical cameras, stereo extrinsics/intrinsics, image size or calibration identity changes. Camera numeric USB index alone cannot establish physical identity. Changing just numeric indexes without physical geometry change should warn, not arbitrarily destroy calibration. World metadata references the originating stereo component/hash and validation must detect mismatches.

A stereo re-solve `C→R` must clear the active world alignment from the new stereo version until re-registered, and never silently transfer it to a new rig. `P` current pin semantics must remain usable.

## 5. Real-time eye/joint readout

- Include `left_eye`, `right_eye`, and computed `eye_midpoint` (non-COCO derived feature) in the user-facing display. Midpoint only when **both eyes** have valid accepted XYZ. Mark that it is NOT the eye rotation center or gaze point.
- User-selectable groups/joints; keep existing ergonomics output available and no second YOLO pass. Clear camera/world frame selection and unit `mm`, live updates and confidence/status; display exact XYZ with convenient precision (e.g. 0.1mm formatted, not a claim of 0.1mm accuracy).
- Accepted filtered C XYZ -> apply validated R/t -> display W XYZ. Preserve raw camera and accepted filtered camera values for recovery. Inverse transform available for debugging.
- Distinguish **accepted**, **rejected-but-triangulated candidate**, **missing**, **stale**. Rejected candidate must be labeled visibly and not published as accepted. No inventing zeros/previous-frame values for missing joints.
- Keep old stereo quality gate: 3px epipolar, reprojection, depth, quality score, speed; do not loosen to improve visual output count.
- Preserve legacy `stereo_pose_3d/v1.2` exactly (camera coordinates and original fields); optional additive named world output/new version must be opt-in and separately documented.

## 6. Manual time-series CSV recorder (no video this task)

Example defaults (final documented schema may expand):

```json
"recording": {
  "enabled": true,
  "auto_start": false,
  "sample_rate_hz": 5,
  "save_csv": true,
  "output_dir": "runtime/recordings",
  "include_rejected_candidates": true
}
```

Here `enabled` only enables the ability to press `T` — **must NOT start recording on application startup**. `T` toggles start/stop only in tracking state; REC visual status and console summary show duration, actual sample count and path; app exit cleanly stops/flushed.

- Record fresh **processed inference** frames at a configurable max nominal **5 samples/s**, using monotonic cadence (not frame-index % 6 and not polling cameras separately). When inference <5FPS, record available fresh frames with true timestamps — no duplicated/repeated placeholders. Capture raw wall timestamp_ns, frame index and monotonic elapsed time.
- CSV **long format**: one row per `(sample, requested joint)`; include even rejected/missing joints with explicit status and **blank numeric cells**, never `0,0,0` placeholders. Persist accepted camera filtered/raw XYZ, transformed world XYZ, optionally finite rejected candidate XYZ in **separate clearly labeled columns**, both confidences, pixel residuals and terminal reject reason, plus calibration/frame identifiers.
- Include `eye_midpoint` only when both accepted; it is derived, not a raw YOLO joint. Support later calculation without corrupting existing CSV meaning.
- `runtime/recordings/<unique-session>/joints.csv`, `session.json` (sample rate requested + achieved, video disabled, coordinate frame/axes/units, frozen NPZ identity/sha256 and world transform, model, quality+filtering configuration, camera identities/resolution, start/stop/exit status). Use one frozen calibration per recording session. Do not allow silent world-frame swaps in active recording; stop/segment with an explicit reason.
- Streaming/flushing appropriately, bounded memory, recoverable partial recording or clearly marked failure, no overwrites, no cleanup of sessions by `G`. No image/video data in this task; CSV of eye/face keypoints still sensitive, local only.
- **No** P1/P2 video recording, `B` events, history browser, plot/replay or complex desktop UI.

## 7. Integration constraints & privacy

- Keep Windows unzip+RUN_ME path, no required internet service, no automatic dependency download, no destructive environment changes. Add only essential packaged dependency with explicit rationale and instructions; do not silently install.
- Preserve existing hotkeys `S/M/D/V/C/R/P/F/G/Q`; `W` for world setup, `T` for CSV. World UI and recording must not steal calibration-mode `R`, `SPACE`, `X`.
- Untrusted/invalid/calibration file paths must remain inside project-managed storage for generated artifacts. No symlink escape or path traversal; never delete user recordings. Recording path failure must not crash the tracking loop or destroy prior sessions.
- Never commit, upload, transmit or embed in docs/tests real face images, user snapshots, per-person identifiable keypoint traces, calibration NPZ or runtime recordings. All tests synthetic; users explicitly control any later sharing. No automatic external telemetry.

## 8. Deterministic tests (minimum)

1. Generate 3D target points under known arbitrary proper R/t; recover exact to numerical tolerance; verify `R.T@R=I`, `det(R)>0`, distances preserved, inverse works. No scaling.
2. Reject 0/1/2 points, collinear/near-collinear, duplicate/mismatched IDs, nonfinite/invalid XYZ, inconsistent coordinate definition, insufficient inliers; report residuals. Include coplanar >=3 noncollinear and tilted reference sheet; no automatic vertical inference.
3. Synthetic ArUco IDs / left/right projected corners or detector-injected data; correct marker centers, proper ID-to-XYZ map, swapped/missing ID and occlusion cases; ensure user cancels preserve calibration.
4. NPZ metadata round-trip (`allow_pickle=False`), old NPZ compatibility, row/column distortion vectors unchanged, file never overwritten, atomic failure recovery, initial selection and restart restore complete artifact; new stereo solve invalidates W; wrong cal fingerprint warns/refuses.
5. Transform accepted raw+filtered vs candidate separately, eye midpoint correct only both accepted, reason flags accurate; verify `stereo_pose_3d/v1.2` coordinate semantics **unchanged**.
6. Fake-clock recorder at 30, 7, 5, 2FPS input, jitter, start/stop/rapid toggles, exception/disk-full, app exit and no automatic start; timestamp fidelity, no artificial repeats or missed duplicate sampling, invalid rows not zero-filled, frozen session metadata and exact CSV columns.
7. Full existing deterministic regression tests, S offline replay, M/D/V/C/P hotkey compatibility, Windows launcher smoke check; list exact commands/results/platform, declare non-exercised physical-camera/UI tests.

## 9. Owner/manual acceptance

Only after reviewer has inspected code:
- Owner selects camera pair and loads current stereo calibration (unchanged physical installation).
- Place printed markers at known positions; enter >=3 known non-collinear real XYZ (recommend >=4), verify marker IDs and physical axes; view fitting errors; save named combined NPZ.
- Restart without markers and confirm **same named coordinate system and transform** loads, no latest-auto fallback.
- Show both eye XYZ and other selected joints with `CAMERA FRAME` vs world label and rejected status; verify camera/world relationship numerically using a chosen reference.
- Press `T` once to begin, move/pose, press `T` to stop; verify CSV around 5Hz only when inference supports, time series and per-frame joint rows, session path, correct units and transform, no privacy-sensitive images.
- Check failed/cancelled W, lost joint visibility, file write error (if safe), UI hotkeys.
- Precision P95 targets **cannot be certified without independent truth**; no "±5mm achieved" assertion.

## 10. Review report package

Agent must update `CHANGE_SUMMARY.md`, `TEST_REPORT.md`, `REVIEW_FOR_OWNERS.md`, `REVIEW_INBOX.md`, relevant `README_先看我.txt`, `README.md`, `docs/architecture/DATA_FLOW.md`, config schema, protocol/NPZ definitions, tests.

Submit a reviewable diff with links, exact commit SHA, tests count and example **synthetic** reference_points.csv / CSV rows (not actual user snapshots); stop before any merge. Reviewer prioritizes protocol and frame semantics, NPZ linkage, rigid algebra, availability and privacy, effective 5Hz cadence and Windows path.

## 11. Phase order inside Task003A

1. **003A-1:** SE(3) pure solver, marker correspondence adapter and unit tests, new versioned calibration package/selection and restart tests.
2. **003A-2:** W interaction, reference point import/preview/confirm, both eye and selected joint readout; preserve status/quality.
3. **003A-3:** T on-demand CSV writer/metadata/recovery, integrate config and user docs; full tests and review.

Test/checkpoint after each sub-phase; avoid all-in-one changes without intermediate verification.

## 12. Owner-authorized existing branch and review gate

**Owner's latest instruction, 2026-10-12 17:16 Asia/Shanghai:**
“直接在当前分支继续开发吧。你弄好交接文档后我通知其他智能体开始开发。”

This authorizes Task003A implementation on existing `trae/agent-c3dfMx`
and continued use of existing PR #3. It supersedes the earlier separate
stacked-branch proposal and the instruction-publication-only branch restriction.

Verified immediately before this documentation update:
- `main`: `d26e64772b8c634851b5812b6015a7ab57124e83`, Task001 only.
- PR #2: `feat/002-metric-validation-diagnostics` at `ed0421ae595bb2fe19b38ea209b05fba3084ae41` -> `main`, OPEN/unmerged.
- PR #3: `trae/agent-c3dfMx` at `d7adf887cba73608c1ea2eecdfef586fa1b20985` -> `feat/002-metric-validation-diagnostics`, OPEN/unmerged.
- Last code-reviewed implementation is `288860d297ef32a4258b5f5b5f1d632de6a4497c`; the four subsequent commits through `d7adf88` only changed documents.

Coding agent must fetch the CURRENT remote head before starting; the hashes
above identify preparation history, not permission to discard later work.
Keep small phase-specific commits and update the same PR #3. Do not start from
`main`, create another branch/PR, merge, retarget/close old PRs, force-push,
rebase or delete branches. If a cloud coding environment cannot retain this
branch, explain that concrete platform constraint to the owner before acting.

Read the active Task003A owner decision in `CURRENT_TASK.md` and
`REVIEW_INBOX.md`; older Task002/002B restrictions are historical when they
conflict with this scope. Existing code-quality, compatibility, privacy and
no-merge gates remain in force.

The reviewer prepares handoff only; another agent implements after the owner's
notification. Submit code, exact tests and reproduction SHA for GPT review,
then perform owner hardware acceptance. Stop before merging.
