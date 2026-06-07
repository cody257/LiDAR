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
