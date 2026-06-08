# Building the lidar-arch wheel for the container

The container installs `lidar-arch` from a **pre-built wheel** in `wheels/` instead
of copying the repo-root source. This keeps the Docker build context limited to
`web/container/`, which is what `wrangler deploy` uses when it builds the image.

`wheels/` is gitignored — regenerate the wheel before building/deploying whenever
the Python source under the repo root (`src/lidar_arch/`, `pyproject.toml`) changes.

## Regenerate

PowerShell helper (recommended):

    pwsh web/container/build-wheel.ps1

Or directly:

    & "C:\Users\codyl\miniforge3\Scripts\conda.exe" run -n lidar-arch `
        python -m pip wheel . -w web/container/wheels --no-deps

`--no-deps` is intentional: numpy / scipy / rasterio / pyproj / click come from the
conda-forge env inside the image (see `env.yml`), not from PyPI.

## Build the image (context = web/container/)

    docker build -t lidar-arch:dev web/container      # from repo root
    # or, equivalently, `wrangler deploy` builds it via wrangler.jsonc `containers[].image`
