# Instruction 002B — Stereo diagnostic snapshot and compact developer menu

**Canonical tracking:** [Issue #4](https://github.com/CaiKerman/stereo-pose/issues/4)
**Owner request:** 2026-10-08
**Status:** READY FOR IMPLEMENTATION — GPT review required before hardware retest.
**Immediate working branch:** `trae/agent-c3dfMx` (existing Trae Cloud working branch); existing PR #3 targets `feat/002-metric-validation-diagnostics`. No new branches/PRs.

## 1. Why

Task 002 was run on real hardware after a three-camera laptop was configured:
- Camera picker discovered CAM [0,1,2]; LEFT=2, RIGHT=1; tracking worked.
- The owner repositioned both webcams and physically confirmed new stereo baseline ~552 mm; do **not** treat the prior ~289 mm layout as a mismatch.
- New calibration: `stereo_20261008_162345.npz`, RMS=0.5614 px; 24 checkerboard captures, 19 retained after prune.
- `V` produced 54/54 reconstructed corners at all three distances: depth ~421mm, combined spacing 25.175mm (+0.700%); ~608mm, 24.940mm (-0.242%); ~897mm, 24.459mm (-2.165%). All are single-frame, not statistically sufficient for universal accuracy.
- `D` revealed extreme human-joint epipolar errors, **not merely low YOLO confidence**: 129 diagnostic snapshots, 96 had 0 accepted joints; median right_shoulder ~49.5px, right_elbow ~215.7px, left_shoulder ~12.3px. Current epipolar acceptance limit is 3px.
- Root cause remains unknown. Candidates to investigate: pose-label correspondence, frame mirroring/image-space transforms, asymmetric occlusion/YOLO semantics, capture timing or extrinsic mismatch.

**Do NOT relax thresholds or auto-swap joint identities without evidence.**

## 2. Required work — Part A: on-demand diagnostic snapshot (`S`)

Add **S** hotkey in normal live tracking to save one self-contained, inspectable sample of the **already captured left/right stereo frame pair and the already completed pose inference**. Never open another camera or read a second pair and never rerun YOLO to fulfill the snapshot.

### Files

Produce a uniquely named folder under `runtime/diagnostics/snapshots/<timestamp>_<sequence>/`:
- `left_raw.png` / `right_raw.png`: full-size, unannotated camera frames actually passed to inference. Preserve original orientation and resolution, not YOLO render/plot or UI resize.
- `left_annotated.png` / `right_annotated.png`: visually readable overlays, keypoint names + compact confidence labels for relevant upper-body joints; include both full-frame context and each camera's own labeling, no accidental left/right semantics inversion due to screen mirroring.
- `manifest.json`: documented versioned schema with complete per-camera/raw and rectified coordinates, quality states and capture metadata. A 3D reconstruction (when available) is optional evidence, **not a precondition** to saving 2D diagnostics.
- A self-contained geometrical `calibration_snapshot.npz` (or JSON arrays) with the exact intrinsics, distortion, rectification and projection matrices needed to reproduce rectified keypoints and epipolar errors offline; do not mutate the active NPZ. Store provenance path + SHA-256 when available. Save a clear no-calibration reason when missing.
- `README.txt` optional, if required to explain files.

### Manifest minimum fields
- schema/version, unique snapshot ID, wall timestamp (UTC/offset explicit), tracking frame index, pair source indexes `camera.left/right`, capture backend and requested/actual resolution;
- raw camera frame dimensions, whether full camera frame was mirrored/rotated/cropped/resized upstream, and all mappings needed to recover original `uv`;
- host-grab timing/skew fields if available; label as **host observation, not sensor exposure synchronization**;
- active calibration identity/path/hash and coordinate frame name `rectified_left_camera`, spatial units `mm`;
- per camera: pose/person detection count and chosen person index, per-keypoint anatomical label and index, raw full-frame `(u,v)`, confidence and missing flag;
- per anatomical joint pair: left/right keypoint labels/IDs, undistorted-rectified `uv` on both cameras, **signed** `y_left - y_right` pixel delta and absolute epipolar error, any existing reprojection/quality rejection stage, missing stage if no available points;
- use explicit `null` where observations do not exist; preserve valid zero-valued coordinates.

The saved JSON must be readable without OpenCV in a text editor. Numeric units and coordinate-space mapping must be unambiguous.

### Offline recheck

Provide a simple command or script (e.g. `python tools/inspect_snapshot.py <snapshot_dir>`) to re-evaluate epipolar errors from saved raw keypoints and saved calibration **without a camera, Torch, CUDA, YOLO or model weights**. Only NumPy and OpenCV already used by the project are allowed. Cross-check the reported signed deltas within floating tolerance and print a compact per-joint table. Include at least one synthetic replay fixture/test.

### Failure / safety behavior

- No recording by default and no continuous background save. Images of humans are sensitive: NEVER upload/copy into GitHub, external services, logs or test fixtures.
- Only a physical `S` press saves; output only inside project-managed runtime and **never** overwrites historical snapshots or calibration. Ordinary `G` cleanup must not touch snapshots.
- Simulated disk-full, read-only path, corrupt calibration: report failure cleanly without crashing/restarting the tracker or modifying previous outputs.
- When no calibration or partial body is visible, still save available raw frames and keypoints; explain missing 3D fields.
- Use atomic or failure-safe file creation where feasible. Avoid unmanaged temporary files.

## 3. Required work — Part B: compact Developer/Diagnostics menu (`M`)

Add `M` hotkey to toggle a small built-in panel rendered using the existing OpenCV preview/overlay architecture.

**Collapsed/default view:** focus on left/right camera previews with their indexes, calibration valid/unavailable, accepted/total joints, approximate FPS if available and meaningful live alarms. Avoid permanent long hotkey rows, one-euro internals, calibration test metadata and verbose diagnostics clutter.

**Expanded panel:** show discoverable entries for `S` Snapshot, `D` per-joint reject reasons, `V` checkerboard validation, `C` calibrate, `P` pin calibration, `G` cleanup, `F` smoothing and `M` collapse. Display on-screen only when requested; do not remove hotkeys from actual key handler. Provide a compact collapsed indicator `M: Developer tools`.

The menu is an information/shortcut overlay, **not** a new desktop GUI framework or mouse-driven widget requirement. Implement for both tracking and calibration states if needed to maintain coherent help; ensure calibration-mode hotkeys do not conflict. Keep important warnings visible even when menu is collapsed. Do not disturb three-camera startup picker.

## 4. Deterministic tests (no cameras/GPU/model weights)

1. Snapshot uses exactly the same paired frame objects and pose results as the corresponding tracking iteration (no extra camera reads/YOLO calls).
2. Saved raw frames have correct width/height, orientation and source attribution; annotations do not modify raw buffers in memory.
3. Manifest + NPZ replay produces same rectified `uv` and signed epipolar differences for exact/synthetic camera matrices and an introduced known mismatch.
4. Joint label/index and confidence mapping matches YOLO data; missing/low-confidence joints and no active calibration are correctly represented.
5. Failure-safe writes/path containment, no overwriting, zero network effects, no snapshot deletion through `G` cleanup.
6. `M` toggles panel visibility, simplified overlay retains warnings, hotkeys remain callable even when collapsed, quality/temporal/3D numerical outputs unchanged.
7. Existing Task001/002/002A offline suite continues passing with `stereo_pose_3d/v1.2` wire schema intact.

Report exact commands, counts, OS, and tests skipped; no claiming real-hardware verification from fake test inputs.

## 5. Constraints / exclusions

- **Do not** change camera order, calibration maths, reference coordinate frame, image geometry, joint thresholds, speed gate, YOLO confidence gate, smoothing behavior or output protocol to make acceptance numbers look better.
- **Do not** implement Task 002C joint repair, Task 003 world frame, multi-person matching, new GUI framework, hardware sync, background recording or auto-upload.
- No new required pip packages, no system modification; `RUN_ME.bat` still unzip-and-run.
- All on-demand snapshots and reports stay inside runtime; never commit physical-user data to repo.

## 6. Deliverables and handoff

- New snapshot module, simple offline inspector/replay path, `S` live integration, tests, `M` menu implementation.
- User-facing Chinese instructions in `README_先看我.txt`; update `README.md`, `CHANGE_SUMMARY.md`, `TEST_REPORT.md`, `REVIEW_FOR_OWNERS.md`, `REVIEW_INBOX.md` with Task002B status.
- Code should be tightly scoped, independently reviewable; keep existing Task002A selection functionality intact.
- Trae must push to the **already existing** `trae/agent-c3dfMx` and **existing PR #3**, no other branch or PR. Do not merge/delete/rebase/force-push/change base. If the cloud agent cannot honor this, pause and ask owner before changing topology.
- Stop after push and notify owner: “Task 002B ready for GPT review”; link PR #3, test results and example simulated manifest.
- **Reviewer gate:** GPT code review, then owner uses `S` for 1–3 on-demand **static** upper-body frames (strong epipolar failures), then Task002C chooses a fix based on these snapshots.
- The current real hardware user has *not* confirmed the camera picker's cancel/rescan UX; retain this as an outstanding manual check. Task 002/PR #2 and Task 002A/PR #3 remain unmerged pending owner/reviewer acceptance.

## 7. Agent startup sequence

1. Pull latest `trae/agent-c3dfMx` (existing PR #3).
2. Read `AGENTS.md`, `CURRENT_TASK.md`, `REVIEW_INBOX.md`, **this document**, [Issue #4](https://github.com/CaiKerman/stereo-pose/issues/4), Task 002 and 002A instructions.
3. Implement Part A fully before Part B; review your own tests, docs and branch diff.
4. Push to same PR #3 and stop for review.
