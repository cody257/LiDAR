<#
  setup_env.ps1 — Stand up the LiDAR archaeology toolchain on native Windows.

  1. Installs Miniforge (conda-forge) to %USERPROFILE%\miniforge3 if absent.
  2. Creates the `lidar-arch` conda env (PDAL, GDAL, rasterio, pyproj, ...).
  3. Installs rvt-py via pip --no-deps (conda already provides GDAL/numpy/scipy).
  4. Verifies the toolchain.

  Logs to out\install.log. Safe to re-run (idempotent-ish).
#>
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # makes Invoke-WebRequest far faster

$root   = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $root 'out'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'install.log'

function Log($m) {
    $line = "{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $log -Value $line
    Write-Host $line
}

try {
    $prefix  = Join-Path $env:USERPROFILE 'miniforge3'
    $conda   = Join-Path $prefix 'Scripts\conda.exe'
    $envRoot = Join-Path $prefix 'envs\lidar-arch'
    $envPy   = Join-Path $envRoot 'python.exe'

    # --- 1. Miniforge ---------------------------------------------------------
    if (Test-Path $conda) {
        Log "Miniforge already present at $prefix"
    } else {
        $installer = Join-Path $env:TEMP 'Miniforge3-Windows-x86_64.exe'
        $url = 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe'
        Log "Downloading Miniforge..."
        Invoke-WebRequest -Uri $url -OutFile $installer
        Log "Installing Miniforge silently to $prefix ..."
        Start-Process -FilePath $installer -ArgumentList '/InstallationType=JustMe','/RegisterPython=0','/S',"/D=$prefix" -Wait
        if (-not (Test-Path $conda)) { throw "conda.exe not found after install: $conda" }
        Log "Miniforge installed."
    }

    # --- 2. conda env (the slow part) -----------------------------------------
    if (Test-Path $envPy) {
        Log "Env 'lidar-arch' already exists; skipping create."
    } else {
        Log "Creating conda env 'lidar-arch' (downloads PDAL/GDAL stack, slow)..."
        & $conda create -y -n lidar-arch -c conda-forge `
            python=3.11 pdal python-pdal gdal rasterio pyproj numpy scipy click pytest 2>&1 |
            Tee-Object -FilePath $log -Append
        if ($LASTEXITCODE -ne 0) { throw "conda create failed (exit $LASTEXITCODE)" }
        Log "conda env created."
    }

    # --- 3. rvt-py (pip, no deps so it won't try to build GDAL) ---------------
    Log "Installing rvt-py (pip --no-deps)..."
    & $envPy -m pip install --no-deps rvt-py 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Log "WARN: rvt-py install failed (exit $LASTEXITCODE) — resolve during build." }

    # --- 3b. editable install of this package (so `lidar-arch` is runnable) ----
    Log "Editable install of lidar-arch..."
    & $envPy -m pip install -e $root 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Log "WARN: editable install failed (exit $LASTEXITCODE)" }

    # --- 4. verify ------------------------------------------------------------
    Log "Verifying..."
    & $envPy -c "import pdal,rasterio,pyproj,numpy,scipy,click; print('python deps OK')" 2>&1 | Tee-Object -FilePath $log -Append
    & $envPy -c "import rvt.vis; print('rvt OK')" 2>&1 | Tee-Object -FilePath $log -Append
    $pdalExe = Join-Path $envRoot 'Library\bin\pdal.exe'
    if (Test-Path $pdalExe) { & $pdalExe --version 2>&1 | Tee-Object -FilePath $log -Append }

    Log "SETUP DONE"
}
catch {
    Log ("SETUP FAILED: " + $_.Exception.Message)
    throw
}
