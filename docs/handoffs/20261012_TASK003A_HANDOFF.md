# Stereo Pose 项目移交摘要 — 2026-10-12

> **给下一个 GPT 会话和其他编码智能体。** 本文件只含项目状态、设计决策、审查约束；**不含用户人脸、真实摄像头图像、眼部原始观察或任何私密校准 NPZ**。
> Authoritative task: [Issue #5](https://github.com/CaiKerman/stereo-pose/issues/5) + [003A instruction](../instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md). Existing `AGENTS.md` governs agent behavior unless owner later explicitly adjusts it.

## A. 项目与当前代码

Repo: **private** [CaiKerman/stereo-pose](https://github.com/CaiKerman/stereo-pose). Windows unzip-and-run via `RUN_ME.bat`, local model `yolo11n-pose.pt`, Python/OpenCV/Ultralytics. Two USB webcams + stereo checkerboard calibration -> YOLO 17 keypoints -> `StereoTriangulator` -> quality filtering -> OneEuro smoothing -> console/JSONL/UDP. XYZ presently **rectified-left-camera mm**, not engineering/world coordinates.

Existing modules:
- `src/stereo_pose/capture/*`: camera open/pair grabs and visual picker.
- `src/stereo_pose/calibration/collection.py`: OpenCV mono/stereo solve and versioned stereo NPZ; `calibration/selection.py`: newest auto/legacy selection; `calibration/metadata.py`: checks.
- `src/stereo_pose/pose/estimator.py`: one YOLO inference on a pair per frame.
- `src/stereo_pose/geometry/triangulation.py`: rectified C XYZ, epi/reproj.
- `src/stereo_pose/quality/scoring.py`: legacy 3px epi, 2.5px reproj and more quality gates.
- `src/stereo_pose/joints.py`: all 17 including `left_eye/right_eye`, default `ergonomics` **excludes** eyes.
- `src/stereo_pose/app/runner.py`: live tracking, `C/R/P/F/G/D/V/S/M`.
- `src/stereo_pose/diagnostics/snapshot.py`: privacy-sensitive manual `S` paired frames, keypoints, geometry NPZ and JSON; `tools/inspect_snapshot.py`: offline replay.
- `src/stereo_pose/outputs/v1_message.py`: legacy `stereo_pose_3d/v1.2` message (C coordinates). `outputs/publishers.py`: Console/JSONL/UDP. No 5Hz CSV recorder yet.
- `configs/default.json` + `config.py` validation.

## B. Git dependencies — critical

| Item | Source | Status |
|---|---|---|
| main | `d26e64772b8c634851b5812b6015a7ab57124e83` | Task001 stable baseline, lacks Task002/002A/002B |
| PR #2 | `feat/002-metric-validation-diagnostics` -> main, `ed0421ae...` | Open, **not merged** |
| PR #3 | `trae/agent-c3dfMx` -> PR #2 branch, Task002A camera picker + Task002B S/M | Open, **not merged** |
| Task003A | [Issue #5](https://github.com/CaiKerman/stereo-pose/issues/5), [detailed spec](../instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md) | **Defined only; no feature code / coding PR begun** |

Task002B last reviewed code commit `288860d`; reviewer documentation `3a1e97c` passed code review for hardware acceptance, **not merge approval**; report said 214/214 tests (Trae Linux headless run, not independent GitHub CI). Documentation subsequently added on same existing PR #3 branch; check current tip before coding.

**No new coding branch/PR/merge authorized by publication.** New agent should propose a separate stacked branch based on current verified PR #3 head and obtain owner approval before making it. Do NOT base on main, merge PR2/3, force-push, rebase history, delete branches, or put Task003A implementation into PR3 without permission. `AGENTS.md` generally says PR -> main, but prerequisites are missing on main, so verify explicit branch/PR plan with owner.

## C. Hardware/sample evidence and what it does NOT prove

- Two external USB webcams (laptop also has its own), camera indices may change across runs. Latest user snapshot reported LEFT=1 RIGHT=2, resolution 1280x720, baseline ~555.46mm. Earlier confirmed physical arrangement ~552mm. Never treat old ~289mm config as a fault.
- User has already used checkerboard calibration, D diagnosis, V 25mm grid validation, S snapshot/replay.
- Past snapshots: shoulder/elbow/eye often high-confidence yet fail epipolar gate. Later snapshots with fixed checkerboard show the board has much lower epi residual than eyes; these are **diagnostic observations**, not independent eye XYZ truth. Some prior analysis computed eye-point relative movement and registration differences, but the eye XYZ **absolute error cannot be established from photos alone**. Do not claim measured P95 ±5mm.
- Engineering goals: left/right eye absolute 3D position **P95 ≤5mm** (stretch ≤3mm); shoulder/elbow **P95 ≤10mm**, conditional evaluation up to 15mm. Goals **not yet verified**; owner chose not to block P0 app features on accuracy closure.
- Webcam sensor exposures not hardware synchronized; host grab skew is not exposure skew.
- User deliberately changed pose between snapshot presses; they attempted to be still at actual S instant. Do not treat different-pose images as identical static replicates.
- **Privacy:** snapshots may show face. Do not add to repo, PR descriptions, CI test fixtures, telemetry or public links; use synthetic pictures/points only. The handoff must not include/re-emit user face images or identifiable keypoint traces.

## D. Owner's decisions in the most recent conversation

1. **Prioritize a complete practical application over unresolved precision tuning.** Task002C metric root-cause still open but **deferred**.
2. World-coordinate system is **P0**, not later enhancement. Use printed fiducials / known real XYZ to automatically align camera C -> engineering W; enter 3+ true 3D coordinates (recommend >=4-6) and solve rigid R/t, no scale correction. World XY/origin are user-selected; confirm true upward +Z if earth/ground frame intended.
3. Calibration + world registration **together in one versioned NPZ**, same load/save/pin/selection system, survives restart and does not silently load unrelated latest auto. Old NPZ supported and source files immutable; new camera geometry/recalibration invalidates W.
4. Live eye (`left_eye/right_eye`) XYZ, derived eye midpoint and configurable body joints, show coordinate frame and invalid/rejected candidate status. Candidate cannot be labeled accurate/accepted. Legacy v1.2 output remains C XYZ.
5. **Recording optional by explicit T toggle**, not active on startup. CSV defaults to 5 samples/sec (not a reduction of inference FPS). Long format one row/joint/sample incl true timestamps, C and W XYZ, quality/rejection, session metadata and calibration fingerprint. No automatic image/video recording or external sync.
6. **P1/P2 postponed:** video, bookmarks, historical records browser, plots/playback, extended GUI, extra AI eye models, auto-marker tracking etc. Keep existing S/M/D/V hotkeys and calibration workflows.

## E. Already printed target resources

Personal project file `StereoPose_Markers_A4_ALL_14pages.pdf` exists in the user's earlier Project context; a new agent may need owner to provide it again, rather than invent tag mapping.

Known designs: ArUco DICT_4X4_50 loose ID0-7 black edge 60mm; WORLD TRIAD 3 marked centers P0=(0,0), P1=(100,0), P2=(0,100)mm (not necessarily marker ID 0/1/2); ChArUco 5x7 with 28/20mm square/marker; ChArUco 7x10 with 20/14mm; backup DICT_5X5_50 IDs0–5 black edge50mm; crosshair 50mm P0..P11 grid. Printed actual size should be physically checked; point definition marker center vs corner matters.

## F. Dev order and reviewer acceptance

1. **003A-1:** Implement pure `R/t` SE(3) fit, point ID association, fiducial adapter, geometric residual tests; integrate immutable combined calibration NPZ and explicit restart selection.
2. **003A-2:** Implement user W wizard or reference_points.csv import with ID preview and real XYZ entry, confirm/cancel, eye/joint XYZ panel, distinguish W from camera and candidate from accepted.
3. **003A-3:** Add manual T CSV recorder, `recording.sample_rate_hz=5`, robust long format, session metadata, timestamp, start/stop/restart/error handling, Windows usability, full tests.

**Reviewer blockers:**
- rigid transform `det(R)=+1`, `R.T R=I`, preserves distances and units, rejects collinear/mismatched ID, demonstrates residual and user-confirmed +Z convention;
- old stereo-only NPZ backward-compatible; exact K/D shapes preserved and new W keys roundtrip `allow_pickle=False`; saved W alignment never quietly displaced by newest auto or transposed into old C message; stale W clearly refused after calibration change;
- eyes included; midpoint only if both valid; existing 3px epi gate unchanged; raw/rejected candidate separate; no missing-as-zero nor stale-as-new;
- T **OFF** by default, true 5Hz clock behavior (not modulo frame), no repeated old frames when inference is slow, robust rows and no erased historical CSV, no video;
- S/M/D/V and existing tests/protocol preserved; real tests vs mocked tests clearly separated; no real face uploads, no unauthorized external access;
- on completion exact tests/OS info, code diff and changed config/schema docs, [REVIEW_INBOX](../../REVIEW_INBOX.md), `CHANGE_SUMMARY.md`, `TEST_REPORT.md`, `REVIEW_FOR_OWNERS.md` updated. Review before merge; physical marker and CSV owner acceptance after code review.

## G. Suggested new-conversation starter

> 继续 private GitHub 项目 `CaiKerman/stereo-pose`。下一任务是 [Issue #5](https://github.com/CaiKerman/stereo-pose/issues/5) / `docs/instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md`，详细背景见 `docs/handoffs/20261012_TASK003A_HANDOFF.md`。请先核对分支与未合并 PR #2/#3、阅读 AGENTS/CURRENT_TASK/REVIEW_INBOX，不要直接从 main 开发。我们优先实现 P0 世界坐标标定（已知图码XYZ→无缩放刚体变换、和双目标定同 NPZ）、眼点实时XYZ和手动 5Hz CSV 记录；精度未闭环暂缓，P1/P2 不做。我会让其他智能体编码，你负责审核；在分支计划得到确认前不要新建/合并 PR，不要上传任何人脸/快照。
