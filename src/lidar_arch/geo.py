"""CRS conversions for the EPT pipeline. The bbox CRS dance lives here, isolated
so it can be unit-tested without touching PDAL or the network."""
import math

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


def bbox_area_km2(bbox):
    """Approximate ground area (km^2) of a lon/lat bbox via cos(lat) scaling.

    bbox = (min_lon, min_lat, max_lon, max_lat). Good enough for picking a grid
    resolution; one degree of latitude ~= 111.32 km, longitude shrinks by
    cos(center latitude)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    center_lat = (min_lat + max_lat) / 2.0
    height_km = abs(max_lat - min_lat) * 111.32
    width_km = abs(max_lon - min_lon) * 111.32 * math.cos(math.radians(center_lat))
    return width_km * height_km


def auto_resolution(bbox):
    """Pick a DTM grid resolution (metres) from a lon/lat bbox's area.

    Larger areas get coarser grids so big requests stay fast: area < 0.25 km^2
    -> 1.0 m; < 2 -> 2.0; < 10 -> 3.0; else 5.0."""
    area = bbox_area_km2(bbox)
    if area < 0.25:
        return 1.0
    if area < 2.0:
        return 2.0
    if area < 10.0:
        return 3.0
    return 5.0
