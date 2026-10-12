# AGENTS.md — Stereo Pose repository agent contract

This file applies to the entire repository. Every coding/implementation agent must read it before making changes.

## 1. Authority and source of truth

Use this precedence order:

1. The owner's latest explicit instruction.
2. `CURRENT_TASK.md`.
3. The instruction file referenced by `CURRENT_TASK.md`.
4. This `AGENTS.md`.
5. Architecture/protocol/calibration documentation.
6. Existing implementation.

If two sources conflict, do not silently choose a new convention. Record the conflict in `REVIEW_FOR_OWNERS.md` and preserve the last verified behavior unless the owner explicitly changed it.

## 2. Git workflow

- `main` contains reviewed baseline code only.
- Never implement directly on `main`.
- Read `CURRENT_TASK.md` and use exactly the task branch declared there.
- Keep commits small and reviewable.
- Push work to the exact existing task branch and PR declared in `CURRENT_TASK.md`; use its declared PR base. Target `main` only when that task explicitly declares it.
- Do not merge your own PR unless the owner explicitly instructs you to do so.
- Do not force-push shared reviewed history unless explicitly authorized.

### Current owner-approved branch exception (2026-10-12 21:15)

Task003B uses new `feat/003b-default-camera-midpoint`, starting exactly from
`cf408cdd252ae3f277e5d7b6cba48f7b31e7a899` of `trae/agent-c3dfMx`.
The owner explicitly requested a separate branch for the default camera-midpoint
coordinate feature. A new PR targets `trae/agent-c3dfMx`; original PR #2/#3
remain unchanged. This supersedes the earlier no-new-branch rule for Task003B.
Read `docs/instructions/003B_DEFAULT_CAMERA_MIDPOINT.md`; no merge/retarget,
force-push, rebase or branch deletion is authorized.

### Historical Task003A branch exception (2026-10-12)

Task003A continues on existing `trae/agent-c3dfMx` / PR #3, whose base remains
`feat/002-metric-validation-diagnostics` (PR #2). The owner explicitly chose
this workflow. Older separate-branch proposals are superseded. Do not merge,
retarget, force-push, rebase, delete branches, or create new branch/PR.
At 2026-10-12 19:30 the owner additionally authorized GPT to complete this
implementation after checking the other agent's delivery. That takeover is
within this same branch/PR authorization; no new coding-approval gate applies.

## 2.1 Review feedback channel

Pull-request comments are useful for humans, but implementation environments may not have GitHub API/CLI access to private PR discussions.

Therefore:

- `REVIEW_INBOX.md`, when present and marked OPEN, is the repository-visible authoritative mirror of actionable review feedback.
- Before continuing an existing task/PR, implementation agents must read `REVIEW_INBOX.md` after pulling the task branch.
- Resolve every blocking item there, update its status/notes, and keep using the existing task branch and PR.
- PR comments may duplicate the same feedback, but inability to read PR comments is not a blocker when `REVIEW_INBOX.md` is available.

## 3. Required task startup sequence

Before coding:

1. Read this file.
2. Read `CURRENT_TASK.md`.
3. Read the referenced instruction.
4. Inspect the affected source and tests.
5. Run the existing deterministic test suite if one exists.
6. Only then modify code.

Do not rely on chat context when the repository contains the relevant decision.

## 4. Numerical and geometry safety

This project is a measurement system. Numerical behavior is part of the product contract.

Before changing stereo geometry, calibration, coordinate transforms, quality rejection, or filtering:

- add or update a regression test;
- preserve units explicitly;
- document behavior changes;
- never change coordinate conventions silently;
- never describe host-side webcam grab timing as true sensor exposure synchronization.

Known physical constraints:

- ordinary USB webcams may differ in frame rate, buffering, latency, and exposure timing;
- stereo calibration must use spatially stable calibration targets;
- legacy protocol coordinates are rectified-left-camera coordinates;
- Task003B default live/CSV coordinates use the optical-center midpoint,
  +X forward, +Y right-to-left, +Z upward assuming a level/upright rig. Relative
  stereo geometry alone cannot establish absolute gravity; label this assumption;
- Task003A full engineering/world registration uses an owner-defined origin and X/Y axes, with physically confirmed `+Z` upward; the chosen ground plane is `Z=0` when a ground frame is requested;
- translation-only zero/reference mode preserves current axes and must not claim to establish gravity/world-up.

## 5. Offline-first rule

The application and deterministic tests must not require network access.

- Pose model weights are local files.
- Do not add automatic GitHub/model downloads.
- Missing local assets must fail with a clear message.

## 6. Reference implementation

Files under `reference/` are evidence/baseline material.

- Do not "clean up" or silently edit reference code.
- Formal implementation belongs under the project source tree defined by the current engineering instruction.
- If a reference bug is discovered: document it, reproduce it in a test if possible, then fix only the formal implementation unless instructed otherwise.

## 7. Runtime artifacts

Generated files must stay under project-managed runtime locations.

Do not commit by default:

- model weights;
- captured camera frames;
- generated stereo/world calibration artifacts;
- logs;
- caches;
- temporary sessions.

Cleanup code must never delete outside its explicitly managed runtime roots.

## 8. Data and protocol compatibility

The current `stereo_pose_3d/v1`-style message is a compatibility baseline.

Internal refactors may use typed models, but existing external fields/units must not be silently renamed or reinterpreted. Use adapters when needed.

Keep distinctions between:

- raw measurement;
- accepted/rejected measurement;
- filtered measurement;
- coordinate system;
- units;
- timestamps;
- quality metrics.

## 9. Required completion artifacts

At the end of every task, create or update:

### `CHANGE_SUMMARY.md`
Include:
- Added
- Modified
- Deleted
- Behavior changes
- Numerical behavior changes
- Protocol/config changes
- Known issues

### `TEST_REPORT.md`
Include:
- exact test commands;
- passed/failed/skipped counts;
- environment notes;
- failures or untested hardware paths.

### `REVIEW_FOR_OWNERS.md`
Include only decisions or risks that genuinely require owner/architect review.
Do not fill this with ordinary implementation details.

Also update relevant permanent documentation when behavior changes.

## 10. Review handoff

When implementation is ready:

1. Ensure working tree is clean except intentional untracked runtime files.
2. Run tests.
3. Commit and push the task branch.
4. Update the existing PR and preserve the base declared in `CURRENT_TASK.md`. Open a new PR only when the owner/current task explicitly authorizes one.
5. Put the PR number/URL and head commit SHA into `REVIEW_FOR_OWNERS.md`.
6. Stop. Do not merge unless instructed.

The reviewer should be able to review from Git history/diff without receiving a full ZIP.

## 11. Do not over-engineer

Prefer explicit module boundaries, typed data, tests, and stable interfaces.

Do not create speculative abstractions, final UI frameworks, UE architecture, world-axis conventions, multi-person tracking, or integrations unless the current instruction asks for them.
