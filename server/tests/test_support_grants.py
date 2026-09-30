"""Support Access Grants: one named Administrator reads one Run, or one
Discussion with its Turns, for 24 hours, until revoked; each read is logged
for the owner; nothing can be changed under a grant."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_user
from test_trash_and_cost import configured, run_fake  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


def _admin_id(admin):
    return next(u["id"] for u in admin.get("/api/admin/users").json() if u["role"] == "admin")


def _second_admin(admin, browser):
    b = make_user(admin, browser, email="helper@example.org")
    uid = next(u["id"] for u in admin.get("/api/admin/users").json() if u["email"] == "helper@example.org")
    admin.patch(f"/api/admin/users/{uid}", json={"role": "admin"})
    return b, uid


def test_a_granted_run_can_be_read_by_that_administrator_only(admin, browser, configured, db):
    alice = make_user(admin, browser, email="alice@example.org")
    session = alice.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()
    run = session["runs"][0]
    run_fake(db, run["id"])
    other = alice.post(f"/api/sessions/{session['id']}/runs", json={"topic": "Songkran again", "language": "th"}).json()
    helper, helper_id = _second_admin(admin, browser)

    # Nothing by default.
    assert admin.get(f"/api/runs/{run['id']}").status_code == 404
    assert admin.get(f"/api/admin/support").json() == []

    admins = alice.get("/api/support/admins").json()
    assert {a["email"] for a in admins} == {"admin@example.org", "helper@example.org"}
    g = alice.post("/api/grants", json={"admin_id": _admin_id(admin), "run_id": run["id"]})
    assert g.status_code == 201, g.text
    grant = g.json()
    assert grant["live"] and grant["kind"] == "run"
    lifetime = datetime.fromisoformat(grant["expires_at"]) - datetime.fromisoformat(grant["created_at"])
    assert abs(lifetime - timedelta(hours=24)) < timedelta(seconds=5)

    detail = admin.get(f"/api/runs/{run['id']}")
    assert detail.status_code == 200 and detail.json()["read_only"] is True
    assert admin.get(f"/api/runs/{run['id']}/report").status_code == 200
    assert admin.get(f"/api/runs/{run['id']}/export", params={"format": "md"}).status_code == 200
    listed = admin.get("/api/admin/support").json()
    assert listed[0]["title"] == "Songkran" and listed[0]["owner_email"] == "alice@example.org"

    # Only that Run: not the topic, not its other Run; and not another Administrator.
    assert admin.get(f"/api/sessions/{session['id']}").status_code == 404
    assert admin.get(f"/api/runs/{other['id']}").status_code == 404
    assert helper.get(f"/api/runs/{run['id']}").status_code == 404

    # Reading only.
    assert admin.post(f"/api/runs/{run['id']}/retry").status_code == 404
    assert admin.delete(f"/api/runs/{run['id']}").status_code == 404

    # The owner sees each read.
    seen = alice.get("/api/grants", params={"run_id": run["id"]}).json()[0]["accesses"]
    assert sorted(a["what"] for a in seen) == ["export", "report", "run"]

    # Revoked, it stops at once.
    alice.delete(f"/api/grants/{grant['id']}")
    assert admin.get(f"/api/runs/{run['id']}").status_code == 404


def test_a_grant_ends_after_24_hours(admin, browser, configured, db):
    from litstorm.db.models import SupportGrant

    alice = make_user(admin, browser, email="alice@example.org")
    run = alice.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    grant = alice.post("/api/grants", json={"admin_id": _admin_id(admin), "run_id": run["id"]}).json()
    assert admin.get(f"/api/runs/{run['id']}").status_code == 200
    row = db.get(SupportGrant, uuid.UUID(grant["id"]))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert admin.get(f"/api/runs/{run['id']}").status_code == 404
    assert alice.get("/api/grants").json()[0]["live"] is False


def test_a_discussion_is_granted_whole(admin, browser, configured, db):
    alice = make_user(admin, browser, email="alice@example.org")
    d = alice.post("/api/discussions", json={"topic": "Songkran and tourism", "language": "th"}).json()
    turn = d["turns"][0]
    assert alice.post("/api/grants", json={"admin_id": _admin_id(admin), "run_id": turn["id"]}).json()["detail"] == "grant_the_discussion"
    assert alice.post("/api/grants", json={"admin_id": _admin_id(admin), "session_id": d["id"]}).status_code == 201

    assert admin.get(f"/api/discussions/{d['id']}").json()["read_only"] is True
    assert admin.get(f"/api/sessions/{d['id']}").status_code == 200
    assert admin.get(f"/api/runs/{turn['id']}").status_code == 200  # its Turns come with it
    assert admin.post(f"/api/discussions/{d['id']}/turns", json={"action": "step"}).status_code == 404

    # A topic of Runs is granted Run by Run.
    research = alice.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()
    r = alice.post("/api/grants", json={"admin_id": _admin_id(admin), "session_id": research["id"]})
    assert r.json()["detail"] == "grant_a_run"


def test_only_an_administrator_and_only_ones_own_things(admin, browser, configured):
    alice = make_user(admin, browser, email="alice@example.org")
    bob = make_user(admin, browser, email="bob@example.org")
    bob_id = next(u["id"] for u in admin.get("/api/admin/users").json() if u["email"] == "bob@example.org")
    run = alice.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    assert alice.post("/api/grants", json={"admin_id": bob_id, "run_id": run["id"]}).json()["detail"] == "not_an_administrator"
    assert bob.post("/api/grants", json={"admin_id": _admin_id(admin), "run_id": run["id"]}).status_code == 404
    grant = alice.post("/api/grants", json={"admin_id": _admin_id(admin), "run_id": run["id"]}).json()
    assert bob.delete(f"/api/grants/{grant['id']}").status_code == 404
    # A User who is not an Administrator reads nothing under anyone's grant.
    assert bob.get(f"/api/runs/{run['id']}").status_code == 404
