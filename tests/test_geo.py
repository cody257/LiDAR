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
