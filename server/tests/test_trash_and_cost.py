"""The Trash, the purge after 30 days, cost estimates, usage, and test buttons."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from conftest import make_user

pytestmark = pytest.mark.db


@pytest.fixture
def configured(admin):
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-test-0000"})
    model = admin.post(
        "/api/admin/llm-models",
        json={"label": "M", "provider": "openrouter", "model": "a/m", "is_default": True,
              "price_in_per_mtok": "1.0", "price_out_per_mtok": "2.0"},
    ).json()
    search = admin.post(
        "/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True}
    ).json()
    return {"model": model, "search": search}


def research(user, name="P", topic="Songkran"):
    project = user.post("/api/projects", json={"name": name}).json()
    session = user.post(
        f"/api/projects/{project['id']}/sessions", json={"topic": topic, "language": "th"}
    ).json()
    return project, session, session["runs"][0]


def run_fake(db, run_id, script=None):
    """Run a queued Run to its end with the fake engine, as the Worker would."""
    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.worker import main, queue

    run = db.get(Run, uuid.UUID(run_id))
    run.engine = "fake"
    run.config = {**run.config, "params": {"script": script or [{"stage": "research"}, {"stage": "polish"}]}}
    db.commit()
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    main.run_one(claim)


def age(db, table, row_id, days):
    row = db.get(table, uuid.UUID(row_id))
    row.trashed_at = datetime.now(timezone.utc) - timedelta(days=days)
    db.commit()


def purge():
    from litstorm import db as db_mod
    from litstorm import settings, trash

    with db_mod.sessions()() as s:
        return trash.purge(s, settings.get().runs_dir)


# --- the Trash -----------------------------------------------------------------------


def test_a_trashed_project_hides_everything_in_it_until_restored(admin, browser, configured):
    alice = make_user(admin, browser)
    project, session, run = research(alice)
    assert alice.delete(f"/api/projects/{project['id']}").status_code == 204
    assert alice.get("/api/projects").json() == []
    assert alice.get(f"/api/sessions/{session['id']}").status_code == 404
    assert alice.get(f"/api/runs/{run['id']}").status_code == 404

    listed = alice.get("/api/trash").json()
    assert [(i["kind"], i["id"]) for i in listed] == [("project", project["id"])]  # not its contents too
    purge_at = datetime.fromisoformat(listed[0]["purge_at"])
    trashed_at = datetime.fromisoformat(listed[0]["trashed_at"])
    assert purge_at - trashed_at == timedelta(days=30)

    assert alice.post(f"/api/trash/project/{project['id']}/restore").status_code == 204
    assert alice.get(f"/api/sessions/{session['id']}").status_code == 200


def test_trashing_stops_the_work_inside(admin, browser, configured):
    alice = make_user(admin, browser)
    project, session, run = research(alice)
    alice.delete(f"/api/sessions/{session['id']}")
    alice.post(f"/api/trash/session/{session['id']}/restore")
    stopped = alice.get(f"/api/runs/{run['id']}").json()
    assert stopped["status"] == "cancelled" and stopped["quota_refunded"] is True


def test_only_a_finished_run_goes_to_the_trash_on_its_own(admin, browser, configured, db):
    alice = make_user(admin, browser)
    _, session, run = research(alice)
    assert alice.delete(f"/api/runs/{run['id']}").status_code == 409
    run_fake(db, run["id"])
    assert alice.delete(f"/api/runs/{run['id']}").status_code == 204
    assert alice.get(f"/api/sessions/{session['id']}").json()["runs"] == []
    assert alice.get(f"/api/runs/{run['id']}/report").status_code == 404


def test_nobody_else_can_trash_or_restore(admin, browser, configured):
    alice = make_user(admin, browser, "alice@example.org")
    bob = make_user(admin, browser, "bob@example.org")
    project, _, _ = research(alice)
    assert bob.delete(f"/api/projects/{project['id']}").status_code == 404
    alice.delete(f"/api/projects/{project['id']}")
    assert bob.post(f"/api/trash/project/{project['id']}/restore").status_code == 404
    assert bob.get("/api/trash").json() == []


# --- the purge -------------------------------------------------------------------------------


def test_after_30_days_content_goes_but_the_months_figures_stay(admin, browser, configured, db):
    from litstorm import settings
    from litstorm.db.models import Project, ResearchSession, Run, RunEvent

    alice = make_user(admin, browser)
    project, session, run = research(alice)
    run_fake(db, run["id"])
    run_dir = os.path.join(settings.get().runs_dir, run["id"])
    assert os.path.exists(run_dir)
    quota_before = alice.get("/api/me/quota").json()

    alice.delete(f"/api/projects/{project['id']}")
    age(db, Project, project["id"], days=29)
    assert purge() == 0  # not yet
    age(db, Project, project["id"], days=31)
    assert purge() == 1

    db.expire_all()
    kept = db.get(Run, uuid.UUID(run["id"]))
    assert kept.purged_at is not None and kept.topic == "" and kept.session_id is None
    assert "Songkran" not in str(kept.config)
    assert kept.cost_usd is not None  # accounting stays
    assert db.query(RunEvent).filter(RunEvent.run_id == kept.id).count() == 0
    assert not os.path.exists(run_dir)
    assert db.get(ResearchSession, uuid.UUID(session["id"])) is None
    assert db.get(Project, uuid.UUID(project["id"])) is None
    # Deleting did not give the quota back.
    assert alice.get("/api/me/quota").json() == quota_before
    assert alice.get("/api/trash").json() == []


def test_the_purge_waits_for_a_run_that_is_still_stopping(admin, browser, configured, db):
    from litstorm.db.models import Project

    alice = make_user(admin, browser)
    project, _, run = research(alice)
    from litstorm import db as db_mod
    from litstorm.worker import queue

    with db_mod.sessions()() as s:
        queue.claim(s)  # running
    alice.delete(f"/api/projects/{project['id']}")  # asks it to stop
    age(db, Project, project["id"], days=31)
    assert purge() == 0


# --- cost ----------------------------------------------------------------------------------------


def test_cost_uses_the_admins_price_when_set():
    from litstorm import cost

    events = [
        {"llm": {"x/m": {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}}, "search": {"S": 3}},
        {"llm": {"x/m": {"prompt_tokens": 0, "completion_tokens": 500_000}}, "search": {"S": 1}},
    ]
    tokens_in, tokens_out, searches, by_model = cost.totals(events)
    assert (tokens_in, tokens_out, searches) == (1_000_000, 1_000_000, 4)
    assert cost.estimate(by_model, Decimal("1"), Decimal("2")) == Decimal("3.000000")


def test_an_unknown_model_has_no_cost_rather_than_a_guess():
    from litstorm import cost

    assert cost.estimate({"nobody/unknown-model-xyz": [10, 10]}) is None


def test_a_run_records_its_tokens_and_cost(admin, browser, configured, db):
    from litstorm.db.models import Run

    alice = make_user(admin, browser)
    _, _, run = research(alice)
    run_fake(db, run["id"])
    db.expire_all()
    stored = db.get(Run, uuid.UUID(run["id"]))
    # The fake engine reports 10 in / 5 out per stage, two stages.
    assert (stored.tokens_in, stored.tokens_out, stored.search_calls) == (20, 10, 2)
    assert stored.cost_usd == Decimal("0.000040")  # 20 × $1/M + 10 × $2/M


def test_admins_see_usage_but_not_research(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    _, _, run = research(alice, topic="A very private topic")
    run_fake(db, run["id"])
    usage = admin.get("/api/admin/usage").json()
    row = next(r for r in usage["rows"] if r["email"] == "alice@example.org")
    assert (row["runs"], row["succeeded"], row["tokens_in"]) == (1, 1, 20)
    runs = admin.get("/api/admin/runs").json()
    assert runs[0]["email"] == "alice@example.org" and runs[0]["status"] == "succeeded"
    assert "private" not in str(runs) and "private" not in str(usage)
    user = make_user(admin, browser, "bob@example.org")
    assert user.get("/api/admin/usage").status_code == 403


# --- test buttons ------------------------------------------------------------------------------------


class _Reply:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


def test_the_model_test_button(admin, configured, monkeypatch):
    import litellm

    sent = {}

    def fake(**kwargs):
        sent.update(kwargs)
        return _Reply("ok")

    monkeypatch.setattr(litellm, "completion", fake)
    r = admin.post(f"/api/admin/llm-models/{configured['model']['id']}/test").json()
    assert r["ok"] is True and r["message"] == "ok"
    assert sent["api_key"] == "sk-test-0000" and sent["model"] == "openrouter/a/m"
    assert "sk-test" not in str(r)

    monkeypatch.setattr(litellm, "completion", lambda **kw: _Reply(None))
    r = admin.post(f"/api/admin/llm-models/{configured['model']['id']}/test").json()
    assert r["ok"] is False and "no text" in r["message"]


def test_a_model_can_be_tried_before_it_is_saved(admin, configured, monkeypatch):
    import litellm

    sent = {}
    monkeypatch.setattr(litellm, "completion", lambda **kw: (sent.update(kw), _Reply("ok"))[1])
    draft = {"provider": "openrouter", "model": "b/new", "reasoning": "off", "max_tokens": {"conversation": 300}}

    # With no key typed, the one stored for the provider.
    r = admin.post("/api/admin/llm-models/check", json=draft).json()
    assert r["ok"] and sent["api_key"] == "sk-test-0000" and sent["model"] == "openrouter/b/new"
    assert sent["max_tokens"] == 300 and sent["reasoning"] == {"enabled": False}

    # A key typed in the dialog wins, and is not repeated back.
    r = admin.post("/api/admin/llm-models/check", json={**draft, "api_key": "sk-typed-1234"}).json()
    assert r["ok"] and sent["api_key"] == "sk-typed-1234" and "sk-typed" not in str(r)
    assert [m["model"] for m in admin.get("/api/admin/llm-models").json()] == ["a/m"]  # nothing saved


def test_a_model_draft_without_what_it_needs_says_so(admin, configured):
    no_key = admin.post("/api/admin/llm-models/check", json={"provider": "groq", "model": "x"}).json()
    assert (no_key["ok"], no_key["message"]) == (False, "no API key stored for this provider")
    no_base = admin.post(
        "/api/admin/llm-models/check", json={"provider": "openai-compatible", "model": "x", "api_key": "k"}
    ).json()
    assert (no_base["ok"], no_base["message"]) == (False, "this provider needs an API base URL")
    assert admin.post("/api/admin/llm-models/check", json={"provider": "nope", "model": "x"}).status_code == 422


def test_the_search_test_button(admin, configured, monkeypatch):
    import requests

    class Resp:
        status_code = 200
        text = (
            "<feed><title>query</title><entry><title>First\n  paper</title></entry>"
            "<entry><title>Second</title></entry></feed>"
        )

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: Resp())
    r = admin.post(f"/api/admin/search-providers/{configured['search']['id']}/test").json()
    assert r == {"ok": True, "message": "2 results", "seconds": r["seconds"], "samples": ["First paper", "Second"]}


def test_a_search_provider_can_be_tried_before_it_is_saved(admin, configured, monkeypatch):
    import requests

    sent = {}

    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"title": "A"}, {"title": "B"}]}

    def post(url, json, timeout):
        sent.update(json)
        return Resp()

    monkeypatch.setattr(requests, "post", post)
    r = admin.post(
        "/api/admin/search-providers/check",
        json={"kind": "tavily", "api_key": "tvly-draft-1234", "query": "songkran"},
    ).json()
    assert r["ok"] and r["samples"] == ["A", "B"]
    assert (sent["api_key"], sent["query"]) == ("tvly-draft-1234", "songkran")
    assert "tvly-draft-1234" not in str(r)
    # Nothing was saved by trying it.
    assert [p["kind"] for p in admin.get("/api/admin/search-providers").json()] == ["arxiv"]


def test_editing_tries_the_stored_key_when_none_is_typed(admin, configured, monkeypatch):
    import requests

    sent = {}

    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"title": "A"}]}

    monkeypatch.setattr(requests, "post", lambda url, json, timeout: (sent.update(json), Resp())[1])
    saved = admin.post(
        "/api/admin/search-providers", json={"label": "T", "kind": "tavily", "api_key": "tvly-stored-9999"}
    ).json()
    r = admin.post("/api/admin/search-providers/check", json={"kind": "tavily", "id": saved["id"]}).json()
    assert r["ok"] and sent["api_key"] == "tvly-stored-9999"


def test_a_draft_without_what_it_needs_says_so(admin, configured):
    no_key = admin.post("/api/admin/search-providers/check", json={"kind": "tavily"}).json()
    assert (no_key["ok"], no_key["message"]) == (False, "Tavily needs an API key")
    no_url = admin.post("/api/admin/search-providers/check", json={"kind": "searxng"}).json()
    assert (no_url["ok"], no_url["message"]) == (False, "SearXNG needs an endpoint")
    assert admin.post("/api/admin/search-providers/check", json={"kind": "google"}).status_code == 422
