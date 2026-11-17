# Windows build of the PR10 portable app. Only the BUILD host needs Python.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repo

# Copy the first-party source into a single flat import root. Both the entry
# and stereo_pose must share their parent folder for PyArmor --pack to replace
# the same modules that PyInstaller analyzed from original source.
$stage = "build\package_source"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item "RUN_ME.py" (Join-Path $stage "RUN_ME.py")
Copy-Item "src\stereo_pose" (Join-Path $stage "stereo_pose") -Recurse

# Preserve editable user files before replacing a previously built onedir.
$old = "dist\StereoPose"
$backup = "build\portable_user_data"
if (Test-Path $backup) { Remove-Item $backup -Recurse -Force }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($name in @("config.json", "runtime")) {
    $original = Join-Path $old $name
    if (Test-Path $original) {
        Copy-Item $original (Join-Path $backup $name) -Recurse -Force
    }
}
if (Test-Path $old) {
    Get-ChildItem $old -Filter "*.pt" -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $backup $_.Name) -Force
    }
    Remove-Item $old -Recurse -Force
}

# Build-time model download only; no network or license key at app startup.
if (-not (Test-Path ".\yolo11n-pose.pt")) {
    Invoke-WebRequest -Uri "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt" -OutFile ".\yolo11n-pose.pt"
}

# IMPORTANT: --pack reads the UNOBFUSCATED source graph and patches the
# .spec to replace its modules with PyArmor output. Do not run PyInstaller
# directly against protected RUN_ME.py: hidden imports will be incomplete.
pyarmor gen --pack "packaging\StereoPose.spec" -r (Join-Path $stage "RUN_ME.py") (Join-Path $stage "stereo_pose")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

New-Item -ItemType Directory -Force -Path "dist\StereoPose\configs" | Out-Null
Copy-Item "configs\default.json" "dist\StereoPose\configs\default.json" -Force
Copy-Item "yolo11n-pose.pt" "dist\StereoPose\yolo11n-pose.pt" -Force
Copy-Item "packaging\README_WINDOWS.txt" "dist\StereoPose\README_WINDOWS.txt" -Force
Copy-Item "docs\instructions\006_PROJECTION_MODEL_EXPERIMENT.md" "dist\StereoPose\PR10_标定对照说明.md" -Force

# Restore user's editable content without checking hashes or refusing edits.
Get-ChildItem $backup -Force | ForEach-Object {
    Copy-Item $_.FullName "dist\StereoPose\" -Recurse -Force
}
Write-Host "Windows portable package: $repo\dist\StereoPose\StereoPose.exe"
