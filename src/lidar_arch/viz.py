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
