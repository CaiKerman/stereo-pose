# Windows developer-side one-click build. End users do NOT need Python.
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repo
$venv = Join-Path $repo ".build-venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv $venv
    } else {
        & python -m venv $venv
    }
}
$env:PATH = "$(Join-Path $venv 'Scripts');$env:PATH"
& $python -m pip install --upgrade pip
& $python -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128
& $python -m pip install -e ".[live]" pyinstaller==6.16.0 pyarmor==9.3.0
& $python -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python-headless
& $python -m pip install --no-deps --force-reinstall opencv-contrib-python==4.11.0.86
& (Join-Path $PSScriptRoot "build_windows.ps1")
