@echo off
setlocal
cd /d "%~dp0"
title Stereo Pose - RUN ME

echo ================================================================
echo Stereo Pose Task003B - camera midpoint XYZ and manual 5 Hz CSV
echo This test does NOT pip-install the project.
echo.
echo A camera selection window opens FIRST: pick your two USB
echo webcams as LEFT / RIGHT by pressing their CAM numbers,
echo then press ENTER to confirm.
echo ================================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found in PATH.
  echo.
  echo Please run this from the same Python environment that previously
  echo ran your stereo-pose PoC.
  echo.
  pause
  exit /b 1
)

python "%~dp0RUN_ME.py"

echo.
pause
