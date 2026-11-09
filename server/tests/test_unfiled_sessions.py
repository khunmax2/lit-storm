"""Research that belongs to no Project, and moving topics between Projects."""

import pytest

from conftest import make_user
from test_trash_and_cost import age, configured, purge  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


def start(user, topic="Songkran", **extra):
    r = user.post("/api/sessions", json={"topic": topic, "language": "th", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_research_needs_no_project(admin, browser, configured):
    alice = make_user(admin, browser)
    s = start(alice)
    assert s["project_id"] is None and s["project_name"] is None
    assert alice.get("/api/projects").json() == []  # none made behind the owner's back
    assert [x["id"] for x in alice.get("/api/sessions").json()] == [s["id"]]
    assert alice.get("/api/sessions/recent").json()[0]["project_id"] is None
    assert alice.get(f"/api/sessions/{s['id']}").json()["runs"][0]["status"] == "queued"


def test_a_topic_can_start_in_a_project_from_the_same_endpoint(admin, browser, configured):
    alice = make_user(admin, browser)
    project = alice.post("/api/projects", json={"name": "Thesis"}).json()
    s = start(alice, project_id=project["id"])
    assert (s["project_id"], s["project_name"]) == (project["id"], "Thesis")


def test_moving_files_and_unfiles_a_topic_with_its_runs(admin, browser, configured):
    alice = make_user(admin, browser)
    s = start(alice)
    project = alice.post("/api/projects", json={"name": "Thesis"}).json()

    moved = alice.patch(f"/api/sessions/{s['id']}", json={"project_id": project["id"]}).json()
    assert moved["project_name"] == "Thesis" and moved["runs"][0]["id"] == s["runs"][0]["id"]
    assert [x["id"] for x in alice.get(f"/api/projects/{project['id']}").json()["sessions"]] == [s["id"]]

    out = alice.patch(f"/api/sessions/{s['id']}", json={"project_id": None}).json()
    assert out["project_id"] is None
    assert alice.get(f"/api/projects/{project['id']}").json()["sessions"] == []


def test_a_topic_cannot_move_into_someone_elses_project(admin, browser, configured):
    alice = make_user(admin, browser)
    bob = make_user(admin, browser, email="bob@example.org")
    s = start(alice)
    theirs = bob.post("/api/projects", json={"name": "Bob's"}).json()
    assert alice.patch(f"/api/sessions/{s['id']}", json={"project_id": theirs["id"]}).status_code == 404
    assert bob.patch(f"/api/sessions/{s['id']}", json={"project_id": theirs["id"]}).status_code == 404
    assert bob.post("/api/sessions", json={"topic": "x y z", "language": "th"}).status_code == 201
    assert bob.get("/api/sessions").json()[0]["title"] == "x y z"  # and only Bob's own


def test_an_unfiled_topic_goes_to_the_trash_and_back(admin, browser, configured):
    alice = make_user(admin, browser)
    s = start(alice)
    assert alice.delete(f"/api/sessions/{s['id']}").status_code == 204
    assert alice.get("/api/sessions").json() == []
    assert [(i["kind"], i["id"]) for i in alice.get("/api/trash").json()] == [("session", s["id"])]
    assert alice.post(f"/api/trash/session/{s['id']}/restore").status_code == 204
    assert alice.get(f"/api/sessions/{s['id']}").status_code == 200


def test_an_unfiled_topic_is_purged_after_30_days(admin, browser, configured, db):
    from litstorm.db.models import ResearchSession

    alice = make_user(admin, browser)
    s = start(alice)
    alice.post(f"/api/runs/{s['runs'][0]['id']}/cancel")
    alice.delete(f"/api/sessions/{s['id']}")
    age(db, ResearchSession, s["id"], 31)
    assert purge() == 1
    assert alice.get("/api/trash").json() == []
