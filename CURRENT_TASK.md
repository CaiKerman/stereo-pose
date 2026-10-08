# CURRENT_TASK

## Active: Task 002B — Stereo diagnostic snapshots + compact developer menu

- **Status:** READY — owner authorized implementation; no merge.
- **Issue:** https://github.com/CaiKerman/stereo-pose/issues/4
- **Full spec:** `docs/instructions/002B_STEREO_SNAPSHOT_AND_DEBUG_MENU.md`
- **Existing working branch:** `trae/agent-c3dfMx`
- **Existing working PR:** #3 -> `feat/002-metric-validation-diagnostics`
- **Parent task/PR:** Task 002, PR #2 -> `main` (remain unmerged)

### Agent startup (follow in order)

1. Pull the **existing** `trae/agent-c3dfMx` branch; do not start from stale `main`.
2. Read `AGENTS.md`, `REVIEW_INBOX.md`, this file and **`docs/instructions/002B_STEREO_SNAPSHOT_AND_DEBUG_MENU.md`**.
3. Read Issue #4 and the existing Task 002/002A instructions for compatibility.
4. Implement the **S one-shot stereo frame+2D joints diagnostic snapshot and offline replay first**.
5. Implement the **M toggleable compact Developer/Diagnostics menu second**.
6. Add deterministic tests, update all review artifacts, push to the **same existing branch/PR #3**.
7. **STOP for GPT code review**. Do not merge, delete branches, create extra PRs/branches, or change PR base. If Trae Cloud absolutely requires new branch topology, ask owner approval before acting.

### Hardware facts already confirmed by owner

- Two external USB webcams selected on a 3-camera laptop: LEFT CAM 2, RIGHT CAM 1.
- Both webcam positions changed. New physical lens-center baseline approximately 552 mm is **correct**. Do not use old approximately 289 mm spacing as a calibration fault.
- Checkerboard V successfully saved 3 x 54/54-corner reports; 3D-scale deviation exists (far view -2.165%), but calibration works.
- D revealed human joint epipolar rejections frequently far above 3px; no cause established. **Do not relax the gate** or assume left-right label swapping without frame evidence.

### Scope / protection

- No new required dependencies, automatic pip or online uploads.
- Never commit real user camera frames or calibration artifacts to GitHub.
- Keep calibration and snapshots in bounded `runtime/`; preserve v1.2 output protocol and all existing hotkeys.
- Task 002C root-cause fix and Task 003 world coordinate system are **not in this task**.
- Camera-picker cancel / hotplug rescan remain outstanding owner manual checks; do not invent a pass.

## Previous task context (not active)

The parent `docs/instructions/002_METRIC_VALIDATION_DIAGNOSTICS.md` implemented per-joint D diagnosis and checkerboard V metrics. `docs/instructions/002A_CAMERA_SELECTION_PRETEST.md` implemented the pre-test camera selection UI on PR #3. Both code paths were evaluated by reviewer; owner has performed a successful visual-pick/confirm and D/V workflow. Parent Task002 and PRs #2/#3 remain **open and unmerged** until targeted diagnosis and end-to-end stability acceptance.
