"""Submitting Runs, the Worker's queue, and reading the result."""

import time

import pytest

from conftest import make_user

pytestmark = pytest.mark.db


@pytest.fixture
def configured(admin):
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-test-0000"})
    model = admin.post(
        "/api/admin/llm-models",
        json={"label": "Gemini Lite", "provider": "openrouter", "model": "google/x", "reasoning": "effort:minimal",
              "max_tokens": {"conversation": 1500}, "is_default": True},
    ).json()
    search = admin.post(
        "/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True}
    ).json()
    return model, search


def _session(user):
    project = user.post("/api/projects", json={"name": "P"}).json()
    return user.post(
        f"/api/projects/{project['id']}/sessions", json={"topic": "Songkran", "language": "th"}
    ).json()


def test_a_run_keeps_what_it_was_started_with(admin, browser, configured, db):
    from litstorm.db.models import Run

    user = make_user(admin, browser)
    session = _session(user)
    run = session["runs"][0]
    assert run["status"] == "queued" and run["model_label"] == "Gemini Lite"

    # Changing the model afterwards does not rewrite the Run.
    model, _ = configured
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "label": "Renamed", "model": "google/y"})
    stored = db.get(Run, run["id"])
    assert stored.config["llm"]["model"] == "google/x"
    assert stored.config["params"]["max_tokens"] == {"conversation": 1500}
    assert "sk-test" not in str(stored.config)


def test_no_run_without_a_configured_default(admin, browser):
    user = make_user(admin, browser)
    project = user.post("/api/projects", json={"name": "P"}).json()
    r = user.post(f"/api/projects/{project['id']}/sessions", json={"topic": "Songkran", "language": "th"})
    assert r.status_code == 422 and r.json()["detail"] == "no_default_configured"


def test_a_disabled_model_cannot_be_chosen(admin, browser, configured):
    model, _ = configured
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "enabled": False, "is_default": False})
    user = make_user(admin, browser)
    project = user.post("/api/projects", json={"name": "P"}).json()
    r = user.post(
        f"/api/projects/{project['id']}/sessions",
        json={"topic": "Songkran", "language": "th", "llm_model_id": model["id"]},
    )
    assert r.status_code == 422


def test_cancelling_a_queued_run_stops_it_and_refunds(admin, browser, configured):
    user = make_user(admin, browser)
    run = _session(user)["runs"][0]
    r = user.post(f"/api/runs/{run['id']}/cancel").json()
    assert r["status"] == "cancelled" and r["quota_refunded"] is True
    assert user.post(f"/api/runs/{run['id']}/cancel").status_code == 409


# --- the Worker's side -------------------------------------------------------


def _fake(db, run_id, script):
    """Point a queued Run at the scriptable fake engine."""
    from litstorm.db.models import Run

    run = db.get(Run, run_id)
    run.engine = "fake"
    run.config = {**run.config, "params": {"script": script}}
    db.commit()


def test_claims_respect_the_system_ceiling(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    # One User here, so lift their own ceiling to see the system's.
    current = admin.get("/api/admin/limits").json()
    admin.put("/api/admin/limits", json={**current, "max_concurrent_per_user": 5})
    user = make_user(admin, browser)
    for _ in range(3):
        _session(user)
    Session = db_mod.sessions()
    claims = []
    for _ in range(3):
        with Session() as s:
            claims.append(queue.claim(s))
    assert [c is not None for c in claims] == [True, True, False]  # default ceiling: 2
    assert claims[0].secrets.llm_api_key == "sk-test-0000"


def test_the_worker_runs_a_run_to_its_report(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import main, queue

    user = make_user(admin, browser)
    run = _session(user)["runs"][0]
    _fake(db, run["id"], [{"stage": "research"}, {"stage": "polish"}])
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    main.run_one(claim)

    done = user.get(f"/api/runs/{run['id']}").json()
    assert done["status"] == "succeeded" and done["source_count"] == 1
    assert [e["data"]["stage"] for e in done["events"] if e["type"] == "stage"] == ["research", "polish"]
    report = user.get(f"/api/runs/{run['id']}/report").json()
    assert report["sections"][0]["heading"] == "Background"
    html = user.get(f"/api/runs/{run['id']}/export", params={"format": "html", "evidence": True})
    assert html.status_code == 200 and "A passage." in html.text
    # Nobody else can read it.
    other = make_user(admin, browser, "other@example.org")
    assert other.get(f"/api/runs/{run['id']}/report").status_code == 404


def test_cancel_reaches_a_running_run(admin, browser, configured, db):
    import threading

    from litstorm import db as db_mod
    from litstorm.worker import main, queue

    main.DB_TOUCH = 0.5
    user = make_user(admin, browser)
    run = _session(user)["runs"][0]
    _fake(db, run["id"], [{"stage": "research"}, {"sleep": 3}, {"stage": "outline"}, {"sleep": 30}])
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    worker = threading.Thread(target=main.run_one, args=(claim,))
    worker.start()
    time.sleep(1.5)
    assert user.post(f"/api/runs/{run['id']}/cancel").json()["status"] == "cancelling"
    worker.join(timeout=40)
    final = user.get(f"/api/runs/{run['id']}").json()
    assert final["status"] == "cancelled" and final["quota_refunded"] is False


def test_a_run_whose_worker_vanished_is_interrupted_not_restarted(admin, browser, configured, db):
    from datetime import datetime, timedelta, timezone

    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.runner.supervisor import Outcome
    from litstorm.worker import queue

    user = make_user(admin, browser)
    run = _session(user)["runs"][0]
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    # The Worker dies: nobody renews, and the lease runs out.
    stored = db.get(Run, run["id"])
    stored.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    with db_mod.sessions()() as s:
        assert queue.sweep_interrupted(s) == 1
    final = user.get(f"/api/runs/{run['id']}").json()
    assert final["status"] == "interrupted" and final["quota_refunded"] is True

    # The old Worker comes back and tries to finish: its token no longer holds.
    with db_mod.sessions()() as s:
        assert queue.finish(s, claim, Outcome("succeeded", "succeeded")) is False
    assert user.get(f"/api/runs/{run['id']}").json()["status"] == "interrupted"
    with db_mod.sessions()() as s:
        assert queue.claim(s) is None  # and it is not queued again
