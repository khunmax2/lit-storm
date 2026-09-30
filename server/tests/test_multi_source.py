"""Several Search Providers in one STORM Run (docs/web-app-design.md,
รุ่นสอง: ค้นหลายแหล่งต่อ Run): results taken from each in turn, a URL once,
the budget shared, a failed source skipped and said so."""

from types import SimpleNamespace

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)


class _Source:
    def __init__(self, name, urls, fail=False):
        self.name, self.urls, self.fail = name, urls, fail
        self.asked = []

    def forward(self, queries, exclude_urls=()):
        self.asked.append(list(queries))
        if self.fail:
            raise ConnectionError("down")
        return [{"url": u, "snippets": [u]} for u in self.urls if u not in exclude_urls]

    def get_usage_and_reset(self):
        return {"SearXNG": len(self.asked)}


@pytest.mark.slow
def test_results_come_from_each_source_in_turn_each_url_once():
    from knowledge_storm.rm import MultiRM

    a = _Source("A", ["a1", "shared", "a3"])
    b = _Source("B", ["shared", "b2"])
    rm = MultiRM([a, b], k=3, names=["A", "B"])
    assert [r["url"] for r in rm.forward("q", exclude_urls=["a3"])] == ["a1", "shared", "b2"]
    # Two sources of one kind: their searches add up, not overwrite.
    assert rm.get_usage_and_reset() == {"SearXNG": 2}


@pytest.mark.slow
def test_a_source_that_fails_is_skipped_and_named():
    from knowledge_storm.rm import MultiRM

    rm = MultiRM([_Source("A", [], fail=True), _Source("B", ["b1"])], names=["TCI", "SearXNG"])
    assert [r["url"] for r in rm.forward(["q1", "q2"])] == ["b1"]
    assert rm.failures == {"TCI": (2, "ConnectionError: down")}
    assert rm.refused == 2 and "TCI: ConnectionError: down" in rm.last_refusal


@pytest.mark.slow
def test_the_budget_per_query_is_shared_out(monkeypatch):
    from knowledge_storm.rm import MultiRM

    from litstorm.engines.storm import engine, providers

    built = []
    monkeypatch.setattr(providers, "build_rm", lambda search, key, k, timeout: built.append((search["label"], key, k)) or _Source(search["label"], []))
    config = SimpleNamespace(
        search={"provider": "searxng", "label": "S"}, search_extra=[{"provider": "tci", "label": "T"}, {"provider": "tavily", "label": "V"}],
        request_timeout=5, search_cache_dir=None,
    )
    secrets = SimpleNamespace(search_api_key="", search_extra_api_keys=("", "tvly-1"))
    rm = engine.build_search(config, secrets, 3)
    assert isinstance(rm, MultiRM) and rm.names == ["S", "T", "V"]
    assert built == [("S", "", 1), ("T", "", 1), ("V", "tvly-1", 1)]
    built.clear()
    one = engine.build_search(SimpleNamespace(**{**config.__dict__, "search_extra": []}), secrets, 3)
    assert not isinstance(one, MultiRM) and built == [("S", "", 3)]


# --- the Run -----------------------------------------------------------------------


@pytest.fixture
def sources(admin, configured):
    model, arxiv = configured
    tci = admin.post("/api/admin/search-providers", json={"label": "TCI", "kind": "tci"}).json()
    tavily = admin.post("/api/admin/search-providers",
                        json={"label": "Tavily", "kind": "tavily", "api_key": "tvly-secret-1"}).json()
    return arxiv, tci, tavily


@pytest.mark.db
def test_a_storm_run_keeps_its_other_sources_and_the_worker_gets_their_keys(admin, browser, sources, db):
    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.worker import queue

    arxiv, tci, tavily = sources
    user = make_user(admin, browser)
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "search_provider_id": arxiv["id"],
                                         "extra_search_provider_ids": [tci["id"], tavily["id"], arxiv["id"]]})
    assert r.status_code == 201, r.text
    run = r.json()["runs"][0]
    assert run["search_label"] == "arXiv + TCI + Tavily"
    kept = db.get(Run, run["id"]).config["search_extra"]
    assert [x["label"] for x in kept] == ["TCI", "Tavily"] and "tvly" not in str(kept)

    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert [x["provider"] for x in claim.config.search_extra] == ["tci", "tavily"]
    assert claim.secrets.search_extra_api_keys == ("", "tvly-secret-1")

    # Tried again after it failed, it searches the same sources.
    db.expire_all()
    stored = db.get(Run, run["id"])
    stored.status, stored.reason = "failed", "retries_exhausted"
    db.commit()
    again = user.post(f"/api/runs/{run['id']}/retry").json()
    assert again["search_label"] == "arXiv + TCI + Tavily"


@pytest.mark.db
def test_one_source_switched_off_is_left_out_when_the_run_starts(admin, browser, sources):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    arxiv, tci, tavily = sources
    user = make_user(admin, browser)
    user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "search_provider_id": arxiv["id"],
                                     "extra_search_provider_ids": [tci["id"], tavily["id"]]})
    admin.put(f"/api/admin/search-providers/{tavily['id']}", json={**tavily, "enabled": False})
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert [x["provider"] for x in claim.config.search_extra] == ["tci"] and claim.secrets.search_extra_api_keys == ("",)


@pytest.mark.db
def test_only_an_engine_that_can_search_several_is_given_several(admin, browser, sources):
    arxiv, tci, tavily = sources
    user = make_user(admin, browser)
    body = {"topic": "Songkran", "language": "th", "search_provider_id": tavily["id"]}
    r = user.post("/api/sessions", json={**body, "engine": "deep", "extra_search_provider_ids": [tci["id"]]})
    assert r.json()["detail"] == "too_many_sources"
    r = user.post("/api/sessions", json={**body, "extra_search_provider_ids": [tci["id"], arxiv["id"]]})
    assert r.status_code == 201  # three in all
    arxiv2 = admin.post("/api/admin/search-providers", json={"label": "arXiv 2", "kind": "arxiv"}).json()
    r = user.post("/api/sessions", json={**body, "extra_search_provider_ids": [tci["id"], arxiv["id"], arxiv2["id"]]})
    assert r.json()["detail"] == "too_many_sources"  # four
    storm = next(e for e in user.get("/api/options").json()["engines"] if e["id"] == "storm")
    assert storm["max_sources"] == 3
