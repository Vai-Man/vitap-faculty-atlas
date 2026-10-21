"""Scraper helpers (failed requests, robots.txt) and the shipped dataset."""
import json

import pytest
import requests

from src import config, scraper, storage
from scripts.validate_dataset import validate


class FlakySession:
    """Fails ``fail_times`` times, then returns a 200 response."""

    def __init__(self, fail_times, status=200, exc=True):
        self.calls, self.fail_times, self.status, self.exc = 0, fail_times, status, exc

    def request(self, method, url, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            if self.exc:
                raise requests.ConnectionError("boom")
            r = requests.Response(); r.status_code = 503
            return r
        r = requests.Response(); r.status_code = self.status
        return r


def test_fetch_retries_then_succeeds():
    s = FlakySession(2)
    r = scraper.fetch_with_retry("https://x", session=s, retries=3, sleep=lambda _: None)
    assert r is not None and r.status_code == 200 and s.calls == 3


def test_fetch_gives_up_and_returns_none():
    s = FlakySession(10, exc=False)
    assert scraper.fetch_with_retry("https://x", session=s, retries=3, sleep=lambda _: None) is None
    assert s.calls == 3


def test_fetch_does_not_retry_404():
    s = FlakySession(0, status=404)
    r = scraper.fetch_with_retry("https://x", session=s, retries=3, sleep=lambda _: None)
    assert r.status_code == 404 and s.calls == 1


def test_robots_parsing():
    txt = "User-agent: *\nAllow: /\nDisallow: /vitiebot\n"  # the live file, 17 Oct 2026
    assert scraper.robots_allows("https://vitap.ac.in/allfaculty", robots_text=txt)
    assert not scraper.robots_allows("https://vitap.ac.in/vitiebot/x", robots_text=txt)


def test_snapshot_roundtrip_strips_phone(tmp_path, raw_records):
    snap = scraper.build_snapshot(raw_records, method="test")
    p = scraper.save_snapshot(snap, tmp_path / "s.json")
    loaded = scraper.load_snapshot(p)
    assert loaded["record_count"] == 5
    assert all("Contact_No" not in r for r in loaded["records"])


def test_load_snapshot_rejects_bad_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([1, 2]))
    with pytest.raises(ValueError):
        scraper.load_snapshot(p)


def test_storage_roundtrip(tmp_path, cleaned):
    recs, _ = cleaned
    storage.save_json(recs, tmp_path / "f.json", meta={"a": 1})
    assert storage.load_records(tmp_path / "f.json") == recs
    storage.save_csv(recs, tmp_path / "f.csv")
    storage.save_sqlite(recs, tmp_path / "f.db")
    import sqlite3
    with sqlite3.connect(tmp_path / "f.db") as con:
        assert con.execute("select count(*) from faculty").fetchone()[0] == 5
        assert con.execute("select count(*) from specialisation").fetchone()[0] == 9


# ---- checks on the real, shipped dataset --------------------------------
needs_data = pytest.mark.skipif(not config.FACULTY_JSON.exists(), reason="run the pipeline first")


@needs_data
def test_shipped_dataset_valid():
    assert validate(config.FACULTY_JSON) == []


@needs_data
def test_every_record_has_official_source_and_photo_or_flag():
    recs = storage.load_records()
    assert len(recs) > 500
    for r in recs:
        assert any(u.startswith("https://vitap.ac.in/") for u in r["source_urls"])
        assert r["photograph_url"] or "missing_photo" in r["quality_issues"]
        assert "contact_no" not in {k.lower() for k in r}
