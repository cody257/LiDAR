from pathlib import Path
from click.testing import CliRunner
from lidar_arch import cli, fetch, dem, viz

BBOX = ["-111.9856", "33.4452", "-111.9816", "33.4482"]


def _patch_pipeline(monkeypatch, calls):
    monkeypatch.setattr(fetch, "fetch_dtm",
                        lambda *a, **k: (calls.append("fetch"), a[2])[1])
    monkeypatch.setattr(dem, "fill_holes",
                        lambda src, out, **k: (calls.append("fill"), out)[1])
    for name in ("svf", "lrm", "slope", "openness", "rrim"):
        monkeypatch.setattr(
            viz, name,
            (lambda n: lambda *a, **k: (calls.append(n), (a[1], a[1]))[1])(name))


def test_run_orchestrates_default(monkeypatch, tmp_path):
    calls = []
    _patch_pipeline(monkeypatch, calls)
    out = tmp_path / "o"
    r = CliRunner().invoke(cli.cli, ["run", "--bbox", *BBOX, "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert calls == ["fetch", "fill", "svf", "lrm", "slope", "openness", "rrim"]


def test_run_products_subset(monkeypatch, tmp_path):
    calls = []
    _patch_pipeline(monkeypatch, calls)
    out = tmp_path / "o"
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *BBOX, "--out", str(out), "--products", "svf,slope"])
    assert r.exit_code == 0, r.output
    assert calls == ["fetch", "fill", "svf", "slope"]


def test_run_rejects_unknown_product(monkeypatch, tmp_path):
    calls = []
    _patch_pipeline(monkeypatch, calls)
    out = tmp_path / "o"
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *BBOX, "--out", str(out), "--products", "svf,bogus"])
    assert r.exit_code != 0
    assert "bogus" in r.output.lower()
    # nothing should have been computed
    assert "svf" not in calls


def test_run_rejects_out_of_coverage(tmp_path):
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", "-80.0", "40.0", "-79.99", "40.01",
        "--out", str(tmp_path / "o")])
    assert r.exit_code != 0
    assert "coverage" in r.output.lower()


# --- generalized --resource / --out-srs ---------------------------------------

DENVER_BBOX = ["-105.01", "39.73", "-104.99", "39.75"]
DENVER_EPT = ("https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"
              "AZ_MaricopaPinal_1_2020/ept.json")


def _capture_fetch(monkeypatch, seen):
    """Patch the pipeline and record the Resource handed to fetch_dtm."""
    monkeypatch.setattr(
        fetch, "fetch_dtm",
        lambda *a, **k: (seen.update(resource=a[1]), a[2])[1])
    monkeypatch.setattr(dem, "fill_holes", lambda src, out, **k: out)
    for name in ("svf", "lrm", "slope", "openness", "rrim"):
        monkeypatch.setattr(viz, name, lambda *a, **k: a[1])


def test_run_resource_url_uses_ept_and_auto_utm(monkeypatch, tmp_path):
    # Denver bbox with an explicit EPT URL: out-srs auto must derive 26913,
    # the URL must reach fetch, and the Phoenix coverage check must be skipped.
    seen = {}
    _capture_fetch(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *DENVER_BBOX, "--out", str(tmp_path / "o"),
        "--resource", DENVER_EPT])
    assert r.exit_code == 0, r.output
    assert seen["resource"].ept_url == DENVER_EPT
    assert seen["resource"].target_srs == "EPSG:26913"
    assert "coverage" not in r.output.lower()


def test_run_default_uses_phoenix_and_auto_resolves_26912(monkeypatch, tmp_path):
    # No --resource: Phoenix collection, and out-srs auto naturally yields 26912.
    seen = {}
    _capture_fetch(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *BBOX, "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    assert seen["resource"].name == "AZ_MaricopaPinal_1_2020"
    assert seen["resource"].target_srs == "EPSG:26912"


def test_run_explicit_out_srs_passthrough(monkeypatch, tmp_path):
    # An explicit --out-srs overrides auto for an arbitrary resource.
    seen = {}
    _capture_fetch(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *DENVER_BBOX, "--out", str(tmp_path / "o"),
        "--resource", DENVER_EPT, "--out-srs", "EPSG:6342"])
    assert r.exit_code == 0, r.output
    assert seen["resource"].target_srs == "EPSG:6342"


# --- --resolution auto / explicit ---------------------------------------------

def _capture_resolution(monkeypatch, seen):
    """Patch the pipeline and record the resolution handed to fetch_dtm."""
    monkeypatch.setattr(
        fetch, "fetch_dtm",
        lambda *a, **k: (seen.update(resolution=a[3]), a[2])[1])
    monkeypatch.setattr(dem, "fill_holes", lambda src, out, **k: out)
    for name in ("svf", "lrm", "slope", "openness", "rrim"):
        monkeypatch.setattr(viz, name, lambda *a, **k: a[1])


def test_run_resolution_auto_uses_area_based_value(monkeypatch, tmp_path):
    # Default (auto): the Pueblo Grande box is tiny -> auto_resolution -> 1.0.
    seen = {}
    _capture_resolution(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, ["run", "--bbox", *BBOX, "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    from lidar_arch import geo
    expected = geo.auto_resolution(tuple(float(v) for v in BBOX))
    assert seen["resolution"] == expected == 1.0


def test_run_resolution_auto_scales_with_larger_bbox(monkeypatch, tmp_path):
    # A larger box must auto-resolve coarser than 1.0 (proves area flows through,
    # not a coincidental 1.0 default). ~0.04 deg square near Phoenix ~ 14 km2.
    seen = {}
    _capture_resolution(monkeypatch, seen)
    big = ["-111.9856", "33.4452", "-111.9456", "33.4852"]
    r = CliRunner().invoke(cli.cli, ["run", "--bbox", *big, "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    from lidar_arch import geo
    expected = geo.auto_resolution(tuple(float(v) for v in big))
    assert seen["resolution"] == expected
    assert seen["resolution"] > 1.0


def test_run_resolution_auto_explicit_string(monkeypatch, tmp_path):
    # Passing the literal "auto" behaves like the default.
    seen = {}
    _capture_resolution(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *BBOX, "--out", str(tmp_path / "o"), "--resolution", "auto"])
    assert r.exit_code == 0, r.output
    assert seen["resolution"] == 1.0


def test_run_resolution_explicit_float(monkeypatch, tmp_path):
    # An explicit float overrides auto and flows straight to fetch_dtm.
    seen = {}
    _capture_resolution(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *BBOX, "--out", str(tmp_path / "o"), "--resolution", "2.5"])
    assert r.exit_code == 0, r.output
    assert seen["resolution"] == 2.5


def test_run_resolution_rejects_garbage(monkeypatch, tmp_path):
    # A non-numeric, non-"auto" value is a usage error.
    seen = {}
    _capture_resolution(monkeypatch, seen)
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", *BBOX, "--out", str(tmp_path / "o"), "--resolution", "fine"])
    assert r.exit_code != 0
    assert "resolution" in r.output.lower()
