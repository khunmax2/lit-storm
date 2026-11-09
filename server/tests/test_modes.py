"""Research modes: only ready Engines the Administrator has not switched off
are offered; a Run's search provider and model must fit its mode; a model's
test records whether it can call tools."""

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


def test_only_ready_modes_are_offered_and_the_run_says_which(admin, browser, configured):
    user = make_user(admin, browser)
    options = user.get("/api/options").json()
    assert [e["id"] for e in options["engines"]] == ["storm", "co-storm", "deep", "agent"]
    storm = options["engines"][0]
    assert storm["stages"] == ["research", "outline", "article", "polish"] and "tci" in storm["search_kinds"]
    assert {p["kind"] for p in options["search_providers"]} >= {"arxiv"}

    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    assert (run["engine"], run["engine_label"]) == ("storm", "STORM")
    # Co-STORM is offered, but as a Discussion (tests/test_discussions.py).
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "engine": "co-storm"})
    assert r.status_code == 422 and r.json()["detail"] == "use_discussion"
    admin.put("/api/admin/engines/co-storm", json={"enabled": False})
    r = user.post("/api/discussions", json={"topic": "Songkran", "language": "th"})
    assert r.status_code == 422 and r.json()["detail"] == "engine_not_available"


def test_the_administrator_switches_a_mode_off_but_not_the_last(admin, browser, configured):
    listed = {e["id"]: e for e in admin.get("/api/admin/engines").json()}
    assert listed["storm"]["ready"] and listed["storm"]["enabled"]
    assert listed["co-storm"]["ready"] and listed["agent"]["needs_tools"]
    r = admin.put("/api/admin/engines/storm", json={"enabled": False})
    assert r.status_code == 200 and not {e["id"]: e for e in r.json()}["storm"]["enabled"]
    user = make_user(admin, browser)
    admin.put("/api/admin/engines/co-storm", json={"enabled": False})
    admin.put("/api/admin/engines/deep", json={"enabled": False})
    assert [e["id"] for e in user.get("/api/options").json()["engines"]] == ["agent"]
    r = admin.put("/api/admin/engines/agent", json={"enabled": False})
    assert r.status_code == 409 and r.json()["detail"] == "last_engine"
    assert admin.put("/api/admin/engines/nope", json={"enabled": False}).status_code == 404


def test_agent_research_needs_a_model_that_calls_tools(admin, browser, configured, monkeypatch):
    """Agent Research searches with any Search Provider (through the search
    bridge where its library cannot reach it), and needs a model whose test
    showed it calls tools."""
    model, arxiv = configured
    searxng = admin.post("/api/admin/search-providers",
                         json={"label": "S", "kind": "searxng", "endpoint": "http://s.test"}).json()
    user = make_user(admin, browser)
    body = {"topic": "Songkran", "language": "th", "engine": "agent"}

    r = user.post("/api/sessions", json={**body, "search_provider_id": arxiv["id"]})
    assert r.json()["detail"] == "model_cannot_use_tools"  # arXiv is fine; the model is untested
    r = user.post("/api/sessions", json={**body, "search_provider_id": searxng["id"]})
    assert r.json()["detail"] == "model_cannot_use_tools"  # untested

    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "supports_tools": True})
    r = user.post("/api/sessions", json={**body, "search_provider_id": searxng["id"], "depth": "deep"})
    assert r.status_code == 201 and r.json()["runs"][0]["engine"] == "agent"

    # Its own settings for the level, not STORM's.
    from litstorm.db import sessions
    from litstorm.db.models import Run

    with sessions()() as s:
        params = s.get(Run, r.json()["runs"][0]["id"]).config["params"]
    assert (params["mode"], params["max_iterations"]) == ("deep", 2) and "max_perspective" not in params


def test_the_model_test_records_whether_it_calls_tools(admin, configured, monkeypatch):
    from litstorm import checks

    model, _ = configured
    monkeypatch.setattr(checks, "llm", lambda *a, **k: (True, "ok", 0.1))
    monkeypatch.setattr(checks, "tools", lambda *a, **k: True)
    r = admin.post(f"/api/admin/llm-models/{model['id']}/test").json()
    assert r["ok"] and r["tools"] is True
    listed = {m["id"]: m for m in admin.get("/api/admin/llm-models").json()}
    assert listed[model["id"]]["supports_tools"] is True

    # An outage says nothing about the model: what was known stays.
    monkeypatch.setattr(checks, "tools", lambda *a, **k: None)
    admin.post(f"/api/admin/llm-models/{model['id']}/test")
    listed = {m["id"]: m for m in admin.get("/api/admin/llm-models").json()}
    assert listed[model["id"]]["supports_tools"] is True
