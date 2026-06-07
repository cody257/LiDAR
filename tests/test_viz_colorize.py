import numpy as np
from lidar_arch import viz


def test_clip_range_symmetric():
    arr = np.array([[-5.0, -1.0, 0.0], [1.0, 2.0, 50.0]])
    vmin, vmax = viz._clip_range(arr, lo=2, hi=98, symmetric=True)
    assert vmin == -vmax
    assert vmax > 0
    # symmetric uses the high percentile of |finite|
    expected = np.percentile(np.abs(arr), 98)
    assert abs(vmax - expected) < 1e-9


def test_clip_range_ignores_nonfinite():
    arr = np.array([[np.nan, 0.0, 1.0], [2.0, 3.0, np.inf]])
    vmin, vmax = viz._clip_range(arr, lo=0, hi=100, symmetric=False)
    assert vmin == 0.0
    assert vmax == 3.0


def test_colorize_shape_dtype_and_range():
    arr = np.linspace(0.0, 1.0, 12).reshape(3, 4)
    rgb = viz._colorize(arr, "gray", 0.0, 1.0)
    assert rgb.shape == (3, 4, 3)
    assert rgb.dtype == np.uint8
    assert rgb.min() >= 0 and rgb.max() <= 255


def test_colorize_nan_is_white():
    arr = np.array([[0.0, 0.5], [1.0, np.nan]])
    rgb = viz._colorize(arr, "viridis", 0.0, 1.0)
    assert tuple(rgb[1, 1]) == (255, 255, 255)
    # a finite cell should not be forced white
    assert tuple(rgb[0, 0]) != (255, 255, 255)


def test_write_png_rgb(tmp_path):
    rgb = np.zeros((4, 6, 3), dtype="uint8")
    rgb[..., 0] = 200
    out = tmp_path / "rgb.png"
    p = viz._write_png_rgb(out, rgb)
    assert p.exists()
    assert p.stat().st_size > 0
    import rasterio
    with rasterio.open(p) as ds:
        assert ds.count >= 3  # RGB (imsave may add an alpha band)
