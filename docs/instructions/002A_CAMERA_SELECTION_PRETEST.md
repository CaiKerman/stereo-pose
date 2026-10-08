# Instruction 002A — Pre-test camera discovery and left/right selection

**Priority: BLOCKING BEFORE TASK 002 REAL-HARDWARE TEST.**

Owner request (2026-10-08): the test laptop has one integrated camera plus two externally connected USB webcams (three cameras total). The operator must be able to identify and select the physical LEFT and RIGHT USB webcams **without editing config.json or knowing Git/Python/CLI**, before the Task 002 D/V hardware test.

This is a pre-test UX subtask of the **existing Task 002 and PR #2**. Work on `feat/002-metric-validation-diagnostics`; **do not open a new PR or merge PR #2**.

## Functional requirements

### A. Beginner-friendly startup flow

Launching `RUN_ME.bat` must present a camera selection phase **before the main live tracking loop opens its two cameras**.

Expected operator experience (example only):

```text
Detected camera inputs:
CAM 0 — built-in laptop camera  [preview image]
CAM 1 — USB webcam A           [preview image]
CAM 2 — USB webcam B           [preview image]

LEFT camera  = 1
RIGHT camera = 2

[Confirm / Start stereo] [Rescan] [Cancel]
```

The crucial requirement is **visual identification**, not camera names: device names can be optional / unavailable on Windows, but each usable candidate must be associated with a visible image labeled by its current OpenCV index. Implement a lightweight OpenCV-based selector/preview (or equivalent dependency-free in-project UI) suited to the current WIN10/Win11 Python + OpenCV environment. A text-only menu containing indexes **without visual previews does not meet acceptance**.

Allow re-scan after plugging/unplugging devices. Do not silently assume indexes 0/1 or silently pick the first two when 3 are present.

### B. Safe discovery and selection

- Probe a bounded, configurable index range (reasonable initial default e.g. 0..7) using the selected camera backend; support sparse indexes (e.g. 0, 2, 5).
- Mark only cameras that can actually open **and deliver at least one frame** as usable. A device name alone is insufficient.
- Display a labeled still/preview so the operator knows which physical webcam is CAM 1 vs CAM 2. Prefer no preview files persisted to disk.
- Allow selection of exactly **two distinct, usable** cameras and explicit assignment to LEFT and RIGHT.
- Handle camera permission denial, read timeout/failure, unplugged devices, and fewer than two usable cameras with an actionable error and the ability to retry/exit.
- All temporary `cv2.VideoCapture` handles/windows **must be released**, including on error/cancel, before the normal stereo `open_camera` calls.
- Avoid long startup hangs when probing missing camera indexes; document fallback/workaround for drivers that hang.
- Keep webcam backend/FourCC/FPS/resolution configuration coherent with the existing capture code; no global OS camera setting or driver changes.

### C. Config and automation compatibility

- After confirmation, save the chosen `camera.left` and `camera.right` to the local `config.json` **safely**, keeping unrelated settings unchanged. Use an atomic replace or equivalent error-safe persistence (with sensible handling of write failure) so the choice survives restart.
- If the selection is canceled, do not change the previous config.
- Support pre-existing `config.json` and first-run default generation from `RUN_ME.py`.
- The same selection functionality should be reachable from the normal project CLI as appropriate, not only a stand-alone script. Keep current `--left-cam` / `--right-cam` overrides and other noninteractive/test workflows functional. Define and document precedence between explicit CLI arguments, interactive choice, and config defaults. In automated/noninteractive runs do not unexpectedly open a blocking selection interface.
- No `pip install` during `RUN_ME`; no new required third-party packages; logs/runtime files remain inside the extracted test folder.
- Keep existing Task 002 D/V hotkeys, tracking, and calibration workflow unchanged.

### D. Calibration identity / safety

A saved stereo NPZ is valid for a particular **physical** left/right camera pairing and rig geometry, not merely two currently available numeric indexes.

- Changing computers can cause camera enumeration to shift (e.g. old USB webcams 0/1 become 1/2 because built-in cam is 0).
- If the same two *physical* USB cameras and their mount geometry/order are unchanged, the old calibration may still be useful after mapping the new indexes. Do not automatically invalidate solely due to an index change.
- But **do not silently claim** the old NPZ is compatible just because resolution and board size match. Before tracking, show a prominent and intelligible warning when current left/right indexes differ from the NPZ recorded indexes, or when the physical pairing cannot be established, and instruct the operator to confirm the physical LEFT/RIGHT assignment and recalibrate if devices or geometry changed.
- Keep `saved/` calibrations, active calibration selection, and validation reports safe. Do not delete or rewrite older NPZ as a side effect of re-selecting cameras.
- At startup clearly print the selected camera indexes and the active calibration path.

### E. Tests (camera hardware not required for deterministic suite)

Use fake/injected camera open/read/close functions or mock `cv2.VideoCapture` to test:

1. 3 detected inputs (built-in + USB + USB): user selects LEFT=1, RIGHT=2; confirmed order is passed into the real startup pipeline.
2. Sparse indexes, a device that opens but cannot deliver frames, and less than two cameras.
3. Same camera chosen for both roles is rejected.
4. Preview/cancel/re-scan and error paths always release camera resources.
5. Config persistence retains other user fields; cancellation makes no write; malformed or failed write does not corrupt previous config.
6. CLI override / noninteractive entry still works and does not block on GUI.
7. Existing NPZ warning on camera index mismatch is shown without discarding calibration.
8. Existing Task 002 deterministic suite continues to pass.

Include a manual acceptance checklist for a 3-camera laptop. Trae cannot claim actual 3-camera hardware pass unless physically exercised; leave that step for the owner.

## Deliverables

- Camera discovery/preview/selection implementation, integrated with `RUN_ME.bat` and normal entrypoint.
- Config persistence and calibration-index change warning.
- Unit/integration tests.
- `README_先看我.txt` update explaining how to visually pick LEFT/RIGHT without editing config.
- Updated `CHANGE_SUMMARY.md`, `TEST_REPORT.md`, `REVIEW_FOR_OWNERS.md`.
- Mark the new OPEN item in `REVIEW_INBOX.md` resolved only once implemented and tested.
- Push commits to **existing PR #2** and stop for reviewer re-review. Do not merge.

## Scope exclusions

Do not introduce a full production desktop UI, Windows driver installation, auto camera download, new pose model, hardware frame synchronization, world coordinates, auto-deleting calibrations, or changes to stereo numerical filters/thresholds.

**Usability acceptance:** the owner can unzip the RC, double-click `RUN_ME.bat`, visually identify all three camera feeds, choose the two USB webcams as LEFT/RIGHT, confirm, and immediately run D/V tests with no `pip install` and no manual editing of `config.json`.
