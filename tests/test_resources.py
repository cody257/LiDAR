from lidar_arch import resources


def test_resolve_returns_phoenix():
    r = resources.resolve()
    assert r.name == "AZ_MaricopaPinal_1_2020"
    assert r.ept_url.endswith("/AZ_MaricopaPinal_1_2020/ept.json")
    assert r.target_srs == "EPSG:26912"
    assert len(r.extent_3857) == 4
    xmin, ymin, xmax, ymax = r.extent_3857
    assert xmin < xmax and ymin < ymax
