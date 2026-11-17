# Builds a portable Windows application. Python is needed on the BUILD host only.
# The end user runs StereoPose.exe without Python/pip or license prompts.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repo

# The released model stays outside the executable: editable/replacable,
# no runtime download, and no additional integrity/anti-edit gate.
if (-not (Test-Path ".\yolo11n-pose.pt")) {
    Invoke-WebRequest -Uri "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt" -OutFile ".\yolo11n-pose.pt"
}

# Obfuscate our code, not the local configuration or measurement artifacts.
pyarmor gen -O "build\obfuscated" -r "RUN_ME.py" "src\stereo_pose"

# Standalone Windows PE with bundled Python, torch, OpenCV and Ultralytics.
python -m PyInstaller --noconfirm --clean "packaging\StereoPose.spec"

New-Item -ItemType Directory -Force -Path "dist\StereoPose\configs" | Out-Null
Copy-Item "configs\default.json" "dist\StereoPose\configs\default.json" -Force
Copy-Item "yolo11n-pose.pt" "dist\StereoPose\yolo11n-pose.pt" -Force
Copy-Item "packaging\README_WINDOWS.txt" "dist\StereoPose\README_WINDOWS.txt" -Force
Copy-Item "docs\instructions\006_PROJECTION_MODEL_EXPERIMENT.md" "dist\StereoPose\PR10_标定对照说明.md" -Force
Write-Host "Windows portable package: $repo\dist\StereoPose\StereoPose.exe"
