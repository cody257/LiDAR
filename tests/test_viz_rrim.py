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


def _half_flat_half_slope(n=30, break_x=15):
    """Flat (z=0) for x < break_x, then a 45-degree ramp (1 m rise per 1 m cell)."""
    yy, xx = np.mgrid[0:n, 0:n]
    z = np.zeros((n, n), dtype="float64")
    ramp = (xx - break_x).astype("float64")
    z = np.where(xx >= break_x, ramp, 0.0)
    return z.astype("float32")


def test_rrim_tif_is_3band_uint8(tmp_path):
    arr = _half_flat_half_slope()
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.rrim(src, tmp_path / "rrim.tif")
    with rasterio.open(out) as r:
        assert r.count == 3
        assert r.dtypes[0] == "uint8"
        assert (r.height, r.width) == arr.shape
        assert r.crs.to_epsg() == 26912
    assert png.exists()


def test_rrim_steep_is_red_dominant_flat_is_neutral(tmp_path):
    arr = _half_flat_half_slope(n=30, break_x=15)
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.rrim(src, tmp_path / "rrim.tif")
    with rasterio.open(out) as r:
        red = r.read(1).astype("float64")
        blue = r.read(3).astype("float64")
    # interior STEEP block (well inside the 45-degree ramp, away from edges)
    steep_r = red[10:20, 20:28].mean()
    steep_b = blue[10:20, 20:28].mean()
    # interior FLAT block (well inside the flat half)
    flat_r = red[10:20, 2:10].mean()
    flat_b = blue[10:20, 2:10].mean()
    assert steep_r > steep_b + 20          # red clearly dominant on the slope
    assert abs(flat_r - flat_b) < 10       # roughly neutral on the flat
