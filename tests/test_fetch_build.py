from lidar_arch import fetch


def test_build_pipeline_structure():
    bbox = (-12466000.0, 3953000.0, -12465000.0, 3954000.0)
    p = fetch.build_pipeline(bbox, "https://x/ept.json", "dtm_raw.tif",
                             resolution=1.0, target_srs="EPSG:26912")
    stages = p["pipeline"]
    # order is load-bearing: read (3857 bounds) -> reproject -> ground -> grid
    assert stages[0]["type"] == "readers.ept"
    assert stages[0]["filename"] == "https://x/ept.json"
    assert "-12466000" in stages[0]["bounds"] and "3953000" in stages[0]["bounds"]
    # the EPT read is capped to the grid resolution so we don't stream full
    # point density for a coarse grid (the big perf win)
    assert stages[0]["resolution"] == 1.0
    assert stages[1]["type"] == "filters.reprojection"
    assert stages[1]["out_srs"] == "EPSG:26912"
    assert stages[2]["type"] == "filters.range"
    assert stages[2]["limits"] == "Classification[2:2]"
    assert stages[3]["type"] == "writers.gdal"
    assert stages[3]["output_type"] == "idw"
    assert stages[3]["resolution"] == 1.0
