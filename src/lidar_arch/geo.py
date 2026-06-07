"""CRS conversions for the EPT pipeline. The bbox CRS dance lives here, isolated
so it can be unit-tested without touching PDAL or the network."""
from pyproj import Transformer

_TO_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


def bbox_to_3857(min_lon, min_lat, max_lon, max_lat):
    """lat/lon bbox -> (xmin, ymin, xmax, ymax) in EPSG:3857 (EPT native CRS)."""
    xmin, ymin = _TO_3857.transform(min_lon, min_lat)
    xmax, ymax = _TO_3857.transform(max_lon, max_lat)
    return (xmin, ymin, xmax, ymax)


def to_4326(x, y):
    """EPSG:3857 (x, y) -> (lon, lat)."""
    return _TO_4326.transform(x, y)
