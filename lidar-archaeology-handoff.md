# Handoff: LiDAR Archaeology Visualization Pipeline

## What we're building

A command-line tool that takes raw USGS 3DEP LiDAR point cloud data for a bounding box and produces archaeology-optimized terrain visualizations — the kind that reveal low-relief earthworks (mounds, canals, compound walls) that standard hillshade maps wash out.

Default ground returns → bare-earth DEM → **three derivative rasters**: Sky-View Factor (SVF), Local Relief Model (LRM), and Slope. These three are what actually surface subtle anthropogenic features, and they're under-represented in public-facing LiDAR tools. That gap is the entire point of this project.

**First validation target: the Hohokam canal systems and platform mounds of the Salt River Valley, Phoenix AZ.** Pueblo Grande / S'edav Va'aki is the known-feature anchor (a documented Hohokam platform mound). The buried/eroded canal network is the discovery surface. Casa Grande Ruins (Coolidge, Pinal County) is a secondary target.

---

## Data source (confirmed, free, no auth)

USGS 3DEP LiDAR is on AWS Open Data in two buckets:

- **`s3://usgs-lidar-public`** — Entwine Point Tile (EPT) format, public, **no AWS credentials, no egress cost**. This is what we use. EPT is a streamable octree of LAZ data; PDAL has a native `readers.ept` that pulls only the points inside a requested bounding box, so we never download a whole tile.
- `s3://usgs-lidar` — Requester Pays, raw LAZ 1.4, more complete coverage. Fallback only; needs AWS creds.

Resource index and footprint map: `https://usgs.entwine.io` (click a polygon → get the EPT path + point counts). Resource names match USGS project names.

EPT data is served in **EPSG:3857**; reproject on the fly in the PDAL pipeline with `filters.reprojection` to the local UTM zone (Phoenix = **EPSG:26912**, UTM 12N NAD83) before gridding.

EPT format spec: https://entwine.io/en/latest/entwine-point-tile.html

For finding the right EPT resource programmatically for a given lat/lon, the boundary-resource lookup approach in `hobuinc/usgs-lidar` (GitHub) and the OpenTopography `OT_3DEP_Workflows` notebooks are good references to adapt.

---

## Tech stack

- **PDAL** (Point Data Abstraction Library) — point cloud → DEM. Install via conda: `conda install -c conda-forge pdal python-pdal gdal`. Pin nothing unless a version breaks.
- **GDAL** — raster ops, hillshade, slope (`gdaldem`).
- **Python 3.11+** — orchestration, SVF/LRM computation. Libs: `numpy`, `scipy`, `rasterio`. SVF specifically: either implement directly or use `rvt-py` (Relief Visualization Toolbox, ZRC SAZU) which has SVF, LRM, openness, and multi-hillshade built in and is the de facto archaeology standard — **strongly prefer `rvt-py` over hand-rolling these**.
- CLI: `argparse` or `click`.

---

## Pipeline stages

### 1. Fetch + ground filter + DEM (PDAL)

Input: bounding box (the tool accepts `--bbox minx miny maxx maxy` in lat/lon, plus the EPT resource URL or an auto-lookup). Pull ground-classified points only and grid to a bare-earth DTM.

Reference PDAL pipeline (adapt — EPT reader, reprojection, ground filter, GDAL writer):

```json
{
  "pipeline": [
    {
      "type": "readers.ept",
      "filename": "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/<RESOURCE>/ept.json",
      "bounds": "([minx, maxx], [miny, maxy])"
    },
    {
      "type": "filters.reprojection",
      "out_srs": "EPSG:26912"
    },
    {
      "type": "filters.range",
      "limits": "Classification[2:2]"
    },
    {
      "type": "writers.gdal",
      "filename": "dtm.tif",
      "gdaldriver": "GTiff",
      "output_type": "idw",
      "resolution": 1.0,
      "window_size": 6
    }
  ]
}
```

Notes:
- `Classification[2:2]` keeps ASPRS ground returns. USGS 3DEP is pre-classified, so we usually trust class 2 rather than re-running SMRF. **But** add an optional `--reclassify` flag that runs `filters.smrf` + `filters.outlier` for datasets where the supplied classification is poor (common in older AZ collections). When reclassifying, the order is: `filters.assign` (reset class) → `filters.elm` → `filters.outlier` → `filters.smrf` → `filters.range`.
- `bounds` for `readers.ept` must be in the EPT's native CRS (3857). Convert the user's lat/lon bbox to 3857 for the bounds argument, then reproject points to 26912 after reading. Get this ordering right — it's the most common failure.
- 1 m resolution is right for canals/mounds at this scale. Expose `--resolution`.
- `idw` output fills better than `min`/`mean` for sparse ground; follow with `gdal_fillnodata.py` (max distance ~25 cells) to close holes.

### 2. Derivative visualizations

From the bare-earth DTM, generate:

1. **Slope** — `gdaldem slope dtm.tif slope.tif` then a color ramp, OR via rvt-py.
2. **Sky-View Factor** — `rvt.vis.sky_view_factor()`. Best single visualization for low mounds. Default 16 directions, max search radius ~10 px.
3. **Local Relief Model** — `rvt.vis.local_relief_model()` (or implement: DTM minus a low-pass-filtered DTM, kernel radius ~10–20 m, to remove the regional trend so small features pop). This is the canal-finder.
4. **(stretch) Openness (positive)** and a **Red Relief Image Map** composite (slope + openness blended) — the highest-signal product for eroded earthworks.

Output all as GeoTIFFs (georeferenced, EPSG:26912) so they drop straight into QGIS, plus 8-bit PNG previews for quick eyeballing.

### 3. CLI shape

```
lidar-arch fetch   --bbox <minx miny maxx maxy> --resource <ept-url|auto> --out <dir>
lidar-arch dem     --in <dir> [--resolution 1.0] [--reclassify]
lidar-arch viz     --in <dir> [--products svf,lrm,slope,openness,rrim]
lidar-arch run     --bbox ... --resource auto --out <dir>   # all three, sane defaults
```

`run` is the path 90% of users take. Everything else is sane defaults; surface a default only when it's load-bearing (CRS, resolution, classification trust).

---

## Validation plan

1. Run `run` on a small bbox over **Pueblo Grande / S'edav Va'aki** (≈ 33.4467, -111.9836). The platform mound should be obvious in SVF/LRM. If it isn't, the pipeline is wrong — this is the regression test.
2. Expand to a Salt River canal corridor and confirm linear features appear in LRM that aren't visible in plain hillshade.
3. Casa Grande Ruins (≈ 32.9797, -111.5326) as a second known anchor.

Confirm 3DEP coverage for these exact spots first via `https://usgs.entwine.io` — Maricopa has good coverage but verify the resource name and vintage before coding the bbox in.

---

## Repo layout (suggested, not prescriptive)

```
lidar-arch/
  pyproject.toml
  src/lidar_arch/
    cli.py
    fetch.py        # bbox→3857, EPT pipeline build/run
    dem.py          # ground filter, grid, fillnodata
    viz.py          # rvt-py wrappers: svf, lrm, slope, openness, rrim
    resources.py    # lat/lon → EPT resource lookup (adapt hobuinc/usgs-lidar)
  pipelines/        # reference PDAL JSON templates
  README.md
```

---

## Things to get right / known traps

- **CRS dance**: EPT bounds in 3857, reproject points to 26912, all rasters out in 26912. Mixing these silently produces empty or warped output.
- **Don't re-classify by default** — trust USGS class 2 unless `--reclassify`. Re-running SMRF on good data wastes time and can erase real ground.
- **rvt-py over DIY** for SVF/LRM/openness — it's validated against the archaeology literature and saves a lot of fiddly correctness work.
- **Hole-filling matters** — sparse ground in desert collections leaves nodata that ruins LRM. Fill before deriving.
- Keep the point fetch bbox-scoped via `readers.ept` `bounds`; never pull a whole resource.

---

## Why this helps the community

Public 3DEP viewers and most hobbyist tools stop at hillshade. SVF/LRM/openness/RRIM are exactly what finds eroded mounds and buried canals, and there's no easy one-command tool that goes from "here's a bounding box" to "here are archaeology-grade visualizations" without a GIS workstation and manual PDAL/QGIS assembly. That's the contribution: lowering the barrier from expert-only to one command.
