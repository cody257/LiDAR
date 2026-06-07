from pathlib import Path
from click.testing import CliRunner
from lidar_arch import cli, fetch, dem, viz


def test_run_orchestrates(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(fetch, "fetch_dtm",
                        lambda *a, **k: (calls.append("fetch"), a[2])[1])
    monkeypatch.setattr(dem, "fill_holes",
                        lambda src, out, **k: (calls.append("fill"), out)[1])
    monkeypatch.setattr(viz, "svf", lambda *a, **k: (calls.append("svf"), (a[1], a[1]))[1])
    monkeypatch.setattr(viz, "lrm", lambda *a, **k: (calls.append("lrm"), (a[1], a[1]))[1])
    monkeypatch.setattr(viz, "slope", lambda *a, **k: (calls.append("slope"), (a[1], a[1]))[1])

    out = tmp_path / "o"
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", "-111.9856", "33.4452", "-111.9816", "33.4482",
        "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert calls == ["fetch", "fill", "svf", "lrm", "slope"]


def test_run_rejects_out_of_coverage(tmp_path):
    r = CliRunner().invoke(cli.cli, [
        "run", "--bbox", "-80.0", "40.0", "-79.99", "40.01",
        "--out", str(tmp_path / "o")])
    assert r.exit_code != 0
    assert "coverage" in r.output.lower()
