# Build the lidar-arch wheel into web/container/wheels/ so the container is
# self-contained (Docker build context = web/container/, which is what
# `wrangler deploy` uses). Re-run whenever the repo-root Python source changes.
#
# Usage (from anywhere):
#   pwsh web/container/build-wheel.ps1
$ErrorActionPreference = "Stop"

# repo root = two levels up from this script (web/container/ -> web/ -> repo)
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$wheelsDir = Join-Path $PSScriptRoot "wheels"
$conda = "C:\Users\codyl\miniforge3\Scripts\conda.exe"

Write-Host "Building lidar-arch wheel -> $wheelsDir"
if (Test-Path $wheelsDir) { Remove-Item "$wheelsDir\*.whl" -Force -ErrorAction SilentlyContinue }

& $conda run -n lidar-arch python -m pip wheel $repoRoot -w $wheelsDir --no-deps
if ($LASTEXITCODE -ne 0) { throw "pip wheel failed (exit $LASTEXITCODE)" }

Write-Host "Done:"
Get-ChildItem "$wheelsDir\*.whl" | ForEach-Object { Write-Host "  $($_.Name)" }
