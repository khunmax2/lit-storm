"""Every Engine searches any Search Provider, or several (litstorm.engines.sources)."""

import asyncio
import json
import urllib.error
import urllib.request

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401 - a fixture


class _Source:
    def __init__(self, url="https://tci.test/1", fail=False):
        self.url, self.fail, self.calls = url, fail, 0

    def forward(self, query_or_queries, exclude_urls=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("down")
        return [{"url": self.url, "title": "บทความ", "description": "d", "snippets": ["ข้อความ", "อีกตอน"]}]

    def get_usage_and_reset(self):
        calls, self.calls = self.calls, 0
        return {"TciRM": calls}


def _get(url):
    return json.loads(urllib.request.urlopen(url, timeout=10).read())


def test_the_bridge_answers_as_searxng_does():
    from litstorm.engines.sources import SearchBridge

    with SearchBridge(_Source()) as bridge:
        assert bridge.url.startswith("http://127.0.0.1:") and bridge.url.endswith("/search")
        body = _get(bridge.url + "?q=%E0%B8%AA%E0%B8%87%E0%B8%81%E0%B8%A3%E0%B8%B2%E0%B8%99%E0%B8%95%E0%B9%8C&format=json")
        assert body["results"] == [{"url": "https://tci.test/1", "title": "บทความ", "content": "ข้อความ อีกตอน"}]
        assert body["unresponsive_engines"] == []
        assert bridge.usage() == {"TciRM": 1} and bridge.usage() == {"TciRM": 0}
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(bridge.url.replace("/search", "/other"), timeout=10)
        assert missing.value.code == 404


def test_a_failing_source_is_an_empty_answer_not_an_error():
    from litstorm.engines.sources import SearchBridge

    with SearchBridge(_Source(fail=True)) as bridge:
        assert _get(bridge.url + "?q=x&format=json")["results"] == []


def test_agent_researchs_own_searxng_client_reads_the_bridge():
    """The library's client, unchanged, as Agent Research uses it."""
    import os

    from deep_researcher.tools.web_search import SearchXNGClient

    from litstorm.engines.sources import SearchBridge

    with SearchBridge(_Source()) as bridge:
        os.environ["SEARCHXNG_HOST"] = bridge.url
        os.environ.pop("SEARCHXNG_ENGINES", None)
        try:
            found = asyncio.run(SearchXNGClient(filter_agent=None).search("x", filter_for_relevance=False))
        finally:
            os.environ.pop("SEARCHXNG_HOST", None)
    assert [(f.url, f.title, f.description) for f in found] == [("https://tci.test/1", "บทความ", "ข้อความ อีกตอน")]


def test_bridge_for_builds_one_only_when_the_run_needs_it(monkeypatch):
    from litstorm.engines import sources
    from litstorm.engines.base import RunConfig, Secrets
    from litstorm.engines.storm import providers

    monkeypatch.setattr(providers, "build_rm", lambda search, key, k, timeout: _Source(search["provider"]))
    native = {"searxng": "searxng", "tavily": "tavily"}

    def config(**over):
        return RunConfig(**{"run_id": "r", "engine": "agent", "topic": "t", "language": "th",
                            "llm": {}, "search": {"provider": "searxng", "endpoint": "http://s"}, **over})

    with sources.bridge_for(config(), Secrets(), native) as none:
        assert none is None
    two = config(search={"provider": "tci", "label": "TCI"}, search_extra=[{"provider": "arxiv", "label": "arXiv"}])
    with sources.bridge_for(two, Secrets(), native) as bridge:
        assert bridge.name == "TCI + arXiv"
        urls = [r["url"] for r in _get(bridge.url + "?q=x&format=json")["results"]]
        assert sorted(urls) == ["arxiv", "tci"]  # both sources, each answering with its own name


# --- the API --------------------------------------------------------------



@pytest.mark.db
def test_every_mode_offers_three_sources_of_any_kind(admin, browser, configured):  # noqa: F811
    user = make_user(admin, browser)
    engines = {e["id"]: e for e in user.get("/api/options").json()["engines"]}
    for name in ("storm", "co-storm", "deep", "agent"):
        assert engines[name]["max_sources"] == 3
        assert set(engines[name]["search_kinds"]) == {"searxng", "tavily", "arxiv", "tci"}


@pytest.mark.db
def test_a_deep_research_run_takes_arxiv_and_tci_together(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import Run

    tci = admin.post("/api/admin/search-providers", json={"label": "TCI", "kind": "tci"}).json()
    _, arxiv = configured
    user = make_user(admin, browser)
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "engine": "deep",
                                         "search_provider_id": arxiv["id"], "extra_search_provider_ids": [tci["id"]]})
    assert r.status_code == 201, r.text
    run = db.get(Run, r.json()["runs"][0]["id"])
    assert run.config["search"]["provider"] == "arxiv"
    assert [s["provider"] for s in run.config["search_extra"]] == ["tci"]


@pytest.mark.db
def test_a_discussion_keeps_its_sources_for_every_turn(admin, browser, configured, db):  # noqa: F811
    from sqlalchemy import update

    from litstorm.db.models import Run

    tci = admin.post("/api/admin/search-providers", json={"label": "TCI", "kind": "tci"}).json()
    _, arxiv = configured
    user = make_user(admin, browser)
    d = user.post("/api/discussions", json={"topic": "Songkran", "language": "th", "search_provider_id": arxiv["id"],
                                            "extra_search_provider_ids": [tci["id"]]})
    assert d.status_code == 201, d.text
    d = d.json()
    assert d["search_label"] == "arXiv + TCI"
    first = db.get(Run, d["turns"][0]["id"])
    assert [s["label"] for s in first.config["search_extra"]] == ["TCI"]

    db.execute(update(Run).where(Run.id == first.id).values(status="succeeded"))
    db.commit()
    said = user.post(f"/api/discussions/{d['id']}/turns", json={"action": "say", "text": "and today?"})
    assert said.status_code in (200, 201), said.text
    turn = db.get(Run, said.json()["id"])
    assert [s["label"] for s in turn.config["search_extra"]] == ["TCI"]


@pytest.mark.db
def test_four_sources_are_too_many_for_a_discussion(admin, browser, configured):  # noqa: F811
    _, arxiv = configured
    others = [admin.post("/api/admin/search-providers", json={"label": f"TCI {i}", "kind": "tci"}).json()["id"]
              for i in range(3)]
    user = make_user(admin, browser)
    r = user.post("/api/discussions", json={"topic": "Songkran", "language": "th", "search_provider_id": arxiv["id"],
                                            "extra_search_provider_ids": others})
    assert r.status_code == 422 and r.json()["detail"] == "too_many_sources"
