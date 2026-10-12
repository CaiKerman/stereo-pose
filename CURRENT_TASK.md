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
