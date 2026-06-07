# lidar-arch

One command from a bounding box to archaeology-grade terrain visualizations
(Sky-View Factor, Local Relief Model, Slope) built on free USGS 3DEP LiDAR.

## Setup (Windows)

    pwsh -File scripts/setup_env.ps1     # installs Miniforge + the lidar-arch env
    conda activate lidar-arch
    pip install -e .

## Use

    lidar-arch run --bbox <minlon> <minlat> <maxlon> <maxlat> --out <dir>

Example (Pueblo Grande / S'edav Va'aki, Phoenix AZ):

    lidar-arch run --bbox -111.9856 33.4452 -111.9816 33.4482 --out out/pueblo_grande

Outputs `dtm.tif`, `svf.tif`, `lrm.tif`, `slope.tif` (GeoTIFF, EPSG:26912) plus
8-bit PNG previews. M1 covers the Phoenix `AZ_MaricopaPinal_1_2020` collection.

## Tests

    pytest -m "not slow"     # fast unit tests
    pytest -m slow           # Pueblo Grande end-to-end (network + toolchain)
