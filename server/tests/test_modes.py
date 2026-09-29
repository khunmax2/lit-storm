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
    assert [e["id"] for e in options["engines"]] == ["storm"]
    storm = options["engines"][0]
    assert storm["stages"] == ["research", "outline", "article", "polish"] and "tci" in storm["search_kinds"]
    assert {p["kind"] for p in options["search_providers"]} >= {"arxiv"}

    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    assert (run["engine"], run["engine_label"]) == ("storm", "STORM")
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "engine": "agent"})
    assert r.status_code == 422 and r.json()["detail"] == "engine_not_available"


def test_the_administrator_switches_a_mode_off_but_not_the_last(admin, browser, configured):
    listed = {e["id"]: e for e in admin.get("/api/admin/engines").json()}
    assert listed["storm"]["ready"] and listed["storm"]["enabled"]
    assert not listed["agent"]["ready"] and listed["agent"]["needs_tools"]
    r = admin.put("/api/admin/engines/storm", json={"enabled": False})
    assert r.status_code == 409 and r.json()["detail"] == "last_engine"
    assert admin.put("/api/admin/engines/nope", json={"enabled": False}).status_code == 404


def test_a_mode_takes_only_its_search_kinds_and_tool_models(admin, browser, configured, monkeypatch):
    """Agent Research is not built yet; pretend it is, to see its rules."""
    from litstorm import catalog

    monkeypatch.setitem(catalog.ENGINES, "agent", {**catalog.ENGINES["agent"], "ready": True})
    model, arxiv = configured
    searxng = admin.post("/api/admin/search-providers",
                         json={"label": "S", "kind": "searxng", "endpoint": "http://s.test"}).json()
    user = make_user(admin, browser)
    body = {"topic": "Songkran", "language": "th", "engine": "agent"}

    r = user.post("/api/sessions", json={**body, "search_provider_id": arxiv["id"]})
    assert r.json()["detail"] == "search_not_for_engine"
    r = user.post("/api/sessions", json={**body, "search_provider_id": searxng["id"]})
    assert r.json()["detail"] == "model_cannot_use_tools"  # untested

    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "supports_tools": True})
    r = user.post("/api/sessions", json={**body, "search_provider_id": searxng["id"]})
    assert r.status_code == 201 and r.json()["runs"][0]["engine"] == "agent"


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
