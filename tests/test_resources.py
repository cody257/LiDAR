from lidar_arch import resources


def test_resolve_returns_phoenix():
    r = resources.resolve()
    assert r.name == "AZ_MaricopaPinal_1_2020"
    assert r.ept_url.endswith("/AZ_MaricopaPinal_1_2020/ept.json")
    assert r.target_srs == "EPSG:26912"
    assert len(r.extent_3857) == 4
    xmin, ymin, xmax, ymax = r.extent_3857
    assert xmin < xmax and ymin < ymax


def test_from_ept_parses_name_from_url():
    url = ("https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"
           "CO_DenverDRCOG_2020/ept.json")
    r = resources.from_ept(url, "EPSG:26913")
    assert r.name == "CO_DenverDRCOG_2020"
    assert r.ept_url == url
    assert r.target_srs == "EPSG:26913"
    assert r.extent_3857 is None


def test_from_ept_explicit_name_overrides():
    url = "https://example.com/usgs-lidar-public/WA_Seattle/ept.json"
    r = resources.from_ept(url, "EPSG:26910", name="Seattle override")
    assert r.name == "Seattle override"
    assert r.target_srs == "EPSG:26910"
