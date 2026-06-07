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


def _write_tif_rgb(out_tif, rgb_uint8, profile):
    """Write an (H, W, 3) uint8 RGB array as a 3-band GeoTIFF (same CRS/transform)."""
    p = profile.copy()
    p.update(dtype="uint8", count=3)
    p.pop("nodata", None)
    with rasterio.open(out_tif, "w", **p) as dst:
        for b in range(3):
            dst.write(rgb_uint8[..., b], b + 1)
    return out_tif


def _write_png(src_tif, png_path):
    """8-bit auto-stretched PNG preview of a single-band raster."""
    gdal.Translate(str(png_path), str(src_tif), format="PNG",
                   outputType=gdal.GDT_Byte, scaleParams=[[]])
    return png_path


def _clip_range(arr, lo=2, hi=98, symmetric=False):
    """Percentile clip bounds from the finite values of arr.

    Returns (vmin, vmax). If symmetric, v = percentile(|finite|, hi) and the
    range is centred at zero: (-v, +v) (for diverging colormaps like RdBu_r).
    """
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return (0.0, 1.0)
    if symmetric:
        v = float(np.percentile(np.abs(finite), hi))
        if v == 0.0:
            v = 1.0
        return (-v, v)
    vmin = float(np.percentile(finite, lo))
    vmax = float(np.percentile(finite, hi))
    if vmin == vmax:
        vmax = vmin + 1.0
    return (vmin, vmax)


def _colorize(arr, cmap_name, vmin, vmax):
    """Map a 2-D array to an (H, W, 3) uint8 RGB image with a matplotlib cmap.

    arr is normalised to [0, 1] over [vmin, vmax] (clipped), the colormap is
    applied, and the alpha channel dropped. Non-finite cells (NaN / nodata)
    are rendered white so previews carry no garbage.
    """
    from matplotlib import colormaps
    finite = np.isfinite(arr)
    span = vmax - vmin
    if span == 0:
        span = 1.0
    norm = np.clip((np.where(finite, arr, vmin) - vmin) / span, 0.0, 1.0)
    cmap = colormaps[cmap_name]
    rgba = cmap(norm)                       # (H, W, 4) float in [0, 1]
    rgb = (rgba[..., :3] * 255).round().astype("uint8")
    rgb[~finite] = (255, 255, 255)          # NaN / nodata -> white
    return rgb


def _write_png_rgb(path, rgb_uint8):
    """Write an (H, W, 3) uint8 array as an RGB PNG (matplotlib-base, no Pillow)."""
    import matplotlib.image as mpimg
    mpimg.imsave(str(path), rgb_uint8)
    return Path(path)


def _write_colorized_png(path, arr, cmap_name, lo=2, hi=98, symmetric=False,
                         vmin=None, vmax=None):
    """Colorize a 2-D array with a clipped matplotlib cmap and write an RGB PNG.

    If vmin/vmax are given they override the percentile clip; otherwise the
    bounds come from _clip_range(arr, lo, hi, symmetric).
    """
    if vmin is None or vmax is None:
        vmin, vmax = _clip_range(arr, lo=lo, hi=hi, symmetric=symmetric)
    rgb = _colorize(arr, cmap_name, vmin, vmax)
    return _write_png_rgb(path, rgb)


def _pixel_size(profile):
    return abs(profile["transform"].a)


def slope(dtm_tif, out_tif, png=True):
    """Slope in degrees via gdaldem. Returns (geotiff_path, png_path).

    Preview: inferno colormap, vmin=0, vmax=p98 (flat dark, steep bright).
    """
    gdal.DEMProcessing(str(out_tif), str(dtm_tif), "slope",
                       slopeFormat="degree", computeEdges=True)
    png_path = Path(out_tif).with_suffix(".png")
    if png:
        slope_arr, _ = _read(out_tif)
        _, vmax = _clip_range(slope_arr, hi=98)
        _write_colorized_png(png_path, slope_arr, "inferno", vmin=0.0, vmax=vmax)
    return Path(out_tif), png_path


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
        # Diverging RdBu_r centred at 0: mounds red, hollows blue.
        _write_colorized_png(png_path, lrm_arr, "RdBu_r", hi=98, symmetric=True)
    return Path(out_tif), png_path


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
        _write_colorized_png(png_path, svf_arr, "gray", lo=2, hi=98)
    return Path(out_tif), png_path


def _positive_openness(arr, res, n_dir, r_max):
    """Positive topographic openness (degrees) via rvt sky_view_factor."""
    import rvt.vis
    return rvt.vis.sky_view_factor(
        dem=arr, resolution=res,
        compute_svf=False, compute_asvf=False, compute_opns=True,
        svf_n_dir=n_dir, svf_r_max=r_max,
    )["opns"]


def openness(dtm_tif, out_tif, n_dir=16, r_max=10, png=True):
    """Positive topographic openness via rvt-py. Returns (geotiff, png).

    Convex terrain (peaks, ridges) reads high; concave terrain (pits, ditches)
    reads low, so it complements SVF for spotting archaeological earthworks.
    Preview: gray colormap, clip (2, 98).
    """
    arr, profile = _read(dtm_tif)
    res = _pixel_size(profile)
    opns_arr = _positive_openness(arr, res, n_dir, r_max)
    _write_tif(out_tif, opns_arr, profile)
    png_path = Path(out_tif).with_suffix(".png")
    if png:
        _write_colorized_png(png_path, opns_arr, "gray", lo=2, hi=98)
    return Path(out_tif), png_path


def rrim(dtm_tif, out_tif, n_dir=16, r_max=10, png=True):
    """Red Relief Image Map: a self-contained slope x openness composite.

    Slope drives a Reds colormap (flat ~white, steep -> dark red); the
    positive-minus-negative openness difference drives brightness (ridges
    bright, hollows dark) via a multiply blend. Result is a 3-band uint8 RGB
    GeoTIFF plus an RGB PNG. Returns (geotiff, png).
    """
    from matplotlib import colormaps
    arr, profile = _read(dtm_tif)
    res = _pixel_size(profile)

    # Slope in degrees from the array (NaNs propagate).
    gy, gx = np.gradient(arr, res)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    # Openness difference: ridges > 0, hollows < 0.
    pos = _positive_openness(arr, res, n_dir, r_max)
    neg = _positive_openness(-arr, res, n_dir, r_max)
    diff = pos - neg

    # Red layer: steepness -> deeper red.
    t_slope = np.clip(slope_deg / 45.0, 0.0, 1.0)
    red = colormaps["Reds"](t_slope)[..., :3]          # (H, W, 3) float in [0, 1]

    # Lightness from openness difference, centred on 0.5.
    fd = diff[np.isfinite(diff)]
    v = float(np.percentile(np.abs(fd), 98)) if fd.size else 1.0
    if v == 0.0:
        v = 1.0
    light = np.clip(0.5 + diff / (2.0 * v), 0.0, 1.0)

    # Multiply blend; non-finite cells -> white.
    rrim_f = red * light[..., None]
    rgb = (rrim_f * 255.0).astype("uint8")
    finite = np.isfinite(slope_deg) & np.isfinite(diff)
    rgb[~finite] = (255, 255, 255)

    _write_tif_rgb(out_tif, rgb, profile)
    png_path = Path(out_tif).with_suffix(".png")
    if png:
        _write_png_rgb(png_path, rgb)
    return Path(out_tif), png_path
