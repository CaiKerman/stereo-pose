# Task003B — default optical-center midpoint frame

Owner instruction, 2026-10-12 21:15 Asia/Shanghai: create a new branch from the
working `trae/agent-c3dfMx` delivery. Before W world alignment, default origin
is midway between cameras; +Y right camera -> left camera, +X away from cameras,
+Z upward perpendicular to the horizontal plane.

## Authorized workflow

- Branch: `feat/003b-default-camera-midpoint`.
- Locked starting commit: `cf408cdd252ae3f277e5d7b6cba48f7b31e7a899`.
- New PR base: `trae/agent-c3dfMx`. Original PR #2/#3 unchanged and unmerged.
- This latest explicit instruction supersedes earlier no-new-branch restrictions
  for this task only. No merging, force-push, rebase, retarget or branch deletion.

## Default coordinate contract

- Requires valid metric stereo calibration; no W controls or fiducials needed.
  If stereo geometry is absent, metric XYZ cannot be manufactured.
- Centers are optical centers (not casing centers) in the same rectified-left
  frame as triangulation. Solve `P_i[:,:3] @ c_i = -P_i[:,3]` from P1/P2.
  Do not use raw OpenCV T/2 as the origin.
- `o=(c_left+c_right)/2`; `y=normalize(c_left-c_right)`.
- The average of R1/R2-transformed raw camera up `(0,-1,0)`, projected
  perpendicular to y, defines z. `x=y cross z` must face along average optical
  forward. R stacks x/y/z as rows; translation is `-R@o`, in mm.
- The result is a proper no-scale rotation. Reject zero baseline, singular or
  nonfinite matrices, invalid rotations and ambiguous mounting/order.
- **Physical limitation:** relative stereo geometry cannot determine absolute
  gravity. Assume level optical centers and upright, level camera mounting.
  UI and session metadata must say this; `up_confirmed=false`. A common rig
  pitch/roll cannot be auto-corrected. W with real horizontal controls and
  physical-up confirmation remains the way to establish actual world-up.
- Valid saved W/relative alignment has priority over default. Cancelling W
  preserves the current frame; C/R stereo solve derives a fresh default from
  the new stereo artifact, never carries old W forward.
- No new config keys, dependencies or writes to the stereo NPZ. Restart derives
  the same default from the exact selected artifact. Zero-only alignment keeps
  its axes and installation assumption even after saved NPZ restart.
- Live readout and CSV accepted/raw/filtered/candidate W fields share the same
  transform. CSV frame name `camera_midpoint` and frozen session definition
  identify this derived frame. Legacy v1.2 camera fields remain unchanged.
- Defaults remain recording OFF; no quality gate changes or P1/P2 development.

## Acceptance

Synthetic level, toe-in and projection-only legacy rigs must establish midpoint
zero, camera centers at +/-baseline/2 on Y, positive forward X and upward Z,
proper inverse/distance preservation, invalid rig refusal, W precedence,
cancel/restart, zero-axis inheritance and C/R recomputation. Full regression
must pass. Owner checks Windows camera installation, actual movement signs,
CSV and existing W workflow after download. Prior user's successful XYZ test
is evidence for the parent branch only, not physical acceptance of this change.
