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
