# Task005 — responsive operator interface

Owner 2026-10-14 09:39 Asia/Shanghai requests a NEW branch focused on interaction
and display, including window resizing and different screen resolutions, with
the verified lower-level implementation preserved.

- Branch `feat/005-responsive-desktop-ui` starts exactly at Task004 delivery
  `b093e2d327b358c4571f5358d7e797930399774d`.
- New PR targets `fix/004-calibration-auto-capture`; all older PRs remain open,
  unchanged and unmerged. No main edits, merge, retarget, rebase or force push.
- This explicit UI assignment supersedes historical exclusions of GUI work.
- Presentation only: native resizable desktop shell, Chinese contextual buttons,
  aspect-preserving display images, scrollable XYZ/diagnostics, readable status,
  world reference form and step guidance. No camera capture resolution changes.
- Buttons dispatch existing hotkeys/actions. Preserve original keyboard controls,
  AUTO/SPACE/R behavior, exact measurement/quality/filter/protocol semantics,
  world fitting/zero/save activation, NPZ and CSV lifecycle/privacy.
- Keep all math/detection/capture-policy/persistence/recording modules unchanged.
  World setup may change its presentation/input adapter only, retaining the
  original fitting, validation and save/activation block.
- Desktop toolkit uses Python's optional standard Tk interface; unavailable
  desktop falls back to a resizable OpenCV view. No pip install/download at run.
- Deterministic layout/action/lifecycle regression without cameras/GPU/network;
  full existing suite and synthetic native GUI smoke where environment permits.
- Document exact test counts, protected-file identity and unverified Windows
  hardware/DPI paths. Do not claim physical accuracy or hardware acceptance.
