"""Graceful finish: at 80% of the depth level's target, research starts no
new turns and the Run writes from what it has (docs/web-app-design.md)."""

import time
from types import SimpleNamespace

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)


def _simulator(turns, turn_seconds):
    from knowledge_storm.storm_wiki.modules.knowledge_curation import ConvSimulator

    sim = ConvSimulator(None, None, None, max_search_queries_per_turn=1, search_top_k=1, max_turn=turns)

    def ask(**kw):
        time.sleep(turn_seconds)
        return SimpleNamespace(question="Why?")

    sim.wiki_writer = ask
    sim.topic_expert = lambda **kw: SimpleNamespace(answer="Because.", queries=["q"], searched_results=[])
    return sim


def _talk(sim):
    handler = SimpleNamespace(on_dialogue_turn_end=lambda **kw: None)
    return sim(topic="t", persona="p", ground_truth_url="", callback_handler=handler).dlg_history


@pytest.mark.slow
def test_without_a_stop_time_every_turn_is_asked():
    sim = _simulator(turns=3, turn_seconds=0)
    assert len(_talk(sim)) == 3 and sim.cut_short == 0


@pytest.mark.slow
def test_past_the_stop_time_a_conversation_keeps_what_it_has():
    sim = _simulator(turns=5, turn_seconds=0.2)
    sim.stop_at = time.time() + 0.3
    history = _talk(sim)
    assert 1 <= len(history) < 5 and sim.cut_short == 1


@pytest.mark.slow
def test_a_conversation_always_gets_its_first_turn():
    sim = _simulator(turns=3, turn_seconds=0)
    sim.stop_at = time.time() - 1  # already late when it starts
    assert len(_talk(sim)) == 1


@pytest.mark.db
def test_the_run_card_says_how_the_run_went(admin, browser, configured, db):
    """Writing from what it had, a failed embedding service, cached searches:
    kept on the Run so a list of Runs shows them. A working embedding
    service is not news."""
    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.worker import main, queue

    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    stored = db.get(Run, run["id"])
    stored.engine = "fake"
    stored.config = {**stored.config, "params": {"script": [
        {"stage": "research"},
        {"note": "research_cut_short", "data": {"conversations": 2, "seconds": 240}},
        {"note": "search_cache", "data": {"hits": 5, "misses": 30}},
        {"note": "embedding", "data": {"fallback": False, "texts": 90}},
        {"note": "browsed", "data": {"urls": ["https://a.test"]}},
    ]}}
    db.commit()
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    main.run_one(claim)

    listed = user.get(f"/api/sessions/{run['session_id']}").json()["runs"][0]
    assert listed["notes"] == {
        "research_cut_short": {"conversations": 2, "seconds": 240},
        "search_cache": {"hits": 5, "misses": 30},
    }


@pytest.mark.db
def test_the_worker_hands_the_run_its_levels_target(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    user = make_user(admin, browser)
    user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "depth": "fast"})
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert claim.config.target_seconds == 120.0
