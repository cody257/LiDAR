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


def test_openness_shape_finite_and_png(tmp_path):
    arr = np.zeros((40, 40), dtype="float32")
    arr[18:22, 18:22] = -3.0
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.openness(src, tmp_path / "opns.tif")
    with rasterio.open(out) as r:
        opns = r.read(1)
        assert r.crs.to_epsg() == 26912
    assert opns.shape == arr.shape
    assert np.isfinite(opns).all()
    assert png.exists()


def test_positive_openness_peak_greater_than_pit(tmp_path):
    """Positive openness is convex-favouring: a peak opens wider than a pit."""
    arr = np.zeros((40, 40), dtype="float32")
    arr[10, 10] = 5.0       # a peak
    arr[30, 30] = -5.0      # a pit
    src = tmp_path / "dtm.tif"; _dtm(src, arr)
    out, png = viz.openness(src, tmp_path / "opns.tif")
    with rasterio.open(out) as r:
        opns = r.read(1)
    assert opns[10, 10] > opns[30, 30]
