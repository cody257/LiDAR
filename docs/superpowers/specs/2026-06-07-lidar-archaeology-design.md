# LiDAR Archaeology Visualization Pipeline — Design Spec

**Date:** 2026-06-07
**Status:** Approved (brainstorming)
**Source:** `lidar-archaeology-handoff.md` + live USGS 3DEP research (this doc supersedes open questions in the handoff)

---

## 1. Goal

A command-line tool that turns a raw USGS 3DEP LiDAR point cloud (for a bounding box) into archaeology-optimized terrain visualizations that reveal low-relief earthworks — mounds, canals, compound walls — which standard hillshade washes out.

Core output: bare-earth DEM → three derivative rasters that actually surface subtle anthropogenic features and are under-represented in public tools:

- **Sky-View Factor (SVF)** — best single view for low mounds
- **Local Relief Model (LRM)** — the canal finder
- **Slope**

The contribution is lowering the barrier from "expert-only GIS workstation" to one command.

## 2. Scope & phasing

Built as a **vertical slice first**, so the riskiest links (the CRS handling and the point-cloud toolchain) are proven against a known feature before any breadth is added.

### Milestone 1 — validated vertical slice (this spec)

One command works end-to-end:

```
lidar-arch run --bbox <minx miny maxx maxy> --out <dir>
```

Produces, for the given lat/lon box: a bare-earth DTM plus **SVF, LRM, and Slope** as georeferenced GeoTIFFs (EPSG:26912) and 8-bit PNG previews. **Validated on the Pueblo Grande / S'edav Va'aki platform mound** — if the mound is not obvious in SVF/LRM, M1 is not done.

### Milestone 2 — depth (separate backlog, not in this spec)

- Positive **Openness** + **Red Relief Image Map (RRIM)** composite
- `--reclassify` flag (SMRF/ELM/outlier re-classification for poor older collections)
- lat/lon → EPT resource **auto-lookup**
- Split `fetch` / `dem` / `viz` subcommands
- Casa Grande Ruins + a Salt River canal corridor as second validations

## 3. Confirmed inputs (from research, 2026-06-07)

The one thing the handoff doc could not pin down — the exact resource and vintage — is now verified against the live EPT index and the public S3 bucket:

| Field | Value |
|---|---|
| EPT resource | **`AZ_MaricopaPinal_1_2020`** |
| EPT URL | `https://s3-us-west-2.amazonaws.com/usgs-lidar-public/AZ_MaricopaPinal_1_2020/ept.json` |
| Vintage | collected **2020-10-02 → 2021-12-18** |
| Point density | **18.57 pts/m²** (supports 1 m, even sub-meter) |
| Total points | ~249.9 billion |
| Native SRS | **EPSG:3857** (Web Mercator) |
| Data extent (3857, `boundsConforming`) | X `-12,555,542 … -12,363,850`, Y `3,847,680 … 4,010,355`, Z `64 … 1541 m` |
| Pre-classified | Yes (ASPRS `Classification` dimension present) |

**Coverage confirmed** for both validation targets (converted lat/lon → 3857, both inside the extent):

| Target | lat, lon | 3857 (approx) | Inside? |
|---|---|---|---|
| Pueblo Grande / S'edav Va'aki | 33.4467, -111.9836 | (-12,465,956, 3,946,000) | ✓ |
| Casa Grande Ruins | 32.9797, -111.5326 | (-12,415,752, 3,888,800) | ✓ |

**Implication for `--reclassify`:** this is a recent (2020–21), high-density collection, so we **trust ASPRS class 2** and do **not** reclassify in M1. (`--reclassify` is deferred to M2 for older, poorer datasets.)

**Data access:** `s3://usgs-lidar-public` is public — no AWS credentials, no egress cost. PDAL `readers.ept` streams only the points inside the requested bounds; we never download a whole resource.

## 4. Architecture

### Data flow (M1)

```
lat/lon bbox
   │  (reproject bbox corners to EPSG:3857)
   ▼
readers.ept  ── stream only points in bounds ──►  points (3857)
   │  filters.reprojection → EPSG:26912
   │  filters.range Classification[2:2]  (ground only)
   ▼
writers.gdal (idw, 1 m)  ──►  dtm_raw.tif (26912)
   │  gdal_fillnodata (max distance ~25 cells)
   ▼
dtm.tif  (bare-earth, hole-filled, 26912)
   │
   ├── rvt-py sky_view_factor ──► svf.tif  + svf.png
   ├── rvt-py local_relief_model ──► lrm.tif + lrm.png
   └── gdaldem slope ──► slope.tif + slope.png
```

### Modules (`src/lidar_arch/`)

Each unit has one job, a clear interface, and is testable in isolation.

| File | Responsibility | Key interface (sketch) |
|---|---|---|
| `cli.py` | `click` CLI; the `run` command; wiring | `run(bbox, out, resolution)` |
| `geo.py` | CRS conversions (lat/lon ↔ 3857 ↔ 26912), bbox handling | `bbox_to_3857(bbox) -> (xmin,xmax,ymin,ymax)` |
| `fetch.py` | build + execute the PDAL EPT→DTM pipeline | `fetch_dtm(bbox, resource, out, resolution) -> Path` |
| `dem.py` | hole-fill + finalize the bare-earth DTM | `fill_holes(dtm_raw) -> dtm` |
| `viz.py` | rvt-py / gdaldem wrappers → GeoTIFF + PNG | `svf(dtm)`, `lrm(dtm)`, `slope(dtm)` |
| `resources.py` | resource registry; M1 returns the hard-coded Phoenix resource | `resolve(bbox\|name) -> ept_url` |
| `pipelines/` | reference PDAL JSON template(s) | — |

`geo.py` is split out from `fetch.py` deliberately: the CRS dance is the highest-risk logic and the easiest to unit-test in isolation (pure coordinate math, no I/O).

## 5. Pipeline detail

### 5.1 Fetch + ground filter + grid (PDAL)

The **CRS dance** (the doc's #1 trap) — get this ordering exactly right:

1. User passes `--bbox minx miny maxx maxy` in **lat/lon** (EPSG:4326).
2. Reproject the bbox **to EPSG:3857** for the `readers.ept` `bounds` argument (EPT native CRS).
3. `filters.reprojection` reprojects the *points* to **EPSG:26912** (UTM 12N NAD83) after reading.
4. All rasters are written and stay in **26912**.

Reference pipeline (templated in `pipelines/`):

```json
{
  "pipeline": [
    { "type": "readers.ept",
      "filename": "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/AZ_MaricopaPinal_1_2020/ept.json",
      "bounds": "([xmin_3857, xmax_3857], [ymin_3857, ymax_3857])" },
    { "type": "filters.reprojection", "out_srs": "EPSG:26912" },
    { "type": "filters.range", "limits": "Classification[2:2]" },
    { "type": "writers.gdal", "filename": "dtm_raw.tif", "gdaldriver": "GTiff",
      "output_type": "idw", "resolution": 1.0, "window_size": 6 }
  ]
}
```

Notes:
- `idw` fills sparse ground better than `min`/`mean`.
- `resolution` exposed via `--resolution` (default 1.0).
- `bounds` string is in **3857**; points come out in **26912**.

### 5.2 Hole-filling

Desert collections leave nodata gaps that ruin LRM. After `writers.gdal`, run `gdal_fillnodata` (max distance ~25 cells) **before** deriving anything. Output `dtm.tif`.

### 5.3 Derivatives (rvt-py + gdaldem)

Prefer **rvt-py** (Relief Visualization Toolbox) — validated against the archaeology literature, avoids fiddly hand-rolled correctness work.

- **SVF** — `rvt.vis.sky_view_factor`, ~16 directions, max search radius ~10 px. Default-best for low mounds.
- **LRM** — `rvt.vis.local_relief_model` (DTM minus a low-pass DTM; kernel radius ~10–20 m) to strip regional trend so small features pop.
- **Slope** — `gdaldem slope` + color ramp (or rvt-py slope).

> Implementation note: confirm exact rvt-py function names/signatures against the installed version during TDD; the API above follows the handoff doc and may differ slightly by release.

Each derivative is written as a georeferenced GeoTIFF (26912) and an 8-bit PNG preview.

## 6. CLI shape (M1)

```
lidar-arch run --bbox <minx miny maxx maxy> --out <dir> [--resolution 1.0]
```

Surface a default only when it is load-bearing: CRS (fixed 26912), resolution (1.0), classification trust (class 2). The resource is fixed to `AZ_MaricopaPinal_1_2020` in M1 (`resources.resolve` stub).

## 7. Toolchain / environment

**Native Windows + Miniforge** (confirmed). One dedicated conda-forge env:

```
conda create -n lidar-arch -c conda-forge python=3.11 \
  pdal python-pdal gdal rvt_py rasterio numpy scipy click
```

(Exact `rvt-py` conda package name to be confirmed at install — may be `rvt_py` or pip-installed.) Pin nothing unless a version breaks. The env lives outside the repo; only the env spec (an `environment.yml`) is committed.

## 8. Validation / regression

1. `run` on a small bbox over **Pueblo Grande / S'edav Va'aki (33.4467, -111.9836)**. The platform mound must be obvious in SVF and LRM. **This is the regression test** — if it isn't visible, the pipeline is wrong.
2. (M2) Expand to a Salt River canal corridor; confirm linear features appear in LRM that plain hillshade misses.
3. (M2) Casa Grande Ruins (32.9797, -111.5326) as a second anchor.

**M1 success criteria:** `run` completes on the Pueblo Grande bbox with no manual GIS steps; outputs are correctly georeferenced (load aligned in QGIS at 26912); the mound is visually unmistakable in SVF/LRM.

## 9. Error handling

- **Empty output / no points:** detect zero-point reads (almost always a CRS-bounds mistake — bounds not in 3857) and fail with a clear message naming the likely cause, not a silent empty raster.
- **Bbox outside coverage:** validate the requested bbox against the resource extent up front; refuse with a helpful message.
- **Missing toolchain:** detect absent `pdal`/`gdal` and point to the env setup.
- **All-nodata DTM:** warn before attempting derivatives.

## 10. Testing strategy

- **`geo.py`:** pure unit tests on coordinate conversions (known lat/lon → expected 3857/26912), including the two validation targets.
- **Pipeline build:** unit-test the generated PDAL JSON (correct bounds CRS, filter order, classification) without executing.
- **Integration (the regression test):** a tiny real bbox over Pueblo Grande, run end-to-end, assert non-empty georeferenced outputs in 26912. Marked slow/network; this is the M1 gate.
- Follow TDD (red-green-refactor) per task.

## 11. Repo layout

```
LiDAR/
  pyproject.toml
  environment.yml
  README.md
  src/lidar_arch/
    cli.py  geo.py  fetch.py  dem.py  viz.py  resources.py
  pipelines/            # reference PDAL JSON templates
  tests/
  docs/superpowers/specs/
  lidar-archaeology-handoff.md
```

## 12. Risks / open items

- **rvt-py packaging on Windows/conda-forge** — package name and availability to verify at install; pip fallback if needed.
- **rvt-py exact API** — confirm `sky_view_factor` / `local_relief_model` signatures against installed version.
- **PDAL `readers.ept` over HTTPS on native Windows** — expected to work (conda-forge PDAL ships with the EPT/arbiter stack); verify early in M1.
- **gdal_fillnodata invocation** — script vs. `rasterio.fill`; decide during implementation.

## 13. Out of scope (M1)

Everything in Milestone 2 (§2), plus: multi-resource mosaicking, non-Phoenix regions, web UI, and any AWS-credentialed (`s3://usgs-lidar` Requester-Pays) fallback.
