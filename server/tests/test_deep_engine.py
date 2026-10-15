"""The Deep Research Engine around its Node CLI, with a stand-in CLI."""

import os
import sys
import threading

import pytest

from litstorm import report as report_mod
from litstorm.engines.base import Cancelled, EngineFailure, RunConfig, Secrets

FAKE = os.path.join(os.path.dirname(__file__), "fake_deep_cli.py")


class Progress:
    def __init__(self):
        self.stages, self.notes, self.usages = [], [], []

    def stage(self, name):
        self.stages.append(name)

    def note(self, kind, **data):
        self.notes.append((kind, data))

    def usage(self, stage, llm, search):
        self.usages.append((stage, llm, search))


class Cancel:
    def __init__(self):
        self.asked = threading.Event()

    def requested(self):
        return self.asked.is_set()

    def check(self):
        if self.requested():
            raise Cancelled()


def _config(**over):
    fields = dict(
        run_id="r", engine="deep", topic="Songkran", language="en",
        llm={"provider": "openrouter", "model": "google/x", "reasoning": "effort:minimal"},
        search={"provider": "searxng", "endpoint": "http://searxng:8080/search"},
        params={"breadth": 2, "depth": 1}, target_seconds=120,
        refinement=[{"question": "Which era?", "answer": "Ayutthaya"}],
    )
    return RunConfig(**{**fields, **over})


@pytest.fixture
def engine(monkeypatch):
    from litstorm.engines.deep import engine as deep

    monkeypatch.setattr(deep, "NODE", sys.executable)
    monkeypatch.setattr(deep, "CLI", FAKE)
    return deep.DeepEngine()


def run(engine, tmp_path, script="ok", cancel=None, **over):
    if script != "ok":
        over.setdefault("topic", f"[{script}] Songkran")
    progress = Progress()
    report = engine.run(_config(**over), Secrets(llm_api_key="sk-or-1"), str(tmp_path), progress, cancel or Cancel())
    return report, progress


def test_a_run_becomes_a_report_with_evidence(engine, tmp_path):
    # Tavily: the CLI searches it itself, and counts its own searches.
    report, progress = run(engine, tmp_path, search={"provider": "tavily"})
    report_mod.validate(report)
    assert report["engine"] == "deep" and report["title"] == "Songkran"
    # Learnings 1 and 3 share a URL: one source, with both passages.
    assert [s["url"] for s in report["sources"]] == ["https://a.test/x", "https://b.test/y"]
    assert report["lead"] == "It is the Thai New Year [1]. It falls in April [2][1]."
    assert report["sources"][0]["evidence"] == ["Songkran marks the Thai New Year.", "People splash water."]
    assert progress.stages == ["research", "report", "normalize"]
    assert progress.usages[0] == ("research", {"openrouter/google/x": {"prompt_tokens": 100, "completion_tokens": 20}},
                                 {"Tavily": 1})
    assert progress.usages[1][1]["openrouter/google/x"] == {"prompt_tokens": 300, "completion_tokens": 200}


def test_the_cli_gets_the_runs_settings_and_only_its_keys():
    from litstorm.engines.deep.engine import cli_input

    class Bridge:
        url = "http://127.0.0.1:5000/search"

    line, env = cli_input(_config(), Secrets(llm_api_key="sk-or-1", search_api_key=""), Bridge())
    assert (line["breadth"], line["depth"], line["gatherMs"]) == (2, 1, 96000)
    assert line["ai"] == {"provider": "openrouter", "model": "google/x", "apiBase": None,
                          "extraBody": {"reasoning": {"effort": "minimal"}, "provider": {"require_parameters": True}}}
    assert line["search"] == {"provider": "searxng", "apiBase": Bridge.url, "engines": None}
    assert line["query"].endswith("Focus: Which era? Ayutthaya")
    assert set(env) - {"SYSTEMROOT"} == {"PATH", "HOME", "LITSTORM_AI_API_KEY", "LITSTORM_SEARCH_API_KEY"}


def test_a_failure_and_an_empty_result_are_told_apart(engine, tmp_path):
    with pytest.raises(EngineFailure) as failed:
        run(engine, tmp_path, "fail")
    assert failed.value.reason == "engine_error" and "refused" in str(failed.value)
    with pytest.raises(EngineFailure) as empty:
        run(engine, tmp_path, "empty")
    assert empty.value.reason == "empty_report"


def test_a_stop_kills_the_cli(engine, tmp_path):
    cancel = Cancel()
    threading.Timer(1.5, cancel.asked.set).start()
    with pytest.raises(Cancelled):
        run(engine, tmp_path, "hang", cancel=cancel)


class _Source:
    """A retriever that answers every query with one paper."""

    def __init__(self):
        self.calls = 0

    def forward(self, query_or_queries, exclude_urls=None):
        self.calls += 1
        return [{"url": "https://arxiv.test/1", "title": "A paper", "description": "",
                 "snippets": ["Songkran is the Thai New Year."]}]

    def get_usage_and_reset(self):
        calls, self.calls = self.calls, 0
        return {"ArxivRM": calls}


def test_a_source_the_cli_cannot_reach_is_searched_through_the_bridge(engine, tmp_path, monkeypatch):
    from litstorm.engines.storm import providers

    monkeypatch.setattr(providers, "build_rm", lambda search, key, k, timeout: _Source())
    report, progress = run(engine, tmp_path, "search", search={"provider": "arxiv", "label": "arXiv"})
    assert [s["url"] for s in report["sources"]] == ["https://arxiv.test/1"]
    assert report["sources"][0]["evidence"] == ["Songkran is the Thai New Year."]
    # Counted by the bridge, by source, not as the CLI's own SearXNG.
    assert progress.usages[0][2] == {"ArxivRM": 1}


def test_searxng_reaches_the_cli_without_results_about_something_else(engine, tmp_path, monkeypatch):
    """The CLI keeps SearXNG's first results as they come. A fast Thai Run
    ended empty when an engine behind SearXNG answered other queries and its
    pages came first (2026-10-06); through the bridge they are left out."""
    import requests

    asked = []

    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [
                {"url": "https://www.zhihu.com/q/1", "title": "如何证明数学等式 1 + 1 = 2 的成立？ - 知乎", "content": "知乎"},
                {"url": "https://support.microsoft.com/1", "title": "Snipping Tool", "content": "Take a screenshot"},
                {"url": "https://songkran.test/1", "title": "Songkran", "content": "Songkran is the Thai New Year."},
            ]}

    def get(url, headers, params, timeout):
        asked.append((url, params))
        return Resp()

    monkeypatch.setattr(requests, "get", get)
    report, progress = run(engine, tmp_path, "search", search={"provider": "searxng", "endpoint": "http://searxng:8080"})
    assert asked == [("http://searxng:8080/search", {"q": "Songkran", "format": "json"})]
    assert [s["url"] for s in report["sources"]] == ["https://songkran.test/1"]
    assert progress.usages[0][2] == {"SearXNG": 1}


def test_the_bridge_is_used_only_when_needed():
    from litstorm.engines import sources
    from litstorm.engines.deep.engine import SEARCH

    assert not sources.bridged(_config(search={"provider": "tavily"}), SEARCH)  # the CLI's own client
    assert sources.bridged(_config(), SEARCH)  # SearXNG: through STORM's retriever
    assert sources.bridged(_config(search={"provider": "tci"}), SEARCH)
    assert sources.bridged(_config(search_extra=[{"provider": "searxng", "endpoint": "http://x"}]), SEARCH)


def test_a_search_no_one_can_reach_is_a_configuration_error(engine, tmp_path):
    with pytest.raises(EngineFailure) as bad:
        run(engine, tmp_path, search={"provider": "bing"})
    assert bad.value.reason == "bad_configuration"
