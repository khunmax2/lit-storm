"""Served under a path (host 203: /litstorm beside DeepWitya): the session's
cookies are scoped to it, and set-password links point inside it."""

import pytest

pytestmark = pytest.mark.db


@pytest.fixture
def under_litstorm(monkeypatch):
    from litstorm import settings

    monkeypatch.setenv("LITSTORM_PUBLIC_URL", "http://127.0.0.1:8090/litstorm/")
    settings.get.cache_clear()
    yield
    monkeypatch.undo()
    settings.get.cache_clear()


def test_cookies_and_links_stay_inside_the_base_path(under_litstorm, browser, bootstrap_code, db):
    from litstorm.api.auth import issue_link
    from litstorm.db.models import User

    admin = browser()
    r = admin.post("/api/setup", json={"code": bootstrap_code, "email": "a@example.org", "name": "A",
                                       "password": "correct horse"})
    assert r.status_code == 200, r.text
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 2 and all("Path=/litstorm" in c for c in cookies)
    # So the test client, which calls /api directly, no longer sends them:
    # behind nginx the browser calls /litstorm/api, inside the path.
    assert admin.get("/api/me").status_code == 401

    link, _ = issue_link(db, db.query(User).one())
    assert link.startswith("http://127.0.0.1:8090/litstorm/set-password#")

    out = admin.post("/api/auth/logout")
    assert all("Path=/litstorm" in c for c in out.headers.get_list("set-cookie"))


def test_at_the_root_cookies_are_for_the_whole_site(browser, bootstrap_code):
    admin = browser()
    r = admin.post("/api/setup", json={"code": bootstrap_code, "email": "a@example.org", "name": "A",
                                       "password": "correct horse"})
    assert all("Path=/;" in c or c.endswith("Path=/") for c in r.headers.get_list("set-cookie"))
