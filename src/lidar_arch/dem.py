"""Finalize the bare-earth DTM: fill nodata holes left by sparse desert ground
returns before any derivative is computed (holes ruin LRM/SVF)."""
import rasterio
from rasterio.fill import fillnodata


def fill_holes(in_tif, out_tif, max_distance=25):
    """Fill nodata in a single-band DTM via IDW interpolation. Returns out_tif."""
    with rasterio.open(in_tif) as src:
        arr = src.read(1)
        mask = src.read_masks(1)  # 0 where nodata, 255 where valid
        profile = src.profile
    filled = fillnodata(arr, mask=mask, max_search_distance=max_distance)
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(filled, 1)
    return out_tif
