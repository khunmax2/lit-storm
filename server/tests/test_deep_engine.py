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
    report, progress = run(engine, tmp_path)
    report_mod.validate(report)
    assert report["engine"] == "deep" and report["title"] == "Songkran"
    # Learnings 1 and 3 share a URL: one source, with both passages.
    assert [s["url"] for s in report["sources"]] == ["https://a.test/x", "https://b.test/y"]
    assert report["lead"] == "It is the Thai New Year [1]. It falls in April [2][1]."
    assert report["sources"][0]["evidence"] == ["Songkran marks the Thai New Year.", "People splash water."]
    assert progress.stages == ["research", "report", "normalize"]
    assert progress.usages[0] == ("research", {"openrouter/google/x": {"prompt_tokens": 100, "completion_tokens": 20}},
                                 {"SearXNG": 1})
    assert progress.usages[1][1]["openrouter/google/x"] == {"prompt_tokens": 300, "completion_tokens": 200}


def test_the_cli_gets_the_runs_settings_and_only_its_keys():
    from litstorm.engines.deep.engine import cli_input

    line, env = cli_input(_config(), Secrets(llm_api_key="sk-or-1", search_api_key=""))
    assert (line["breadth"], line["depth"], line["gatherMs"]) == (2, 1, 96000)
    assert line["ai"] == {"provider": "openrouter", "model": "google/x", "apiBase": None,
                          "extraBody": {"reasoning": {"effort": "minimal"}, "provider": {"require_parameters": True}}}
    assert line["search"]["provider"] == "searxng" and line["query"].endswith("Focus: Which era? Ayutthaya")
    assert set(env) == {"PATH", "HOME", "LITSTORM_AI_API_KEY", "LITSTORM_SEARCH_API_KEY"}


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


def test_a_search_it_cannot_use_is_a_configuration_error(engine, tmp_path):
    with pytest.raises(EngineFailure) as bad:
        run(engine, tmp_path, search={"provider": "arxiv"})
    assert bad.value.reason == "bad_configuration"
