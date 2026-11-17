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
# Preserve backups across failed builds. A previous packaging attempt may
# have removed dist/StereoPose, leaving the sole copy in this backup folder.
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($name in @("config.json", "runtime")) {
    $original = Join-Path $old $name
    if (Test-Path $original) {
        $destination = Join-Path $backup $name
        if (Test-Path $destination) { Remove-Item $destination -Recurse -Force }
        Copy-Item $original $destination -Recurse -Force
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
$pack_mode = "PyArmor-obfuscated"
pyarmor gen --pack "packaging\StereoPose.spec" -r (Join-Path $stage "RUN_ME.py") (Join-Path $stage "stereo_pose")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "PyArmor could not complete (trial licenses can report 'out of license')."
    Write-Warning "Continuing with PyInstaller-only EXE. The application will run without Python; code protection is weaker."
    $pack_mode = "PyInstaller-bytecode"
    python -m PyInstaller --noconfirm --clean "packaging\StereoPose.spec"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller failed to build. No new EXE has been produced."
        exit 1
    }
}
if (-not (Test-Path "dist\StereoPose\StereoPose.exe")) {
    Write-Error "The packer did not produce dist\StereoPose\StereoPose.exe."
    exit 1
}

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
Write-Host "Packaging mode: $pack_mode"
Set-Content "dist\StereoPose\PACKAGING_MODE.txt" -Value $pack_mode -Encoding utf8
