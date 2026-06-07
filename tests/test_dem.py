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
