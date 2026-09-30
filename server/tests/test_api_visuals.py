"""Drawing a report's visual blocks through the API: once, by the owner,
within a daily cap, its cost added to the Run (litstorm.visuals)."""

import json
import os

import pytest

from conftest import make_user
from test_api_runs import _fake, _session, configured  # noqa: F401  (fixture)
from test_visuals import REPORT

pytestmark = pytest.mark.db


@pytest.fixture
def finished(admin, browser, configured, db):  # noqa: F811
    """A User, and a Run of theirs that finished with a report worth drawing."""
    from litstorm import db as db_mod
    from litstorm import report as report_mod
    from litstorm import settings
    from litstorm.worker import main, queue

    user = make_user(admin, browser)
    run = _session(user)["runs"][0]
    _fake(db, run["id"], [{"stage": "research"}])
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    main.run_one(claim)
    report_mod.write(REPORT, os.path.join(settings.get().runs_dir, run["id"], "report.json"))
    return user, run


def _answer(monkeypatch, blocks, calls=None):
    """The model, answering with `blocks` (a list, or raw text)."""
    from litstorm import visuals

    def ask(model, api_key, api_base, messages):
        if calls is not None:
            calls.append(messages)
        text = blocks if isinstance(blocks, str) else json.dumps({"blocks": blocks}, ensure_ascii=False)
        return text, "openrouter/google/x", (1000, 200)

    monkeypatch.setattr(visuals, "_ask", ask)


def _figures(facts_text):
    from litstorm import visuals

    facts = visuals.facts(REPORT)
    f1 = next(f["id"] for f in facts if facts_text in f["text"])
    return [{"type": "stat_cards", "anchor": "s1", "title": "ตัวเลข",
             "items": [{"label": "ส่งออก", "value": 929000, "unit": "ตัน", "fact": f1},
                       {"label": "แต่ง", "value": 5, "unit": "ตัน", "fact": f1}]},
            {"type": "chart", "chart": "bar", "series": [{"name": "x", "points": [{"x": "a", "y": 1, "fact": "F99"}]}]}]


def test_the_owner_draws_once_and_the_run_pays(finished, monkeypatch, db):
    from litstorm.db.models import Run

    user, run = finished
    before = db.get(Run, run["id"])
    tokens_before = before.tokens_in or 0
    calls = []
    _answer(monkeypatch, _figures("929,000"), calls)

    assert user.get(f"/api/runs/{run['id']}/visuals").json()["ready"] is False
    drawn = user.post(f"/api/runs/{run['id']}/visuals").json()
    assert drawn["ready"] and [b["type"] for b in drawn["blocks"]] == ["stat_cards"]
    assert drawn["dropped"] == 1 and drawn["blocks"][0]["sources"] == [1]
    # The facts went to the model, and the report's language with them.
    assert "929,000" in calls[0][0]["content"] and "Thai" in calls[0][0]["content"]

    db.expire_all()
    assert db.get(Run, run["id"]).tokens_in == tokens_before + 1000

    # Asked again: the kept file, no second call.
    again = user.post(f"/api/runs/{run['id']}/visuals").json()
    assert again["blocks"] == drawn["blocks"] and len(calls) == 1


def test_unreadable_json_is_repaired_once_then_given_up(finished, monkeypatch):
    user, run = finished
    calls = []
    _answer(monkeypatch, "sorry, no JSON here", calls)
    r = user.post(f"/api/runs/{run['id']}/visuals")
    assert r.status_code == 502 and r.json()["detail"] == "visuals_failed"
    assert len(calls) == 2  # one ask, one repair


def test_only_the_owner_draws_and_hides(finished, monkeypatch, admin, browser):
    user, run = finished
    _answer(monkeypatch, _figures("929,000"))
    other = make_user(admin, browser, "other@example.org")
    assert other.post(f"/api/runs/{run['id']}/visuals").status_code == 404
    assert other.get(f"/api/runs/{run['id']}/visuals").status_code == 404

    user.post(f"/api/runs/{run['id']}/visuals")
    hidden = user.patch(f"/api/runs/{run['id']}/visuals", json={"hidden": ["v1", "nope"]}).json()
    assert [b["hidden"] for b in hidden["blocks"]] == [True]
    assert other.patch(f"/api/runs/{run['id']}/visuals", json={"hidden": []}).status_code == 404


def test_a_daily_cap(finished, monkeypatch, admin):
    user, run = finished
    current = admin.get("/api/admin/limits").json()
    assert current["visuals_per_day"] == 10
    admin.put("/api/admin/limits", json={**current, "visuals_per_day": 1})
    _answer(monkeypatch, "not json")
    assert user.post(f"/api/runs/{run['id']}/visuals").status_code == 502  # counted all the same
    r = user.post(f"/api/runs/{run['id']}/visuals")
    assert r.status_code == 429 and r.json()["detail"] == "visuals_limit"
