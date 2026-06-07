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
