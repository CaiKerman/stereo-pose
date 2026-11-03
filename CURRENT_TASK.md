Task005 owner acceptance update 2026-11-03: owner still cannot save W coordinate frame; four ArUco IDs recognized in 2D, first ID0 corner0 fails stereo quality (cause formerly opaque), and the W preview pane is collapsed. Same PR #8 now adds per-corner numeric error/limit reporting, accurate "2D identified" labels, deferred W splitter initialization, and regression tests. Geometry/limits untouched. Owner Windows validation and full test run OPEN.

Task005 acceptance update 2026-11-03: Owner screenshot exposes preview pane collapsed to ~1 pixel on Windows Tk. Same existing PR #8 now includes nonzero preview requested height and first-frame deferred splitter initialization, plus native GUI smoke coverage for collapsed sash. Windows hardware approval remains OPEN. Do not merge.

Task005 UI hardware follow-up (2026-11-03): blank Windows Tk camera preview reported; OpenCV compatibility view works. Presentation-only fix pushed to the same `feat/005-responsive-desktop-ui` branch and PR #8, with pixel-level tests. Full repo tests and owner Windows acceptance remain open; do not merge or change PR topology.

Task005 delivery: PR #8 https://github.com/CaiKerman/stereo-pose/pull/8
Tested implementation commit: `5bcc3135f2ebe93bf5785fef90a4ca3b0c98f738`; following completion commit changes documentation only.

# CURRENT_TASK

## Task005 — responsive desktop/operator interface

- Owner authorized new branch on 2026-10-14 09:39 Asia/Shanghai.
- Branch: `feat/005-responsive-desktop-ui`, parent Task004 `b093e2d327b358c4571f5358d7e797930399774d`.
- New PR base: `fix/004-calibration-auto-capture`; existing PR #2/#3/#6/#7 unchanged/unmerged.
- Status: SOFTWARE UI COMPLETE; full 331-method/60-subtest regression and 30 native GUI executions passed. Instruction: `docs/instructions/005_RESPONSIVE_DESKTOP_UI.md`.
- Scope is UI/input adapters; protect verified math, detection, capture policy, NPZ/CSV and protocols.
- No merge/main edits/retarget/rebase/force-push/deletion authorized.

## Previous Task004 delivery (history)

# CURRENT_TASK

## Task004 P0 — automatic checkerboard capture repair

- Latest owner instruction: 2026-10-13 09:42 Asia/Shanghai, implement/fix/tests/submit the static-board WAITING FOR STILLNESS failure autonomously.
- Branch: `fix/004-calibration-auto-capture`; base `feat/003b-default-camera-midpoint` at `082ba5e41e9f3dae47e4d2bfc787a4877523868b`.
- PR: https://github.com/CaiKerman/stereo-pose/pull/7 . Existing #2/#3/#6 unchanged/unmerged; no merge/retarget/rebase/force-push/deletion.
- Tested implementation: `b2922dbaa3ffe4cfdaa593a28f15737a9318adb4`; following completion commit contains documentation only.
- Status: SOFTWARE REPAIR COMPLETE / FULL REGRESSION PASSED: 312 methods + 48 subtests, unittest 312 OK; physical hardware acceptance pending.
- Instruction/root analysis: `docs/instructions/004_CALIBRATION_AUTO_CAPTURE.md`; tests and limits in TEST_REPORT.md, operator guide README_先看我.txt.
- Confirmed sufficient code defect: >=3 observations in .30s never satisfied at 5/2Hz; reproduced without hardware. Owner actual detection cadence and Stereo RMS=3.2548 cause not confirmed.
- Scope: timestamped stable evidence, adaptive loss, coherent motion/order handling, unique pose + interval/diversity state, cached SPACE force/duplicate warnings, diagnostic panel, write truth, synthetic solver/NPZ regression. Original numeric gates and protected math modules preserved.
- Config: old configs merge new stable_loss_grace_s=1.25. Keep .30s / 3 / 5px / .7s / .12; explicitly disabled AUTO remains disabled. No default-config replacement or dependency install required.
- Owner short test: RUN_ME -> C -> full board in both views, AUTO ON -> hold 2–3s (count+1) -> keep fixed (no repeat) -> visibly move/tilt and hold (count+1). C returns without replacing current NPZ; no R needed for this short test.

## Previous Task003B delivery (history)

## Task003B — default camera midpoint coordinates

- Latest follow-up: owner at 2026-10-13 07:43 asked to audit completeness for one-attempt startup. Startup fixes and full verification completed on this SAME branch/PR #6.
- Latest tested implementation: `3d977f45f65f77f75eac29351724ceb124d717e8`; documentation-only completion commit follows.
- Latest verification: **285 pytest methods + 35 subtests passed; unittest 285 OK**, no failures/skips. Earlier 274/32 figures below describe the original midpoint delivery.
- Startup fixes: configured model path, UTF-8 BOM configs, exact-hash moved NPZ recovery before cleanup/picker, headless-GUI diagnosis and setup failure resource release. No math/quality/dependency changes. Run latest ZIP in the working directory preserving local config/runtime/model.

- Latest owner instruction: 2026-10-12 21:15 Asia/Shanghai, create a new branch and implement optical-center midpoint zero, +Y right->left, +X forward, +Z up.
- Branch: `feat/003b-default-camera-midpoint`, starting from exact delivered parent `cf408cdd252ae3f277e5d7b6cba48f7b31e7a899`.
- New PR base: `trae/agent-c3dfMx`; existing PR #2/#3 remain unchanged/unmerged. No merge/retarget/rebase/force-push/deletion.
- Instruction: `docs/instructions/003B_DEFAULT_CAMERA_MIDPOINT.md`.
- Delivery: https://github.com/CaiKerman/stereo-pose/pull/6 ; implementation `59b2e90e312244976372fb001da07f138b37fc6f`, following reports-only commit.
- Status: IMPLEMENTED / FULL DETERMINISTIC REGRESSION PASSED (274 methods + 32 subtests; unittest 274 OK). Owner Windows/physical sign acceptance pending; no merge authorized.
- Scope: derived default live/CSV frame, saved W precedence, cancel/restart/zero/C-R behavior, numerical regression and operator docs. No dependencies/config keys, legacy v1.2 changes, precision closure or P1/P2.
- Physical assumption: level optical centers, upright/level cameras. Stereo-only parameters do not observe gravity; W establishes verified world-up when needed.
- Parent hardware evidence: owner downloaded `stereo-pose-trae-agent-c3dfMx`, ran RUN_ME and confirmed XYZ visible/usable. Parent full marker/recording acceptance not asserted.
- New change status and exact verification: see latest `TEST_REPORT.md`; owner Windows/physical sign verification pending.

## Previous Task003A delivery and history (branch-specific restrictions superseded for Task003B)

## Task003A P0 — implemented; owner hardware acceptance pending

- **Latest instruction (2026-10-12 19:30 Asia/Shanghai):** owner asked GPT to check the other agent's delivery and finish this development if incomplete.
- **Takeover evidence:** branch remained at documentation-only `389042ee2849a1b3148c04d0ddd63eaf09ab8372`; no new remote code/branch/PR. The other agent's unpublished local work is not observable.
- **Status:** IMPLEMENTATION COMPLETE / DETERMINISTIC VERIFICATION PASSED; awaiting Windows/physical owner acceptance, not approved for merge.
- **Implementation head:** `08da0e6ef0e10711bc1c341302bdec3b5daac312`.
- **Branch/PR:** existing `trae/agent-c3dfMx` / https://github.com/CaiKerman/stereo-pose/pull/3 .
- **Base:** unchanged `feat/002-metric-validation-diagnostics`; parent PR #2 -> main remains open/unmerged. No new branch/PR, merge, retarget, rebase, force-push or deletion.
- **Issue:** https://github.com/CaiKerman/stereo-pose/issues/5 .
- **Scope completed:** P0 engineering rigid world coordinates + translation-only zero, unified immutable NPZ + exact activation/restart, fresh eye/selected joint XYZ, T manual nominal 5Hz CSV (default OFF).
- **Verification:** full pytest 261 methods + 26 subtests, unittest 261 OK; original 214-method baseline independently reproduced before edits. Hardware/model/Windows UI injected; actual owner hardware untested.
- **Sources:** docs/instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md ; docs/protocols/WORLD_NPZ_CSV_V1.md ; TEST_REPORT.md ; REVIEW_INBOX.md .
- **Deferred:** Task002C absolute accuracy/root cause and P1/P2. Original quality gates and legacy v1.2 camera XYZ/statistics remain unchanged.
- **Next:** owner tests current code in the existing working environment, keeping local model/config/runtime data. Check W/R/U/Enter, restart W, optional Z, eyes/candidates, T CSV, S/M/D/V and picker cancel/rescan. Any later code change requires regression and a reviewable commit on this same branch.
- **Privacy:** only synthetic examples/tests committed; user face snapshots, real calibration and recordings remain local.

## Earlier handoff and audit history (superseded active status)

# CURRENT_TASK

## Active: Task 003A — P0 world alignment, live XYZ and manual 5Hz CSV

- **Status:** OWNER-AUTHORIZED ON EXISTING BRANCH / HANDOFF READY; implementation pending the owner's instruction to the coding agent.
- **Owner instruction, 2026-10-12 17:16 Asia/Shanghai:** “直接在当前分支继续开发吧。你弄好交接文档后我通知其他智能体开始开发。”
- **Task branch:** `trae/agent-c3dfMx` (existing; do not create a replacement branch).
- **Existing PR:** https://github.com/CaiKerman/stereo-pose/pull/3
- **PR base:** `feat/002-metric-validation-diagnostics`; parent PR #2 remains OPEN/unmerged into `main`.
- **Issue:** https://github.com/CaiKerman/stereo-pose/issues/5
- **Full instruction:** `docs/instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md`
- **Coding/reviewer handoff:** `docs/handoffs/20261012_TASK003A_HANDOFF.md`
- **Priority:** P0 only: known real fiducials -> no-scale rigid C→W, immutable complete stereo+world NPZ with explicit activation/restart recovery, live eyes/selected joints XYZ, manual `T` CSV recording default OFF at nominal 5Hz. Translation-only zero/reference origin is P0.
- **Deferred:** Task002C absolute-accuracy/root-cause closure, P1/P2, video, bookmarks, plots/playback, history browser, extra eye AI models and complex GUI.
- **Accuracy:** eye P95≤5mm and shoulder/elbow P95≤10mm remain unproven targets. Do not relax 3px epipolar or other quality gates.
- **Authorization scope:** add Task003A commits to this same branch and update the same PR #3. This expressly supersedes older proposals requiring a new stacked coding branch, generic PR→main instructions, and the old Task002C-before-Task003 sequencing.
- **Not authorized:** merging, retargeting/closing existing PRs, force-push, rebase, branch deletion, new branch/PR, or modifying `main` / PR #2 source. If the coding platform cannot use the authorized branch, report the concrete limitation before changing topology.
- **Privacy:** no real face images, snapshots, calibration NPZ, per-person coordinates or recordings in GitHub/tests/CI.

## Coding-agent startup

1. Fetch and fast-forward the existing `trae/agent-c3dfMx` branch; inspect local changes and do not overwrite them.
2. Verify current branch, remote head and unchanged PR #3 base; never start from `main`.
3. Read `AGENTS.md`, this file, the active Task003A section of `REVIEW_INBOX.md`, full instruction and handoff. Older inbox sections are historical.
4. Inspect affected modules/tests and run the complete deterministic baseline before edits; report actual counts and environment.
5. Implement/checkpoint 003A-1 (rigid math + correspondences + NPZ/restart), 003A-2 (W interaction + live XYZ), 003A-3 (T CSV + recovery + complete regression).
6. Update completion artifacts and Chinese user documentation; push to the SAME branch/PR #3; provide implementation head SHA and exact reproduction commands.
7. Stop for GPT review. Owner hardware acceptance follows code review. Neither review readiness nor P0 completion authorizes merging.

## Verified preparation baseline

- Before this documentation update: PR #3 head `d7adf887cba73608c1ea2eecdfef586fa1b20985`.
- Last code-reviewed implementation: `288860d297ef32a4258b5f5b5f1d632de6a4497c`; the next four commits through `d7adf88` changed documentation only.
- PR #2 head: `ed0421ae595bb2fe19b38ea209b05fba3084ae41`; `main`: `d26e64772b8c634851b5812b6015a7ab57124e83`.
- Existing report: 214 passed / 0 failed / 0 skipped, reported by the prior coding agent on Linux/headless. This handoff update does not claim an independent rerun or hardware/Windows acceptance.

## Previous task: Task 002B — Stereo diagnostic snapshots + compact developer menu

- **Status:** Implementation and final *code* review passed for owner S/M hardware acceptance on PR #3; do **not** interpret as permission to merge or precision closure. Later owner supplied 3 snapshot groups and offline analysis; `M` full operator check and picker cancel/rescan were not formally confirmed.
- **Issue:** https://github.com/CaiKerman/stereo-pose/issues/4
- **Spec:** `docs/instructions/002B_STEREO_SNAPSHOT_AND_DEBUG_MENU.md`
- **Review verdict:** https://github.com/CaiKerman/stereo-pose/pull/3#issuecomment-6063507171
- **Legacy numerical protocol:** `stereo_pose_3d/v1.2` uses rectified-left-camera XYZ in mm; must never silently be changed to world XYZ.
- **Physical:** two external webcams, user has moved between arrangements; latest private diagnostic snapshots showed LEFT CAM1, RIGHT CAM2, ~555.5mm baseline, 1280x720; camera indexes are not physical identity. The true eye spatial position has no independent reference, so no absolute precision claim.
- **Historical acceptance:** Task002 initial real V and D worked, with eye/shoulder/elbow epipolar rejections; S snapshot and offline replay code have been validated. Existing 3px epi and related gates remain.

## Other prior history

Task002 source PR #2 introduced `D` per-joint rejection diagnostics and `V` checkerboard 3D metrics. Task002A within PR #3 introduced visual camera picker; Task002B within PR #3 introduced S snapshots and M menu. Previous detailed Task002B instructions remain in `docs/instructions/002B_STEREO_SNAPSHOT_AND_DEBUG_MENU.md` and previous reviewer findings in `REVIEW_INBOX.md`.

