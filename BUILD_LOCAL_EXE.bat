@echo off
setlocal
cd /d "%~dp0"
title Stereo Pose - Build Windows EXE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\build_local.ps1"
echo.
echo The build output is in dist\StereoPose\StereoPose.exe if compilation succeeded.
pause
