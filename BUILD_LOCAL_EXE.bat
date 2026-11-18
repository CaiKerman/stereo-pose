@echo off
setlocal
cd /d "%~dp0"
title Stereo Pose - Build Windows EXE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\build_local.ps1"
set "BUILD_EXIT=%errorlevel%"
echo.
if not "%BUILD_EXIT%"=="0" (
    echo [BUILD FAILED] No new EXE is available. Check the error above.
) else (
    if exist "dist\StereoPose\StereoPose.exe" (
        echo [BUILD COMPLETE] %CD%\dist\StereoPose\StereoPose.exe
        echo Open the entire dist\StereoPose folder. Keep _internal alongside the EXE.
    ) else (
        echo [BUILD INCOMPLETE] No EXE exists under dist\StereoPose.
    )
)
pause
