import datetime as dt
import io

import pytest

from aquaos.data import cache as cache_mod
from aquaos.data.cache import DataCache, OfflineCacheMiss
from aquaos.data.provenance import Provenance

TEMPLATE = Provenance(title="t", kind="primary", source_url="https://example.gov/x", retrieved=dt.date(2026, 1, 1))


def test_put_get_roundtrip_records_sha(tmp_path):
    c = DataCache(tmp_path, offline=True)
    assert c.get("a/b.csv") is None
    hit = c.put("a/b.csv", b"hello", TEMPLATE)
    again = c.get("a/b.csv")
    assert again is not None and again.path.read_bytes() == b"hello"
    assert again.provenance.sha256 == hit.provenance.sha256 and len(hit.provenance.sha256 or "") == 64


def test_offline_miss_raises(tmp_path):
    with pytest.raises(OfflineCacheMiss):
        DataCache(tmp_path, offline=True).fetch("x.csv", "https://example.gov/x", TEMPLATE)


def test_fetch_downloads_once_then_serves_cache(tmp_path, monkeypatch):
    calls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return Resp(b"data")

    monkeypatch.setattr(cache_mod.urllib.request, "urlopen", fake_urlopen)
    c = DataCache(tmp_path, offline=False)
    h1 = c.fetch("x.csv", "https://example.gov/x", TEMPLATE)
    h2 = c.fetch("x.csv", "https://example.gov/x", TEMPLATE)
    assert calls == ["https://example.gov/x"]
    assert h1.path.read_bytes() == h2.path.read_bytes() == b"data"
    assert h2.provenance.retrieved == dt.date.today()
    c.fetch("x.csv", "https://example.gov/x", TEMPLATE, refresh=True)
    assert len(calls) == 2
