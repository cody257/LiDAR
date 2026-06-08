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


def bbox_within(bbox_3857, extent_3857):
    """True if bbox_3857 (xmin,ymin,xmax,ymax) lies fully inside extent_3857."""
    xmin, ymin, xmax, ymax = bbox_3857
    exmin, eymin, exmax, eymax = extent_3857
    return exmin <= xmin and eymin <= ymin and xmax <= exmax and ymax <= eymax


def utm_epsg_for_bbox(bbox):
    """NAD83 UTM North EPSG (int) for a lon/lat bbox center.

    bbox = (min_lon, min_lat, max_lon, max_lat). Zone from the center longitude;
    EPSG = 26900 + zone (e.g. zone 12 -> 26912)."""
    min_lon, _min_lat, max_lon, _max_lat = bbox
    center_lon = (min_lon + max_lon) / 2.0
    zone = int((center_lon + 180) // 6) + 1
    return 26900 + zone
