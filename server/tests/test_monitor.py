"""System status for Administrators (litstorm.monitor): failures grouped into
Issues, acknowledged until they happen again, without anyone's research."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_user

pytestmark = pytest.mark.db

LIMITED = "Failed after 3 attempts. Last error: Too Many Requests"


@pytest.fixture
def configured(admin):
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-test-0000"})
    admin.post("/api/admin/llm-models",
               json={"label": "Flash", "provider": "openrouter", "model": "g/flash", "is_default": True})
    admin.post("/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True})


def started(user, topic="Songkran"):
    project = user.post("/api/projects", json={"name": "P"}).json()
    rs = user.post(f"/api/projects/{project['id']}/sessions", json={"topic": topic, "language": "th"}).json()
    return rs["runs"][0]["id"]


def ended(db, run_id, status="failed", reason="retries_exhausted", message=LIMITED, engine="deep",
          minutes_ago=5, took=3):
    """Mark a Run ended, as the Worker would have."""
    from litstorm.db.models import Run

    run = db.get(Run, uuid.UUID(run_id))
    finished = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    run.status, run.reason, run.message, run.engine = status, reason, message, engine
    run.started_at, run.finished_at = finished - timedelta(minutes=took), finished
    db.commit()


def test_failures_of_one_kind_are_one_issue(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    bob = make_user(admin, browser, "bob@example.org")
    for who, ago in ((alice, 30), (bob, 10), (alice, 2)):
        ended(db, started(who), minutes_ago=ago)
    ended(db, started(bob), reason="bad_configuration", message="Key limit exceeded (total limit).", engine="storm")

    status = admin.get("/api/admin/monitor").json()
    limited = next(i for i in status["issues"] if i["reason"] == "retries_exhausted")
    assert (limited["engine"], limited["model_label"], limited["count"]) == ("deep", "Flash", 3)
    assert limited["users"] == ["alice@example.org", "bob@example.org"]
    assert limited["message"] == LIMITED and limited["open"] is True and limited["severity"] == "system"
    assert [o["who"] for o in limited["recent"]] == ["alice@example.org", "bob@example.org", "alice@example.org"]
    assert status["open_count"] == 2


def test_two_causes_of_one_kind_are_two_issues(admin, browser, configured, db):
    """A spent key and a wrong search address are both bad configuration, and two things to fix."""
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), reason="bad_configuration", message="Key limit exceeded (total limit).", engine="storm")
    ended(db, started(alice), reason="bad_configuration", message="SearXNGConfigError: SearXNG returned 400", engine="storm")
    ended(db, started(alice), reason="bad_configuration", message="SearXNGConfigError: SearXNG returned 502", engine="storm")
    issues = admin.get("/api/admin/monitor").json()["issues"]
    assert sorted(i["count"] for i in issues) == [1, 2]


def test_an_acknowledged_issue_opens_again_when_it_happens_again(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), minutes_ago=10)
    key = admin.get("/api/admin/monitor").json()["issues"][0]["key"]
    assert admin.post("/api/admin/monitor/acknowledge", json={"keys": [key]}).status_code == 204
    issue = admin.get("/api/admin/monitor").json()["issues"][0]
    assert issue["open"] is False and issue["acknowledged_at"] is not None

    ended(db, started(alice), minutes_ago=0)
    status = admin.get("/api/admin/monitor").json()
    assert status["issues"][0]["open"] is True and status["open_count"] == 1


def test_a_run_the_worker_dropped_is_an_issue(admin, browser, configured, db):
    """An interrupted Run has a status of its own, not "failed"."""
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), status="interrupted", reason="interrupted", message="the Worker running this Run stopped")
    issue = admin.get("/api/admin/monitor").json()["issues"][0]
    assert (issue["reason"], issue["open"]) == ("interrupted", True)


def test_a_run_filed_before_the_words_were_read_is_read_now(admin, browser, configured, db):
    """Runs that failed before outcomes.from_message all say engine_error; their words still tell."""
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), reason="engine_error", message="APIError: Key limit exceeded (total limit).")
    assert admin.get("/api/admin/monitor").json()["issues"][0]["reason"] == "bad_configuration"


def test_a_key_in_a_message_is_not_shown(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), reason="bad_configuration", message="401 Incorrect API key provided: sk-or-v1-0123456789abcdef")
    assert "0123456789abcdef" not in admin.get("/api/admin/monitor").text


def test_only_the_systems_failures_open_an_issue(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), reason="empty_report", message="the research found no sources for this topic")
    ended(db, started(alice), status="cancelled", reason="cancelled", message="")
    ended(db, started(alice), status="succeeded", reason="succeeded", message="")
    status = admin.get("/api/admin/monitor").json()
    assert [(i["reason"], i["severity"], i["open"]) for i in status["issues"]] == [("empty_report", "watch", False)]
    assert status["open_count"] == 0


def test_the_topic_is_not_in_what_admins_see(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    topic = "A very private topic"
    ended(db, started(alice, topic), reason="engine_error", message=f"KeyError while writing about {topic}")
    status = admin.get("/api/admin/monitor").json()
    assert "private" not in str(status)
    assert status["issues"][0]["message"] == "KeyError while writing about …"


def test_how_long_runs_take_and_the_queue(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    for took in (2, 4, 10):
        ended(db, started(alice), status="succeeded", reason="succeeded", message="", engine="storm", took=took)
    ended(db, started(alice), engine="storm")
    started(alice)  # still waiting
    status = admin.get("/api/admin/monitor").json()
    storm = next(e for e in status["engines"] if e["engine"] == "storm")
    assert (storm["runs"], storm["succeeded"], storm["failed"]) == (4, 3, 1)
    assert storm["p50_minutes"] == pytest.approx(4) and storm["p90_minutes"] == pytest.approx(10)
    assert status["queue"]["queued"] == 1 and status["queue"]["oldest_wait_seconds"] is not None


def test_old_failures_fall_out_of_the_window(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    ended(db, started(alice), minutes_ago=60 * 24 * 8)
    assert admin.get("/api/admin/monitor").json()["issues"] == []
    assert len(admin.get("/api/admin/monitor?days=30").json()["issues"]) == 1


def test_the_badge_counts_what_needs_a_look(admin, browser, configured, db):
    alice = make_user(admin, browser, "alice@example.org")
    assert admin.get("/api/admin/monitor/open").json() == {"open_count": 0, "last_at": None}
    ended(db, started(alice), minutes_ago=3)
    ended(db, started(alice), reason="empty_report", message="the research found no sources", minutes_ago=1)
    badge = admin.get("/api/admin/monitor/open").json()
    assert badge["open_count"] == 1 and badge["last_at"] is not None
    key = next(i["key"] for i in admin.get("/api/admin/monitor").json()["issues"] if i["open"])
    admin.post("/api/admin/monitor/acknowledge", json={"keys": [key]})
    assert admin.get("/api/admin/monitor/open").json()["open_count"] == 0


def test_users_cannot_see_the_system_status(admin, browser):
    user = make_user(admin, browser)
    assert user.get("/api/admin/monitor").status_code == 403
    assert user.get("/api/admin/monitor/open").status_code == 403
    assert user.post("/api/admin/monitor/acknowledge", json={"keys": ["x"]}).status_code == 403
