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
