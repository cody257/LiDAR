# LiDAR Archaeology Pipeline — M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `lidar-arch run --bbox ... --out ...` that turns a lat/lon bounding box of USGS 3DEP LiDAR into a bare-earth DEM plus SVF, LRM, and Slope rasters (GeoTIFF + PNG), validated on the Pueblo Grande platform mound.

**Architecture:** A small `click` CLI orchestrates a linear pipeline: lat/lon bbox → reproject to EPSG:3857 → PDAL `readers.ept` streams ground points → reproject to EPSG:26912 → grid to 1 m DTM → fill holes → derive SVF/LRM/Slope. The CRS-conversion logic (`geo.py`) is isolated for unit testing because it is the highest-risk piece.

**Tech Stack:** Python 3.11, PDAL (`python-pdal`), GDAL (`osgeo.gdal`), rasterio, pyproj, scipy, rvt-py, click. Toolchain lives in the `lidar-arch` conda env.

---

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | package metadata, `lidar-arch` entry point, pytest config |
| `src/lidar_arch/__init__.py` | package marker |
| `src/lidar_arch/geo.py` | CRS conversions, bbox-in-extent check (pure, pyproj) |
| `src/lidar_arch/resources.py` | `Resource` dataclass + `resolve()` (M1: hard-coded Phoenix) |
| `src/lidar_arch/fetch.py` | build + run the PDAL EPT→DTM pipeline |
| `src/lidar_arch/dem.py` | hole-fill the raw DTM |
| `src/lidar_arch/viz.py` | SVF / LRM / Slope → GeoTIFF + PNG, shared raster I/O helpers |
| `src/lidar_arch/cli.py` | `click` group + `run` command wiring it together |
| `tests/…` | one test module per source module + the integration regression test |

Each derivative writes a GeoTIFF (EPSG:26912) and an 8-bit PNG preview (via `gdal.Translate`, so no extra image deps).

---

## Task 0: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/lidar_arch/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lidar-arch"
version = "0.1.0"
description = "Archaeology-optimized terrain visualizations from USGS 3DEP LiDAR."
requires-python = ">=3.11"
dependencies = ["click", "numpy", "scipy", "rasterio", "pyproj"]
# pdal, gdal (osgeo), and rvt-py are provided by the conda env, not pip-resolvable here.

[project.scripts]
lidar-arch = "lidar_arch.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/lidar_arch"]

[tool.pytest.ini_options]
markers = ["slow: end-to-end tests that hit the network and full toolchain"]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Create `src/lidar_arch/__init__.py`**

```python
"""lidar-arch: archaeology-optimized terrain visualizations from USGS 3DEP LiDAR."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `tests/__init__.py`** (empty file)

- [ ] **Step 4: Write the smoke test** in `tests/test_smoke.py`

```python
import lidar_arch

def test_package_imports():
    assert lidar_arch.__version__ == "0.1.0"
```

- [ ] **Step 5: Editable install into the env**

Run: `conda run -n lidar-arch pip install -e .`
Expected: `Successfully installed lidar-arch-0.1.0`

- [ ] **Step 6: Run the smoke test**

Run: `conda run -n lidar-arch pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/lidar_arch/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold lidar-arch package"
```

---

## Task 1: `geo.py` — bbox lat/lon → EPSG:3857

**Files:**
- Create: `src/lidar_arch/geo.py`
- Test: `tests/test_geo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_geo.py
from lidar_arch import geo

# AZ_MaricopaPinal_1_2020 data extent in EPSG:3857 (xmin, ymin, xmax, ymax)
EXTENT = (-12555542.0, 3847680.0, -12363850.0, 4010355.0)

def test_pueblo_grande_point_inside_extent():
    # tiny box around Pueblo Grande / S'edav Va'aki (lon, lat)
    x = geo.bbox_to_3857(-111.9856, 33.4452, -111.9816, 33.4482)
    xmin, ymin, xmax, ymax = x
    assert xmin < xmax and ymin < ymax
    assert EXTENT[0] <= xmin and EXTENT[1] <= ymin
    assert xmax <= EXTENT[2] and ymax <= EXTENT[3]

def test_roundtrip_recovers_latlon():
    lon, lat = -111.9836, 33.4467
    xmin, ymin, xmax, ymax = geo.bbox_to_3857(lon, lat, lon, lat)
    back = geo.to_4326(xmin, ymin)
    assert abs(back[0] - lon) < 1e-6
    assert abs(back[1] - lat) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_geo.py -v`
Expected: FAIL (module `geo` has no attribute `bbox_to_3857`)

- [ ] **Step 3: Implement `geo.py`**

```python
"""CRS conversions for the EPT pipeline. The bbox CRS dance lives here, isolated
so it can be unit-tested without touching PDAL or the network."""
from pyproj import Transformer

_TO_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


def bbox_to_3857(min_lon, min_lat, max_lon, max_lat):
    """lat/lon bbox -> (xmin, ymin, xmax, ymax) in EPSG:3857 (EPT native CRS)."""
    xmin, ymin = _TO_3857.transform(min_lon, min_lat)
    xmax, ymax = _TO_3857.transform(max_lon, max_lat)
    return (xmin, ymin, xmax, ymax)


def to_4326(x, y):
    """EPSG:3857 (x, y) -> (lon, lat)."""
    return _TO_4326.transform(x, y)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_geo.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/geo.py tests/test_geo.py
git commit -m "feat: lat/lon to EPSG:3857 bbox conversion"
```

---

## Task 2: `geo.py` — bbox-within-extent guard

**Files:**
- Modify: `src/lidar_arch/geo.py`
- Test: `tests/test_geo.py`

- [ ] **Step 1: Add the failing test** to `tests/test_geo.py`

```python
def test_bbox_within_extent():
    inside = (-12466000.0, 3953000.0, -12465000.0, 3954000.0)
    outside = (-13000000.0, 3953000.0, -12999000.0, 3954000.0)
    assert geo.bbox_within(inside, EXTENT) is True
    assert geo.bbox_within(outside, EXTENT) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_geo.py::test_bbox_within_extent -v`
Expected: FAIL (no attribute `bbox_within`)

- [ ] **Step 3: Append to `geo.py`**

```python
def bbox_within(bbox_3857, extent_3857):
    """True if bbox_3857 (xmin,ymin,xmax,ymax) lies fully inside extent_3857."""
    xmin, ymin, xmax, ymax = bbox_3857
    exmin, eymin, exmax, eymax = extent_3857
    return exmin <= xmin and eymin <= ymin and xmax <= exmax and ymax <= eymax
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_geo.py -v`
Expected: PASS (all three)

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/geo.py tests/test_geo.py
git commit -m "feat: bbox-within-coverage guard"
```

---

## Task 3: `resources.py` — resource registry

**Files:**
- Create: `src/lidar_arch/resources.py`
- Test: `tests/test_resources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resources.py
from lidar_arch import resources

def test_resolve_returns_phoenix():
    r = resources.resolve()
    assert r.name == "AZ_MaricopaPinal_1_2020"
    assert r.ept_url.endswith("/AZ_MaricopaPinal_1_2020/ept.json")
    assert r.target_srs == "EPSG:26912"
    assert len(r.extent_3857) == 4
    xmin, ymin, xmax, ymax = r.extent_3857
    assert xmin < xmax and ymin < ymax
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_resources.py -v`
Expected: FAIL (no module `resources`)

- [ ] **Step 3: Implement `resources.py`**

```python
"""3DEP EPT resource registry. M1 hard-codes the Phoenix collection confirmed
during research (AZ_MaricopaPinal_1_2020). M2 will add lat/lon auto-lookup."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Resource:
    name: str
    ept_url: str
    extent_3857: tuple  # (xmin, ymin, xmax, ymax) data extent in EPSG:3857
    target_srs: str = "EPSG:26912"  # UTM 12N NAD83, Phoenix


PHOENIX = Resource(
    name="AZ_MaricopaPinal_1_2020",
    ept_url=(
        "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"
        "AZ_MaricopaPinal_1_2020/ept.json"
    ),
    extent_3857=(-12555542.0, 3847680.0, -12363850.0, 4010355.0),
)


def resolve(name_or_bbox=None) -> Resource:
    """M1: always the Phoenix resource. (M2: real lat/lon -> resource lookup.)"""
    return PHOENIX
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_resources.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/resources.py tests/test_resources.py
git commit -m "feat: Phoenix 3DEP resource registry"
```

---

## Task 4: `fetch.py` — build the PDAL pipeline (pure)

**Files:**
- Create: `src/lidar_arch/fetch.py`
- Test: `tests/test_fetch_build.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_build.py
from lidar_arch import fetch

def test_build_pipeline_structure():
    bbox = (-12466000.0, 3953000.0, -12465000.0, 3954000.0)
    p = fetch.build_pipeline(bbox, "https://x/ept.json", "dtm_raw.tif",
                             resolution=1.0, target_srs="EPSG:26912")
    stages = p["pipeline"]
    # order is load-bearing: read (3857 bounds) -> reproject -> ground -> grid
    assert stages[0]["type"] == "readers.ept"
    assert stages[0]["filename"] == "https://x/ept.json"
    assert "-12466000" in stages[0]["bounds"] and "3953000" in stages[0]["bounds"]
    assert stages[1]["type"] == "filters.reprojection"
    assert stages[1]["out_srs"] == "EPSG:26912"
    assert stages[2]["type"] == "filters.range"
    assert stages[2]["limits"] == "Classification[2:2]"
    assert stages[3]["type"] == "writers.gdal"
    assert stages[3]["output_type"] == "idw"
    assert stages[3]["resolution"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_fetch_build.py -v`
Expected: FAIL (no module `fetch`)

- [ ] **Step 3: Implement the builder in `fetch.py`**

```python
"""Build and run the PDAL EPT -> bare-earth DTM pipeline.

CRS dance (the #1 trap): `readers.ept` `bounds` MUST be in the EPT's native CRS
(EPSG:3857); points are then reprojected to the target UTM CRS after reading."""
import json


def build_pipeline(bbox_3857, ept_url, out_tif, resolution=1.0,
                   target_srs="EPSG:26912"):
    """Return a PDAL pipeline dict. bbox_3857 = (xmin, ymin, xmax, ymax)."""
    xmin, ymin, xmax, ymax = bbox_3857
    bounds = f"([{xmin}, {xmax}], [{ymin}, {ymax}])"  # ([xmin,xmax],[ymin,ymax]) in 3857
    return {
        "pipeline": [
            {"type": "readers.ept", "filename": ept_url, "bounds": bounds},
            {"type": "filters.reprojection", "out_srs": target_srs},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {
                "type": "writers.gdal",
                "filename": str(out_tif),
                "gdaldriver": "GTiff",
                "output_type": "idw",
                "resolution": resolution,
                "window_size": 6,
            },
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_fetch_build.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/fetch.py tests/test_fetch_build.py
git commit -m "feat: build PDAL EPT->DTM pipeline"
```

---

## Task 5: `fetch.py` — run the pipeline + empty-output guard

**Files:**
- Modify: `src/lidar_arch/fetch.py`
- Test: `tests/test_fetch_run.py`

- [ ] **Step 1: Write the failing test** (mocks PDAL — no network)

```python
# tests/test_fetch_run.py
import pytest
from lidar_arch import fetch, resources

class _FakePipe:
    def __init__(self, n): self._n = n
    def execute(self): return self._n

def test_fetch_dtm_raises_on_zero_points(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "_pipeline", lambda d: _FakePipe(0))
    with pytest.raises(RuntimeError, match="No points"):
        fetch.fetch_dtm((-12466000.0, 3953000.0, -12465000.0, 3954000.0),
                        resources.PHOENIX, tmp_path / "dtm_raw.tif")

def test_fetch_dtm_returns_path_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "_pipeline", lambda d: _FakePipe(123))
    out = tmp_path / "dtm_raw.tif"
    result = fetch.fetch_dtm((-12466000.0, 3953000.0, -12465000.0, 3954000.0),
                             resources.PHOENIX, out)
    assert result == out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_fetch_run.py -v`
Expected: FAIL (no attribute `_pipeline` / `fetch_dtm`)

- [ ] **Step 3: Append run logic to `fetch.py`**

```python
def _pipeline(pipeline_dict):
    """Wrap PDAL construction so tests can monkeypatch it."""
    import pdal
    return pdal.Pipeline(json.dumps(pipeline_dict))


def fetch_dtm(bbox_3857, resource, out_tif, resolution=1.0):
    """Run the pipeline; return out_tif. Raise if zero points (usually a CRS slip)."""
    pipe = build_pipeline(bbox_3857, resource.ept_url, out_tif, resolution,
                          resource.target_srs)
    n = _pipeline(pipe).execute()
    if n == 0:
        raise RuntimeError(
            "No points returned. Check that bbox bounds are in EPSG:3857 and "
            "inside the resource coverage."
        )
    return out_tif
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_fetch_run.py -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/fetch.py tests/test_fetch_run.py
git commit -m "feat: run EPT pipeline with empty-output guard"
```

---

## Task 6: `dem.py` — hole-filling

**Files:**
- Create: `src/lidar_arch/dem.py`
- Test: `tests/test_dem.py`

- [ ] **Step 1: Write the failing test** (synthetic raster with a nodata hole)

```python
# tests/test_dem.py
import numpy as np
import rasterio
from rasterio.transform import from_origin
from lidar_arch import dem

def _make_raster(path, arr, nodata=-9999.0):
    h, w = arr.shape
    profile = dict(driver="GTiff", height=h, width=w, count=1, dtype="float32",
                   crs="EPSG:26912", transform=from_origin(400000, 3700000, 1, 1),
                   nodata=nodata)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype("float32"), 1)

def test_fill_holes_closes_nodata(tmp_path):
    arr = np.full((20, 20), 5.0, dtype="float32")
    arr[10, 10] = -9999.0  # a one-cell hole
    src = tmp_path / "raw.tif"; _make_raster(src, arr)
    out = dem.fill_holes(src, tmp_path / "dtm.tif")
    with rasterio.open(out) as r:
        filled = r.read(1)
    assert abs(filled[10, 10] - 5.0) < 1e-3  # hole filled from neighbours
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_dem.py -v`
Expected: FAIL (no module `dem`)

- [ ] **Step 3: Implement `dem.py`**

```python
"""Finalize the bare-earth DTM: fill nodata holes left by sparse desert ground
returns before any derivative is computed (holes ruin LRM/SVF)."""
import rasterio
from rasterio.fill import fillnodata


def fill_holes(in_tif, out_tif, max_distance=25):
    """Fill nodata in a single-band DTM via IDW interpolation. Returns out_tif."""
    with rasterio.open(in_tif) as src:
        arr = src.read(1)
        mask = src.read_masks(1)  # 0 where nodata, 255 where valid
        profile = src.profile
    filled = fillnodata(arr, mask=mask, max_search_distance=max_distance)
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(filled, 1)
    return out_tif
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_dem.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/dem.py tests/test_dem.py
git commit -m "feat: DTM hole-filling"
```

---

## Task 7: `viz.py` — raster I/O helpers + Slope

**Files:**
- Create: `src/lidar_arch/viz.py`
- Test: `tests/test_viz_slope.py`

- [ ] **Step 1: Write the failing test** (inclined plane → known slope)

```python
# tests/test_viz_slope.py
import numpy as np
import rasterio
from rasterio.transform import from_origin
from lidar_arch import viz

def _dtm(path, arr):
    h, w = arr.shape
    profile = dict(driver="GTiff", height=h, width=w, count=1, dtype="float32",
                   crs="EPSG:26912", transform=from_origin(400000, 3700000, 1, 1),
                   nodata=-9999.0)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype("float32"), 1)

def test_slope_of_inclined_plane(tmp_path):
    # rise 1 m per 1 m cell in +x => 45 degrees
    yy, xx = np.mgrid[0:30, 0:30]
    arr = xx.astype("float32")
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.slope(src, tmp_path / "slope.tif")
    with rasterio.open(out) as r:
        s = r.read(1)
    assert abs(np.median(s[5:25, 5:25]) - 45.0) < 2.0
    assert png.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_viz_slope.py -v`
Expected: FAIL (no module `viz`)

- [ ] **Step 3: Implement helpers + `slope` in `viz.py`**

```python
"""Archaeology derivatives from the bare-earth DTM: SVF, LRM, Slope.
Each writes a georeferenced GeoTIFF (EPSG:26912) and an 8-bit PNG preview.
PNG previews use gdal.Translate so no extra image library is required."""
from pathlib import Path
import numpy as np
import rasterio
from osgeo import gdal

gdal.UseExceptions()


def _read(dtm_tif):
    with rasterio.open(dtm_tif) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        return arr, src.profile


def _write_tif(out_tif, arr, profile):
    p = profile.copy()
    p.update(dtype="float32", count=1, nodata=-9999.0)
    out = np.where(np.isfinite(arr), arr, -9999.0).astype("float32")
    with rasterio.open(out_tif, "w", **p) as dst:
        dst.write(out, 1)
    return out_tif


def _write_png(src_tif, png_path):
    """8-bit auto-stretched PNG preview of a single-band raster."""
    gdal.Translate(str(png_path), str(src_tif), format="PNG",
                   outputType=gdal.GDT_Byte, scaleParams=[[]])
    return png_path


def _pixel_size(profile):
    return abs(profile["transform"].a)


def slope(dtm_tif, out_tif, png=True):
    """Slope in degrees via gdaldem. Returns (geotiff_path, png_path)."""
    gdal.DEMProcessing(str(out_tif), str(dtm_tif), "slope",
                       slopeFormat="degree", computeEdges=True)
    png_path = Path(out_tif).with_suffix(".png")
    if png:
        _write_png(out_tif, png_path)
    return Path(out_tif), png_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_viz_slope.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/viz.py tests/test_viz_slope.py
git commit -m "feat: viz helpers + slope derivative"
```

---

## Task 8: `viz.py` — Local Relief Model

**Files:**
- Modify: `src/lidar_arch/viz.py`
- Test: `tests/test_viz_lrm.py`

LRM = DTM minus a low-pass (regional-trend) DTM, so small features pop. Implemented directly with a NaN-aware mean filter (the doc-endorsed definition; deterministic and testable). rvt's LRM can be swapped in M2.

- [ ] **Step 1: Write the failing test** (ramp + small bump → bump shows in LRM)

```python
# tests/test_viz_lrm.py
import numpy as np
import rasterio
from rasterio.transform import from_origin
from lidar_arch import viz

def _dtm(path, arr):
    h, w = arr.shape
    profile = dict(driver="GTiff", height=h, width=w, count=1, dtype="float32",
                   crs="EPSG:26912", transform=from_origin(400000, 3700000, 1, 1),
                   nodata=-9999.0)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype("float32"), 1)

def test_lrm_highlights_local_bump(tmp_path):
    yy, xx = np.mgrid[0:60, 0:60]
    arr = (0.05 * xx).astype("float64")          # gentle regional trend
    arr[30, 30] += 1.0                            # a small local mound
    src = tmp_path / "dtm.tif"; _dtm(src, arr.astype("float32"))
    out, png = viz.lrm(src, tmp_path / "lrm.tif", kernel_radius_m=10)
    with rasterio.open(out) as r:
        lrm = r.read(1)
    # bump cell should stand well above the flat surroundings in the LRM
    assert lrm[30, 30] > lrm[30, 10] + 0.5
    assert png.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_viz_lrm.py -v`
Expected: FAIL (no attribute `lrm`)

- [ ] **Step 3: Append `lrm` + `_smooth_nan` to `viz.py`**

```python
from scipy.ndimage import uniform_filter


def _smooth_nan(arr, radius_px):
    """NaN-aware box mean. Cells that are NaN stay NaN; others use valid neighbours."""
    valid = np.isfinite(arr)
    a0 = np.where(valid, arr, 0.0)
    w = valid.astype("float64")
    size = 2 * radius_px + 1
    num = uniform_filter(a0, size=size, mode="nearest")
    den = uniform_filter(w, size=size, mode="nearest")
    out = np.divide(num, den, out=np.full_like(num, np.nan), where=den > 0)
    return np.where(valid, out, np.nan)


def lrm(dtm_tif, out_tif, kernel_radius_m=15, png=True):
    """Local Relief Model: DTM minus its low-pass. Returns (geotiff, png)."""
    arr, profile = _read(dtm_tif)
    radius_px = max(1, int(round(kernel_radius_m / _pixel_size(profile))))
    trend = _smooth_nan(arr, radius_px)
    lrm_arr = arr - trend
    _write_tif(out_tif, lrm_arr, profile)
    png_path = Path(out_tif).with_suffix(".png")
    if png:
        _write_png(out_tif, png_path)
    return Path(out_tif), png_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_viz_lrm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/viz.py tests/test_viz_lrm.py
git commit -m "feat: local relief model derivative"
```

---

## Task 9: `viz.py` — Sky-View Factor (rvt-py)

**Files:**
- Modify: `src/lidar_arch/viz.py`
- Test: `tests/test_viz_svf.py`

- [ ] **Step 1: Confirm the installed rvt API**

Run: `conda run -n lidar-arch python -c "import rvt.vis, inspect; print(inspect.signature(rvt.vis.sky_view_factor))"`
Expected: a signature including `dem`, `resolution`, `compute_svf`, `svf_n_dir`, `svf_r_max`. If parameter names differ in the installed version, adjust the call in Step 3 to match (keep the `svf` output key handling).

- [ ] **Step 2: Write the failing test** (SVF is bounded [0,1]; a pit is darker than flat)

```python
# tests/test_viz_svf.py
import numpy as np
import rasterio
from rasterio.transform import from_origin
from lidar_arch import viz

def _dtm(path, arr):
    h, w = arr.shape
    profile = dict(driver="GTiff", height=h, width=w, count=1, dtype="float32",
                   crs="EPSG:26912", transform=from_origin(400000, 3700000, 1, 1),
                   nodata=-9999.0)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype("float32"), 1)

def test_svf_bounds_and_pit(tmp_path):
    arr = np.zeros((40, 40), dtype="float32")
    arr[18:22, 18:22] = -3.0                      # a pit
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.svf(src, tmp_path / "svf.tif")
    with rasterio.open(out) as r:
        svf = r.read(1)
    assert np.nanmin(svf) >= 0.0 and np.nanmax(svf) <= 1.0001
    assert np.nanmean(svf[18:22, 18:22]) < np.nanmean(svf[0:4, 0:4])  # pit is more enclosed
    assert png.exists()
```

- [ ] **Step 3: Append `svf` to `viz.py`**

```python
def svf(dtm_tif, out_tif, n_dir=16, r_max=10, png=True):
    """Sky-View Factor via rvt-py. Returns (geotiff, png)."""
    import rvt.vis
    arr, profile = _read(dtm_tif)
    res = _pixel_size(profile)
    result = rvt.vis.sky_view_factor(
        dem=arr, resolution=res,
        compute_svf=True, compute_asvf=False, compute_opns=False,
        svf_n_dir=n_dir, svf_r_max=r_max,
    )
    svf_arr = result["svf"]
    _write_tif(out_tif, svf_arr, profile)
    png_path = Path(out_tif).with_suffix(".png")
    if png:
        _write_png(out_tif, png_path)
    return Path(out_tif), png_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_viz_svf.py -v`
Expected: PASS. (If rvt returns NaNs at the border, the central-region asserts still hold.)

- [ ] **Step 5: Commit**

```bash
git add src/lidar_arch/viz.py tests/test_viz_svf.py
git commit -m "feat: sky-view factor derivative"
```

---

## Task 10: `cli.py` — the `run` command

**Files:**
- Create: `src/lidar_arch/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** (CliRunner; pipeline stages monkeypatched)

```python
# tests/test_cli.py
from pathlib import Path
from click.testing import CliRunner
from lidar_arch import cli, fetch, dem, viz

def test_run_orchestrates(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(fetch, "fetch_dtm",
                        lambda *a, **k: (calls.append("fetch"), a[2])[1])
    monkeypatch.setattr(dem, "fill_holes",
                        lambda src, out, **k: (calls.append("fill"), out)[1])
    monkeypatch.setattr(viz, "svf", lambda *a, **k: (calls.append("svf"), (a[1], a[1]))[1])
    monkeypatch.setattr(viz, "lrm", lambda *a, **k: (calls.append("lrm"), (a[1], a[1]))[1])
    monkeypatch.setattr(viz, "slope", lambda *a, **k: (calls.append("slope"), (a[1], a[1]))[1])

    out = tmp_path / "o"
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", "-111.9856", "33.4452", "-111.9816", "33.4482",
        "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert calls == ["fetch", "fill", "svf", "lrm", "slope"]

def test_run_rejects_out_of_coverage(tmp_path):
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", "-80.0", "40.0", "-79.99", "40.01",
        "--out", str(tmp_path / "o")])
    assert r.exit_code != 0
    assert "coverage" in r.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n lidar-arch pytest tests/test_cli.py -v`
Expected: FAIL (no module `cli`)

- [ ] **Step 3: Implement `cli.py`**

```python
"""lidar-arch command-line interface."""
from pathlib import Path
import click
from . import geo, resources, fetch, dem, viz


@click.group()
def cli():
    """Archaeology-optimized terrain visualizations from USGS 3DEP LiDAR."""


@cli.command()
@click.option("--bbox", nargs=4, type=float, required=True,
              metavar="MINLON MINLAT MAXLON MAXLAT",
              help="Bounding box in lon/lat (WGS84).")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), required=True,
              help="Output directory.")
@click.option("--resolution", type=float, default=1.0, show_default=True,
              help="DTM grid resolution in metres.")
def run(bbox, out_dir, resolution):
    """Fetch -> DTM -> SVF/LRM/Slope for a bounding box (sane defaults)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res = resources.resolve()
    bbox_3857 = geo.bbox_to_3857(*bbox)
    if not geo.bbox_within(bbox_3857, res.extent_3857):
        raise click.ClickException(
            f"Requested bbox is outside the {res.name} coverage area.")

    click.echo(f"Fetching ground points from {res.name} ...")
    dtm_raw = fetch.fetch_dtm(bbox_3857, res, out / "dtm_raw.tif", resolution)
    click.echo("Filling DTM holes ...")
    dtm = dem.fill_holes(dtm_raw, out / "dtm.tif")
    click.echo("Computing SVF / LRM / Slope ...")
    viz.svf(dtm, out / "svf.tif")
    viz.lrm(dtm, out / "lrm.tif")
    viz.slope(dtm, out / "slope.tif")
    click.echo(f"Done. Outputs in {out}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n lidar-arch pytest tests/test_cli.py -v`
Expected: PASS (both)

- [ ] **Step 5: Verify the entry point works**

Run: `conda run -n lidar-arch lidar-arch run --help`
Expected: usage text listing `--bbox`, `--out`, `--resolution`

- [ ] **Step 6: Commit**

```bash
git add src/lidar_arch/cli.py tests/test_cli.py
git commit -m "feat: run command wiring the pipeline"
```

---

## Task 11: Integration regression test — Pueblo Grande (the M1 gate)

**Files:**
- Create: `tests/test_integration_pueblo_grande.py`

This hits the live EPT (network) and exercises the full toolchain. It is the M1 acceptance gate: the pipeline must produce valid, georeferenced, non-empty outputs over the known platform mound.

- [ ] **Step 1: Write the integration test**

```python
# tests/test_integration_pueblo_grande.py
import numpy as np
import rasterio
import pytest
from click.testing import CliRunner
from lidar_arch import cli

# Small box (~360 x 330 m) centred on Pueblo Grande / S'edav Va'aki.
BBOX = ["-111.9856", "33.4452", "-111.9816", "33.4482"]

@pytest.mark.slow
def test_pueblo_grande_end_to_end(tmp_path):
    out = tmp_path / "pg"
    r = CliRunner().invoke(cli.cli, ["run", "--bbox", *BBOX, "--out", str(out)])
    assert r.exit_code == 0, r.output
    for name in ("dtm.tif", "svf.tif", "lrm.tif", "slope.tif"):
        f = out / name
        assert f.exists(), f"missing {name}"
        with rasterio.open(f) as ds:
            assert ds.crs.to_epsg() == 26912
            band = ds.read(1, masked=True)
            assert band.count() > 0          # has valid (non-masked) data
            assert np.isfinite(band.mean())
```

- [ ] **Step 2: Run the regression test**

Run: `conda run -n lidar-arch pytest tests/test_integration_pueblo_grande.py -v -m slow`
Expected: PASS (may take 1-3 min for the EPT fetch). Outputs land in a temp dir.

- [ ] **Step 3: Manual visual confirmation**

Run the CLI to a persistent dir and open the rasters:
`conda run -n lidar-arch lidar-arch run --bbox -111.9856 33.4452 -111.9816 33.4482 --out out/pueblo_grande`
Open `out/pueblo_grande/svf.png` and `lrm.png`. The platform mound should be visually obvious. **If it is not, the pipeline is wrong — stop and debug before declaring M1 done.**

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_pueblo_grande.py
git commit -m "test: Pueblo Grande end-to-end regression gate"
```

---

## Task 12: README + full-suite green

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
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
```

- [ ] **Step 2: Run the full fast suite**

Run: `conda run -n lidar-arch pytest -m "not slow" -v`
Expected: all unit tests PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with setup and usage"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push -u origin main
```

---

## Self-review notes

- **Spec coverage:** `run` command (§6) ✓ T10; EPT fetch + CRS dance (§5.1) ✓ T4/T5; class-2 trust ✓ T4; hole-fill (§5.2) ✓ T6; SVF/LRM/Slope (§5.3) ✓ T7-T9; GeoTIFF+PNG outputs ✓ T7-T9; Pueblo Grande regression (§8) ✓ T11; error handling — empty output ✓ T5, out-of-coverage ✓ T10; toolchain (§7) ✓ T0 + setup script.
- **Deferred to M2 (not in this plan):** openness, RRIM, `--reclassify`, auto-lookup, Casa Grande, split subcommands.
- **Runtime checks flagged:** rvt `sky_view_factor` signature (T9 Step 1); LRM uses the doc's scipy definition rather than rvt to avoid API risk on the canal-finder.
```
