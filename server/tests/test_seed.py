"""What a fresh install has before anyone configures it."""

import pytest

pytestmark = pytest.mark.db


def test_setup_seeds_searxng_twice_and_thai_journals(browser, bootstrap_code, monkeypatch):
    from litstorm.api.auth import ACADEMIC_ENGINES

    monkeypatch.setenv("LITSTORM_SEARXNG_URL", "http://searxng:8080/search")
    admin = browser()
    r = admin.post("/api/setup", json={"code": bootstrap_code, "email": "a@example.org", "name": "A",
                                       "password": "correct horse"})
    assert r.status_code == 200, r.text
    seeded = {p["label"]: p for p in admin.get("/api/admin/search-providers").json()}
    assert set(seeded) == {"SearXNG", "SearXNG LDR-academic", "TCI-ThaiJO"}
    assert seeded["TCI-ThaiJO"]["kind"] == "tci" and not seeded["TCI-ThaiJO"]["is_default"]
    # The web search is the default; the academic one is the same instance
    # asked only its academic engines.
    assert seeded["SearXNG"]["is_default"] and not seeded["SearXNG"]["engines"]
    assert not seeded["SearXNG LDR-academic"]["is_default"]
    assert seeded["SearXNG LDR-academic"]["engines"] == ACADEMIC_ENGINES
    assert "semantic scholar" in ACADEMIC_ENGINES and "base" not in ACADEMIC_ENGINES.split(",")
