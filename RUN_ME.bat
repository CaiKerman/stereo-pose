@echo off
setlocal
cd /d "%~dp0"
title Stereo Pose - RUN ME

echo ================================================================
echo Stereo Pose Task002 - metric validation + joint diagnostics
echo This test does NOT pip-install the project.
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
