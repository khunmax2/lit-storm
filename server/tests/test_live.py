"""Postgres's nudges (migration 0012, litstorm.notify) and the live stream a
Run page reads instead of polling."""

import json
import threading
import time

import psycopg
import pytest

from conftest import make_user
from test_api_runs import _session, configured  # noqa: F401 - a fixture

pytestmark = pytest.mark.db


def _listening(*channels):
    from litstorm import notify

    conn = psycopg.connect(notify._dsn(), autocommit=True)
    for channel in channels:
        conn.execute(f"LISTEN {channel}")
    return conn


def _heard(conn, timeout=1.0):
    return [(n.channel, n.payload) for n in conn.notifies(timeout=timeout)]


def test_postgres_says_when_the_queue_or_a_run_changes(admin, browser, configured, db):  # noqa: F811
    from sqlalchemy import update

    from litstorm.db.models import Run, RunEvent

    conn = _listening("litstorm_queue", "litstorm_run")
    user = make_user(admin, browser)
    run_id = _session(user)["runs"][0]["id"]
    assert ("litstorm_queue", "") in _heard(conn)  # a Run was queued

    db.execute(update(Run).where(Run.id == run_id).values(status="running"))
    db.commit()
    heard = _heard(conn)
    assert ("litstorm_run", run_id) in heard and ("litstorm_queue", "") not in heard

    db.execute(update(Run).where(Run.id == run_id).values(lease_expires_at=Run.queued_at))
    db.commit()
    assert _heard(conn, timeout=0.5) == []  # a lease renewal says nothing

    db.add(RunEvent(run_id=run_id, type="stage", data={"stage": "outline"}))
    db.commit()
    assert _heard(conn) == [("litstorm_run", run_id)]

    db.execute(update(Run).where(Run.id == run_id).values(status="succeeded"))
    db.commit()
    heard = _heard(conn)
    assert ("litstorm_queue", "") in heard  # a slot came free
    conn.close()


def test_the_worker_wakes_when_a_run_is_queued(admin, browser, configured):  # noqa: F811
    from litstorm import notify

    wakeup, stopping = notify.QueueWakeup(), threading.Event()
    started = time.monotonic()
    assert wakeup.wait(0.5, stopping) is False  # nothing queued: the timer runs out
    assert time.monotonic() - started >= 0.4

    user = make_user(admin, browser)
    threading.Timer(0.3, lambda: _session(user)).start()
    started = time.monotonic()
    assert wakeup.wait(10, stopping) is True
    assert time.monotonic() - started < 5
    wakeup.close()


def _messages(response):
    """Each server-sent message's data, decoded; comments skipped."""
    for line in response.iter_lines():
        if line.startswith("data: "):
            yield json.loads(line[len("data: "):])


def test_a_run_page_is_sent_each_change_as_it_happens(admin, browser, configured, db):  # noqa: F811
    from sqlalchemy import update

    from litstorm.db.models import Run, RunEvent

    user = make_user(admin, browser)
    run_id = _session(user)["runs"][0]["id"]
    db.execute(update(Run).where(Run.id == run_id).values(status="running"))
    db.commit()

    def worker():
        time.sleep(0.5)
        db.add(RunEvent(run_id=run_id, type="stage", data={"stage": "outline"}))
        db.execute(update(Run).where(Run.id == run_id).values(stage="outline"))
        db.commit()
        time.sleep(0.5)
        db.execute(update(Run).where(Run.id == run_id).values(status="succeeded"))
        db.commit()

    threading.Thread(target=worker).start()
    started = time.monotonic()
    with user.client.stream("GET", f"/api/runs/{run_id}/live") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        seen = list(_messages(response))
    # Well inside the stream's own timer: the nudges did it.
    assert time.monotonic() - started < 10
    assert seen[0]["status"] == "running" and seen[0]["events"] == []
    assert any(m["stage"] == "outline" and [e["data"] for e in m["events"]] == [{"stage": "outline"}] for m in seen)
    assert seen[-1]["status"] == "succeeded"  # and the stream ended with the Run


def test_a_reconnecting_page_carries_on_from_its_last_event(admin, browser, configured, db):  # noqa: F811
    from sqlalchemy import update

    from litstorm.db.models import Run, RunEvent

    user = make_user(admin, browser)
    run_id = _session(user)["runs"][0]["id"]
    for stage in ("research", "outline"):
        db.add(RunEvent(run_id=run_id, type="stage", data={"stage": stage}))
    db.execute(update(Run).where(Run.id == run_id).values(status="succeeded"))
    db.commit()
    first = db.query(RunEvent).filter_by(run_id=run_id).order_by(RunEvent.id).first()

    headers = {"Last-Event-ID": str(first.id)}
    with user.client.stream("GET", f"/api/runs/{run_id}/live", headers=headers) as response:
        seen = list(_messages(response))
    assert [e["data"]["stage"] for m in seen for e in m["events"]] == ["outline"]


def test_only_the_owner_has_the_stream(admin, browser, configured):  # noqa: F811
    owner = make_user(admin, browser)
    run_id = _session(owner)["runs"][0]["id"]
    other = make_user(admin, browser, email="other@example.org")
    assert other.get(f"/api/runs/{run_id}/live").status_code == 404
    assert browser().get(f"/api/runs/{run_id}/live").status_code == 401
