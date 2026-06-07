import pytest
from lidar_arch import fetch, resources


class _FakePipe:
    def __init__(self, n): self._n = n
    def execute(self): return self._n


def test_fetch_dtm_raises_on_zero_points(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "_pipeline", lambda d: _FakePipe(0))
    with pytest.raises(RuntimeError, match="No points"):
        fetch.fetch_dtm((-12466000.0, 3953000.0, -12465000.0, 3954000.0),
                        resources.PHOENIX, tmp_path / "dtm_raw.tif")


def test_fetch_dtm_returns_path_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "_pipeline", lambda d: _FakePipe(123))
    out = tmp_path / "dtm_raw.tif"
    result = fetch.fetch_dtm((-12466000.0, 3953000.0, -12465000.0, 3954000.0),
                             resources.PHOENIX, out)
    assert result == out
