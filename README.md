# lidar-arch

One command from a bounding box to archaeology-grade terrain visualizations
(Sky-View Factor, Local Relief Model, Slope, Openness, Red Relief Image Map)
built on free USGS 3DEP LiDAR.

## Setup (Windows)

    pwsh -File scripts/setup_env.ps1     # installs Miniforge + the lidar-arch env
                                         # and does the editable `pip install -e .`

Miniforge installs to `%USERPROFILE%\miniforge3` without changing PATH. To put the
`conda` / `lidar-arch` commands on your PATH, enable conda once and restart the shell:

    & "$env:USERPROFILE\miniforge3\Scripts\conda.exe" init powershell
    # restart the shell, then:
    conda activate lidar-arch

Prefer not to touch your shell profile? Run everything through conda instead:

    & "$env:USERPROFILE\miniforge3\Scripts\conda.exe" run -n lidar-arch lidar-arch run ...

## Use

    lidar-arch run --bbox <minlon> <minlat> <maxlon> <maxlat> --out <dir>

Example (Pueblo Grande / S'edav Va'aki, Phoenix AZ):

    lidar-arch run --bbox -111.9856 33.4452 -111.9816 33.4482 --out out/pueblo_grande

Outputs `dtm.tif`, `svf.tif`, `lrm.tif`, `slope.tif`, `opns.tif` (single-band
GeoTIFF) and `rrim.tif` (3-band RGB GeoTIFF), all EPSG:26912, each with a
colormapped 8-bit PNG preview. M1 covers the Phoenix `AZ_MaricopaPinal_1_2020`
collection.

What the products show:

- **svf** Sky-View Factor: how much sky each cell sees; shades enclosed
  features (ditches, depressions).
- **lrm** Local Relief Model: DTM minus its low-pass trend; mounds red,
  hollows blue (RdBu_r centred at zero).
- **slope** steepness in degrees.
- **openness** positive topographic openness: convex terrain (mounds, ridges)
  reads high, concave (pits, ditches) low; a flat-illumination complement to
  SVF for spotting earthworks.
- **rrim** Red Relief Image Map: slope (redness) blended with positive-minus-
  negative openness (brightness) into one shaded relief that reveals both
  convex and concave micro-relief without a fixed light direction.

Pick a subset with `--products` (comma-separated; default
`svf,lrm,slope,openness,rrim`):

    lidar-arch run --bbox ... --out ... --products lrm,rrim

## Tests

    pytest -m "not slow"     # fast unit tests
    pytest -m slow           # Pueblo Grande end-to-end (network + toolchain)
