# Task 001 hardware acceptance — 2026-09-30

## Environment

- Windows 10
- Python 3.12.1
- OpenCV 5.0.0
- NumPy 2.2.1
- PyTorch 2.9.0+cu128
- CUDA available, 1 device
- YOLO pose model loaded locally

## Live stereo calibration result

- sample count: 17
- readiness: 74/100
- Stereo RMS: 0.5074 px
- sample epipolar mean: 0.735 px
- sample epipolar max: 1.190 px
- translation vector T: [266.63, -65.858, 90.818] mm
- implied stereo baseline norm: approximately 289.3 mm

The owner physically measured the camera-center spacing and reported millimeter-level agreement with the reconstructed baseline. This is strong evidence that the metric scale from the 25 mm checkerboard calibration is correct.

## Runtime acceptance

Verified on real hardware:

- dual-camera capture
- CUDA pose inference
- manual checkerboard sample capture
- stereo solve
- calibration NPZ persistence
- immediate activation of new calibration
- 3D joint output
- saved/pinned calibration
- process restart and automatic calibration reload

## Remaining observation

With only the upper body in view, some shoulder observations intermittently disappear from the accepted 3D output even though the shoulder is expected to remain visible. This should be investigated with explicit per-joint rejection diagnostics before changing thresholds.

## Disposition

Task 001 engineering foundation is accepted on real hardware.

Next task should focus on:
1. transparent per-joint rejection diagnostics;
2. checkerboard-based metric 3D validation using the known 25 mm grid;
3. validation reports suitable for later world-coordinate work.
