"""Discussions: Co-STORM's Turns through the Run queue (litstorm.discussion).

The Worker's side is simulated by `finish`, which does to a Turn's row and
workspace what a finished Turn would: the engine itself is proven against a
real model (docs/acceptance), not here.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import pytest

from conftest import make_user
from test_trash_and_cost import configured  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


def start(user, **extra):
    r = user.post("/api/discussions", json={"topic": "Songkran and tourism", "language": "th", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def finish(db, run_id, status="succeeded", refunded=False, view=None):
    """What the Worker leaves when a Turn ends."""
    from litstorm import discussion, settings
    from litstorm.db.models import Run

    db.expire_all()
    run = db.get(Run, uuid.UUID(run_id))
    now = datetime.now(timezone.utc)
    run.status, run.started_at, run.finished_at, run.quota_refunded = status, run.started_at or now, now, refunded
    db.commit()
    if status == "succeeded":
        work = os.path.join(settings.get().runs_dir, run_id, "work")
        os.makedirs(work, exist_ok=True)
        with open(os.path.join(work, discussion.STATE), "w", encoding="utf-8") as f:
            json.dump({"from": run_id}, f)
        with open(os.path.join(work, discussion.VIEW), "w", encoding="utf-8") as f:
            json.dump(view or {"turns": [{"role": "Moderator", "text": run_id}]}, f)


def ask(user, discussion_id, **body):
    return user.post(f"/api/discussions/{discussion_id}/turns", json=body)


def test_starting_queues_the_warm_start_and_takes_one_unit(admin, browser, configured):
    user = make_user(admin, browser)
    d = start(user)
    assert [t["turn"]["action"] for t in d["turns"]] == ["start"]
    assert d["turns"][0]["quota_units"] == 1 and d["current"]["id"] == d["turns"][0]["id"]
    assert d["allowance"] == {"per_block": 20, "blocks": 1, "used": 1, "remaining": 19}
    assert d["view"] is None
    assert user.get("/api/me/quota").json()["reserved"] == 1
    # It is a topic like any other, marked as a Discussion.
    listed = user.get("/api/sessions/recent").json()
    assert listed[0]["kind"] == "discussion" and listed[0]["title"] == "Songkran and tourism"


def test_one_turn_at_a_time_and_only_after_the_warm_start(admin, browser, configured, db):
    user = make_user(admin, browser)
    d = start(user)
    assert ask(user, d["id"], action="step").json()["detail"] == "turn_in_progress"
    finish(db, d["turns"][0]["id"], status="failed")
    assert ask(user, d["id"], action="step").json()["detail"] == "not_started"
    again = ask(user, d["id"], action="start")
    assert again.status_code == 201
    finish(db, again.json()["id"])
    assert ask(user, d["id"], action="start").json()["detail"] == "already_started"
    assert ask(user, d["id"], action="say", text="  ").json()["detail"] == "nothing_said"
    said = ask(user, d["id"], action="say", text="What about the local economy?").json()
    assert said["turn"] == {"action": "say", "text": "What about the local economy?"} and said["quota_units"] == 0


def test_a_block_of_turns_then_an_extension_that_takes_a_unit(admin, browser, configured, db):
    limits = admin.get("/api/admin/limits").json()
    admin.put("/api/admin/limits", json={**limits, "turns_per_quota": 3})
    user = make_user(admin, browser)
    d = start(user)
    finish(db, d["turns"][0]["id"])
    for _ in range(2):
        finish(db, ask(user, d["id"], action="step").json()["id"])
    assert ask(user, d["id"], action="report").json()["detail"] == "turns_exhausted"
    extended = ask(user, d["id"], action="report", extend=True).json()
    assert extended["quota_units"] == 1
    finish(db, extended["id"])
    quota = user.get("/api/me/quota").json()
    assert (quota["used"], quota["reserved"]) == (2, 0)
    assert user.get(f"/api/discussions/{d['id']}").json()["allowance"]["remaining"] == 2


def test_a_turn_whose_quota_came_back_uses_no_turn(admin, browser, configured, db):
    user = make_user(admin, browser)
    d = start(user)
    # The warm start failed in a way that refunds: nothing is paid for, and
    # starting again takes the unit again.
    finish(db, d["turns"][0]["id"], status="failed", refunded=True)
    assert user.get("/api/me/quota").json()["used"] == 0
    again = ask(user, d["id"], action="start").json()
    assert again["quota_units"] == 1
    finish(db, again["id"])
    step = ask(user, d["id"], action="step").json()
    finish(db, step["id"], status="interrupted", refunded=True)
    shown = user.get(f"/api/discussions/{d['id']}").json()
    assert shown["allowance"]["used"] == 1  # the warm start; the lost step is not counted
    assert user.get("/api/me/quota").json()["used"] == 1


def test_the_page_shows_what_the_last_finished_turn_left(admin, browser, configured, db):
    user = make_user(admin, browser)
    d = start(user)
    finish(db, d["turns"][0]["id"], view={"turns": [{"text": "warm"}]})
    step = ask(user, d["id"], action="step").json()
    finish(db, step["id"], status="failed")  # a failed Turn leaves nothing
    shown = user.get(f"/api/discussions/{d['id']}").json()
    assert shown["view"] == {"turns": [{"text": "warm"}]}
    assert shown["current"] is None


def test_the_worker_takes_a_turn_before_older_runs_and_tells_it_where_to_continue(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm import discussion, settings
    from litstorm.worker import queue

    current = admin.get("/api/admin/limits").json()
    admin.put("/api/admin/limits", json={**current, "max_concurrent_per_user": 5})
    user = make_user(admin, browser)
    d = start(user)
    with db_mod.sessions()() as s:
        warm = queue.claim(s)
    assert warm.config.engine == "co-storm"
    assert warm.config.discussion == {"action": "start", "state_from": None}
    assert warm.config.params["warmstart_max_num_experts"] == 3  # the standard level
    finish(db, d["turns"][0]["id"])

    run = user.post("/api/sessions", json={"topic": "An older Run", "language": "en"}).json()["runs"][0]
    said = ask(user, d["id"], action="say", text="and prices?").json()
    with db_mod.sessions()() as s:
        first = queue.claim(s)
    assert str(first.run_id) == said["id"]  # the Turn, though the Run queued first
    assert first.config.discussion["text"] == "and prices?"
    assert first.config.discussion["state_from"] == os.path.join(
        settings.get().runs_dir, d["turns"][0]["id"], "work", discussion.STATE
    )
    with db_mod.sessions()() as s:
        assert str(queue.claim(s).run_id) == run["id"]


def test_a_discussion_takes_turns_only_through_its_own_door(admin, browser, configured):
    user = make_user(admin, browser)
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "engine": "co-storm"})
    assert r.json()["detail"] == "use_discussion"
    d = start(user)
    r = user.post(f"/api/sessions/{d['id']}/runs", json={"topic": "Songkran", "language": "th"})
    assert r.json()["detail"] == "use_discussion"
    assert user.get(f"/api/sessions/{d['id']}").json()["kind"] == "discussion"
    # A Research Session is not a Discussion.
    other = user.post("/api/sessions", json={"topic": "A Run", "language": "en"}).json()
    assert user.get(f"/api/discussions/{other['id']}").status_code == 404


def test_a_turn_is_retried_as_a_turn_and_binned_only_with_its_discussion(admin, browser, configured, db):
    user = make_user(admin, browser)
    d = start(user)
    finish(db, d["turns"][0]["id"])
    said = ask(user, d["id"], action="say", text="and prices?").json()
    finish(db, said["id"], status="failed", refunded=True)
    again = user.post(f"/api/runs/{said['id']}/retry")
    assert again.status_code == 201 and again.json()["turn"]["text"] == "and prices?"
    assert user.delete(f"/api/runs/{said['id']}").json()["detail"] == "part_of_discussion"
    assert user.delete(f"/api/sessions/{d['id']}").status_code == 204
    assert user.get(f"/api/discussions/{d['id']}").status_code == 404
    assert [i["kind"] for i in user.get("/api/trash").json()] == ["session"]


def test_another_users_discussion_is_not_found(admin, browser, configured):
    alice = make_user(admin, browser, email="alice@example.org")
    bob = make_user(admin, browser, email="bob@example.org")
    d = start(alice)
    assert bob.get(f"/api/discussions/{d['id']}").status_code == 404
    assert ask(bob, d["id"], action="step").status_code == 404
