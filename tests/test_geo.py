from lidar_arch import geo

# AZ_MaricopaPinal_1_2020 data extent in EPSG:3857 (xmin, ymin, xmax, ymax)
EXTENT = (-12555542.0, 3847680.0, -12363850.0, 4010355.0)


def test_pueblo_grande_point_inside_extent():
    # tiny box around Pueblo Grande / S'edav Va'aki (lon, lat)
    x = geo.bbox_to_3857(-111.9856, 33.4452, -111.9816, 33.4482)
    xmin, ymin, xmax, ymax = x
    assert xmin < xmax and ymin < ymax
    assert EXTENT[0] <= xmin and EXTENT[1] <= ymin
    assert xmax <= EXTENT[2] and ymax <= EXTENT[3]


def test_roundtrip_recovers_latlon():
    lon, lat = -111.9836, 33.4467
    xmin, ymin, xmax, ymax = geo.bbox_to_3857(lon, lat, lon, lat)
    back = geo.to_4326(xmin, ymin)
    assert abs(back[0] - lon) < 1e-6
    assert abs(back[1] - lat) < 1e-6


def test_bbox_within_extent():
    inside = (-12466000.0, 3953000.0, -12465000.0, 3954000.0)
    outside = (-13000000.0, 3953000.0, -12999000.0, 3954000.0)
    assert geo.bbox_within(inside, EXTENT) is True
    assert geo.bbox_within(outside, EXTENT) is False


def test_utm_epsg_phoenix_zone_12():
    # Phoenix center ~-111.98 -> UTM 12N NAD83 -> 26912
    assert geo.utm_epsg_for_bbox((-111.9856, 33.4452, -111.9816, 33.4482)) == 26912


def test_utm_epsg_denver_zone_13():
    # Denver center ~-105 -> UTM 13N NAD83 -> 26913
    assert geo.utm_epsg_for_bbox((-105.01, 39.73, -104.99, 39.75)) == 26913


def test_utm_epsg_seattle_zone_10():
    # Seattle center ~-122.3 -> UTM 10N NAD83 -> 26910
    assert geo.utm_epsg_for_bbox((-122.34, 47.59, -122.32, 47.61)) == 26910


def test_utm_epsg_austin_zone_14():
    # Austin center ~-97.7 -> UTM 14N NAD83 -> 26914
    assert geo.utm_epsg_for_bbox((-97.75, 30.26, -97.73, 30.28)) == 26914


# --- auto_resolution: grid resolution from bbox area ---------------------------

def _box_km2(km2, lat=33.4467):
    """A lon/lat bbox centred at (lat) whose ground area is ~km2 (square)."""
    import math
    side_m = math.sqrt(km2) * 1000.0
    dlat = side_m / 111_320.0
    dlon = side_m / (111_320.0 * math.cos(math.radians(lat)))
    half_lon, half_lat = dlon / 2.0, dlat / 2.0
    return (-111.98 - half_lon, lat - half_lat, -111.98 + half_lon, lat + half_lat)


def test_auto_resolution_tiny_box_is_1m():
    # Pueblo Grande box (~0.12 km2) -> finest grid
    assert geo.auto_resolution((-111.9856, 33.4452, -111.9816, 33.4482)) == 1.0


def test_auto_resolution_small_area_1m():
    assert geo.auto_resolution(_box_km2(0.1)) == 1.0


def test_auto_resolution_medium_area_2m():
    assert geo.auto_resolution(_box_km2(1.0)) == 2.0


def test_auto_resolution_large_area_3m():
    assert geo.auto_resolution(_box_km2(5.0)) == 3.0


def test_auto_resolution_huge_area_5m():
    assert geo.auto_resolution(_box_km2(50.0)) == 5.0
