import numpy as np
import rasterio
import pytest
from click.testing import CliRunner
from lidar_arch import cli

# Small box (~360 x 330 m) centred on Pueblo Grande / S'edav Va'aki.
BBOX = ["-111.9856", "33.4452", "-111.9816", "33.4482"]


@pytest.mark.slow
def test_pueblo_grande_end_to_end(tmp_path):
    out = tmp_path / "pg"
    r = CliRunner().invoke(cli.cli, ["run", "--bbox", *BBOX, "--out", str(out)])
    assert r.exit_code == 0, r.output
    for name in ("dtm.tif", "svf.tif", "lrm.tif", "slope.tif"):
        f = out / name
        assert f.exists(), f"missing {name}"
        with rasterio.open(f) as ds:
            assert ds.crs.to_epsg() == 26912
            band = ds.read(1, masked=True)
            assert band.count() > 0          # has valid (non-masked) data
            assert np.isfinite(band.mean())
