"""Question refinement: a few questions before a Run, no quota, a daily cap;
the answers are kept with the Run, survive a retry, and steer research."""

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)


def test_questions_are_read_from_json_or_from_lines():
    from litstorm import refine

    assert refine.parse('Sure:\n["Which period?", "For whom?"]') == ["Which period?", "For whom?"]
    assert refine.parse("1. Which period?\n2) For whom?\n- Where?\n") == ["Which period?", "For whom?", "Where?"]
    assert len(refine.parse(str([f"q{i}" for i in range(9)]).replace("'", '"'))) == 5


def test_only_answered_questions_steer_the_research():
    from litstorm import refine

    qa = [{"question": "Which period?", "answer": " 1990s "}, {"question": "For whom?", "answer": ""}]
    assert refine.focus(qa) == "Which period? 1990s"
    assert refine.focus([]) == ""


@pytest.mark.db
def test_refining_takes_no_quota_but_has_a_daily_cap(admin, browser, configured, monkeypatch):
    from litstorm import refine

    asked = []
    monkeypatch.setattr(refine, "questions", lambda model, key, base, topic, lang: asked.append((key, topic, lang)) or ["Which period?", "For whom?"])
    limits = admin.get("/api/admin/limits").json()
    admin.put("/api/admin/limits", json={**limits, "refinements_per_day": 2})
    user = make_user(admin, browser)
    before = user.get("/api/me/quota").json()

    body = {"topic": "Songkran", "language": "th"}
    assert user.post("/api/refine", json=body).json() == {"questions": ["Which period?", "For whom?"]}
    assert asked == [("sk-test-0000", "Songkran", "th")]
    user.post("/api/refine", json=body)
    r = user.post("/api/refine", json=body)
    assert r.status_code == 429 and r.json()["detail"] == "refine_limit"
    assert user.get("/api/me/quota").json() == before


@pytest.mark.db
def test_a_model_that_fails_is_reported(admin, browser, configured, monkeypatch):
    from litstorm import refine

    def fail(*a):
        raise refine.RefineError("no")

    monkeypatch.setattr(refine, "questions", fail)
    user = make_user(admin, browser)
    r = user.post("/api/refine", json={"topic": "Songkran", "language": "th"})
    assert r.status_code == 502 and r.json()["detail"] == "refine_failed"


@pytest.mark.db
def test_the_answers_are_kept_with_the_run_and_its_retry(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={
        "topic": "Songkran", "language": "th",
        "refinement": [{"question": "Which period?", "answer": "Ayutthaya"}, {"question": "For whom?", "answer": ""}],
    }).json()["runs"][0]
    assert run["refinement"] == [{"question": "Which period?", "answer": "Ayutthaya"}]

    user.post(f"/api/runs/{run['id']}/cancel")
    again = user.post(f"/api/runs/{run['id']}/retry").json()
    assert again["refinement"] == run["refinement"]
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert str(claim.run_id) == again["id"]
    assert claim.config.refinement == [{"question": "Which period?", "answer": "Ayutthaya"}]
