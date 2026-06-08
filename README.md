# lidar-arch

**Archaeology-grade terrain visualizations from free USGS 3DEP LiDAR — from a bounding box to buried earthworks in one step.**

🛰️ **Live demo: https://lidar-arch.codylecates.workers.dev** — draw a box on the map, see which LiDAR collection covers it, and run it to reveal mounds, canals, and other low-relief features that ordinary maps wash out.

Standard hillshade hides subtle anthropogenic terrain. `lidar-arch` produces the derivatives that actually surface it — Sky-View Factor, Local Relief Model, Slope, positive Openness, and a Red Relief Image Map — straight from the public 3DEP point cloud, no GIS workstation required. First validation target: the Hohokam canals and platform mounds of the Salt River Valley, Phoenix AZ (the Pueblo Grande / S'edav Va'aki mound is the regression anchor).

## Two ways to use it

### 1. Web app (easiest)
Open the **[live demo](https://lidar-arch.codylecates.workers.dev)**, draw or type a bounding box over an area with 3DEP coverage, choose detail vs. speed, and **Run**. The result overlays on the map; toggle between LRM / RRIM / SVF / Slope / Openness. See [`web/README.md`](web/README.md) to run it locally or deploy your own (Cloudflare Worker + Container + R2).

### 2. CLI
```
lidar-arch run --bbox <minlon> <minlat> <maxlon> <maxlat> --out <dir> \
  [--resource <ept-url|auto>] [--resolution auto|<m>] [--products lrm,rrim,...]
```
Runs anywhere with 3DEP coverage and auto-picks the local UTM zone. Outputs georeferenced GeoTIFFs (drop straight into QGIS) plus colormapped 8-bit PNG previews.

## The products
- **SVF** — Sky-View Factor: how much sky each cell sees; shades enclosed features (ditches, depressions). Best single view for low mounds.
- **LRM** — Local Relief Model: DTM minus its regional trend; mounds warm, hollows cool. The canal-finder.
- **Slope** — steepness in degrees.
- **Openness** — positive topographic openness: convex terrain reads high, concave low; a flat-illumination complement to SVF.
- **RRIM** — Red Relief Image Map: slope (redness) blended with differential openness (brightness); reveals convex and concave micro-relief with no fixed light direction. Highest-signal for eroded earthworks.

## CLI setup (Windows)
```
pwsh -File scripts/setup_env.ps1     # installs Miniforge + the lidar-arch conda env + editable install
```
Miniforge installs to `%USERPROFILE%\miniforge3` without changing PATH. Either enable conda once (`& "$env:USERPROFILE\miniforge3\Scripts\conda.exe" init powershell`, restart the shell, `conda activate lidar-arch`) or run through conda directly:
```
& "$env:USERPROFILE\miniforge3\Scripts\conda.exe" run -n lidar-arch \
  lidar-arch run --bbox -111.9856 33.4452 -111.9816 33.4482 --out out/pueblo_grande
```

## Data
USGS 3DEP LiDAR on AWS Open Data (`s3://usgs-lidar-public`, Entwine Point Tile format, no credentials, no egress cost). Coverage comes from the [hobuinc/usgs-lidar](https://github.com/hobuinc/usgs-lidar) resource index (~2,266 collections); the web app shades it by point **density** — the quality signal, since most collections are sparse and density determines whether subtle features resolve.

## Layout
```
src/lidar_arch/   CLI + pipeline:  geo, fetch, dem, viz, resources, cli
web/              map app: static front-end + Cloudflare Worker + container + R2  (web/README.md)
scripts/          environment setup
tests/            unit tests + the Pueblo Grande end-to-end regression
docs/superpowers/ design spec + implementation plan
```

## Tests
```
conda run -n lidar-arch pytest -m "not slow"   # fast unit tests
conda run -n lidar-arch pytest -m slow         # Pueblo Grande end-to-end (network + toolchain)
```

## Status
CLI + web app complete and **deployed** on Cloudflare (Workers + Containers + R2). Runs anywhere with 3DEP coverage, auto-resolution keeps large areas fast. Possible next: async jobs + a progress bar for very large sweeps, more validation sites, a custom domain.
