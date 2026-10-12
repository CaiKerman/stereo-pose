# CURRENT_TASK

## Next planned: Task 003A — World alignment, live XYZ and manual 5Hz CSV

- **Status:** REQUIREMENTS PUBLISHED / WAITING CODING AGENT AND OWNER-APPROVED BRANCH BASE. No Task003A feature code has been started.
- **Issue:** https://github.com/CaiKerman/stereo-pose/issues/5
- **Full instruction:** `docs/instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md`
- **New-conversation handoff:** `docs/handoffs/20261012_TASK003A_HANDOFF.md`
- **Priority:** **P0 only** — engineering XYZ via known real fiducials and rigid C→W coordinate transform (no scale), immutable unified stereo+world NPZ + correct restart activation, live eyes/selected joints XYZ, `T` manual CSV capture default OFF at nominal 5Hz. No video, events, plots, playback or P1/P2.
- **Accuracy status:** Eye P95≤5mm, shoulder/elbow P95≤10mm are targets, not achieved or independently confirmed. Task002C root-cause investigation deferred and no quality gates are to be relaxed.
- **Git status:** PR #2 `feat/002-metric-validation-diagnostics` -> `main` OPEN; PR #3 `trae/agent-c3dfMx` -> PR #2 source branch OPEN. Do not implement from stale `main`.
- **Documentation location:** Task003A issue/spec/handoff are published on the **existing** PR #3 branch to avoid creating a coding branch/PR without approval.
- **CODING BRANCH NOT YET AUTHORIZED:** This section does NOT direct a new agent to add Task003A implementation commits to `trae/agent-c3dfMx`. The owner must explicitly approve a separate non-destructive stacked branch/PR rooted at the verified current PR #3 tip (or an approved safe merge plan) before coding starts. No merge/rebase/force-push/delete of existing branches.
- **Startup for new agent:** read `AGENTS.md`, `REVIEW_INBOX.md`, this file, Issue #5, full instruction, handoff, current modules & tests; verify upstream SHA; agree branch arrangement with owner; implement in stages 003A-1/2/3; request GPT review before merge. No face photos, per-person recordings, real NPZ or runtime artifacts in GitHub.

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
