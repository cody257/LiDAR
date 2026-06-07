"""The svf/lrm/slope PNG previews are colormapped (RGB), not 1-band grayscale.
LRM in particular is a diverging RdBu_r map centred at zero: mounds red, hollows blue."""
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


def _png_bands(png_path):
    with rasterio.open(png_path) as ds:
        return ds.count


def test_slope_preview_is_rgb(tmp_path):
    yy, xx = np.mgrid[0:30, 0:30]
    arr = xx.astype("float32")
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.slope(src, tmp_path / "slope.tif")
    assert png.exists()
    assert _png_bands(png) >= 3


def test_svf_preview_is_rgb(tmp_path):
    arr = np.zeros((40, 40), dtype="float32")
    arr[18:22, 18:22] = -3.0
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.svf(src, tmp_path / "svf.tif")
    assert png.exists()
    assert _png_bands(png) >= 3


def test_lrm_preview_diverging_centered(tmp_path):
    """A mound is red-dominant; a hollow is blue-dominant in the RdBu_r preview."""
    yy, xx = np.mgrid[0:60, 0:60]
    arr = np.zeros((60, 60), dtype="float64")
    arr[20, 20] += 2.0     # mound  -> positive LRM -> red
    arr[40, 40] -= 2.0     # hollow -> negative LRM -> blue
    src = tmp_path / "dtm.tif"; _dtm(src, arr.astype("float32"))
    out, png = viz.lrm(src, tmp_path / "lrm.tif", kernel_radius_m=10)
    assert png.exists()
    assert _png_bands(png) >= 3
    with rasterio.open(png) as ds:
        r = ds.read(1).astype("int32")
        b = ds.read(3).astype("int32")
    assert r[20, 20] > b[20, 20]   # mound red-dominant
    assert b[40, 40] > r[40, 40]   # hollow blue-dominant
