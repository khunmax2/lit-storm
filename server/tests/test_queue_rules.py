"""Queue rules and quota: whose turn it is, how much each User may have
waiting and running, and what a month's quota counts."""

import threading
import uuid

import pytest

from conftest import make_user

pytestmark = pytest.mark.db


@pytest.fixture
def configured(admin):
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-test-0000"})
    model = admin.post(
        "/api/admin/llm-models",
        json={"label": "M", "provider": "openrouter", "model": "a/m", "is_default": True},
    ).json()
    other = admin.post(
        "/api/admin/llm-models", json={"label": "Other", "provider": "openrouter", "model": "a/o"}
    ).json()
    search = admin.post(
        "/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True}
    ).json()
    return {"model": model, "other": other, "search": search}


def limits(admin, **changes):
    current = admin.get("/api/admin/limits").json()
    r = admin.put("/api/admin/limits", json={**current, **changes})
    assert r.status_code == 200, r.text


def start_session(user, topic="Songkran"):
    project = user.post("/api/projects", json={"name": "P"}).json()
    r = user.post(f"/api/projects/{project['id']}/sessions", json={"topic": topic, "language": "th"})
    assert r.status_code == 201, r.text
    return r.json()


def submit(user, session_id, key=None, topic="Songkran"):
    body = {"topic": topic, "language": "th"}
    if key:
        body["request_key"] = key
    return user.post(f"/api/sessions/{session_id}/runs", json=body)


def claim():
    from litstorm import db as db_mod
    from litstorm.worker import queue

    with db_mod.sessions()() as s:
        return queue.claim(s)


def finish(c, status="succeeded", reason="succeeded"):
    from litstorm import db as db_mod
    from litstorm.runner.supervisor import Outcome
    from litstorm.worker import queue

    with db_mod.sessions()() as s:
        assert queue.finish(s, c, Outcome(status, reason))


def owner_of(db, claim_):
    from litstorm.db.models import Run

    db.expire_all()
    return db.get(Run, claim_.run_id).owner_id


# --- whose turn -------------------------------------------------------------------


def test_the_queue_takes_turns_between_users(admin, browser, configured, db):
    limits(admin, max_concurrent_total=1, max_queued_per_user=5, monthly_run_quota=10)
    alice = make_user(admin, browser, "alice@example.org")
    bob = make_user(admin, browser, "bob@example.org")
    carol = make_user(admin, browser, "carol@example.org")
    s = start_session(alice)["id"]  # alice's 1st
    submit(alice, s)  # 2nd
    submit(alice, s)  # 3rd
    start_session(bob)
    start_session(carol)
    ids = {u.get("/api/me").json()["id"]: name for u, name in ((alice, "A"), (bob, "B"), (carol, "C"))}

    order = []
    for _ in range(5):
        c = claim()
        order.append(ids[str(owner_of(db, c))])
        finish(c)
    # Alice queued three before anyone else, but does not get all three first.
    assert order == ["A", "B", "C", "A", "A"]


def test_one_user_is_held_to_their_own_ceiling(admin, browser, configured):
    limits(admin, max_concurrent_total=2, max_concurrent_per_user=1)
    alice = make_user(admin, browser, "alice@example.org")
    s = start_session(alice)["id"]
    submit(alice, s)
    assert claim() is not None
    assert claim() is None  # a slot is free, but not for Alice


def test_an_override_raises_one_users_ceiling(admin, browser, configured):
    limits(admin, max_concurrent_total=2, max_concurrent_per_user=1)
    alice = make_user(admin, browser, "alice@example.org")
    uid = alice.get("/api/me").json()["id"]
    admin.patch(f"/api/admin/users/{uid}", json={"max_concurrent_runs": 2})
    s = start_session(alice)["id"]
    submit(alice, s)
    assert claim() is not None and claim() is not None


# --- how much may wait ---------------------------------------------------------------


def test_the_waiting_limit_counts_runs_parked_for_a_new_model(admin, browser, configured):
    limits(admin, max_queued_per_user=2, monthly_run_quota=10)
    alice = make_user(admin, browser)
    s = start_session(alice)["id"]
    model = configured["model"]
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "enabled": False, "is_default": False})
    admin.put(f"/api/admin/llm-models/{configured['other']['id']}", json={**configured["other"], "is_default": True})
    assert alice.get(f"/api/sessions/{s}").json()["runs"][0]["status"] == "needs_selection"
    assert submit(alice, s).status_code == 201
    r = submit(alice, s)
    assert r.status_code == 429 and r.json()["detail"] == "queue_full"


# --- the month's quota -------------------------------------------------------------------


def test_quota_is_reserved_on_submit_and_given_back_if_cancelled_first(admin, browser, configured):
    limits(admin, monthly_run_quota=2)
    alice = make_user(admin, browser)
    s = start_session(alice)["id"]
    second = submit(alice, s).json()
    assert alice.get("/api/me/quota").json() | {"month": None} == {
        "month": None, "limit": 2, "used": 0, "reserved": 2, "remaining": 0,
    }
    r = submit(alice, s)
    assert r.status_code == 429 and r.json()["detail"] == "quota_exhausted"

    alice.post(f"/api/runs/{second['id']}/cancel")
    assert alice.get("/api/me/quota").json()["remaining"] == 1
    assert submit(alice, s).status_code == 201


def test_a_started_run_counts_even_if_cancelled_later(admin, browser, configured, db):
    limits(admin, monthly_run_quota=1)
    alice = make_user(admin, browser)
    run = start_session(alice)["runs"][0]
    c = claim()
    alice.post(f"/api/runs/{run['id']}/cancel")
    finish(c, "cancelled", "cancelled")
    q = alice.get("/api/me/quota").json()
    assert (q["used"], q["remaining"]) == (1, 0)


def test_system_failures_give_quota_back_and_refusals_do_not(admin, browser, configured):
    limits(admin, monthly_run_quota=5, max_concurrent_total=2, max_concurrent_per_user=2)
    alice = make_user(admin, browser)
    s = start_session(alice)["id"]
    submit(alice, s)
    first, second = claim(), claim()
    finish(first, "failed", "retries_exhausted")
    finish(second, "failed", "refused")
    q = alice.get("/api/me/quota").json()
    assert (q["used"], q["reserved"], q["remaining"]) == (1, 0, 4)


def test_a_run_counts_against_the_month_it_was_booked_in(admin, browser, configured, db):
    from litstorm.db.models import Run

    limits(admin, monthly_run_quota=1)
    alice = make_user(admin, browser)
    run = start_session(alice)["runs"][0]
    # Booked last month, still waiting now: this month is untouched.
    stored = db.get(Run, uuid.UUID(run["id"]))
    stored.quota_month = "2000-01"
    db.commit()
    assert alice.get("/api/me/quota").json()["remaining"] == 1
    # And refunding it later changes last month, not this one.
    alice.post(f"/api/runs/{run['id']}/cancel")
    assert alice.get("/api/me/quota").json()["remaining"] == 1


def test_a_new_month_starts_from_zero_in_bangkok_time():
    from datetime import datetime, timezone

    from litstorm.limits import quota_month

    # 17:30 UTC on 31 August is already 1 September in Bangkok.
    assert quota_month(datetime(2026, 8, 31, 17, 30, tzinfo=timezone.utc)) == "2026-09"
    assert quota_month(datetime(2026, 8, 31, 16, 59, tzinfo=timezone.utc)) == "2026-08"


def test_submissions_at_once_cannot_overspend(admin, browser, configured):
    limits(admin, monthly_run_quota=3, max_queued_per_user=10)
    alice = make_user(admin, browser)
    s = start_session(alice)["id"]  # uses one
    codes = []

    def go(i):
        codes.append(submit(alice, s, key=f"k{i}").status_code)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [201, 201] + [429] * 6


# --- one press, one Run ---------------------------------------------------------------


def test_the_same_request_twice_makes_one_run(admin, browser, configured):
    alice = make_user(admin, browser)
    s = start_session(alice)["id"]
    first = submit(alice, s, key="press-1").json()
    again = submit(alice, s, key="press-1").json()
    assert first["id"] == again["id"]
    assert len(alice.get(f"/api/sessions/{s}").json()["runs"]) == 2


def test_the_same_request_at_once_makes_one_run(admin, browser, configured):
    alice = make_user(admin, browser)
    s = start_session(alice)["id"]
    ids = []
    threads = [threading.Thread(target=lambda: ids.append(submit(alice, s, key="press-2").json()["id"])) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 1


# --- a model or provider is turned off ------------------------------------------------------


def test_turning_a_model_off_parks_its_waiting_runs(admin, browser, configured):
    alice = make_user(admin, browser)
    session = start_session(alice)
    run = session["runs"][0]
    model = configured["model"]
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "enabled": False, "is_default": False})
    assert alice.get(f"/api/runs/{run['id']}").json()["status"] == "needs_selection"
    assert claim() is None  # parked Runs hold no slot
    reserved = alice.get("/api/me/quota").json()["reserved"]

    r = alice.post(
        f"/api/runs/{run['id']}/selection",
        json={"llm_model_id": configured["other"]["id"], "search_provider_id": configured["search"]["id"]},
    )
    assert r.status_code == 200
    after = r.json()
    assert after["id"] == run["id"] and after["status"] == "queued" and after["model_label"] == "Other"
    assert alice.get("/api/me/quota").json()["reserved"] == reserved  # not charged again
    assert claim() is not None


def test_a_running_run_keeps_its_model_when_it_is_turned_off(admin, browser, configured):
    alice = make_user(admin, browser)
    run = start_session(alice)["runs"][0]
    claim()
    model = configured["model"]
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "enabled": False, "is_default": False})
    assert alice.get(f"/api/runs/{run['id']}").json()["status"] == "running"


# --- try again ------------------------------------------------------------------------------------


def test_retry_makes_a_new_run_linked_to_the_failed_one(admin, browser, configured):
    alice = make_user(admin, browser)
    session = start_session(alice)
    run = session["runs"][0]
    assert alice.post(f"/api/runs/{run['id']}/retry").status_code == 409  # still queued
    finish(claim(), "failed", "retries_exhausted")
    again = alice.post(f"/api/runs/{run['id']}/retry").json()
    assert again["parent_run_id"] == run["id"] and again["status"] == "queued"
    assert again["topic"] == run["topic"] and again["id"] != run["id"]
    old = alice.get(f"/api/runs/{run['id']}").json()
    assert old["status"] == "failed" and old["reason"] == "retries_exhausted"


def test_retry_with_a_model_since_turned_off_waits_for_a_choice(admin, browser, configured):
    alice = make_user(admin, browser)
    run = start_session(alice)["runs"][0]
    finish(claim(), "failed", "retries_exhausted")
    model = configured["model"]
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "enabled": False, "is_default": False})
    again = alice.post(f"/api/runs/{run['id']}/retry").json()
    assert again["status"] == "needs_selection"


def test_admins_see_each_users_quota(admin, browser, configured):
    limits(admin, monthly_run_quota=4)
    alice = make_user(admin, browser, "alice@example.org")
    start_session(alice)
    row = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "alice@example.org")
    assert (row["quota_limit"], row["quota_used"], row["quota_reserved"]) == (4, 0, 1)
